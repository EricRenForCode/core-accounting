"""Original document routes (原始凭证/票据附件) — §original-documents.

POST   /original-documents/upload               — upload file, create record
GET    /original-documents                      — list with filtering
GET    /original-documents/{id}                 — detail
GET    /original-documents/{id}/file            — download / preview file
POST   /original-documents/{id}/recognize       — run OCR/AI recognition
PUT    /original-documents/{id}                 — 人工校对识别字段
POST   /original-documents/{id}/create-voucher-draft — generate voucher draft
POST   /original-documents/{id}/link-voucher    — link an existing voucher
DELETE /original-documents/{id}                 — delete (only if no voucher)
"""

import math
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.document_recognizer import recognize_document
from app.config import Settings
from app.core.database import get_db
from app.core.security import auth_scheme, get_current_user, require_permission, verify_token
from app.models.account import Account
from app.models.original_document import (
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    OriginalDocument,
)
from app.models.period import Period
from app.models.user import User
from app.models.voucher import Voucher, VoucherEntry
from app.schemas.common import PaginatedResponse
from app.schemas.original_document import (
    LinkVoucherRequest,
    OriginalDocumentListParams,
    OriginalDocumentResponse,
    UpdateOriginalDocumentRequest,
)

router = APIRouter()

# Extension whitelist: images + PDF + spreadsheet formats (第一版不解析表格)
_ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".pdf", ".xlsx", ".xls", ".csv",
}

_SAFE_NAME_RE = re.compile(r"[^\w一-鿿.\- ()（）]")


def require_any_permission(*permissions: str) -> Callable:
    """Dependency factory: require at least one of the given permissions."""

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    ) -> bool:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        perms = payload.get("permissions", [])
        if not any(p in perms for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: one of {permissions} required",
            )
        return True

    return _check


# 读权限：制单人（voucher:create）或有报表读取权限的人都可以查看票据台账
_read_permission = require_any_permission("voucher:create", "report:read")


# ── Helpers ───────────────────────────────────────────────────

def _upload_root() -> Path:
    """Storage directory for original documents (lazy — env overridable)."""
    return Path(Settings().UPLOAD_DIR) / "original_documents"


def _sanitize_file_name(raw: Optional[str]) -> str:
    """Sanitize an untrusted upload file name for display/storage in DB."""
    name = Path(raw or "").name  # strip any path components
    name = _SAFE_NAME_RE.sub("_", name).strip() or "unnamed"
    return name[:255]


def _document_to_response(doc: OriginalDocument) -> OriginalDocumentResponse:
    """Convert ORM object (with voucher/uploader loaded) to response."""
    return OriginalDocumentResponse(
        id=doc.id,
        file_name=doc.file_name,
        content_type=doc.content_type,
        file_size=doc.file_size,
        document_type=doc.document_type,
        status=doc.status,
        issue_date=doc.issue_date,
        amount=doc.amount,
        tax_amount=doc.tax_amount,
        total_amount=doc.total_amount,
        counterparty_name=doc.counterparty_name,
        invoice_no=doc.invoice_no,
        summary=doc.summary,
        recognized_fields=doc.recognized_fields,
        recognition_confidence=doc.recognition_confidence,
        voucher_id=doc.voucher_id,
        voucher_no=doc.voucher.voucher_no if doc.voucher else None,
        uploader_id=doc.uploader_id,
        uploader_name=doc.uploader.display_name if doc.uploader else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def _load_document(db: AsyncSession, document_id: UUID) -> OriginalDocument:
    """Load a document with voucher + uploader, or raise 404."""
    result = await db.execute(
        select(OriginalDocument)
        .options(
            selectinload(OriginalDocument.voucher),
            selectinload(OriginalDocument.uploader),
        )
        .where(OriginalDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="原始凭证不存在")
    return doc


# ── Routes ────────────────────────────────────────────────────

@router.post("/upload", response_model=OriginalDocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    document_type: str = Form(default="other"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> OriginalDocumentResponse:
    """Upload an original document file and create an `uploaded` record."""
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的票据类型: {document_type}")

    file_name = _sanitize_file_name(file.filename)
    suffix = Path(file_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {suffix or '(无扩展名)'}，"
            f"支持: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    max_bytes = Settings().UPLOAD_MAX_BYTES
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过大小限制 {max_bytes // (1024 * 1024)} MB",
        )

    # Server-generated storage name — never trust the client file name on disk.
    storage_name = f"{uuid.uuid4().hex}{suffix}"
    root = _upload_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / storage_name).write_bytes(content)

    doc = OriginalDocument(
        file_name=file_name,
        storage_key=storage_name,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        document_type=document_type,
        status="uploaded",
        uploader_id=current_user.id,
    )
    db.add(doc)
    await db.flush()

    return _document_to_response(await _load_document(db, doc.id))


@router.get("", response_model=PaginatedResponse[OriginalDocumentResponse])
async def list_documents(
    params: OriginalDocumentListParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_read_permission),
) -> PaginatedResponse[OriginalDocumentResponse]:
    """List original documents with filtering and pagination."""
    filters = []
    if params.status:
        if params.status not in DOCUMENT_STATUSES:
            raise HTTPException(status_code=400, detail=f"无效的状态: {params.status}")
        filters.append(OriginalDocument.status == params.status)
    if params.document_type:
        if params.document_type not in DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400, detail=f"无效的票据类型: {params.document_type}"
            )
        filters.append(OriginalDocument.document_type == params.document_type)
    if params.keyword:
        kw = f"%{params.keyword}%"
        filters.append(
            OriginalDocument.file_name.ilike(kw)
            | OriginalDocument.counterparty_name.ilike(kw)
            | OriginalDocument.invoice_no.ilike(kw)
            | OriginalDocument.summary.ilike(kw)
        )
    if params.date_from:
        filters.append(OriginalDocument.created_at >= params.date_from)
    if params.date_to:
        # created_at is a timestamp — include the whole end day
        filters.append(
            func.date(OriginalDocument.created_at) <= params.date_to
        )
    if params.voucher_id:
        filters.append(OriginalDocument.voucher_id == params.voucher_id)

    count_q = select(func.count(OriginalDocument.id)).where(*filters)
    total: int = (await db.execute(count_q)).scalar_one()

    query = (
        select(OriginalDocument)
        .options(
            selectinload(OriginalDocument.voucher),
            selectinload(OriginalDocument.uploader),
        )
        .where(*filters)
        .order_by(OriginalDocument.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    docs = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[_document_to_response(d) for d in docs],
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=math.ceil(total / params.page_size) if total > 0 else 1,
    )


@router.get("/{document_id}", response_model=OriginalDocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_read_permission),
) -> OriginalDocumentResponse:
    """Get original document detail."""
    return _document_to_response(await _load_document(db, document_id))


@router.get("/{document_id}/file")
async def download_document_file(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_read_permission),
) -> FileResponse:
    """Download / inline-preview the stored file."""
    doc = await _load_document(db, document_id)
    path = _upload_root() / doc.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件已丢失，请重新上传")

    ascii_fallback = "".join(ch if ord(ch) < 128 else "_" for ch in doc.file_name)
    encoded = quote(doc.file_name, safe="")
    return FileResponse(
        path,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": (
                f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
            )
        },
    )


@router.post("/{document_id}/recognize", response_model=OriginalDocumentResponse)
async def recognize(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> OriginalDocumentResponse:
    """Run OCR/AI recognition and store structured fields on the record.

    Result NEVER posts directly — it prefills fields the user must confirm.
    """
    doc = await _load_document(db, document_id)
    if doc.status in ("voucher_created", "archived"):
        raise HTTPException(status_code=409, detail="已生成凭证或已归档，不可再识别")

    file_path = _upload_root() / doc.storage_key
    result = await recognize_document(
        doc.file_name,
        doc.content_type,
        doc.file_size,
        file_path=file_path if file_path.is_file() else None,
    )

    doc.document_type = result.document_type
    doc.issue_date = result.issue_date or doc.issue_date
    doc.amount = result.amount if result.amount is not None else doc.amount
    doc.tax_amount = result.tax_amount if result.tax_amount is not None else doc.tax_amount
    doc.total_amount = (
        result.total_amount if result.total_amount is not None else doc.total_amount
    )
    doc.counterparty_name = result.counterparty_name or doc.counterparty_name
    doc.invoice_no = result.invoice_no or doc.invoice_no
    doc.summary = result.summary or doc.summary
    doc.recognized_fields = result.model_dump(mode="json")
    doc.recognition_confidence = result.confidence
    doc.status = (
        "recognized"
        if result.suggested_entries and result.confidence >= Decimal("0.8")
        else "needs_review"
    )
    await db.flush()

    return _document_to_response(doc)


@router.put("/{document_id}", response_model=OriginalDocumentResponse)
async def update_document(
    document_id: UUID,
    body: UpdateOriginalDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> OriginalDocumentResponse:
    """人工校对：update recognized fields before generating a voucher."""
    doc = await _load_document(db, document_id)
    if doc.status in ("voucher_created", "archived"):
        raise HTTPException(status_code=409, detail="已生成凭证或已归档，不可再修改")

    if body.document_type is not None:
        if body.document_type not in DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400, detail=f"无效的票据类型: {body.document_type}"
            )
        doc.document_type = body.document_type

    for field in (
        "issue_date",
        "amount",
        "tax_amount",
        "total_amount",
        "counterparty_name",
        "invoice_no",
        "summary",
        "recognized_fields",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(doc, field, value)

    if doc.status == "uploaded":
        doc.status = "needs_review"
    await db.flush()

    return _document_to_response(doc)


@router.post("/{document_id}/create-voucher-draft", status_code=201)
async def create_voucher_draft(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> dict:
    """Generate a DRAFT voucher from the (人工校对过的) recognized entries.

    The draft still goes through the normal audit + post workflow — AI/OCR
    output never reaches the ledger without human confirmation.
    """
    doc = await _load_document(db, document_id)
    if doc.voucher_id is not None:
        raise HTTPException(status_code=409, detail="该原始凭证已关联记账凭证")

    suggested = (doc.recognized_fields or {}).get("suggested_entries") or []
    if not suggested:
        raise HTTPException(
            status_code=409, detail="没有可用的建议分录，请先运行识别并校对"
        )

    # 1. Resolve account codes → accounts
    codes = {str(e.get("account_code", "")).strip() for e in suggested}
    acct_result = await db.execute(
        select(Account).where(Account.code.in_(codes), Account.is_enabled == True)  # noqa: E712
    )
    accounts = {a.code: a for a in acct_result.scalars().all()}
    missing = codes - set(accounts.keys())
    if missing:
        raise HTTPException(
            status_code=409, detail=f"建议分录中的科目不存在或已禁用: {sorted(missing)}"
        )

    # 2. Validate entry amounts — they must be explicit after人工校对
    def _amt(raw: object) -> Decimal:
        try:
            return Decimal(str(raw or "0"))
        except InvalidOperation:
            return Decimal("0")

    lines: list[dict] = []
    for e in suggested:
        debit, credit = _amt(e.get("debit_amount")), _amt(e.get("credit_amount"))
        if debit == 0 and credit == 0:
            raise HTTPException(
                status_code=409, detail="建议分录金额缺失，请先校对金额"
            )
        if debit > 0 and credit > 0:
            raise HTTPException(
                status_code=409, detail="建议分录借贷金额互斥，请先校对"
            )
        lines.append(
            {
                "account": accounts[str(e.get("account_code", "")).strip()],
                "summary": str(e.get("summary") or doc.summary or "原始凭证入账")[:200],
                "debit": debit,
                "credit": credit,
            }
        )

    total_debit = sum((line["debit"] for line in lines), Decimal("0"))
    total_credit = sum((line["credit"] for line in lines), Decimal("0"))
    if total_debit != total_credit or total_debit == 0:
        raise HTTPException(
            status_code=409,
            detail=f"建议分录借贷不平衡（借 {total_debit} / 贷 {total_credit}），请先校对",
        )

    # 3. Pick period: match issue_date's open period, else latest open period
    voucher_date = doc.issue_date or date.today()
    period_result = await db.execute(
        select(Period).where(
            Period.year == voucher_date.year,
            Period.month == voucher_date.month,
            Period.status == "open",
        )
    )
    period = period_result.scalar_one_or_none()
    if not period:
        fallback_result = await db.execute(
            select(Period)
            .where(Period.status == "open")
            .order_by(Period.year.desc(), Period.month.desc())
        )
        period = fallback_result.scalars().first()
        if not period:
            raise HTTPException(status_code=409, detail="没有打开的会计期间")
        voucher_date = date(period.year, period.month, 1)

    # 4. Create the draft voucher + entries
    from app.api.v1.vouchers import _generate_voucher_no

    voucher = Voucher(
        voucher_no=await _generate_voucher_no(db, period),
        date=voucher_date,
        period_id=period.id,
        attachments=1,
        status="draft",
        creator_id=current_user.id,
        source="document",
    )
    db.add(voucher)
    await db.flush()

    for i, line in enumerate(lines, start=1):
        db.add(
            VoucherEntry(
                voucher_id=voucher.id,
                row_number=i,
                account_id=line["account"].id,
                summary=line["summary"],
                debit_amount=line["debit"],
                credit_amount=line["credit"],
            )
        )

    doc.voucher_id = voucher.id
    doc.status = "voucher_created"
    await db.flush()

    return {
        "voucher_id": str(voucher.id),
        "voucher_no": voucher.voucher_no,
        "message": "凭证草稿已生成，请前往凭证详情审核",
    }


@router.post("/{document_id}/link-voucher", response_model=OriginalDocumentResponse)
async def link_voucher(
    document_id: UUID,
    body: LinkVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> OriginalDocumentResponse:
    """Link this document to an existing voucher."""
    doc = await _load_document(db, document_id)
    if doc.voucher_id is not None:
        raise HTTPException(status_code=409, detail="该原始凭证已关联记账凭证")

    voucher_result = await db.execute(
        select(Voucher).where(
            Voucher.id == body.voucher_id, Voucher.deleted_at.is_(None)
        )
    )
    if not voucher_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="凭证不存在")

    doc.voucher_id = body.voucher_id
    doc.status = "voucher_created"
    await db.flush()

    return _document_to_response(await _load_document(db, document_id))


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_any_permission("voucher:delete:draft", "admin:users")),
) -> dict:
    """Delete a document that has not generated / linked a voucher."""
    doc = await _load_document(db, document_id)
    if doc.voucher_id is not None:
        raise HTTPException(
            status_code=409, detail="已关联记账凭证的原始凭证不可删除"
        )

    path = _upload_root() / doc.storage_key
    await db.delete(doc)
    await db.flush()
    path.unlink(missing_ok=True)  # best-effort file cleanup

    return {"message": "原始凭证已删除"}

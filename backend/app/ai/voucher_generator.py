"""AI Voucher Generator — Natural Language → Accounting Voucher (§7.3)."""

import json
import uuid as _uuid

from sqlalchemy import func, select

from app.ai.llm_client import invoke_structured
from app.core.errors import AIInvalidResponseError
from app.models.account import Account
from app.models.auxiliary import Counterparty, Department, Individual, Project
from app.models.voucher import Voucher, VoucherEntry
from app.schemas.period import AIVoucherResponse


async def generate_voucher_from_description(
    description: str,
    period_id: _uuid.UUID,
    db,
) -> AIVoucherResponse:
    """Generate accounting voucher entries from a natural language description (§7.3).

    Args:
        description: Natural language description of the transaction.
        period_id: Current accounting period ID.
        db: AsyncSession (passed from API layer).
    """
    if db is None:
        raise ValueError("db session is required")

    # 1. Get leaf accounts + frequent accounts
    leaf_result = await db.execute(
        select(Account)
        .where(
            Account.is_enabled == True,
            ~Account.id.in_(
                select(Account.parent_id).where(
                    Account.parent_id.is_not(None),
                    Account.is_enabled == True,
                )
            ),
        )
        .order_by(Account.code)
    )
    leaf_accounts = list(leaf_result.scalars().all())

    freq_result = await db.execute(
        select(VoucherEntry.account_id, func.count(VoucherEntry.id).label("cnt"))
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .group_by(VoucherEntry.account_id)
        .order_by(func.count(VoucherEntry.id).desc())
        .limit(50)
    )
    freq_ids = {row[0] for row in freq_result}

    all_accts = {a.id: a for a in leaf_accounts}
    if freq_ids:
        freq_result2 = await db.execute(
            select(Account).where(
                Account.id.in_(freq_ids), Account.is_enabled == True
            )
        )
        for a in freq_result2.scalars():
            all_accts[a.id] = a

    accounts_list = list(all_accts.values())

    # 2. Get auxiliary entities
    deps = (await db.execute(select(Department).where(Department.is_enabled == True))).scalars().all()
    inds = (await db.execute(select(Individual).where(Individual.is_enabled == True))).scalars().all()
    cps = (await db.execute(select(Counterparty).where(Counterparty.is_enabled == True))).scalars().all()
    projs = (await db.execute(select(Project).where(Project.is_enabled == True))).scalars().all()

    # 3. Build prompt
    account_lines = []
    for a in accounts_list:
        aux_info = f" | aux:{','.join(a.aux_types)}" if a.aux_types else ""
        account_lines.append(
            f"{a.code} {a.name} (type:{a.type}, dc:{a.dc_type}, lvl:{a.level}{aux_info})"
        )

    aux_lines = []
    for d in deps:
        aux_lines.append(f"部门:{d.code} {d.name} (id:{d.id})")
    for ind in inds:
        aux_lines.append(f"个人:{ind.code} {ind.name} (id:{ind.id})")
    for cp in cps:
        aux_lines.append(f"单位:{cp.code} {cp.name} (id:{cp.id})")
    for p in projs:
        aux_lines.append(f"项目:{p.code} {p.name} (id:{p.id})")

    prompt = f"""你是一位资深会计专家。根据用户的描述生成借贷平衡的会计分录。

可用科目列表:
{chr(10).join(account_lines)}

辅助核算档案:
{chr(10).join(aux_lines) if aux_lines else "无"}

规则:
1. 只使用以上列表中的科目
2. 借方合计必须等于贷方合计
3. 每行分录只能有借方或贷方金额（互斥）
4. 如果科目要求辅助核算，必须填写对应的辅助核算实体
5. 返回严格的 JSON 格式

用户描述: {description}

请返回以下 JSON 格式:
{{
  "entries": [
    {{
      "row_number": 1,
      "account_code": "科目编码",
      "summary": "摘要",
      "debit_amount": "0",
      "credit_amount": "5000.00",
      "auxiliaries": [{{"aux_type": "个人", "entity_code": "编码"}}]
    }}
  ],
  "ai_notes": "简短说明"
}}
"""

    # 4. Call LLM
    raw_response = await invoke_structured(prompt)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        raise AIInvalidResponseError("LLM 返回的不是有效 JSON")

    entries = parsed.get("entries", [])
    if not entries:
        raise AIInvalidResponseError("LLM 未返回任何分录")

    code_to_account = {a.code: a for a in accounts_list}

    # 5. Validate & build entries
    result_entries = []
    matched_accounts = []

    for i, entry in enumerate(entries):
        code = entry.get("account_code", "")
        account = code_to_account.get(code)
        if not account:
            raise AIInvalidResponseError(f"LLM 返回了不存在的科目编码: {code}")

        debit = float(entry.get("debit_amount", 0) or 0)
        credit = float(entry.get("credit_amount", 0) or 0)

        result_entries.append({
            "row_number": i + 1,
            "account": {"id": str(account.id), "code": account.code, "name": account.name},
            "summary": entry.get("summary", description),
            "debit_amount": debit,
            "credit_amount": credit,
            "auxiliaries": entry.get("auxiliaries", []) or [],
        })
        matched_accounts.append(f"{account.name}({account.code})")

    # 6. Balance check + auto-correct (max 1 retry)
    total_debit = sum(e["debit_amount"] for e in result_entries)
    total_credit = sum(e["credit_amount"] for e in result_entries)
    is_balanced = abs(total_debit - total_credit) < 0.01

    if not is_balanced:
        fix_prompt = f"""分录不平衡！借方={total_debit}，贷方={total_credit}。请修正金额使借贷相等。

原始描述: {description}
之前的结果: {json.dumps(parsed, ensure_ascii=False)}
请返回修正后的 JSON。"""
        raw_response2 = await invoke_structured(fix_prompt)
        try:
            parsed2 = json.loads(raw_response2)
        except json.JSONDecodeError:
            raise AIInvalidResponseError("修正后的 LLM 响应不是有效 JSON")

        result_entries = []
        matched_accounts = []
        for i, entry in enumerate(parsed2.get("entries", [])):
            code = entry.get("account_code", "")
            account = code_to_account.get(code)
            if not account:
                raise AIInvalidResponseError(f"LLM 返回了不存在的科目编码: {code}")
            debit = float(entry.get("debit_amount", 0) or 0)
            credit = float(entry.get("credit_amount", 0) or 0)
            result_entries.append({
                "row_number": i + 1,
                "account": {"id": str(account.id), "code": account.code, "name": account.name},
                "summary": entry.get("summary", description),
                "debit_amount": debit,
                "credit_amount": credit,
                "auxiliaries": entry.get("auxiliaries", []) or [],
            })
            matched_accounts.append(f"{account.name}({account.code})")

        total_debit2 = sum(e["debit_amount"] for e in result_entries)
        total_credit2 = sum(e["credit_amount"] for e in result_entries)
        is_balanced = abs(total_debit2 - total_credit2) < 0.01

        if not is_balanced:
            raise AIInvalidResponseError(
                f"两次尝试后仍不平衡: 借方={total_debit2}, 贷方={total_credit2}"
            )

    conversation_id = _uuid.uuid4()

    return AIVoucherResponse(
        conversation_id=conversation_id,
        entries=result_entries,
        is_balanced=is_balanced,
        matched_accounts=matched_accounts,
        ai_notes=parsed.get("ai_notes", ""),
    )

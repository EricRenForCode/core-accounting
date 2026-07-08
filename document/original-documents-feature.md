# 原始凭证 / 票据附件（Original Documents）

## 功能定位

打通「原始凭证采集 → OCR/AI 识别 → 人工校对 → 生成记账凭证草稿 → 关联附件 → 审核记账」的完整链路。
本模块只负责采集、识别与草稿生成；生成的凭证是 **draft 状态**，仍走现有凭证的审核（audit）/ 记账（post）流程，AI/OCR 结果永远不会直接入账。

## 数据模型

表 `original_documents`（migration `004_original_documents`，模型 `app/models/original_document.py`）：

| 字段 | 说明 |
|---|---|
| `file_name` | 清洗后的原始文件名（仅展示用） |
| `storage_key` | 磁盘存储文件名（服务端生成的 `uuid4.hex + 后缀`，不信任客户端文件名） |
| `content_type` / `file_size` | MIME 类型 / 字节数 |
| `document_type` | `invoice / bank_receipt / reimbursement / contract / payroll / other` |
| `status` | `uploaded → recognized / needs_review → voucher_created → archived` |
| `issue_date` `amount` `tax_amount` `total_amount` `counterparty_name` `invoice_no` `summary` | 识别 + 人工校对字段 |
| `recognized_fields` (JSONB) | 完整识别结果，含 `suggested_entries`（建议分录）与 `warnings` |
| `recognition_confidence` | 置信度 0–1；≥0.8 且有建议分录 → `recognized`，否则 `needs_review` |
| `voucher_id` | 关联凭证（`ON DELETE SET NULL`） |
| `uploader_id` | 上传人 |

文件存储在 `{UPLOAD_DIR}/original_documents/`（配置项 `UPLOAD_DIR`，默认 `backend/uploads/`，已加入 `.gitignore`）。单文件大小限制 `UPLOAD_MAX_BYTES`（默认 20 MB）。允许的扩展名：图片（jpg/png/gif/webp/bmp）、PDF、Excel/CSV（第一版不解析表格内容）。

## API（`/api/v1/original-documents`）

| 方法/路径 | 说明 | 权限 |
|---|---|---|
| `POST /upload` | multipart 上传，创建 `uploaded` 记录 | `voucher:create` |
| `GET /` | 列表；过滤：`status` `document_type` `keyword`（文件名/对方单位/发票号/摘要）`date_from` `date_to` `voucher_id` | `voucher:create` 或 `report:read` |
| `GET /{id}` | 详情 | 同上 |
| `GET /{id}/file` | 下载/内联预览（`inline` + UTF-8 文件名） | 同上 |
| `POST /{id}/recognize` | 运行识别，写入 `recognized_fields` 并更新状态 | `voucher:create` |
| `PUT /{id}` | 人工校对字段（含编辑 `suggested_entries`）；已生成凭证/归档后拒绝（409） | `voucher:create` |
| `POST /{id}/create-voucher-draft` | 由建议分录生成 **草稿凭证**（校验科目存在、借贷平衡），返回 `voucher_id/voucher_no` | `voucher:create` |
| `POST /{id}/link-voucher` | 关联已有凭证 | `voucher:create` |
| `DELETE /{id}` | 删除（仅未关联凭证的记录；同时清理磁盘文件） | `voucher:delete:draft` 或 admin |

生成草稿的期间选择：优先匹配票据日期所在的 open 期间；否则回落到最新 open 期间（凭证日期取该期间 1 号）。生成的凭证 `source="document"`、`attachments=1`，并把文档置为 `voucher_created`。

## 识别引擎（`app/ai/document_recognizer.py`）

- 接口：`recognize_document(file_name, content_type, file_size) -> RecognitionResult`
- 输出结构：`document_type / issue_date / amount / tax_amount / total_amount / counterparty_name / invoice_no / summary / suggested_entries[] / confidence / warnings[]`
- 第一版为确定性 mock 规则（从文件名提取金额/日期 + 关键词映射）：
  - `travel/差旅` → 借 6602 管理费用，贷 1001 库存现金（报销单）
  - `rent/房租`、`office/办公` → 费用类发票
  - `bank/回单/转账` → 借 1002 银行存款，贷 2202（银行回单）
  - `invoice/发票` → 发票类
  - `contract/合同` → 仅归档，不建议分录
- 替换为真实 OCR/LLM 时只需重写该函数，路由与前端零改动。

## 前端流程

- 侧边栏「凭证管理 → 原始凭证」；路由 `/original-documents`（列表 + 上传弹窗）、`/original-documents/$documentId`（详情/校对）。
- 列表页（`features/documents/DocumentList.tsx`）：状态/类型/关键词过滤，显示金额、对方单位、关联凭证号（可跳转）、上传时间；未关联记录可删除。
- 详情页（`features/documents/DocumentDetail.tsx`）：左侧文件预览（JWT blob 方式加载图片/PDF），右侧识别字段表单 + 可编辑建议分录表；操作：运行识别 / 保存校对 / 生成凭证草稿（成功后跳转凭证详情）/ 关联已有凭证 / 手工编制凭证。
- 凭证详情（`VoucherDetail`）：新增「关联原始凭证」卡片，反查 `GET /original-documents?voucher_id=`，可跳回文档详情。
- 录入凭证（`VoucherForm`）：支持 `?documentId=` 预填（日期、附件数=1、摘要、按科目编码解析的分录），保存成功后自动调用 link-voucher 关联。

## 测试

- 后端：`tests/integration/test_api_original_documents.py`（19 条）覆盖上传/文件名清洗/扩展名白名单/权限（含 `report:read` 只读访问与 403）/识别状态流转/校对/生成草稿（含重复生成、无分录 409）/关联/删除限制。文件存储通过 `UPLOAD_DIR` 环境变量隔离到 pytest tmp 目录。
- 前端：`tsc -b` 通过。

## 后续扩展点

- **真实 OCR/发票查验**：替换 `recognize_document` 内部实现（百度/腾讯 OCR、税局发票查验 API），可将 `document_id → 文件路径` 传入做真实图像识别；`warnings` 用于承载查验异常。
- **对象存储**：`storage_key` 已抽象为相对 key，切换 OSS/S3 时只需替换 `_upload_root()` 读写与 `GET /{id}/file` 的响应（改为签名 URL 重定向）。
- **多附件/一票多凭证**：当前一文档只关联一张凭证；如需多对多可加中间表 `voucher_documents`。
- **归档流程**：`archived` 状态已预留，可在期末结账时批量归档。

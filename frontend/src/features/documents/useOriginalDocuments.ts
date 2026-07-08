import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import api from '@/lib/api'

// ─── Types ───────────────────────────────────────────

export type DocumentStatus =
  | 'uploaded'
  | 'recognized'
  | 'needs_review'
  | 'voucher_created'
  | 'archived'

export type DocumentType =
  | 'invoice'
  | 'bank_receipt'
  | 'reimbursement'
  | 'contract'
  | 'payroll'
  | 'other'

export interface SuggestedEntry {
  account_code: string
  summary: string
  debit_amount: string
  credit_amount: string
  aux_type?: string | null
  aux_name?: string | null
}

export interface RecognizedFields {
  document_type?: string
  issue_date?: string | null
  amount?: string | null
  total_amount?: string | null
  summary?: string
  suggested_entries?: SuggestedEntry[]
  confidence?: string
  warnings?: string[]
}

export interface OriginalDocument {
  id: string
  file_name: string
  content_type: string
  file_size: number
  document_type: DocumentType
  status: DocumentStatus
  issue_date?: string | null
  amount?: string | null
  tax_amount?: string | null
  total_amount?: string | null
  counterparty_name?: string | null
  invoice_no?: string | null
  summary?: string | null
  recognized_fields?: RecognizedFields | null
  recognition_confidence?: string | null
  voucher_id?: string | null
  voucher_no?: string | null
  uploader_id: string
  uploader_name?: string | null
  created_at: string
  updated_at: string
}

export interface DocumentFilters {
  page?: number
  page_size?: number
  status?: string
  document_type?: string
  keyword?: string
  voucher_id?: string
}

export interface PaginatedDocuments {
  items: OriginalDocument[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface UpdateDocumentRequest {
  document_type?: string
  issue_date?: string | null
  amount?: string | null
  tax_amount?: string | null
  total_amount?: string | null
  counterparty_name?: string | null
  invoice_no?: string | null
  summary?: string | null
  recognized_fields?: RecognizedFields
}

// ─── Labels (shared by list + detail + voucher pages) ─

export const DOC_STATUS_MAP: Record<string, { label: string; colorKey: string }> = {
  uploaded: { label: '已上传', colorKey: 'draft' },
  recognized: { label: '已识别', colorKey: 'posted' },
  needs_review: { label: '待校对', colorKey: 'warn' },
  voucher_created: { label: '已生成凭证', colorKey: 'pass' },
  archived: { label: '已归档', colorKey: 'closed' },
}

export const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: '发票',
  bank_receipt: '银行回单',
  reimbursement: '报销单',
  contract: '合同',
  payroll: '工资单',
  other: '其他',
}

// Path relative to the api client baseURL (/api/v1)
export function documentFileUrl(id: string): string {
  return `/original-documents/${id}/file`
}

// ─── Queries ─────────────────────────────────────────

export function useOriginalDocuments(filters: DocumentFilters = {}) {
  return useQuery<PaginatedDocuments>({
    queryKey: ['original-documents', filters],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page: filters.page || 1,
        page_size: filters.page_size || 20,
      }
      if (filters.status) params.status = filters.status
      if (filters.document_type) params.document_type = filters.document_type
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.voucher_id) params.voucher_id = filters.voucher_id
      const { data } = await api.get<PaginatedDocuments>('/original-documents', { params })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useOriginalDocument(id: string) {
  return useQuery<OriginalDocument>({
    queryKey: ['original-document', id],
    queryFn: async () => {
      const { data } = await api.get<OriginalDocument>(`/original-documents/${id}`)
      return data
    },
    enabled: !!id,
  })
}

// ─── Mutations ───────────────────────────────────────

function useInvalidateDocuments() {
  const queryClient = useQueryClient()
  return (id?: string) => {
    queryClient.invalidateQueries({ queryKey: ['original-documents'] })
    if (id) queryClient.invalidateQueries({ queryKey: ['original-document', id] })
  }
}

export function useUploadDocument() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async ({ file, documentType }: { file: File; documentType: string }) => {
      const form = new FormData()
      form.append('file', file)
      form.append('document_type', documentType)
      const { data } = await api.post<OriginalDocument>('/original-documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return data
    },
    onSuccess: () => invalidate(),
  })
}

export function useRecognizeDocument() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<OriginalDocument>(`/original-documents/${id}/recognize`)
      return data
    },
    onSuccess: (_data, id) => invalidate(id),
  })
}

export function useUpdateDocument() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: UpdateDocumentRequest }) => {
      const { data } = await api.put<OriginalDocument>(`/original-documents/${id}`, body)
      return data
    },
    onSuccess: (_data, { id }) => invalidate(id),
  })
}

export function useCreateVoucherDraft() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<{ voucher_id: string; voucher_no: string; message: string }>(
        `/original-documents/${id}/create-voucher-draft`,
      )
      return data
    },
    onSuccess: (_data, id) => invalidate(id),
  })
}

export function useLinkVoucher() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async ({ id, voucherId }: { id: string; voucherId: string }) => {
      const { data } = await api.post<OriginalDocument>(`/original-documents/${id}/link-voucher`, {
        voucher_id: voucherId,
      })
      return data
    },
    onSuccess: (_data, { id }) => invalidate(id),
  })
}

export function useDeleteDocument() {
  const invalidate = useInvalidateDocuments()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete<{ message: string }>(`/original-documents/${id}`)
      return data
    },
    onSuccess: () => invalidate(),
  })
}

// Documents linked to a voucher (VoucherDetail 反查)
export function useVoucherDocuments(voucherId: string) {
  return useQuery<PaginatedDocuments>({
    queryKey: ['original-documents', { voucher_id: voucherId }],
    queryFn: async () => {
      const { data } = await api.get<PaginatedDocuments>('/original-documents', {
        params: { voucher_id: voucherId, page_size: 50 },
      })
      return data
    },
    enabled: !!voucherId,
  })
}

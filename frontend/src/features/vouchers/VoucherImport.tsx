import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { Upload, X, FileSpreadsheet, AlertCircle, CheckCircle } from 'lucide-react'

interface ImportResult {
  imported: number
  skipped: number
  errors: Array<{ row?: number; voucher_no?: string; error: string }>
}

interface VoucherImportProps {
  periodId: string
  onClose: () => void
  onSuccess?: () => void
}

export default function VoucherImport({ periodId, onClose, onSuccess }: VoucherImportProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const queryClient = useQueryClient()

  const importMutation = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData()
      formData.append('file', f)
      const { data } = await api.post<ImportResult>(
        `/vouchers/import?period_id=${periodId}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return data
    },
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      onSuccess?.()
    },
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setResult(null)
    }
  }

  function handleImport() {
    if (file) importMutation.mutate(file)
  }

  const isPending = importMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6 max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">导入凭证</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Instructions */}
        <div className="rounded-md bg-blue-50 border border-blue-200 px-4 py-3 mb-4">
          <p className="text-sm text-blue-700 font-medium mb-1">Excel 格式要求</p>
          <p className="text-xs text-blue-600">
            必需列：voucher_no, date, account_code, summary, debit_amount, credit_amount
          </p>
          <p className="text-xs text-blue-600 mt-1">
            同一凭证号的多行会自动合并为一个凭证
          </p>
        </div>

        {/* File Input */}
        {!result && (
          <>
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-accent hover:bg-accent/5 transition-colors"
            >
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <FileSpreadsheet size={24} className="text-green-600" />
                  <span className="text-sm font-medium">{file.name}</span>
                </div>
              ) : (
                <div>
                  <Upload size={32} className="mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    点击选择或拖拽 Excel 文件
                  </p>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium rounded-md border hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleImport}
                disabled={!file || isPending}
                className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
              >
                {isPending ? '导入中...' : '开始导入'}
              </button>
            </div>
          </>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-3">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-md bg-green-50 border border-green-200 p-3 text-center">
                <CheckCircle size={20} className="mx-auto text-green-600 mb-1" />
                <p className="text-2xl font-bold text-green-700">{result.imported}</p>
                <p className="text-xs text-green-600">导入成功</p>
              </div>
              <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-center">
                <AlertCircle size={20} className="mx-auto text-amber-600 mb-1" />
                <p className="text-2xl font-bold text-amber-700">{result.errors.length}</p>
                <p className="text-xs text-amber-600">错误/警告</p>
              </div>
            </div>

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="max-h-48 overflow-y-auto">
                <p className="text-xs font-medium text-muted-foreground mb-1">错误详情：</p>
                <ul className="space-y-1">
                  {result.errors.map((err, i) => (
                    <li
                      key={i}
                      className="text-xs text-red-600 bg-red-50 rounded px-2 py-1"
                    >
                      {err.row && <span className="font-mono mr-1">行{err.row}:</span>}
                      {err.voucher_no && (
                        <span className="font-mono mr-1">{err.voucher_no}:</span>
                      )}
                      {err.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Close */}
            <div className="flex justify-end pt-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 transition-colors"
              >
                完成
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

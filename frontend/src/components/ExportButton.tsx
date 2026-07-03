import { useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import {
  exportStatement,
  type StatementType,
} from '@/lib/exportStatement'

interface ExportButtonProps {
  type: StatementType
  periodId?: string
  label?: string
}

/**
 * Export button that streams an Excel file from the backend and downloads it.
 * Disabled until a period is selected; shows a spinner while exporting.
 */
export function ExportButton({
  type,
  periodId,
  label = '导出',
}: ExportButtonProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async () => {
    if (!periodId || loading) return
    setError(null)
    setLoading(true)
    try {
      await exportStatement(type, periodId)
    } catch {
      setError('导出失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleExport}
        disabled={!periodId || loading}
        className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Download size={14} />
        )}
        {label}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  )
}

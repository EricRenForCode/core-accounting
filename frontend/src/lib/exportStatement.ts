import api from '@/lib/api'

export type StatementType =
  | 'balance_sheet'
  | 'income'
  | 'cash_flow'
  | 'trial_balance'

/**
 * Request an Excel export of a financial statement / report from the backend
 * and trigger a browser download. Returns nothing; throws on failure so the
 * caller can surface an error state.
 */
export async function exportStatement(
  type: StatementType,
  periodId: string,
): Promise<void> {
  const response = await api.post(
    '/statements/export',
    { type, period_id: periodId, format: 'excel' },
    { responseType: 'blob' },
  )

  // Prefer the server-provided filename from Content-Disposition.
  const disposition = response.headers['content-disposition'] as
    | string
    | undefined
  let filename = `${type}.xlsx`
  if (disposition) {
    const match = /filename="?([^"]+)"?/.exec(disposition)
    if (match?.[1]) filename = decodeURIComponent(match[1])
  }

  const blob = new Blob([response.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Format a number with thousands separators (千分位).
 * e.g., 5000 → "5,000.00", 1234567.89 → "1,234,567.89"
 */
export function formatAmount(
  value: number | string | undefined | null,
  decimals = 2,
): string {
  if (value === undefined || value === null || value === '') return ''
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return ''
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * Format a date string to Chinese locale display.
 * e.g., "2026-06-13" → "2026年6月13日"
 */
export function formatDate(date: string | Date | undefined | null): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Format a date string to short numeric format.
 * e.g., "2026-06-13" → "06-13"
 */
export function formatDateShort(date: string | Date | undefined | null): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}-${dd}`
}

/**
 * Format a datetime to relative time (刚刚 / X分钟前 / X小时前 / 完整日期).
 */
export function formatRelativeTime(date: string | Date | undefined | null): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  const now = Date.now()
  const diff = now - d.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  return formatDate(date)
}

/**
 * Round to specified decimal places (四舍五入).
 */
export function round(value: number, decimals = 2): number {
  const factor = Math.pow(10, decimals)
  return Math.round((value + Number.EPSILON) * factor) / factor
}

/**
 * cn() utility — merge class names, filtering out falsy values.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}

/**
 * Format a period as "2026年6月".
 */
export function formatPeriod(year: number, month: number): string {
  return `${year}年${month}月`
}

/**
 * Parse amount string (removes commas) back to number.
 */
export function parseAmount(value: string): number {
  return parseFloat(value.replace(/,/g, '')) || 0
}

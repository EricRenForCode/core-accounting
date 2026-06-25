import { cn } from '@/lib/utils'
import { forwardRef, type InputHTMLAttributes } from 'react'

interface AmountInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value?: string
  onChange?: (value: string) => void
  decimals?: number
  align?: 'right' | 'left'
  error?: string
}

export const AmountInput = forwardRef<HTMLInputElement, AmountInputProps>(
  ({ value, onChange, decimals = 2, align = 'right', error, className, ...props }, ref) => {
    const factor = 10 ** decimals

    // Cents-style entry: the user types digits only and the decimal point fills
    // in from the right. e.g. "85678" → 856.78, "8567" → 85.67, backspace shifts back.
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const digits = e.target.value.replace(/\D/g, '')
      if (digits === '') {
        onChange?.('')
        return
      }
      const amount = parseInt(digits, 10) / factor
      onChange?.(amount.toFixed(decimals))
    }

    const displayValue = value
      ? parseFloat(value).toLocaleString('zh-CN', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      : ''

    return (
      <div className="relative">
        <input
          ref={ref}
          type="text"
          inputMode="numeric"
          value={displayValue}
          onChange={handleChange}
          className={cn(
            'w-full rounded-md border bg-card px-3 py-2 font-mono text-sm',
            'focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent',
            align === 'right' && 'text-right',
            error && 'border-destructive focus:ring-destructive',
            className,
          )}
          {...props}
        />
        {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      </div>
    )
  },
)

AmountInput.displayName = 'AmountInput'

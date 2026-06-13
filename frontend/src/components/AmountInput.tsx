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
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value.replace(/,/g, '')
      // Allow only digits and one decimal point
      if (/^\d*\.?\d*$/.test(raw)) {
        onChange?.(raw)
      }
    }

    const handleBlur = () => {
      if (value && onChange) {
        const num = parseFloat(value)
        if (!isNaN(num)) {
          onChange(num.toFixed(decimals))
        }
      }
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
          inputMode="decimal"
          value={displayValue}
          onChange={handleChange}
          onBlur={handleBlur}
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

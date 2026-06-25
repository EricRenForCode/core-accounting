import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { AuxTypeApiPath, type AuxTypeValue } from '@/lib/constants'
import { cn } from '@/lib/utils'

interface AuxEntity {
  id: string
  code: string
  name: string
  is_enabled: boolean
}

interface AuxPickerProps {
  auxType: AuxTypeValue
  value?: string
  onChange: (entityId: string, entityName: string) => void
  disabled?: boolean
  placeholder?: string
  className?: string
}

export function AuxPicker({
  auxType,
  value,
  onChange,
  disabled = false,
  className,
}: AuxPickerProps) {
  const apiPath = AuxTypeApiPath[auxType]
  const defaultPlaceholder = `选择${auxType}...`

  const { data: entities = [], isLoading } = useQuery<AuxEntity[]>({
    queryKey: ['auxiliaries', auxType],
    queryFn: async () => {
      const { data } = await api.get(`/auxiliaries/${apiPath}?page_size=500`)
      // Handle paginated response
      return data.items || data || []
    },
    staleTime: 5 * 60 * 1000,
  })

  const selectedEntity = entities.find((e) => e.id === value)

  return (
    <select
      value={value || ''}
      onChange={(e) => {
        const entity = entities.find((en) => en.id === e.target.value)
        if (entity) onChange(entity.id, entity.name)
      }}
      disabled={disabled}
      className={cn(
        'w-full rounded border px-2 py-1.5 text-xs bg-background',
        'focus:outline-none focus:ring-1 focus:ring-accent',
        disabled && 'opacity-50 cursor-not-allowed',
        !selectedEntity && 'text-muted-foreground',
        className,
      )}
    >
      <option value="">
        {isLoading ? '加载中...' : defaultPlaceholder}
      </option>
      {entities
        .filter((e) => e.is_enabled)
        .map((entity) => (
          <option key={entity.id} value={entity.id}>
            {entity.code} - {entity.name}
          </option>
        ))}
    </select>
  )
}

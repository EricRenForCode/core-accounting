import { Link } from '@tanstack/react-router'

interface BreadcrumbItem {
  label: string
  to?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav aria-label="面包屑导航" className="flex items-center gap-1 text-sm text-muted-foreground">
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-gray-300">/</span>}
            {isLast ? (
              <span className="text-foreground font-medium">{item.label}</span>
            ) : item.to ? (
              <Link to={item.to} className="hover:text-accent transition-colors">
                {item.label}
              </Link>
            ) : (
              <span>{item.label}</span>
            )}
          </span>
        )
      })}
    </nav>
  )
}

import { categoryMeta } from '../../lib/constants'
import { formatRelative } from '../../lib/format'
import type { IssueSummary } from '../../types'

interface TopIssuesProps {
  issues: IssueSummary[]
  now: number
  selectedId: number | null
  onSelect: (id: number) => void
}

/** UI-01 상단 부산 주요 이슈 (FR-003) */
export default function TopIssues({ issues, now, selectedId, onSelect }: TopIssuesProps) {
  if (issues.length === 0) return null
  return (
    <section className="flex shrink-0 items-center gap-2 overflow-x-auto border-b border-line bg-panel/60 px-4 py-2">
      <h2 className="shrink-0 text-xs font-bold text-danger">부산 주요 이슈</h2>
      {issues.map((issue) => {
        const meta = categoryMeta(issue.category)
        return (
          <button
            key={issue.id}
            type="button"
            onClick={() => onSelect(issue.id)}
            aria-pressed={issue.id === selectedId}
            className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs whitespace-nowrap transition-colors ${
              issue.id === selectedId ? 'border-accent bg-accent/10' : 'border-line bg-card hover:border-muted/60'
            }`}
          >
            <span>{meta.icon}</span>
            <span className="font-medium">{issue.title}</span>
            <span className="text-muted">{formatRelative(issue.updated_at, now)}</span>
          </button>
        )
      })}
    </section>
  )
}

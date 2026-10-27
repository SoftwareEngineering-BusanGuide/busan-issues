import { CATEGORY_META, categoryMeta } from '../../lib/constants'
import { formatDistance, formatRelative } from '../../lib/format'
import type { NearbyIssue } from '../../types'

interface IssueListProps {
  issues: NearbyIssue[]
  now: number
  loading: boolean
  error: string | null
  category: string
  onCategoryChange: (category: string) => void
  onSelect: (id: number) => void
}

/** UI-01 내 주변 이슈 목록 (FR-002) + 카테고리 필터 (FR-011) */
export default function IssueList({ issues, now, loading, error, category, onCategoryChange, onSelect }: IssueListProps) {
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-4 pt-3">
        <h2 className="text-sm font-bold">내 주변 이슈</h2>
        <span className="text-xs text-muted">{issues.length}건</span>
      </div>

      <div className="flex gap-1.5 overflow-x-auto px-4 py-2">
        {['', ...Object.keys(CATEGORY_META)].map((c) => (
          <button
            key={c || 'all'}
            type="button"
            onClick={() => onCategoryChange(c)}
            aria-pressed={c === category}
            className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] whitespace-nowrap ${
              c === category ? 'border-accent bg-accent/15 text-foreground' : 'border-line text-muted hover:text-foreground'
            }`}
          >
            {c ? `${categoryMeta(c).icon} ${c}` : '전체'}
          </button>
        ))}
      </div>

      <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-3">
        {error && <li className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-xs">{error}</li>}
        {!error && !loading && issues.length === 0 && (
          // UC-001 대안 흐름 3a
          <li className="p-6 text-center text-sm text-muted">최근 주변 소식이 없습니다.</li>
        )}
        {issues.map((issue) => {
          const meta = categoryMeta(issue.category)
          return (
            <li key={issue.id}>
              <button
                type="button"
                onClick={() => onSelect(issue.id)}
                className="w-full rounded-lg border border-line bg-card p-3 text-left transition-colors hover:border-muted/60"
                style={{ borderLeftColor: meta.color, borderLeftWidth: 3 }}
              >
                <div className="flex items-start gap-2.5">
                  <span className="text-lg leading-none">{meta.icon}</span>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-semibold">{issue.title}</h3>
                    <p className="mt-0.5 truncate text-xs text-muted">{issue.place_name}</p>
                    <p className="mt-1 text-[11px] text-muted">
                      {issue.category} · {formatDistance(issue.distance_km)} · {formatRelative(issue.updated_at, now)}
                    </p>
                  </div>
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

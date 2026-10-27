import { categoryMeta } from '../../lib/constants'
import { formatRelative } from '../../lib/format'
import type { IssueDetail } from '../../types'

/** 원문 링크의 언론사 주소 (예: news.kbs.co.kr) */
function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

interface IssueDetailViewProps {
  detail: IssueDetail | null
  error: string | null
  now: number
  onBack: () => void
}

/** UI-02 이슈 상세 (FR-004) + 같은 사건 기사의 시간순 목록 (FR-005) */
export default function IssueDetailView({ detail, error, now, onBack }: IssueDetailViewProps) {
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="px-4 pt-3">
        <button type="button" onClick={onBack} className="text-xs text-muted hover:text-foreground">
          ← 주변 이슈 목록
        </button>
      </div>

      {error && <p className="m-4 rounded-lg border border-danger/40 bg-danger/10 p-3 text-xs">{error}</p>}
      {!error && !detail && <p className="p-6 text-center text-sm text-muted">불러오는 중…</p>}

      {detail && (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-4">
          <span
            className="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold text-black"
            style={{ background: categoryMeta(detail.issue.category).color }}
          >
            {categoryMeta(detail.issue.category).icon} {detail.issue.category}
          </span>
          <h2 className="mt-2 text-lg leading-snug font-bold">{detail.issue.title}</h2>
          <p className="mt-1 text-xs text-muted">
            {detail.issue.place_name} · {formatRelative(detail.issue.updated_at, now)} 갱신
          </p>

          {detail.issue.status_summary && (
            <div className="mt-3 rounded-lg border border-line bg-card p-3">
              <p className="text-[11px] font-semibold text-accent">현재 상황 요약</p>
              <p className="mt-1 text-sm leading-relaxed">{detail.issue.status_summary}</p>
            </div>
          )}

          <h3 className="mt-5 text-xs font-bold text-muted">관련 기사 {detail.articles.length}건 · 시간순</h3>
          <ol className="mt-2 border-l border-line">
            {detail.articles.map((a) => (
              <li key={a.id} className="relative pb-4 pl-4">
                <span className="absolute top-1.5 -left-[4.5px] h-2 w-2 rounded-full bg-accent" />
                <p className="text-[11px] text-muted">{formatRelative(a.published_at, now)}</p>
                {/* 기사 본문은 보여주지 않고 제목·요약·원문 링크만 제공한다 (SRS 2.4) */}
                <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline">
                  {a.title} ↗
                </a>
                <span className="ml-1 text-[11px] text-muted">{hostname(a.url)}</span>
                <p className="mt-0.5 text-xs leading-relaxed text-foreground/75">{a.description}</p>
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">
            이슈 제목과 상황 요약은 AI(Gemini)가 위 기사들의 제목·요약만으로 정리했습니다. 정확한 내용은 원문을 확인하세요.
            <br />
            기사 출처: 네이버 뉴스 검색 (NAVER API HUB)
          </p>
        </div>
      )}
    </section>
  )
}

import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { ChatMessage } from '../../hooks/useChat'
import { categoryMeta } from '../../lib/constants'
import type { IssueSummary } from '../../types'

interface ChatPanelProps {
  messages: ChatMessage[]
  pending: boolean
  locationLabel: string
  onSend: (text: string) => void
  onClear: () => void
  /** 답변 속 이슈를 누르면 지도와 상세로 이동한다 */
  onSelectIssue: (id: number) => void
}

const SUGGESTIONS = ['지금 내 주변에 무슨 일 있어?', '내일 해운대 가도 괜찮을까?', '이번 주 부산 행사 알려줘', '최근 교통 통제 있는 곳은?']
const ISSUE_REF = /\[#(\d+)\]/g

/** 대화형 질의 (FR-006): AI가 이슈·날씨·재난문자를 찾아보고 출처와 함께 답한다 */
export default function ChatPanel({ messages, pending, locationLabel, onSend, onClear, onSelectIssue }: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  // 새 메시지가 오면 맨 아래로
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending])

  const submit = (text: string) => {
    if (!text.trim() || pending) return
    onSend(text)
    setDraft('')
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-4 pt-2 pb-1 text-[11px] text-muted">
        <span className="truncate">📍 {locationLabel} 기준으로 답해요</span>
        {messages.length > 0 && (
          <button type="button" onClick={onClear} className="shrink-0 hover:text-foreground">
            새 대화
          </button>
        )}
      </div>

      <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-2">
        {messages.length === 0 && (
          <div className="space-y-2 p-2">
            <p className="text-sm text-muted">부산 소식, 날씨, 미세먼지, 재난문자를 물어보세요.</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => submit(s)}
                className="block w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm hover:border-accent"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="ml-10 rounded-2xl rounded-br-sm bg-accent/20 px-3 py-2 text-sm whitespace-pre-wrap">
              {m.text}
            </div>
          ) : (
            <div
              key={i}
              className={`mr-6 rounded-2xl rounded-bl-sm border px-3 py-2 text-sm leading-relaxed ${
                m.error ? 'border-danger/40 bg-danger/10' : 'border-line bg-card'
              }`}
            >
              {renderAnswer(m.text, m.issues ?? [], onSelectIssue)}
              <UnmentionedIssues text={m.text} issues={m.issues ?? []} onSelect={onSelectIssue} />
            </div>
          ),
        )}
        {pending && <div className="mr-6 animate-pulse rounded-2xl border border-line bg-card px-3 py-2 text-sm text-muted">찾아보는 중…</div>}
      </div>

      <form
        className="flex shrink-0 gap-2 border-t border-line px-3 py-2"
        onSubmit={(e) => {
          e.preventDefault()
          submit(draft)
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={500}
          placeholder="예: 서면에 오늘 교통 통제 있어?"
          aria-label="질문"
          // iOS는 글자 크기가 16px보다 작으면 입력할 때 화면을 확대하므로 16px로 둔다
          className="min-w-0 flex-1 rounded-lg border border-line bg-background px-3 py-2 text-base outline-none focus:border-accent md:text-sm"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          className="shrink-0 rounded-lg bg-accent px-3 text-sm font-semibold text-background disabled:opacity-40"
        >
          보내기
        </button>
      </form>
      <p className="shrink-0 px-4 pb-2 text-[10px] text-muted">
        AI가 뉴스·공공데이터로 만든 답이라 틀릴 수 있어요. 긴급 상황은 119·112에 신고하세요.
      </p>
    </section>
  )
}

/** 본문에 [#id]로 나오지 않은 이슈(예: 경과를 물어 타임라인을 연 이슈)는 아래에 따로 보여준다 */
function UnmentionedIssues({ text, issues, onSelect }: { text: string; issues: IssueSummary[]; onSelect: (id: number) => void }) {
  const mentioned = new Set(Array.from(text.matchAll(ISSUE_REF), (m) => Number(m[1])))
  const rest = issues.filter((i) => !mentioned.has(i.id))
  if (!rest.length) return null
  return (
    <div className="mt-2 flex flex-wrap gap-1.5 border-t border-line pt-2">
      {rest.map((issue) => (
        <button
          key={issue.id}
          type="button"
          onClick={() => onSelect(issue.id)}
          className="max-w-full truncate rounded-full border border-line px-2 py-0.5 text-[11px] hover:border-accent"
        >
          {categoryMeta(issue.category).icon} {issue.title} 📍
        </button>
      ))}
    </div>
  )
}

/** 답변을 줄 단위로 그린다. '- '로 시작하는 줄은 목록, '출처:' 줄은 흐리게, [#id]는 누를 수 있는 표시로 바꾼다 (같은 이슈는 처음 한 번만) */
function renderAnswer(text: string, issues: IssueSummary[], onSelect: (id: number) => void): ReactNode {
  const byId = new Map(issues.map((i) => [i.id, i]))
  const shown = new Set<number>()
  return text.split('\n').map((line, i) => {
    if (!line.trim()) return <div key={i} className="h-1.5" />
    const bullet = line.trimStart().startsWith('- ')
    const source = line.startsWith('출처:')
    const parts: ReactNode[] = []
    let last = 0
    const body = bullet ? line.trimStart().slice(2) : line
    for (const match of body.matchAll(ISSUE_REF)) {
      const issue = byId.get(Number(match[1]))
      parts.push(body.slice(last, match.index))
      if (issue && !shown.has(issue.id)) {
        shown.add(issue.id)
        parts.push(
          <button
            key={match.index}
            type="button"
            onClick={() => onSelect(issue.id)}
            aria-label={`${issue.title} 지도에서 보기`}
            className="mx-0.5 rounded bg-accent/15 px-1 text-[11px] text-accent hover:bg-accent/25"
          >
            📍지도
          </button>,
        )
      }
      last = (match.index ?? 0) + match[0].length
    }
    parts.push(body.slice(last))
    return (
      <p key={i} className={`${bullet ? 'flex gap-1.5' : ''} ${source ? 'mt-1 text-[11px] text-muted' : ''}`}>
        {bullet && <span className="text-muted">•</span>}
        <span>{parts}</span>
      </p>
    )
  })
}

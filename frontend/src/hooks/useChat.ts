import { useRef, useState } from 'react'
import { postChat, type ChatTurn } from '../api/client'
import type { IssueSummary, UserLocation } from '../types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  /** 답변의 [#id]가 가리키는 이슈 */
  issues?: IssueSummary[]
  error?: boolean
}

/** 서버로 함께 보내는 이전 대화 수 (서버는 대화를 저장하지 않는다) */
const HISTORY_TURNS = 6

/** 대화형 질의 (FR-006) 대화 상태. 탭을 바꿔도 대화가 남도록 App에서 쓴다 */
export function useChat(location: UserLocation) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  const pendingRef = useRef(false)

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || pendingRef.current) return
    const history: ChatTurn[] = messages
      .filter((m) => !m.error)
      .slice(-HISTORY_TURNS)
      .map(({ role, text }) => ({ role, text }))
    setMessages((prev) => [...prev, { role: 'user', text: message }])
    pendingRef.current = true
    setPending(true)
    try {
      const reply = await postChat(message, history, location)
      setMessages((prev) => [...prev, { role: 'assistant', text: reply.answer, issues: reply.issues }])
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'assistant', text: (e as Error).message, error: true }])
    } finally {
      pendingRef.current = false
      setPending(false)
    }
  }

  return { messages, pending, send, clear: () => setMessages([]) }
}

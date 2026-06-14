import type { ChatMessage, IncidentContinueResponse } from '../api/types'

const CHAT_RESUME_STORAGE_KEY = 'lightpanel-chat-resume'

export interface ChatResumePayload {
  source_incident_id: string
  session_id: string
  history: ChatMessage[]
}

export function saveChatResume(payload: IncidentContinueResponse): void {
  sessionStorage.setItem(
    CHAT_RESUME_STORAGE_KEY,
    JSON.stringify({
      source_incident_id: payload.source_incident_id,
      session_id: payload.session_id,
      history: payload.history,
    } satisfies ChatResumePayload),
  )
}

export function takeChatResume(): ChatResumePayload | null {
  const raw = sessionStorage.getItem(CHAT_RESUME_STORAGE_KEY)
  if (!raw) return null
  sessionStorage.removeItem(CHAT_RESUME_STORAGE_KEY)

  try {
    const value = JSON.parse(raw) as Partial<ChatResumePayload>
    if (!value.session_id || !Array.isArray(value.history)) return null
    const history = value.history.filter(
      (item): item is ChatMessage =>
        (item.role === 'user' || item.role === 'assistant') &&
        typeof item.content === 'string' &&
        item.content.trim().length > 0,
    )
    if (!history.length) return null
    return {
      source_incident_id: value.source_incident_id || '',
      session_id: value.session_id,
      history,
    }
  } catch {
    return null
  }
}

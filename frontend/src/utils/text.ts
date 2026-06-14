import { escapeHtml, renderHighlightedCodeBlock } from './highlight'

export function truncateText(text: string, maxLength: number): string {
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

export function formatShortDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function sanitizeMarkdownHref(value: string): string | null {
  const href = value.trim()
  if (!href) return null
  if (href.startsWith('#') || href.startsWith('/')) return href

  // 只允许聊天和报告链接中相对安全的协议。
  const protocol = /^([a-z][a-z0-9+.-]*):/i.exec(href)?.[1]?.toLowerCase()
  if (!protocol) return href.startsWith('//') ? null : href
  return ['http', 'https', 'mailto'].includes(protocol) ? href : null
}

export function renderSimpleMarkdown(text: string): string {
  const codeFence = /```([A-Za-z0-9_-]+)?[ \t]*\n([\s\S]*?)```/g
  let cursor = 0
  let html = ''
  let match: RegExpExecArray | null

  while ((match = codeFence.exec(text)) !== null) {
    // 单独渲染围栏代码块，让高亮器接收到未转义的原始代码。
    html += renderMarkdownTextChunk(text.slice(cursor, match.index))
    html += renderHighlightedCodeBlock(match[2] ?? '', match[1] ?? 'code')
    cursor = match.index + match[0].length
  }

  html += renderMarkdownTextChunk(text.slice(cursor))
  return html
}

function renderMarkdownTextChunk(text: string): string {
  let html = escapeHtml(text).replace(/\n/g, '<br>')

  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(
    /`(.+?)`/g,
    '<code class="inline-code">$1</code>',
  )
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_, label: string, rawHref: string) => {
      const href = sanitizeMarkdownHref(rawHref)
      if (!href) return label
      return `<a class="inline-link" href="${escapeHtml(href)}" target="_blank" rel="noreferrer noopener">${label}</a>`
    },
  )
  return html
}

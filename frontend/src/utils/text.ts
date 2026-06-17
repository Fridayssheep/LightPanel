import MarkdownIt from 'markdown-it'
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

  const protocol = /^([a-z][a-z0-9+.-]*):/i.exec(href)?.[1]?.toLowerCase()
  if (!protocol) return href.startsWith('//') ? null : href
  return ['http', 'https', 'mailto'].includes(protocol) ? href : null
}

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false,
  highlight(code: string, language: string) {
    return renderHighlightedCodeBlock(code, language || 'code')
  },
})

const defaultLinkOpen =
  markdown.renderer.rules.link_open ??
  ((tokens: any[], idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.link_open = (
  tokens: any[],
  idx: number,
  options: any,
  _env: any,
  self: any,
) => {
  const hrefIndex = tokens[idx].attrIndex('href')
  if (hrefIndex >= 0) {
    const safeHref = sanitizeMarkdownHref(tokens[idx].attrs?.[hrefIndex]?.[1] || '')
    if (!safeHref) {
      tokens[idx].attrs?.splice(hrefIndex, 1)
    } else {
      tokens[idx].attrs![hrefIndex][1] = safeHref
      tokens[idx].attrSet('target', '_blank')
      tokens[idx].attrSet('rel', 'noreferrer noopener')
      tokens[idx].attrJoin('class', 'inline-link')
    }
  }
  return defaultLinkOpen(tokens, idx, options, _env, self)
}

markdown.renderer.rules.code_inline = (tokens: any[], idx: number) => {
  return `<code class="inline-code">${escapeHtml(tokens[idx].content)}</code>`
}

function cleanUnsafeLinks(html: string): string {
  return html.replace(/<a\b([^>]*?)>(.*?)<\/a>/gis, (full, attrs, content) => {
    if (!/\bhref\s*=/.test(attrs)) return content
    return full
  })
}

export function renderSimpleMarkdown(text: string): string {
  return cleanUnsafeLinks(markdown.render(text))
}

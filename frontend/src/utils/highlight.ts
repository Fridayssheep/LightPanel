export type HighlightMode = 'plain' | 'log' | 'yaml' | 'json' | 'shell' | 'code'

interface TokenRule {
  className: string
  pattern: RegExp
}

interface MatchCandidate {
  className: string
  index: number
  text: string
}

const LOG_RULES: TokenRule[] = [
  { className: 'time', pattern: /\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b/ },
  { className: 'time', pattern: /\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b/ },
  { className: 'error', pattern: /\b(?:ERROR|ERR|FATAL|CRITICAL|PANIC|Traceback|Exception)\b/i },
  { className: 'warning', pattern: /\b(?:WARN|WARNING)\b/i },
  { className: 'success', pattern: /\b(?:SUCCESS|READY|STARTED|HEALTHY|OK)\b/i },
  { className: 'info', pattern: /\b(?:INFO|NOTICE|RUNNING|LISTENING)\b/i },
  { className: 'debug', pattern: /\b(?:DEBUG|TRACE)\b/i },
  { className: 'method', pattern: /\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b/ },
  { className: 'number', pattern: /\b[1-5]\d{2}\b/ },
  { className: 'path', pattern: /(?:\/[\w./:@%+-]+)+/ },
]

const GENERIC_RULES: TokenRule[] = [
  { className: 'comment', pattern: /#.*/ },
  { className: 'comment', pattern: /\/\/.*/ },
  { className: 'string', pattern: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/ },
  { className: 'keyword', pattern: /\b(?:const|let|var|function|return|if|else|for|while|class|import|from|export|async|await|try|catch|throw|new|true|false|null|undefined)\b/ },
  { className: 'number', pattern: /\b-?\d+(?:\.\d+)?\b/ },
]

export function normalizeHighlightMode(mode?: string | null): HighlightMode {
  const value = (mode || '').trim().toLowerCase()
  if (['log', 'logs', 'text-log'].includes(value)) return 'log'
  if (['yaml', 'yml', 'compose'].includes(value)) return 'yaml'
  if (value === 'json') return 'json'
  if (['sh', 'shell', 'bash', 'zsh'].includes(value)) return 'shell'
  if (['js', 'ts', 'javascript', 'typescript', 'python', 'py', 'dockerfile'].includes(value)) return 'code'
  return 'plain'
}

export function highlightCodeToHtml(content: string, mode?: string | null): string {
  const resolvedMode = normalizeHighlightMode(mode)
  const safeContent = content.length ? content : ''

  if (resolvedMode === 'yaml') return highlightYaml(safeContent)
  if (resolvedMode === 'log') return highlightByRules(safeContent, LOG_RULES)
  if (resolvedMode === 'json' || resolvedMode === 'shell' || resolvedMode === 'code') {
    return highlightByRules(safeContent, GENERIC_RULES)
  }
  return escapeHtml(safeContent)
}

export function renderHighlightedCodeBlock(content: string, mode?: string | null): string {
  const resolvedMode = normalizeHighlightMode(mode)
  const language = mode?.trim() || resolvedMode
  return `<div class="highlighted-code-frame"><span class="highlighted-code-label">${escapeHtml(language)}</span><pre class="highlighted-code highlighted-code--${resolvedMode}"><code>${highlightCodeToHtml(content, resolvedMode)}</code></pre></div>`
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightByRules(content: string, rules: TokenRule[]): string {
  return content
    .split('\n')
    .map((line) => highlightLineByRules(line, rules))
    .join('\n')
}

function highlightLineByRules(line: string, rules: TokenRule[]): string {
  let html = ''
  let cursor = 0

  // 手动扫描每一行，确保未匹配文本在插入 token 前都被转义。
  while (cursor < line.length) {
    const segment = line.slice(cursor)
    const match = findNextMatch(segment, rules)
    if (!match) {
      html += escapeHtml(segment)
      break
    }

    html += escapeHtml(segment.slice(0, match.index))
    html += token(match.className, match.text)
    cursor += match.index + match.text.length
  }

  return html
}

function findNextMatch(segment: string, rules: TokenRule[]): MatchCandidate | null {
  let best: MatchCandidate | null = null

  for (const rule of rules) {
    const match = rule.pattern.exec(segment)
    if (!match || !match[0]) continue

    const candidate = {
      className: rule.className,
      index: match.index,
      text: match[0],
    }

    if (!best || candidate.index < best.index) {
      // 选择最靠前的匹配；位置相同时由规则顺序通过已有 best 值决定。
      best = candidate
    }
  }

  return best
}

function highlightYaml(content: string): string {
  return content
    .split('\n')
    .map((line) => highlightYamlLine(line))
    .join('\n')
}

function highlightYamlLine(line: string): string {
  if (!line.trim()) return ''

  const commentIndex = findYamlCommentIndex(line)
  const code = commentIndex >= 0 ? line.slice(0, commentIndex) : line
  const comment = commentIndex >= 0 ? line.slice(commentIndex) : ''
  const keyMatch = /^(\s*)(-\s+)?([A-Za-z0-9_.-]+)(\s*:)/.exec(code)

  let html = ''
  if (keyMatch) {
    html += escapeHtml(keyMatch[1])
    if (keyMatch[2]) html += token('punct', keyMatch[2].trim()) + ' '
    html += token('key', keyMatch[3])
    html += token('punct', keyMatch[4])
    html += highlightYamlValue(code.slice(keyMatch[0].length))
  } else {
    html += highlightYamlValue(code)
  }

  if (comment) html += token('comment', comment)
  return html
}

function highlightYamlValue(value: string): string {
  return highlightLineByRules(value, [
    { className: 'string', pattern: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/ },
    { className: 'boolean', pattern: /\b(?:true|false|yes|no|on|off)\b/i },
    { className: 'null', pattern: /\b(?:null|nil|~)\b/i },
    { className: 'number', pattern: /\b-?\d+(?:\.\d+)?\b/ },
    { className: 'punct', pattern: /[{}\[\],|>-]/ },
  ])
}

function findYamlCommentIndex(line: string): number {
  let quote: '"' | "'" | null = null

  // 配置文件注释只在引号外，并且位于行首或空白字符之后才成立。
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const previous = line[index - 1]
    if ((char === '"' || char === "'") && previous !== '\\') {
      quote = quote === char ? null : quote ?? char
    }
    if (char === '#' && !quote && (index === 0 || /\s/.test(previous))) {
      return index
    }
  }

  return -1
}

function token(className: string, value: string): string {
  return `<span class="code-token ${className}">${escapeHtml(value)}</span>`
}

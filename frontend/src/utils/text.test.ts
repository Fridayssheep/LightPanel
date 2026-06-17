import { describe, expect, it } from 'vitest'
import { renderSimpleMarkdown } from './text'

describe('renderSimpleMarkdown', () => {
  it('renders markdown tables as HTML tables', () => {
    const html = renderSimpleMarkdown([
      '| 容器名 | 镜像 | 状态 |',
      '| --- | --- | --- |',
      '| web | nginx:latest | running |',
    ].join('\n'))

    expect(html).toContain('<table')
    expect(html).toContain('<thead>')
    expect(html).toContain('<tbody>')
    expect(html).toContain('<th>容器名</th>')
    expect(html).toContain('<td>web</td>')
  })
})

import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '../src/chat/markdown.js'

// The reference front-end renders answers with markdown-it, which cannot be
// installed offline (TICKET-012 已确认)。This is the documented subset the
// patient chat supports, tested as the renderer's contract.
describe('renderMarkdown (TICKET-014)', () => {
  it('wraps plain text in a paragraph', () => {
    expect(renderMarkdown('建议多休息')).toBe('<p>建议多休息</p>')
  })

  it('keeps a single newline as a line break', () => {
    expect(renderMarkdown('第一行\n第二行')).toBe('<p>第一行<br>第二行</p>')
  })

  it('separates blank-line paragraphs', () => {
    expect(renderMarkdown('第一段\n\n第二段')).toBe('<p>第一段</p><p>第二段</p>')
  })

  it('renders headings', () => {
    expect(renderMarkdown('## 用药建议')).toBe('<h2>用药建议</h2>')
  })

  it('renders emphasis and inline code', () => {
    expect(renderMarkdown('**重点**与*提醒*还有`code`')).toBe(
      '<p><strong>重点</strong>与<em>提醒</em>还有<code>code</code></p>'
    )
  })

  it('renders unordered and ordered lists', () => {
    expect(renderMarkdown('- 多喝水\n- 测体温')).toBe('<ul><li>多喝水</li><li>测体温</li></ul>')
    expect(renderMarkdown('1. 休息\n2. 复诊')).toBe('<ol><li>休息</li><li>复诊</li></ol>')
  })

  it('renders a fenced code block with its content escaped', () => {
    expect(renderMarkdown('```\n<b>x</b>\n```')).toBe(
      '<pre><code>&lt;b&gt;x&lt;/b&gt;</code></pre>'
    )
  })

  it('escapes raw HTML instead of emitting it', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).toBe(
      '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>'
    )
  })

  it('renders an empty answer as an empty string', () => {
    expect(renderMarkdown('')).toBe('')
  })
})

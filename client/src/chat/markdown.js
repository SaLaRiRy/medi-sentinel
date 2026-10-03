/**
 * A small, dependency-free Markdown renderer for streamed answers.
 *
 * The reference front-end used markdown-it; the offline environment cannot
 * install it (TICKET-012 已确认), so this is the deliberate, tested subset the
 * patient chat supports: paragraphs, line breaks, headings, emphasis, inline
 * code, fenced code blocks, ordered/unordered lists and links. Raw HTML is
 * escaped first, so model output can never inject markup.
 */

const HTML_ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char])
}

function isBlockStart(line) {
  return (
    /^\s*```/.test(line) ||
    /^(#{1,6})\s+/.test(line) ||
    /^\s*[-*]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line)
  )
}

/** Inline spans; code spans are protected from the emphasis/link passes. */
function renderInline(raw) {
  const codeSpans = []
  const withTokens = raw.replace(/`([^`]+)`/g, (_match, code) => {
    codeSpans.push(`<code>${escapeHtml(code)}</code>`)
    return `\u0000${codeSpans.length - 1}\u0000`
  })

  let out = escapeHtml(withTokens)
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  out = out.replace(/_([^_]+)_/g, '<em>$1</em>')
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label, url) => {
    const href = /^(https?:|\/|#)/.test(url) ? url : '#'
    return `<a href="${href}" target="_blank" rel="noopener">${label}</a>`
  })
  return out.replace(/\u0000(\d+)\u0000/g, (_match, index) => codeSpans[Number(index)])
}

export function renderMarkdown(text) {
  if (!text) return ''
  const lines = String(text).replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    if (/^\s*$/.test(line)) {
      index += 1
      continue
    }

    if (/^\s*```/.test(line)) {
      const code = []
      index += 1
      while (index < lines.length && !/^\s*```/.test(lines[index])) {
        code.push(lines[index])
        index += 1
      }
      index += 1
      blocks.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`)
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      const level = heading[1].length
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(`<li>${renderInline(lines[index].replace(/^\s*[-*]\s+/, ''))}</li>`)
        index += 1
      }
      blocks.push(`<ul>${items.join('')}</ul>`)
      continue
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(`<li>${renderInline(lines[index].replace(/^\s*\d+\.\s+/, ''))}</li>`)
        index += 1
      }
      blocks.push(`<ol>${items.join('')}</ol>`)
      continue
    }

    const paragraph = []
    while (
      index < lines.length &&
      !/^\s*$/.test(lines[index]) &&
      !isBlockStart(lines[index])
    ) {
      paragraph.push(lines[index])
      index += 1
    }
    blocks.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`)
  }

  return blocks.join('')
}

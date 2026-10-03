/**
 * F-2: the injectable transport. Everything above it can be tested without a network,
 * and the SSE parser is where the frame-arrival edge cases live.
 */

const DATA_PREFIX = 'data:'

export function createHttpTransport({
  fetchImpl = globalThis.fetch,
  baseUrl = '/api/v1',
} = {}) {
  return {
    async request({ method = 'GET', path, query, headers, body }) {
      const response = await fetchImpl(
        buildUrl(baseUrl, path, query),
        initFor(method, body, headers)
      )
      return { status: response.status, payload: await response.json() }
    },

    async *stream({ method = 'POST', path, headers, body }) {
      const response = await fetchImpl(
        buildUrl(baseUrl, path),
        initFor(method, body, headers)
      )
      if (!response.body) return
      yield* parseSse(readChunks(response.body))
    },
  }
}

function initFor(method, body, headers = {}) {
  if (body === undefined) return { method, headers: { ...headers } }
  // FormData sets its own multipart boundary, so it must pass through untouched.
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return { method, headers: { ...headers }, body }
  }
  return {
    method,
    headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
    body: JSON.stringify(body),
  }
}

function buildUrl(baseUrl, path, query) {
  const url = `${baseUrl}${path}`
  if (!query) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) search.append(key, value)
  }
  const encoded = search.toString()
  return encoded ? `${url}?${encoded}` : url
}

async function* readChunks(stream) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) return
      yield decoder.decode(value, { stream: true })
    }
  } finally {
    reader.releaseLock()
  }
}

/** Frames are `data: <JSON>\n\n`; a frame may be split across chunks, or several may share one. */
export async function* parseSse(chunks) {
  let buffer = ''
  for await (const chunk of chunks) {
    buffer += chunk
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const frame = parseFrame(raw)
      if (frame !== null) yield frame
      boundary = buffer.indexOf('\n\n')
    }
  }
}

function parseFrame(raw) {
  const data = raw
    .split('\n')
    .filter((line) => line.startsWith(DATA_PREFIX))
    .map((line) => line.slice(DATA_PREFIX.length).trim())
    .join('\n')
  if (!data) return null
  return JSON.parse(data)
}

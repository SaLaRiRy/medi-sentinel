import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import Ajv2020 from 'ajv/dist/2020.js'
import { describe, expect, it } from 'vitest'

import { createApiClient } from '../src/api/client.js'

const here = dirname(fileURLToPath(import.meta.url))
const contractsDir = resolve(here, '../../contracts')
const sseSchema = readContract('sse-events.json')
const restContract = readContract('openapi.json')

function readContract(name) {
  return JSON.parse(readFileSync(resolve(contractsDir, name), 'utf8'))
}

function frameTypes() {
  return sseSchema.oneOf.map((entry) => entry.$ref.split('/').pop())
}

function sampleFor(spec) {
  if (spec.const !== undefined) return spec.const
  if (spec.enum) return spec.enum[0]
  if (spec.$ref) return sampleFor(sseSchema.$defs[spec.$ref.split('/').pop()])
  const type = Array.isArray(spec.type) ? spec.type[0] : spec.type
  if (type === 'object') {
    return Object.fromEntries(
      Object.entries(spec.properties ?? {}).map(([key, value]) => [key, sampleFor(value)])
    )
  }
  if (type === 'array') {
    return spec.minItems ? Array.from({ length: spec.minItems }, () => sampleFor(spec.items)) : []
  }
  if (type === 'integer' || type === 'number') return 1
  if (type === 'string') return 'x'
  return null
}

function transportStreaming(frames) {
  return {
    stream: async function* generate() {
      for (const frame of frames) yield frame
    },
  }
}

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** A declared path template (`/api/v1/foo/{id}`) matches a concrete request path. */
function matchesDeclaredPath(method, path) {
  const requested = `/api/v1${path}`
  return Object.entries(restContract.paths).some(([candidate, operations]) => {
    const pattern = new RegExp(
      `^${candidate.split(/\{[^}]+\}/).map(escapeRegExp).join('[^/]+')}$`
    )
    return pattern.test(requested) && Object.keys(operations).includes(method.toLowerCase())
  })
}

describe('C-1 from the consuming side', () => {
  it('understands every frame type the contract declares', async () => {
    const types = frameTypes()
    const frames = types.map((type) => ({ type, ...sampleFor({ $ref: `#/$defs/${type}` }) }))
    const client = createApiClient({ transport: transportStreaming(frames) })

    const received = []
    for await (const frame of client.sendChat({ message: '你好' })) received.push(frame)

    expect(received.map((frame) => frame.type)).toEqual(types)
  })

  it('yields frames that satisfy the same schema the server is checked against', async () => {
    const validate = new Ajv2020({ strict: false, allErrors: true }).compile(sseSchema)
    const frames = frameTypes().map((type) => ({
      type,
      ...sampleFor({ $ref: `#/$defs/${type}` }),
    }))
    const client = createApiClient({ transport: transportStreaming(frames) })

    for await (const frame of client.sendChat({ message: '你好' })) {
      expect(validate(frame), JSON.stringify(validate.errors)).toBe(true)
    }
  })

  it('only calls paths the REST contract declares', async () => {
    const requested = []
    const client = createApiClient({
      transport: {
        request: async ({ method, path }) => {
          requested.push({ method, path })
          return { status: 200, payload: { code: 200, message: 'ok', data: {} } }
        },
        stream: async function* stream({ method, path }) {
          requested.push({ method, path })
          yield { type: 'done', ...sampleFor({ $ref: '#/$defs/done' }) }
        },
      },
    })

    await client.health()
    await client.chatSessions()
    await client.chatMessages(1)
    for await (const _frame of client.sendChat({ message: '你好' })) {
      // consume the stream so the path is recorded
    }
    await client.knowledgeFiles({ page: 1, page_size: 10 })
    await client.uploadKnowledge({ name: '指南.md' })
    await client.revectorizeKnowledge(1)
    await client.deleteKnowledge(1)
    await client.graphOverview()
    await client.graphNeighbors('高血压', 1)
    await client.graphSearch('高')
    await client.graphDisease('高血压')
    await client.inferGraph(['头痛'])
    await client.graphStats()
    await client.createAppointment({
      doctor_id: 1,
      department_id: 1,
      visit_date: '2026-10-20',
      time_slot: '上午',
    })
    await client.myAppointments()
    await client.doctorAppointments()
    await client.adminAppointments({ page: 1, page_size: 10 })
    await client.updateAppointmentStatus(1, 0)
    await client.deleteAppointment(1)

    expect(requested).toHaveLength(20)
    for (const { method, path } of requested) {
      expect(matchesDeclaredPath(method, path), `${method} ${path}`).toBe(true)
    }
    expect(matchesDeclaredPath('GET', '/chat/sessions')).toBe(true)
    expect(matchesDeclaredPath('GET', '/chat/sessions/1/messages')).toBe(true)
    expect(matchesDeclaredPath('GET', '/knowledge')).toBe(true)
    expect(matchesDeclaredPath('POST', '/knowledge')).toBe(true)
    expect(matchesDeclaredPath('POST', '/knowledge/1/revectorize')).toBe(true)
    expect(matchesDeclaredPath('DELETE', '/knowledge/1')).toBe(true)
    expect(matchesDeclaredPath('GET', '/graph')).toBe(true)
    expect(matchesDeclaredPath('GET', '/graph/entities/高血压/neighbors')).toBe(true)
    expect(matchesDeclaredPath('GET', '/graph/search')).toBe(true)
    expect(matchesDeclaredPath('GET', '/graph/diseases/高血压')).toBe(true)
    expect(matchesDeclaredPath('POST', '/graph/infer')).toBe(true)
    expect(matchesDeclaredPath('GET', '/graph/stats')).toBe(true)
    expect(matchesDeclaredPath('POST', '/appointments')).toBe(true)
    expect(matchesDeclaredPath('GET', '/appointments/my')).toBe(true)
    expect(matchesDeclaredPath('GET', '/appointments/doctor')).toBe(true)
    expect(matchesDeclaredPath('GET', '/appointments/admin')).toBe(true)
    expect(matchesDeclaredPath('PUT', '/appointments/1/status')).toBe(true)
    expect(matchesDeclaredPath('DELETE', '/appointments/admin/1')).toBe(true)
  })
})

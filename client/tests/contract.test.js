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
      },
    })

    await client.health()

    for (const { method, path } of requested) {
      expect(Object.keys(restContract.paths)).toContain(`/api/v1${path}`)
      expect(Object.keys(restContract.paths[`/api/v1${path}`])).toContain(
        method.toLowerCase()
      )
    }
  })
})

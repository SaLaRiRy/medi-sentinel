import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const srcDir = resolve(dirname(fileURLToPath(import.meta.url)), '../src')

function filesUnder(directory) {
  return readdirSync(directory).flatMap((entry) => {
    const full = join(directory, entry)
    return statSync(full).isDirectory() ? filesUnder(full) : [full]
  })
}

describe('F-1 is the only exit', () => {
  it('no view reaches for the transport', () => {
    const viewsDir = join(srcDir, 'views')

    for (const file of filesUnder(viewsDir)) {
      expect(readFileSync(file, 'utf8'), file).not.toMatch(/transport/)
    }
  })

  it('only the API client imports the transport module', () => {
    const importers = filesUnder(srcDir).filter((file) =>
      /from\s+['"].*transport\.js['"]/.test(readFileSync(file, 'utf8'))
    )

    expect(importers).toEqual([join(srcDir, 'api', 'client.js')])
  })
})

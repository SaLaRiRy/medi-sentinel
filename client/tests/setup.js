/**
 * jsdom has no layout engine, so Element Plus' popper-based components
 * (el-dropdown, el-tooltip, el-menu) fail unless ResizeObserver and matchMedia
 * exist. TICKET-028 wires element-plus into the shells, so every mounting test
 * gets these stubs from one shared place.
 */
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (!globalThis.matchMedia) {
  globalThis.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false
    },
  })
}

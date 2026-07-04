const CHUNK_RELOAD_KEY = 'app:chunk-reload'

function isChunkLoadError(error) {
  const message = String(error?.message || error || '')
  return /Loading chunk|ChunkLoadError|Failed to fetch dynamically imported module|Importing a module script failed/i.test(message)
}

function reloadOnceForChunkError(error) {
  if (!isChunkLoadError(error)) return false
  const reloadKey = `${CHUNK_RELOAD_KEY}:${window.location.pathname}`
  if (sessionStorage.getItem(reloadKey)) return false
  sessionStorage.setItem(reloadKey, '1')
  window.location.reload()
  return true
}

export function createPageLoadingGuard(router) {
  router.beforeEach(() => {
    window.$loadingBar?.start()
  })

  router.afterEach(() => {
    setTimeout(() => {
      window.$loadingBar?.finish()
    }, 200)
  })

  router.onError((error) => {
    if (reloadOnceForChunkError(error)) return
    window.$loadingBar?.error()
  })

  window.addEventListener('unhandledrejection', (event) => {
    if (reloadOnceForChunkError(event.reason)) event.preventDefault()
  })
}

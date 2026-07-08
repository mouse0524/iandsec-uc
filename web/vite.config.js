import { defineConfig, loadEnv } from 'vite'

import { convertEnv, getSrcPath, getRootPath } from './build/utils'
import { viteDefine } from './build/config'
import { createVitePlugins } from './build/plugin'
import { OUTPUT_DIR, PROXY_CONFIG } from './build/constant'

function isKnownPreviewDependencyWarning(warning) {
  const message = typeof warning === 'string' ? warning : warning.message || ''
  const id = typeof warning === 'string' ? '' : warning.id || ''
  const importer = typeof warning === 'string' ? '' : warning.importer || ''
  const text = `${message}\n${id}\n${importer}`

  // ponytail: @open-file-viewer/core has one bundle entry for optional parsers; remove this when it exposes plugin subpaths.
  return (
    (text.includes('Module "buffer" has been externalized') &&
      (text.includes('safer-buffer') || text.includes('safe-buffer'))) ||
    (warning.code === 'EVAL' &&
      (id.includes('bluebird/js/release/util.js') ||
        id.includes('three/examples/jsm/libs/chevrotain.module.min.js')))
  )
}

export default defineConfig(({ command, mode }) => {
  const srcPath = getSrcPath()
  const rootPath = getRootPath()
  const isBuild = command === 'build'

  const env = loadEnv(mode, process.cwd())
  const viteEnv = convertEnv(env)
  const { VITE_PORT, VITE_PUBLIC_PATH, VITE_USE_PROXY, VITE_BASE_API } = viteEnv
  const shouldOpen = process.env.VITE_DEV_OPEN !== 'false' && process.env.CI !== 'true'

  return {
    base: VITE_PUBLIC_PATH || '/',
    resolve: {
      alias: {
        '~': rootPath,
        '@': srcPath,
      },
    },
    define: viteDefine,
    plugins: createVitePlugins(viteEnv, isBuild),
    server: {
      host: '0.0.0.0',
      port: VITE_PORT,
      open: shouldOpen,
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        Pragma: 'no-cache',
        Expires: '0',
      },
      proxy: VITE_USE_PROXY
        ? {
            [VITE_BASE_API]: PROXY_CONFIG[VITE_BASE_API],
          }
        : undefined,
    },
    build: {
      target: 'es2020',
      outDir: OUTPUT_DIR || 'dist',
      reportCompressedSize: false, // Disable gzip size report
      chunkSizeWarningLimit: 6144, // Keep lazy Excel preview below warning limit
      rollupOptions: {
        onwarn(warning, warn) {
          if (isKnownPreviewDependencyWarning(warning)) return
          warn(warning)
        },
      },
    },
  }
})

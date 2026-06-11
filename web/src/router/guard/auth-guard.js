import { getToken, isNullOrWhitespace } from '@/utils'
import { usePermissionStore, useUserStore } from '@/store'

export const WHITE_LIST = ['/login', '/404', '/403', '/public/webdav/share/download']
const BASIC_AUTH_PATHS = ['/profile']
export function createAuthGuard(router) {
  router.beforeEach(async (to) => {
    const token = getToken()
    const isWhiteListed = WHITE_LIST.includes(to.path)

    /** 没有token的情况 */
    if (isNullOrWhitespace(token)) {
      if (isWhiteListed) return true
      return { path: '/login', query: { ...to.query, redirect: to.path } }
    }

    /** 有token的情况 */
    if (to.path === '/login') return { path: '/' }
    if (isWhiteListed) return true

    const userStore = useUserStore()
    const roleNames = (userStore.role || []).map((item) => item?.name).filter(Boolean)
    if (!userStore.isSuperUser && to.path.startsWith('/workbench')) {
      if (roleNames.includes('客服')) return { path: '/ticket/review' }
      if (roleNames.includes('技术')) return { path: '/ticket/tech' }
      return { path: '/ticket/my' }
    }

    const permissionStore = usePermissionStore()
    const isBasicAuthPath = BASIC_AUTH_PATHS.some((path) => to.path === path || to.path.startsWith(`${path}/`))
    if (!userStore.isSuperUser && !isBasicAuthPath && !permissionStore.canAccessPath(to.path)) {
      return { path: '/403' }
    }

    return true
  })
}

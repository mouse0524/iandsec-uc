import { lStorage, sStorage } from '@/utils'

const TOKEN_CODE = 'access_token'
const REMEMBER_TOKEN_EXPIRE_SECONDS = 30 * 24 * 60 * 60

export function getToken() {
  const sessionToken = sStorage.getItem(TOKEN_CODE)
  const localToken = lStorage.getItem(TOKEN_CODE)
  if (!sessionToken?.value) return localToken?.value
  if (!localToken?.value) return sessionToken.value
  return (localToken.time || 0) > (sessionToken.time || 0) ? localToken.value : sessionToken.value
}

export function setToken(token, remember = false) {
  lStorage.remove(TOKEN_CODE)
  sStorage.remove(TOKEN_CODE)
  if (remember) {
    lStorage.set(TOKEN_CODE, token, REMEMBER_TOKEN_EXPIRE_SECONDS)
  } else {
    sStorage.set(TOKEN_CODE, token)
  }
}

export function removeToken() {
  lStorage.remove(TOKEN_CODE)
  sStorage.remove(TOKEN_CODE)
}

export function openAuthRouteInNewTab(href) {
  const targetUrl = new URL(href, window.location.href)
  if (targetUrl.origin !== window.location.origin) {
    window.open(targetUrl.href, '_blank', 'noopener')
    return
  }

  const newTab = window.open(targetUrl.href, '_blank')
  if (!newTab) return
  newTab.opener = null
}

// export async function refreshAccessToken() {
//   const tokenItem = lStorage.getItem(TOKEN_CODE)
//   if (!tokenItem) {
//     return
//   }
//   const { time } = tokenItem
//   // token生成或者刷新后30分钟内不执行刷新
//   if (new Date().getTime() - time <= 1000 * 60 * 30) return
//   try {
//     const res = await api.refreshToken()
//     setToken(res.data.token)
//   } catch (error) {
//     console.error(error)
//   }
// }

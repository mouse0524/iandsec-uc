;(function () {
  var key = 'iandsec:missing-asset-reload'
  var countKey = key + ':count'
  var now = Date.now()
  var count = Number(sessionStorage.getItem(countKey) || 0)
  if (count >= 3) {
    sessionStorage.removeItem(countKey)
    sessionStorage.removeItem(key)
    return
  }
  if (now - Number(sessionStorage.getItem(key) || 0) > 15000) {
    sessionStorage.setItem(key, String(now))
    sessionStorage.setItem(countKey, String(count + 1))
    location.reload()
  }
})()

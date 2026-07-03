;(function () {
  var key = 'iandsec:missing-asset-reload'
  var now = Date.now()
  if (now - Number(sessionStorage.getItem(key) || 0) > 15000) {
    sessionStorage.setItem(key, String(now))
    location.reload()
  }
})()

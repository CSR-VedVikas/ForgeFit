/* ForgeFit offline shell
 *
 * Bumping CACHE invalidates the old shell on activate. Do it whenever the
 * caching strategy below changes.
 */
const CACHE = "forgefit-shell-v2"
const SHELL = ["/", "/index.html", "/manifest.json", "/favicon.svg"]

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  )
})

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting()
})

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url)

  // Never cache the API or media. Sessions and food logs must not be served
  // from a stale shell, and /media is 171 MB of exercise art.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
    return
  }
  if (event.request.method !== "GET") return
  if (url.origin !== self.location.origin) return

  // Navigations go network-first.
  //
  // The old version served the cached shell first for everything, which meant
  // a user who had ever loaded the app could stay pinned to that build
  // indefinitely — talking to an API that had since changed under it. nginx
  // sends `Cache-Control: no-cache` for index.html precisely to prevent this,
  // and a cache-first service worker overrode it. Cache is now the fallback
  // for when the network is genuinely gone, which is the case it exists for.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put("/index.html", copy))
          return res
        })
        .catch(() => caches.match("/index.html").then((c) => c || caches.match("/")))
    )
    return
  }

  // Hashed build assets are immutable, so cache-first is correct for them.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached
      return fetch(event.request).then((res) => {
        if (res && res.status === 200 && res.type === "basic") {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(event.request, copy))
        }
        return res
      })
    })
  )
})

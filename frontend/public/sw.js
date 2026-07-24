/* ForgeFit offline shell */
const CACHE = "forgefit-shell-v1"
const SHELL = ["/", "/index.html", "/manifest.json", "/favicon.svg"]

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  )
})

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url)
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
    return
  }
  if (event.request.method !== "GET") return
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetched = fetch(event.request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(event.request, copy))
          return res
        })
        .catch(() => cached)
      return cached || fetched
    })
  )
})

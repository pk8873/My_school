const CACHE_NAME = "school-saathi-static-v1";
const STATIC_ASSETS = ["/static/css/app.css", "/static/js/app.js", "/static/pwa/manifest.webmanifest"];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // Never cache authenticated HTML, forms, POST requests, or user records.
  if (request.method !== "GET" || url.origin !== self.location.origin || !url.pathname.startsWith("/static/")) return;
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});

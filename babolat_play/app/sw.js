/* Offline support: data.js network-first (fresh stats when the Mac is reachable),
   app shell stale-while-revalidate (instant load, updates on next visit). */
var CACHE = "play-dashboard-v2";
var DATA_TIMEOUT_MS = 2500;
var SHELL = ["./", "index.html", "styles.css", "charts.js", "share.js", "app.js", "data.js",
  "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  var isData = new URL(e.request.url).pathname.endsWith("/data.js");
  e.respondWith(caches.open(CACHE).then(function (cache) {
    var network = fetch(e.request).then(function (res) {
      if (res.ok) cache.put(e.request, res.clone());
      return res;
    });
    if (isData) {
      // Fresh stats if the Mac answers quickly, else the last copy (away from home).
      var timeout = new Promise(function (resolve) { setTimeout(resolve, DATA_TIMEOUT_MS); });
      return Promise.race([network, timeout]).then(function (res) {
        return res || cache.match(e.request).then(function (hit) { return hit || network; });
      }).catch(function () { return cache.match(e.request); });
    }
    return cache.match(e.request).then(function (hit) {
      return hit ? (network.catch(function () {}), hit) : network;
    });
  }));
});

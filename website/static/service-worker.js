const CACHE_NAME = "flask-pwa-cache-v1";
const urlsToCache = new Set([
  "/",
  "/admin",
  "/admin/accounts",
  //"/admin/signup",
  //"/admin/submit_flow",
  //"/admin/review_flow",
  "/deposits",
  "/my_account",
  "/my_trades",
  "/my_transfers",
  "/withdrawals",
  //"/withdrawals/EUR",
  "/withdrawals/STN",
  "/how_it_works",
  //"/market",
  //"/send",
  "/offline",

  //"/logout",
  "/get_account_name",

  "/static/css/alerts.css",
  "/static/css/balance.css",
  "/static/css/fontawesome-all.min.css",
  "/static/css/main.css",
  "/static/css/noscript.css",

  "/static/images/icon.png",
  "/static/images/icon-192.png",
  "/static/images/icon-512.png",
  "/static/images/Sao_Tome.avif",

  "/static/js/breakpoints.min.js",
  "/static/js/browser.min.js",
  "/static/js/getname.js",
  "/static/js/jquery.min.js",
  "/static/js/jquery.scrollex.min.js",
  "/static/js/jquery.scrolly.min.js",
  "/static/js/main.js",
  "/static/js/util.js",

  "/static/webfonts/fa-brands-400.eot",
  "/static/webfonts/fa-brands-400.svg",
  "/static/webfonts/fa-brands-400.ttf",
  "/static/webfonts/fa-brands-400.woff",
  "/static/webfonts/fa-brands-400.woff2",
  "/static/webfonts/fa-regular-400.eot",
  "/static/webfonts/fa-regular-400.svg",
  "/static/webfonts/fa-regular-400.ttf",
  "/static/webfonts/fa-regular-400.woff",
  "/static/webfonts/fa-regular-400.woff2",
  "/static/webfonts/fa-solid-900.eot",
  "/static/webfonts/fa-solid-900.svg",
  "/static/webfonts/fa-solid-900.ttf",
  "/static/webfonts/fa-solid-900.woff",
  "/static/webfonts/fa-solid-900.woff2",

  "/static/manifest.json"
]);

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(async function(cache) {
        for (const url of urlsToCache) {
          try {
            await cache.add(url);
          } catch (error) {
            console.warn('Failed to cache', url, error);
          }
        }
      })
  );
});

// self.addEventListener("activate", (event) => {
//   event.waitUntil(async function() {
//     if ('navigationPreload' in self.registration) {
//       await self.registration.navigationPreload.disable();
//     }
//     await clients.claim();
//   }());
// });

// Check if a requested path is cacheable
function isCacheable(pathname) {
  console.log("about to check if " + pathname + " is cacheable.")
  return urlsToCache.has(pathname);
}

// self.addEventListener('fetch', function(event) {
//   const url = new URL(event.request.url);
// 
//   // Always bypass the service worker for a ping.
//   if (url.pathname === "/ping") {
//     return; // Let the browser handle it normally.
//   }
// 
//   if (url.origin === self.location.origin) {
//     event.respondWith(
//       fetch(event.request).then((networkResponse) => {
//         if (networkResponse && networkResponse.ok && isCacheable(url)) {
//           // Clone the page and store it in the cache.
//           const responseClone = networkResponse.clone();
//           caches.open(CACHE_NAME).then(cache => {
//             cache.put(event.request, responseClone);
//           });
//         }
//         return networkResponse;
//       }).catch(() => {
//         // We failed to get the page, so we will try the cache
//         return caches.match(event.request).then((cachedResponse) => {
//           if (cachedResponse) {
//             return cachedResponse;
//           }
//           if (event.request.mode == "navigate") {
//             return caches.match("/offline")
//           }
// 
//           // Otherwise fail silently
//           return new Response("Offline and not cached", {
//             status: 503,
//             statusText: "Service Unavailable",
//             headers: { "Content-Type": "text/plain" },
//           });
//         });
//       })
//     );
//   }
// });

self.addEventListener('fetch', function(event) {
  console.log("a")
  const url = new URL(event.request.url);

  // Always bypass the service worker for a ping.
  if (url.pathname === "/ping") {
    return; // Let the browser handle it normally.
  }

  if (url.origin === self.location.origin) {
    // The above line makes sure that our service worker only deals with 
    // requests from our website, not from chrome extensions.
    event.respondWith(
      fetch(event.request).then((networkResponse) => {
        console.log("b")
        console.log(networkResponse)
        console.log(networkResponse.ok)
        console.log(url.pathname)
        console.log(isCacheable(url.pathname))
        if (networkResponse && networkResponse.ok && isCacheable(url.pathname)) {
          console.log("c")
          // Clone the page and store it in the cache.
          const responseClone = networkResponse.clone();
          console.log("d")
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone).catch(err => {
              console.error("Cache put failed:", err);
            });
          });
        }
        console.log("e")
        return networkResponse;
      }).catch(() => {
        // We failed to get the page, so we will try the cache
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          if (event.request.mode == "navigate") {
            return caches.match("/offline")
          }
          // Otherwise fail silently
          return new Response("Offline and not cached", {
            status: 503,
            statusText: "Service Unavailable",
            headers: { "Content-Type": "text/plain" },
          });
        });
      })
    );
  }
});
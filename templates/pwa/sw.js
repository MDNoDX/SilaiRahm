{% load static %}/* Silai Rahm service worker: push notifications, and a friendly page when offline. */
const CACHE = "silairahm-v4";
const OFFLINE = "{% url 'offline' %}";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll([OFFLINE, "{% static 'css/app.css' %}", "{% static 'img/icon.svg' %}"]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Pages and files always come from the network (family data must be fresh and
// private); the cache is only the fallback when there is no connection.
self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
  } else if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      }).catch(() => caches.match(request))
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { title: "Silai Rahm", body: event.data ? event.data.text() : "" }; }
  event.waitUntil(self.registration.showNotification(data.title || "Silai Rahm", {
    body: data.body || "",
    icon: "{% static 'img/icon-192.png' %}",
    badge: "{% static 'img/badge.png' %}",
    tag: data.tag || undefined,
    data: { url: data.url || "/" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data && event.notification.data.url || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) { client.navigate(target); return client.focus(); }
      }
      return self.clients.openWindow(target);
    })
  );
});

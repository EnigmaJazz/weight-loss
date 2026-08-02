"use strict";

self.addEventListener("push", (event) => {
  let data = { title: "Weight Loss Tracker", body: "" };
  if (event.data) {
    try {
      data = event.data.json();
    } catch (_e) {
      data = { title: "Weight Loss Tracker", body: event.data.text() };
    }
  }
  const title = data.title || "Weight Loss Tracker";
  const body = data.body || "";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: "weight-loss-tracker",
      renotify: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const url = "/";
      const allClients = await clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of allClients) {
        if ("navigate" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })()
  );
});

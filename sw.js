/* Service worker do Cardápio RU UFCA: só cuida das notificações (lembretes). */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (e) => {
  let dados = {};
  try { dados = e.data ? e.data.json() : {}; } catch { dados = { body: e.data && e.data.text() }; }

  const titulo = dados.title || "Cardápio RU UFCA";
  e.waitUntil(self.registration.showNotification(titulo, {
    body: dados.body || "",
    icon: "img/icone-192.png",
    tag: dados.tag || "cardapio",
    renotify: true,
    data: { url: dados.url || self.registration.scope },
  }));
});

// Tocar na notificação abre o site (ou foca a aba já aberta) direto na refeição
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = e.notification.data && e.notification.data.url || self.registration.scope;
  e.waitUntil((async () => {
    const abertas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const cliente of abertas) {
      if (cliente.url.startsWith(self.registration.scope)) {
        await cliente.focus();
        return cliente.navigate(url);
      }
    }
    return self.clients.openWindow(url);
  })());
});

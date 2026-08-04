/** 서비스 워커 — 웹 푸시 수신/클릭 (docs/specs/push-reminder.md). 캐싱 없음, 푸시 전용. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

/** 채팅 알림 문구 — 페이지가 캐시에 심어둔 현재 테마의 위장 문구 (lib/chat-notice.ts).
 *  워커는 localStorage 를 못 읽어 테마를 알 수 없어서 페이지가 완성된 문구를 넘긴다.
 *  없으면 null → 서버 폴백 문구를 쓴다 (서버 문구도 내용이 없어 안전). */
async function cachedChatNotice() {
  try {
    const cache = await caches.open("esl-prefs");
    const res = await cache.match("/__chat-notice");
    if (!res) return null;
    const notice = await res.json();
    return notice && notice.title ? notice : null;
  } catch {
    return null;
  }
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    // 페이로드 파싱 실패 시 기본 문구로 표시
  }
  event.waitUntil(
    (async () => {
      // 채팅(kind=chat)만 내용 없는 알림 — 잠금화면 미리보기가 위장을 무력화한다
      // (docs/specs/chat.md). 게임 초대·복습 리마인더는 문구를 그대로 표시.
      const notice = data.kind === "chat" ? await cachedChatNotice() : null;
      await self.registration.showNotification(
        (notice && notice.title) || data.title || "ESL Lessonaza",
        {
          body: (notice && notice.body) || data.body || "",
          icon: "/icon-192.png",
          badge: "/icon-192.png",
          tag: data.tag || "esl",
          data: { url: data.url || "/" },
        },
      );
    })(),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        for (const client of list) {
          if ("focus" in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        return self.clients.openWindow(url);
      }),
  );
});

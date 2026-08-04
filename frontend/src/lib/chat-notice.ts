"use client";

import { getAppTheme } from "@/lib/theme";
import { chatNotice } from "@/lib/theme-surfaces";

/** 서비스 워커와 공유하는 캐시 계약 — `public/sw.js` 에 같은 문자열이 박혀 있다
 *  (워커는 번들 대상이 아니라 import 할 수 없다). 바꾸면 양쪽을 함께 고친다. */
const CACHE = "esl-prefs";
const KEY = "/__chat-notice";

/** 현재 테마의 채팅 알림 문구를 워커가 읽을 수 있는 곳에 심는다 (2026-08-04).
 *
 *  워커는 localStorage 를 못 읽어 테마를 모르고, 서버도 모른다 (테마는 기기
 *  로컬 설정). 그래서 페이지가 **완성된 문구**를 캐시에 써두고 워커는 표시만
 *  한다 — 라벨 표가 워커에 복제되지 않아 CHAT_LABEL_OF 가 정본으로 남는다. */
export async function syncChatNotice(): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    const cache = await caches.open(CACHE);
    await cache.put(
      KEY,
      new Response(JSON.stringify(chatNotice(getAppTheme())), {
        headers: { "Content-Type": "application/json" },
      }),
    );
  } catch {
    // 프라이빗 모드 등 캐시 불가 — 워커가 서버 폴백 문구로 표시한다 (내용은 없음)
  }
}

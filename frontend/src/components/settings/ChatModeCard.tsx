"use client";

import { setChatFloating, useChatFloating } from "@/lib/chat-mode";

/** 채팅창 설정 — 표시 방식(플로팅/도킹)만.
 *  새 글 알림 토글은 "알림" 섹션(NotificationCard)으로 통합 — 같은 기기
 *  구독 하나를 두 이름("복습 리마인더"/"새 글 알림")으로 조작하던 이중
 *  토글이 혼란의 원인이었다 (2026-07-31 보고). */
export function ChatModeCard() {
  const floating = useChatFloating();

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">채팅창</p>
      <p className="mb-3 text-xs opacity-60">
        체크 해제하면 팝업 대신 화면 우측에 항상 붙어있는 패널로 바뀌어요. 새
        메시지 알림은 위 &ldquo;알림&rdquo; 섹션에서 관리해요.
      </p>
      <label className="flex min-h-11 max-w-fit cursor-pointer items-center gap-2 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50">
        <input
          type="checkbox"
          checked={floating}
          onChange={(e) => setChatFloating(e.target.checked)}
          className="h-4 w-4"
        />
        플로팅 (우하단 팝업)
      </label>
    </section>
  );
}

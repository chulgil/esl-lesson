"use client";

import { setChatFloating, useChatFloating } from "@/lib/chat-mode";

/** 채팅창 표시 방식 — 플로팅(우하단 팝업, 기본) ↔ 도킹(화면 우측 상시 패널) */
export function ChatModeCard() {
  const floating = useChatFloating();

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">채팅창</p>
      <p className="mb-3 text-xs opacity-60">
        체크 해제하면 팝업 대신 화면 우측에 항상 붙어있는 패널로 바뀌어요.
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

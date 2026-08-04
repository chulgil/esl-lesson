"use client";

import { useEffect, useState } from "react";

const OPEN_EVENT = "esl-open-image";

/** 채팅 사진 확대 — 앱 안 팝업 (2026-08-04).
 *
 *  새 탭은 주소창에 업로드 URL 이 그대로 뜨고 브라우저 UI 로 화면이 바뀌어
 *  위장이 깨진다(docs/specs/chat.md 위장 테마). 모바일에선 앱으로 돌아오는
 *  동선도 끊긴다. 그래서 같은 화면 위에 띄우고 **아무 데나 클릭하면 닫는다** —
 *  힐끗 보일 때 한 번의 탭으로 사라지는 것이 이 앱의 탈출 동선과 맞는다.
 *
 *  전역에 하나만 마운트한다(layout.tsx). 채팅 위젯은 360x480 팝업이라 그 안에서
 *  렌더하면 잘리고, 스킨이 3벌(NoteSkin·ExcelSkin·ChatWidget)이라 각자 상태를
 *  들면 같은 코드가 3번 생긴다. */
export function openImage(url: string): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: url }));
}

export function ImageLightbox() {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    const onOpen = (e: Event) => setSrc((e as CustomEvent<string>).detail);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (src === null) return;
    // Esc 도 닫기 — 채팅 위젯·가이드와 같은 탈출 키 (chat.md)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSrc(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [src]);

  // 뒤 화면이 스크롤되면 모바일에서 사진이 따라 밀린다 — 열려 있는 동안만 잠금
  useEffect(() => {
    if (src === null) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [src]);

  if (src === null) return null;

  return (
    // 클릭 위치와 무관하게 닫힘 — 확대된 사진 자체를 눌러도 버블링으로 닫는다.
    // h-[100dvh]: 모바일 브라우저 툴바가 접히고 펴져도 화면 전체를 채운다
    // (inset-0 만 두면 iOS 에서 하단이 툴바에 잘린다 — 앱의 h-dvh 관례와 동일)
    <div
      role="dialog"
      aria-modal="true"
      aria-label="사진 크게 보기"
      onClick={() => setSrc(null)}
      className="fixed inset-0 z-[70] flex h-[100dvh] w-full cursor-zoom-out items-center justify-center bg-ink/80 p-2 sm:p-4"
    >
      {/* 터치에는 cursor-zoom-out 힌트가 안 보인다 — 닫기 버튼을 명시 (44px 타겟) */}
      <button
        type="button"
        onClick={() => setSrc(null)}
        aria-label="닫기 (Esc)"
        className="absolute top-3 right-3 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-ink/60 text-xl leading-none text-white"
      >
        ×
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="첨부 이미지"
        className="max-h-full max-w-full object-contain"
      />
    </div>
  );
}

"use client";

import { useSyncExternalStore } from "react";

/** 채팅 위젯 표시 방식 — 플로팅(우하단 팝업, 기본) / 도킹(화면 우측 상시 패널).
 *  테마(lib/theme.ts)와 동일한 localStorage + useSyncExternalStore 패턴. */

const STORAGE_KEY = "chat.floating";
const EVENT = "chat-floating-change";

export function getChatFloating(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(STORAGE_KEY) !== "false";
  } catch {
    return true;
  }
}

export function setChatFloating(floating: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(floating));
  } catch {
    // 프라이빗 모드 등 저장 실패 시에도 화면 적용은 진행
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useChatFloating(): boolean {
  return useSyncExternalStore(subscribe, getChatFloating, () => true);
}

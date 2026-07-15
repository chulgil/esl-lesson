"use client";

import { useSyncExternalStore } from "react";

/** 전역 앱 테마 — 디자인 토큰(data-theme)과 게임 보드가 함께 따른다 */
export type AppTheme = "note" | "candy" | "lego" | "cat";

export const APP_THEMES: {
  key: AppTheme;
  label: string;
  swatch: string;
  desc: string;
}[] = [
  {
    key: "note",
    label: "노트",
    swatch: "#FDFBF3",
    desc: "줄노트 + 형광펜 (기본)",
  },
  {
    key: "candy",
    label: "캔디",
    swatch: "#FFD7E8",
    desc: "파스텔 사탕 + 버블",
  },
  {
    key: "lego",
    label: "레고",
    swatch: "#CBDFF8",
    desc: "브릭 스터드 + 클래식 원색",
  },
  {
    key: "cat",
    label: "헤냥이",
    swatch: "#FFEDD6",
    desc: "헤헤 웃는 크림 냥이 + 몰랑 발도장",
  },
];

const STORAGE_KEY = "app.theme";
const EVENT = "app-theme-change";

function isTheme(v: unknown): v is AppTheme {
  return v === "note" || v === "candy" || v === "lego" || v === "cat";
}

export function getAppTheme(): AppTheme {
  if (typeof window === "undefined") return "note";
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return isTheme(saved) ? saved : "note";
  } catch {
    return "note";
  }
}

export function setAppTheme(theme: AppTheme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // 프라이빗 모드 등 저장 실패 시에도 화면 적용은 진행
  }
  document.documentElement.setAttribute("data-theme", theme);
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

/** 현재 테마 구독 훅 — 설정에서 바꾸면 구독 컴포넌트(게임 보드 등)가 즉시 반영 */
export function useAppTheme(): AppTheme {
  return useSyncExternalStore(subscribe, getAppTheme, () => "note");
}

"use client";

import { useSyncExternalStore } from "react";
import { THEME_KEYS, type AppTheme } from "@/lib/theme-keys";

/** 전역 앱 테마 — 디자인 토큰(data-theme)과 게임 보드가 함께 따른다.
 *  키 목록·순서는 theme-keys.ts 가 정본 — 여기는 메타(라벨·스와치)만 보탠다. */
export type { AppTheme } from "@/lib/theme-keys";

// Record 라 키를 빠뜨리면 컴파일 에러 — 새 테마 메타 누락 방지
const THEME_META: Record<
  AppTheme,
  { label: string; swatch: string; desc: string }
> = {
  note: {
    label: "노트",
    swatch: "#FDFBF3",
    desc: "줄노트 + 형광펜 (기본)",
  },
  candy: {
    label: "캔디",
    swatch: "#FFD7E8",
    desc: "파스텔 사탕 + 버블",
  },
  lego: {
    label: "레고",
    swatch: "#CBDFF8",
    desc: "브릭 스터드 + 클래식 원색",
  },
  cat: {
    label: "헤냥이",
    swatch: "#FFEDD6",
    desc: "헤헤 웃는 크림 냥이 + 몰랑 발도장",
  },
  school: {
    label: "학교수업",
    swatch: "#2E5B46",
    desc: "칠판에 분필로 — 교실에서 수업 듣는 기분",
  },
  academy: {
    label: "학원",
    swatch: "#E8DCB8",
    desc: "갱지 모의고사 + 빨간 채점펜 — 문제 푸는 기분",
  },
  ocean: {
    label: "여름 바다",
    swatch: "#BDE9F2",
    desc: "한여름 파도와 물거품 — 시원한 바닷가 기분",
  },
  excel: {
    label: "오피스",
    swatch: "#E2EFDA",
    desc: "스프레드시트 위장 — 채팅이 문서처럼 보여요",
  },
};

export const APP_THEMES: {
  key: AppTheme;
  label: string;
  swatch: string;
  desc: string;
}[] = THEME_KEYS.map((key) => ({ key, ...THEME_META[key] }));

const STORAGE_KEY = "app.theme";
const EVENT = "app-theme-change";

function isTheme(v: unknown): v is AppTheme {
  return typeof v === "string" && (THEME_KEYS as readonly string[]).includes(v);
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

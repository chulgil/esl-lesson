"use client";

import { type AppTheme, useAppTheme } from "@/lib/theme";

/** 테마 컨셉 단일 레지스트리 (2026-07-31) — 시험지·학습 카드·게임 보드·시계가
 *  전부 여기서 컨셉을 읽는다. 새 테마 추가 = 이 파일 + globals.css 토큰 +
 *  theme.ts 카탈로그 + 백엔드 THEME_ACCESS + layout.tsx 부트 스크립트 5곳 (화면별 하드코딩 금지).
 *
 *  컨셉 매핑: 노트=종이 시험지 / 캔디=화이트보드 / 레고=블록판 /
 *  헤냥이=칠판(분필) / 오피스=문서 위장 / 학교수업=갱지 시험지+교실. */

// --- 게임 보드 -----------------------------------------------------------------

/** BoardCanvas 가 전용 스킨을 가진 테마 — 나머지는 노트 보드로 폴백 */
export type BoardSkinTheme = "note" | "candy" | "lego" | "cat";

export function boardThemeOf(theme: AppTheme): BoardSkinTheme {
  return theme === "candy" || theme === "lego" || theme === "cat"
    ? theme
    : "note";
}

// --- 시계 (ExamTimer 등) -------------------------------------------------------

export type ClockKind =
  | "analog" // 교실 벽시계 (노트·학교수업)
  | "analog-candy" // 막대사탕
  | "analog-cat" // 고양이 귀·수염
  | "digital" // 레고 디지털 브릭
  | "cell"; // 오피스 상태바 셀

export const CLOCK_OF: Record<AppTheme, ClockKind> = {
  note: "analog",
  school: "analog",
  candy: "analog-candy",
  cat: "analog-cat",
  lego: "digital",
  excel: "cell",
};

// --- 채팅 메뉴 라벨 — 위장 컨셉과 정합 (2026-07-31) --------------------------------

export const CHAT_LABEL_OF: Record<AppTheme, string> = {
  note: "교환 노트",
  candy: "교환 일기",
  lego: "교환 노트",
  cat: "냥 쪽지",
  excel: "공유 문서",
  school: "쪽지",
};

// --- 표면(문항 카드) 스킨 — 시험지·학습 세션 공용 --------------------------------

export interface SurfaceSkin {
  /** 문항 카드 컨테이너 (배경·테두리·모서리 — 어두운 면은 글자색 포함) */
  section: string;
  /** 표제 밴드 (시험지 상단 제목 상자) */
  band: string;
  bandTitle: string;
  bandMeta: string;
  divider: string;
  number: string;
  prompt: string;
  promptSub: string;
  /** 선지 버튼 — 기본/선택 */
  choice: string;
  choiceSelected: string;
  /** 선지 번호 마크 — 기본/선택 */
  mark: string;
  markSelected: string;
  /** 테마 기본 모서리 — 힌트 강조·OMR 셀 등 공용 도형에 사용 */
  radius: string;
  /** OMR 답안지 — 패널·라벨·셀 3상태 */
  omrPanel: string;
  omrLabel: string;
  omrCell: string;
  omrCellActive: string;
  omrCellMarked: string;
  /** 장식 플래그 */
  studs?: boolean;
  paw?: boolean;
}

export const SURFACE_SKINS: Record<AppTheme, SurfaceSkin> = {
  note: {
    radius: "rounded-md",
    omrPanel: "rounded-lg border-2 border-ink/20 bg-white",
    omrLabel: "답안지",
    omrCell: "rounded-md border-2 border-dashed border-ink/25 bg-white opacity-70 hover:opacity-100",
    omrCellActive: "rounded-md border-2 border-brick-blue bg-brick-blue/15 text-brick-blue",
    omrCellMarked: "rounded-md border-2 border-ink bg-ink text-white",
    section: "rounded-lg border-2 border-ink/15 bg-white",
    band: "border-4 border-double border-ink/50 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-60",
    divider: "mb-3 border-b border-dashed border-ink/25",
    number: "text-xs font-bold opacity-60",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "border-ink/20 bg-white hover:border-brick-blue/60",
    choiceSelected: "border-brick-blue bg-brick-blue/10 font-bold",
    mark: "border-ink/30",
    markSelected: "border-brick-blue bg-brick-blue text-white",
  },
  candy: {
    radius: "rounded-full",
    omrPanel: "rounded-3xl border-4 border-brick-blue/25 bg-white shadow-inner",
    omrLabel: "마킹 보드",
    omrCell: "rounded-full border-2 border-brick-blue/25 bg-white opacity-70 hover:opacity-100",
    omrCellActive: "rounded-full border-2 border-brick-red bg-brick-red/15 text-brick-red",
    omrCellMarked: "rounded-full border-2 border-brick-red bg-brick-red text-white",
    section: "rounded-3xl border-4 border-brick-blue/25 bg-white shadow-inner",
    band: "rounded-full bg-highlight/70 px-4 py-2 text-center",
    bandTitle:
      "font-hand text-lg leading-tight font-bold underline decoration-brick-red/50 decoration-wavy underline-offset-4",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-60",
    divider: "mb-3 border-b-2 border-dotted border-brick-blue/25",
    number: "text-xs font-bold text-brick-red/70",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice:
      "rounded-full border-brick-blue/25 bg-white hover:border-brick-red/50",
    choiceSelected: "rounded-full border-brick-red bg-brick-red/10 font-bold",
    mark: "border-brick-blue/40",
    markSelected: "border-brick-red bg-brick-red text-white",
  },
  lego: {
    radius: "rounded-sm",
    omrPanel: "rounded-md border-4 border-ink bg-white",
    omrLabel: "조립판",
    omrCell: "rounded-sm border-2 border-dashed border-ink/40 bg-white opacity-70 hover:opacity-100",
    omrCellActive: "rounded-sm border-2 border-ink bg-brick-yellow/60 text-ink",
    omrCellMarked: "rounded-sm border-2 border-ink bg-brick-blue text-white",
    section: "rounded-md border-4 border-ink bg-white",
    band: "relative rounded-sm border-2 border-ink bg-brick-yellow/60 px-3 pt-3 pb-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-70",
    divider: "mb-3 border-b-2 border-ink/20",
    number: "text-xs font-bold opacity-60",
    prompt: "text-lg font-bold",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "rounded-sm border-ink/40 bg-white hover:border-ink",
    choiceSelected: "rounded-sm border-ink bg-brick-blue/15 font-bold",
    mark: "rounded-sm border-ink/50",
    markSelected: "rounded-sm border-ink bg-brick-blue text-white",
    studs: true,
  },
  cat: {
    radius: "rounded-lg",
    omrPanel: "rounded-lg border-4 border-[#6b4a2f] bg-[#2f4640] text-[#f4f1e8]",
    omrLabel: "출석부",
    omrCell: "rounded-lg border-2 border-dashed border-[#f4f1e8]/40 bg-white/5 opacity-80 hover:opacity-100",
    omrCellActive: "rounded-lg border-2 border-brick-yellow bg-white/15 text-brick-yellow",
    omrCellMarked: "rounded-lg border-2 border-brick-yellow bg-brick-yellow text-ink",
    // 칠판 — 분필 글씨. 어두운 면이라 텍스트·테두리를 밝게 뒤집는다
    section: "rounded-lg border-8 border-[#6b4a2f] bg-[#2f4640] text-[#f4f1e8]",
    band: "relative border-2 border-dashed border-[#f4f1e8]/50 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-70",
    divider: "mb-3 border-b border-dashed border-[#f4f1e8]/30",
    number: "text-xs font-bold opacity-70",
    prompt: "font-hand text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-70",
    choice: "border-[#f4f1e8]/40 bg-white/5 hover:border-brick-yellow/70",
    choiceSelected: "border-brick-yellow bg-white/15 font-bold",
    mark: "border-[#f4f1e8]/50",
    markSelected: "border-brick-yellow bg-brick-yellow text-ink",
    paw: true,
  },
  excel: {
    radius: "rounded-sm",
    omrPanel: "rounded-sm border border-[#c9cfd6] bg-white font-sans",
    omrLabel: "체크리스트",
    omrCell: "rounded-sm border border-[#c9cfd6] bg-white opacity-80 hover:bg-[#f6f8f9]",
    omrCellActive: "rounded-sm border border-[#217346] bg-[#e2efda] text-[#217346]",
    omrCellMarked: "rounded-sm border border-[#217346] bg-[#217346] text-white",
    // 평가서 시트 위장 — 셀 헤더 스트립 + 격자 느낌
    section: "rounded-sm border border-[#c9cfd6] bg-white font-sans",
    band: "border border-[#c9cfd6] bg-[#e2efda] px-3 py-1.5 text-left",
    bandTitle: "text-sm font-bold text-[#217346]",
    bandMeta: "mt-0 text-[10px] text-[#666]",
    divider: "mb-3 border-b border-[#e3e7eb]",
    number: "text-xs font-bold text-[#666]",
    prompt: "text-base font-medium text-[#24292f]",
    promptSub: "mt-1 text-sm text-[#666]",
    choice: "rounded-sm border-[#c9cfd6] bg-white hover:bg-[#f6f8f9]",
    choiceSelected: "rounded-sm border-[#217346] bg-[#e2efda] font-bold",
    mark: "rounded-sm border-[#c9cfd6]",
    markSelected: "rounded-sm border-[#217346] bg-[#217346] text-white",
  },
  school: {
    radius: "rounded-none",
    omrPanel: "rounded-none border-2 border-ink/40 bg-[#fbf8ee]",
    omrLabel: "OMR 카드",
    omrCell: "rounded-none border-2 border-dashed border-ink/30 bg-white opacity-70 hover:opacity-100",
    omrCellActive: "rounded-none border-2 border-brick-green bg-brick-green/10 text-brick-green",
    omrCellMarked: "rounded-none border-2 border-ink bg-ink text-white",
    // 갱지 시험지 — 직각 모서리 + 이중 괘선, 교실 중간고사 느낌
    section: "rounded-none border-2 border-ink/40 bg-[#fbf8ee]",
    band: "border-4 border-double border-ink/60 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold tracking-wide",
    bandMeta: "mt-0.5 text-[10px] tracking-[0.3em] opacity-60",
    divider: "mb-3 border-b-2 border-ink/30",
    number: "text-xs font-bold opacity-60",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "rounded-none border-ink/30 bg-white hover:border-brick-green",
    choiceSelected:
      "rounded-none border-brick-green bg-brick-green/10 font-bold",
    mark: "rounded-none border-ink/40",
    markSelected: "rounded-none border-brick-green bg-brick-green text-white",
  },
};

/** 현재 테마의 표면 스킨 — 시험지·학습 세션 카드가 공용으로 사용 */
export function useSurfaceSkin(): SurfaceSkin {
  const theme = useAppTheme();
  return SURFACE_SKINS[theme] ?? SURFACE_SKINS.note;
}

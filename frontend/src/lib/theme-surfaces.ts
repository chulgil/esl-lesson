"use client";

import { type AppTheme, useAppTheme } from "@/lib/theme";

/** 테마 컨셉 단일 레지스트리 (2026-07-31) — 시험지·학습 카드·게임 보드·시계가
 *  전부 여기서 컨셉을 읽는다. 새 테마 추가 = 이 파일 + globals.css 토큰 +
 *  theme.ts 카탈로그 + 백엔드 THEME_ACCESS + layout.tsx 부트 스크립트 5곳 (화면별 하드코딩 금지).
 *
 *  컨셉 매핑: 노트=종이 시험지 / 캔디=파스텔 사탕판 / 레고=블록판 /
 *  헤냥이=크림 고양이 카드(발도장) / 오피스=문서 위장 /
 *  학교수업=칠판(분필·나무 프레임) / 학원=갱지 모의고사(빨간 채점펜).
 *
 *  컨셉은 테마마다 배타적이다 — 한 물체는 한 테마만 쓴다. 헤냥이가 칠판을 쓰던
 *  것을 학교수업으로 돌려주고(2026-08-04), 학교수업이 겸하던 갱지는 학원 테마로
 *  분리했다(2026-08-04). 두 은유를 한 테마가 겸하면 그 테마의 정체가 흐려진다. */

// --- 게임 보드 -----------------------------------------------------------------

/** BoardCanvas 가 전용 스킨을 가진 테마 — excel 만 노트 보드로 폴백
 *  (오피스 위장 중 화려한 게임 보드 금지 결정 유지, docs/specs/chat.md) */
export type BoardSkinTheme =
  "note" | "candy" | "lego" | "cat" | "school" | "academy";

export function boardThemeOf(theme: AppTheme): BoardSkinTheme {
  return theme === "candy" ||
    theme === "lego" ||
    theme === "cat" ||
    theme === "school" ||
    theme === "academy"
    ? theme
    : "note";
}

// --- 시계 (ExamTimer 등) -------------------------------------------------------

export type ClockKind =
  | "analog" // 벽시계 (노트·학교수업·학원 — 교실도 시험장도 벽시계를 쓴다)
  | "analog-candy" // 막대사탕
  | "analog-cat" // 고양이 귀·수염
  | "digital" // 레고 디지털 브릭
  | "cell"; // 오피스 상태바 셀

export const CLOCK_OF: Record<AppTheme, ClockKind> = {
  note: "analog",
  school: "analog",
  academy: "analog",
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
  academy: "질문지",
};

/** 채팅 알림에 띄울 내용 없는 문구 (2026-08-04) — 발신자·본문을 싣지 않는다.
 *
 *  잠금화면 미리보기가 위장을 무력화하므로 채팅만 "도착했다"까지만 알린다.
 *  숨김은 채팅 한정 — 게임 초대·복습 리마인더는 문구를 그대로 보여준다.
 *  라벨은 CHAT_LABEL_OF 가 정본이라 여기서 다시 정의하지 않는다. */
export function chatNotice(theme: AppTheme): { title: string; body: string } {
  return {
    title: CHAT_LABEL_OF[theme],
    // 위장 테마는 업무 문서 어투로 — "글"은 사적인 냄새가 난다
    body: theme === "excel" ? "변경 사항이 있어요" : "새 글이 있어요",
  };
}

// --- 전역 메뉴 라벨 — 테마 세계관을 5탭 전체에 적용 (2026-08-03) ------------------
// 채팅만 테마어를 쓰고 나머지가 고정 라벨이면 위장 테마가 메뉴에서 깨진다.
// 채팅 라벨은 CHAT_LABEL_OF 가 정본이라 여기서 중복 정의하지 않는다.

export type NavKey = "home" | "study" | "library" | "game";

export const NAV_LABEL_OF: Record<AppTheme, Record<NavKey, string>> = {
  note: { home: "홈", study: "학습", library: "라이브러리", game: "게임" },
  candy: { home: "홈", study: "학습", library: "보물창고", game: "놀이터" },
  lego: { home: "홈", study: "학습", library: "부품함", game: "놀이터" },
  cat: { home: "홈", study: "학습", library: "보물창고", game: "놀이터" },
  // 위장 테마 — 업무 도구처럼 보여야 하므로 학습 냄새가 나는 단어를 쓰지 않는다
  excel: { home: "대시보드", study: "작업", library: "문서함", game: "도구" },
  school: { home: "교실", study: "수업", library: "교과서", game: "쉬는시간" },
  // 학원 — 교실(학교)과 겹치지 않게 자습·문제풀이 어휘로
  academy: {
    home: "자습실",
    study: "문제풀이",
    library: "문제집",
    game: "쉬는시간",
  },
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
    omrCell:
      "rounded-md border-2 border-dashed border-ink/25 bg-white opacity-70 hover:opacity-100",
    omrCellActive:
      "rounded-md border-2 border-brick-blue bg-brick-blue/15 text-brick-blue",
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
    omrCell:
      "rounded-full border-2 border-brick-blue/25 bg-white opacity-70 hover:opacity-100",
    omrCellActive:
      "rounded-full border-2 border-brick-red bg-brick-red/15 text-brick-red",
    omrCellMarked:
      "rounded-full border-2 border-brick-red bg-brick-red text-white",
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
    omrCell:
      "rounded-sm border-2 border-dashed border-ink/40 bg-white opacity-70 hover:opacity-100",
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
    // 크림 고양이 카드 — 몰랑한 모서리 + 살구 젤리 포인트 + 발도장 (2026-08-04).
    // 이전엔 초록 칠판(분필)이라 학습·시험 화면에서만 고양이 세계관이 끊기고
    // 학교수업 테마와 컨셉이 겹쳤다 — 칠판은 학교수업이 가져간다.
    radius: "rounded-xl",
    omrPanel: "rounded-xl border-2 border-[#f0d6b4] bg-[#fffaf2]",
    omrLabel: "발도장 답안지",
    omrCell:
      "rounded-xl border-2 border-dashed border-[#e8c9a3] bg-white opacity-75 hover:opacity-100",
    omrCellActive:
      "rounded-xl border-2 border-brick-red bg-brick-red/15 text-brick-red",
    omrCellMarked:
      "rounded-xl border-2 border-brick-red bg-brick-red text-brick-label",
    section: "rounded-xl border-2 border-[#f0d6b4] bg-[#fffaf2]",
    // 젤리 자국처럼 둥근 점선 밴드 — 캔디의 물결 밑줄과 겹치지 않게
    band: "relative rounded-xl border-2 border-dashed border-brick-red/35 bg-highlight/50 px-4 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-60",
    divider: "mb-3 border-b-2 border-dotted border-[#e8c9a3]",
    number: "text-xs font-bold text-brick-red/80",
    prompt: "font-hand text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "rounded-xl border-[#e8c9a3] bg-white hover:border-brick-red/60",
    choiceSelected: "rounded-xl border-brick-red bg-brick-red/15 font-bold",
    mark: "rounded-xl border-[#e8c9a3]",
    markSelected: "rounded-xl border-brick-red bg-brick-red text-brick-label",
    paw: true,
  },
  excel: {
    radius: "rounded-sm",
    omrPanel: "rounded-sm border border-[#c9cfd6] bg-white font-sans",
    omrLabel: "체크리스트",
    omrCell:
      "rounded-sm border border-[#c9cfd6] bg-white opacity-80 hover:bg-[#f6f8f9]",
    omrCellActive:
      "rounded-sm border border-[#217346] bg-[#e2efda] text-[#217346]",
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
  // 학교수업 — 칠판 그 자체 (2026-08-04 분리). 나무 프레임 + 딥그린 판 +
  // 분필 글씨. 색은 게임 보드(BoardCanvas school)와 같은 값이라 앱 전체가
  // 같은 칠판을 쓴다. 갱지 시험지는 학원(academy) 테마로 넘겼다.
  school: {
    radius: "rounded-none",
    // chalk-surface: 어두운 면 위에 놓인 흰 배경 요소의 글자색을 되돌리는 마커.
    // 컴포넌트들이 bg-white·형광펜(.hl)을 하드코딩해도 흰 바탕+흰 글씨가 되지
    // 않게 globals.css 가 이 컨테이너 안에서만 보정한다 (2026-08-04 가독성 보고)
    omrPanel:
      "chalk-surface rounded-none border-4 border-[#8a6a48] bg-[#2e5b46]",
    omrLabel: "출석부",
    omrCell:
      "rounded-none border-2 border-dashed border-[#f4f1e8]/40 bg-white/5 text-[#f4f1e8] opacity-80 hover:opacity-100",
    omrCellActive:
      "rounded-none border-2 border-brick-yellow bg-white/15 text-brick-yellow",
    omrCellMarked:
      "rounded-none border-2 border-[#f4f1e8] bg-[#f4f1e8] text-[#22332b]",
    section:
      "chalk-surface rounded-none border-8 border-[#8a6a48] bg-[#2e5b46] text-[#f4f1e8]",
    // 분필로 그은 얇은 밑줄 — 굵은 이중선은 바로 위 글자를 눌러 읽기 어려웠다
    // (2026-08-04 보고). 선은 옅게, 글자와의 간격은 넉넉히.
    band: "relative border-b border-[#f4f1e8]/25 px-3 pb-3 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold tracking-wide",
    bandMeta: "mt-0.5 text-[10px] tracking-[0.3em] opacity-70",
    divider: "mb-3 border-b border-dashed border-[#f4f1e8]/30",
    number: "text-xs font-bold opacity-75",
    prompt: "font-hand text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-75",
    choice:
      "rounded-none border-[#f4f1e8]/40 bg-white/5 hover:border-brick-yellow/70",
    choiceSelected: "rounded-none border-brick-yellow bg-white/15 font-bold",
    mark: "rounded-none border-[#f4f1e8]/50",
    markSelected:
      "rounded-none border-brick-yellow bg-brick-yellow text-[#22332b]",
  },
  // 학원 — 갱지 모의고사지 (2026-08-04 신설, 학교수업에서 갱지를 이관).
  // 직각 인쇄물 + 이중 괘선 표제 + 빨간 채점펜 포인트.
  academy: {
    radius: "rounded-none",
    omrPanel: "rounded-none border-2 border-ink/40 bg-[#fbf6e6]",
    omrLabel: "OMR 카드",
    omrCell:
      "rounded-none border-2 border-dashed border-ink/30 bg-white opacity-70 hover:opacity-100",
    omrCellActive:
      "rounded-none border-2 border-brick-red bg-brick-red/10 text-brick-red",
    omrCellMarked: "rounded-none border-2 border-ink bg-ink text-white",
    section: "rounded-none border-2 border-ink/40 bg-[#fbf6e6]",
    band: "border-4 border-double border-ink/60 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold tracking-wide",
    bandMeta: "mt-0.5 text-[10px] tracking-[0.3em] opacity-60",
    divider: "mb-3 border-b-2 border-ink/30",
    // 문항 번호는 채점펜 빨강 — 갱지 위 빨간 표기가 학원 시그니처
    number: "text-xs font-bold text-brick-red/80",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "rounded-none border-ink/30 bg-white hover:border-brick-red",
    choiceSelected: "rounded-none border-brick-red bg-brick-red/10 font-bold",
    mark: "rounded-none border-ink/40",
    markSelected: "rounded-none border-brick-red bg-brick-red text-white",
  },
};

/** 현재 테마의 표면 스킨 — 시험지·학습 세션 카드가 공용으로 사용 */
export function useSurfaceSkin(): SurfaceSkin {
  const theme = useAppTheme();
  return SURFACE_SKINS[theme] ?? SURFACE_SKINS.note;
}

/** 학습/라이브러리 API 클라이언트 (docs/specs/learning.md) */

export interface Question {
  card_id: number;
  item_id: number;
  state: string;
  quiz_mode: "choice_en2ko" | "choice_ko2en" | "cloze" | "pattern" | "compose";
  level: number;
  prompt?: string;
  prompt_ko?: string;
  choices?: string[];
  chips?: string[];
  template?: string;
  /** 밑줄(___)이 한글 해석의 어느 부분인지 — 패턴 문항 (2026-07-14) */
  blank_ko?: string;
  hint_thinking?: string | null;
  context?: string | null;
  media?: { video_id: string; start_ms: number; end_ms: number } | null;
  hint_answer?: string;
}

export interface AnswerResult {
  correct: boolean;
  rating_applied: number;
  interval_previews: Record<string, number>;
  correct_answer: string;
  /** 오답이 유사단어였을 때 — "아깝다" 비교 카드 (P2) */
  close_match: { item_id: number; en_text: string; ko_text: string } | null;
  explanation: {
    ko: string;
    thinking_ko: string | null;
    context_en: string | null;
  };
  card: { state: string; due_at: string };
}

/** 단어 인사이트 카드 (docs/proposal/word-insight.md) */
export interface WordInsight {
  ipa?: string;
  pos?: string;
  nuance_ko?: string;
  examples?: { en: string; ko: string }[];
  collocations?: string[];
  synonyms?: { word: string; ko: string; diff_ko: string }[];
  confusables?: { word: string; ko: string; diff_ko: string }[];
}

/** 어휘망 그래프 (docs/proposal/word-insight.md P3) */
export interface NetworkNode {
  item_id: number;
  en: string;
  ko: string;
  item_type: string;
  state: string;
  reps: number;
}

export interface NetworkEdge {
  source: number;
  target: number;
  distance: number;
}

export interface NetworkSuggestion {
  item_id: number;
  en: string;
  ko: string;
  distance: number;
  near_item_id: number;
}

export interface VocabNetwork {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  suggestions: NetworkSuggestion[];
  embeddings_enabled: boolean;
}

/** 업적 배지 — 로그 실시간 집계, 소급 반영 (P3) */
export type AchievementTier =
  "beginner" | "intermediate" | "advanced" | "master";

export interface Achievement {
  key: string;
  title: string;
  desc: string;
  current: number;
  target: number;
  achieved: boolean;
  progress: number;
  /** 난이도 티어 — null 은 단발 업적 (첫 걸음 등) */
  tier: AchievementTier | null;
  /** 스티커 벽 섹션 그룹 */
  family: "study" | "streak" | "game" | "social";
}

/** 주간 학습 리더보드 — 나+친구 (P1 데일리 루프) */
export interface StudyRank {
  user_id: number;
  name: string;
  reviews: number;
  rank: number;
  me: boolean;
}

export interface Stats {
  xp: number;
  level: number;
  level_progress: number;
  due_count: number;
  reviews_today: number;
  /** 오늘의 목표 — 밀린 양과 무관한 달성 가능 소량 (포기 방지 기획) */
  daily_goal: number;
  streak_days: number;
  /** 책갈피(스트릭 보호) 보유 — 주 1회 목표 달성 시 지급 (retention-plan.md) */
  streak_savers: number;
  /** 책갈피로 지킨 날짜(ISO) — 잔디 표기용 */
  streak_saved_days: string[];
  levels: {
    level: number;
    item_type: string;
    cards: number;
    /** 내가 만날 수 있는 항목 수 — 공용 승인 ∪ 내 개인 (전역 승인 아님) */
    available_items: number;
  }[];
  daily: Record<string, number>;
}

/** 오늘의 미션 — 날짜 결정적 3종, 진행도는 로그 파생 (retention-plan.md) */
export interface Quest {
  key: string;
  title: string;
  desc: string;
  target: number;
  current: number;
  done: boolean;
  xp: number;
}

export interface QuestBoard {
  date: string;
  items: Quest[];
  all_done: boolean;
  all_done_xp: number;
}

/** 덱 = 담은 콘텐츠 — 덱별 학습 카운트 (docs/specs/study-decks.md) */
export interface StudyDeck {
  content_id: number;
  title: string;
  due: number;
  new_available: number;
  total_cards: number;
}

export interface LibraryContent {
  id: number;
  title: string;
  source: string;
  url: string | null;
  mine: boolean;
  subscribed: boolean;
  /** "creativeCommon" | "youtube"(표준) | null(미확인) — CC 배지·저작자표시용 */
  youtube_license: string | null;
  item_count: number;
}

export interface AlignedWord {
  w: string;
  s: number;
  e: number;
}

export interface LibraryDetail {
  id: number;
  title: string;
  source: string;
  subscribed: boolean;
  youtube_license: string | null;
  youtube_video_id: string | null;
  segments: {
    seq: number;
    start_ms: number | null;
    end_ms: number | null;
    en_text: string;
    ko_text: string | null;
    words: AlignedWord[] | null;
  }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const studyApi = {
  // contentId 지정 시 해당 덱(콘텐츠)만 학습 (docs/specs/study-decks.md)
  queue: (contentId?: number) =>
    request<{
      total_due: number;
      introduced_today: number;
      hint_delay_seconds: number;
      deck: { content_id: number; title: string } | null;
      questions: Question[];
    }>(
      contentId != null
        ? `/api/study/queue?content_id=${contentId}`
        : "/api/study/queue",
    ),
  decks: () => request<{ items: StudyDeck[] }>("/api/study/decks"),
  getSettings: () =>
    request<{
      hint_delay_seconds: number;
      study_level: number;
      levels_enabled: number[];
      daily_goal: number;
    }>("/api/settings"),
  patchSettings: (body: {
    hint_delay_seconds?: number;
    study_level?: number;
    daily_goal?: number;
  }) =>
    request<{
      hint_delay_seconds: number;
      study_level: number;
      levels_enabled: number[];
      daily_goal: number;
    }>("/api/settings", { method: "PATCH", body: JSON.stringify(body) }),
  answer: (body: {
    card_id: number;
    quiz_mode: string;
    answer: string;
    duration_ms: number;
  }) =>
    request<AnswerResult>("/api/study/answer", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  rate: (card_id: number, rating: number) =>
    request("/api/study/rate", {
      method: "POST",
      body: JSON.stringify({ card_id, rating }),
    }),
  addCard: (item_id: number) =>
    request<{ added: boolean; card_id: number }>("/api/cards", {
      method: "POST",
      body: JSON.stringify({ item_id }),
    }),
  insight: (itemId: number) =>
    request<WordInsight>(`/api/study/items/${itemId}/insight`),
  network: () => request<VocabNetwork>("/api/study/network"),
  achievements: () =>
    request<{ items: Achievement[]; achieved_count: number; total: number }>(
      "/api/study/achievements",
    ),
  leaderboard: () => request<{ items: StudyRank[] }>("/api/study/leaderboard"),
  quests: () => request<QuestBoard>("/api/study/quests"),
  stats: () => request<Stats>("/api/study/stats"),
  library: () => request<{ items: LibraryContent[] }>("/api/contents"),
  libraryDetail: (id: number) => request<LibraryDetail>(`/api/contents/${id}`),
};

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
export interface Achievement {
  key: string;
  title: string;
  desc: string;
  current: number;
  target: number;
  achieved: boolean;
  progress: number;
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
  levels: {
    level: number;
    item_type: string;
    cards: number;
    /** 내가 만날 수 있는 항목 수 — 공용 승인 ∪ 내 개인 (전역 승인 아님) */
    available_items: number;
  }[];
  daily: Record<string, number>;
}

export interface LibraryContent {
  id: number;
  title: string;
  source: string;
  url: string | null;
  mine: boolean;
  item_count: number;
}

export interface LibraryDetail {
  id: number;
  title: string;
  source: string;
  youtube_video_id: string | null;
  segments: {
    seq: number;
    start_ms: number | null;
    end_ms: number | null;
    en_text: string;
    ko_text: string | null;
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
  queue: () =>
    request<{
      total_due: number;
      introduced_today: number;
      hint_delay_seconds: number;
      questions: Question[];
    }>("/api/study/queue"),
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
  stats: () => request<Stats>("/api/study/stats"),
  library: () => request<{ items: LibraryContent[] }>("/api/contents"),
  libraryDetail: (id: number) => request<LibraryDetail>(`/api/contents/${id}`),
};

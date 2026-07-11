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
  hint_thinking?: string | null;
  context?: string | null;
}

export interface AnswerResult {
  correct: boolean;
  rating_applied: number;
  correct_answer: string;
  explanation: {
    ko: string;
    thinking_ko: string | null;
    context_en: string | null;
  };
  card: { state: string; due_at: string };
}

export interface Stats {
  due_count: number;
  reviews_today: number;
  streak_days: number;
  levels: {
    level: number;
    item_type: string;
    cards: number;
    approved_items: number;
  }[];
  daily: Record<string, number>;
}

export interface LibraryContent {
  id: number;
  title: string;
  source: string;
  url: string | null;
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
      questions: Question[];
    }>("/api/study/queue"),
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
  stats: () => request<Stats>("/api/study/stats"),
  library: () => request<{ items: LibraryContent[] }>("/api/contents"),
  libraryDetail: (id: number) => request<LibraryDetail>(`/api/contents/${id}`),
};

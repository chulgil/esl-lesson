/** 학습/라이브러리 API 클라이언트 (docs/specs/learning.md) */

export interface Question {
  card_id: number;
  item_id: number;
  state: string;
  /** 직전 리뷰 등급(1~4) — null 은 처음 학습. 힌트 정책 분기: 쉬움(4)만
   *  시간차 힌트, 그 외는 순차 힌트 (learning.md 힌트 타이머) */
  last_rating: number | null;
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
  /** 이번 정답으로 기억 안정도가 장기 기억 임계(7일)를 넘었는가 — 마이크로 보상 */
  long_term_reached: boolean;
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
  /** 어원 분해 — ted-routine P1-4 (구 캐시엔 없음, 신규 생성분부터) */
  etymology_ko?: string;
  same_root?: { word: string; ko: string }[];
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
  family: "study" | "streak" | "game" | "social" | "exam";
  /** 달성 시 지급되는 테마 키 — 보상 규칙이 있을 때만 (theme-mall.md) */
  reward_theme: string | null;
}

/** 주간 학습 리더보드 — 나+친구 (P1 데일리 루프) */
export interface StudyRank {
  user_id: number;
  name: string;
  reviews: number;
  rank: number;
  me: boolean;
  /** 플레이어 배지 — 마스코트·대표 업적 칭호 (게임 리더보드와 동일) */
  mascot?: string | null;
  title?: string | null;
}

/** 장기 기억 — stability 7일+ 카드 수와 주별 도달 누적 (learning.md 장기 기억 지표) */
export interface LongTermMemory {
  count: number;
  weekly: { week_start: string; count: number }[];
}

export interface Stats {
  xp: number;
  level: number;
  level_progress: number;
  /** 오답 정리 대상 — 최근 7일 내 틀린 카드 수 (learning.md 오답 정리 모드) */
  weak_count: number;
  long_term: LongTermMemory;
  due_count: number;
  /** 내일(KST) 안에 새로 due 가 되는 카드 수 — 세션 완료 "내일 예고" */
  due_tomorrow: number;
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
    /** 학습 난이도(levels_enabled)로 활성화된 타입인가 — 컬렉션 잠김 표시용 */
    enabled?: boolean;
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
  /** 정복(루틴) 완료 단계 수 0~6 — 시작한 여정 상기 (content-routine.md) */
  routine_done: number;
}

/** 주간 성적표 — 지난주 vs 그 전주, 전부 로그 실시간 파생 (docs/specs/weekly-report.md) */
export interface WeeklyReport {
  week_start: string;
  week_end: string;
  reviews: number;
  reviews_delta: number;
  accuracy: number | null;
  /** 전주 복습이 없으면 null — 0% 에서 올랐다고 말하지 않는다 */
  accuracy_delta: number | null;
  long_term_new: number;
  long_term_new_delta: number;
  routine_steps: number;
  routine_steps_delta: number;
  /** 재청취 이해도 전후 평균 차 — 비교쌍 없으면 null */
  listen: { delta: number; contents: number } | null;
  streak_days: number;
  /** 지난주 복습 1개 이상 — 노출 게이트 */
  has_data: boolean;
}

/** 콘텐츠 루틴 여정 — 6단계 + 한 문장 요약 (docs/proposal/ted-routine-2026-08.md) */
export interface ContentRoutine {
  steps: { step: number; done: boolean }[];
  completed: boolean;
  summary: { text: string; feedback: string | null; created_at: string } | null;
  /** 재청취 이해도 1~5 — before=첫 청취(1단계), after=루틴 후(6단계) */
  listen: { before: number | null; after: number | null };
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
  /** 항목 difficulty_hint 분포에서 파생 — 항목이 없으면 null */
  difficulty: "beginner" | "intermediate" | "advanced" | null;
  /** 이미 내 카드가 있는 항목 비율(0~100) — 항목이 없으면 null */
  known_ratio: number | null;
  /** 콘텐츠 언어 — 라이브러리 배지·필터 (i18n) */
  lang: "en" | "ja" | "ko";
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
  /** 콘텐츠 언어 (i18n) */
  lang: "en" | "ja" | "ko";
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
  // mode="weak" 는 오답 정리 — 최근 오답 카드만 (docs/specs/learning.md)
  queue: (contentId?: number, mode?: "weak") => {
    const params = new URLSearchParams();
    if (contentId != null) params.set("content_id", String(contentId));
    if (mode) params.set("mode", mode);
    const qs = params.toString();
    return request<{
      total_due: number;
      introduced_today: number;
      hint_delay_seconds: number;
      deck: { content_id: number; title: string } | null;
      mode?: string;
      questions: Question[];
    }>(qs ? `/api/study/queue?${qs}` : "/api/study/queue");
  },
  decks: () => request<{ items: StudyDeck[] }>("/api/study/decks"),
  getSettings: () =>
    request<{
      hint_delay_seconds: number;
      study_level: number;
      levels_enabled: number[];
      daily_goal: number;
      /** 복습 리마인더 시각(KST, 5-23) — push-reminder.md */
      reminder_hour: number;
      /** 대표 업적 키 — 대전·리더보드 칭호 (mascot-shop.md 플레이어 배지) */
      featured_achievement: string | null;
      /** 내 기기 중 푸시 구독이 하나라도 있는가 — 온보딩 ③ 완료 판정 */
      push_subscribed: boolean;
      /** 주언어 — 채팅 자동번역의 번역 대상 언어 기준 */
      primary_lang: "ko" | "en" | "ja";
      /** 학습언어(복수) — 주언어 제외 */
      learning_langs: string[];
      /** 채팅 자동번역 on/off */
      chat_translate: boolean;
      translate_mine: boolean;
      translate_theirs: boolean;
    }>("/api/settings"),
  patchSettings: (body: {
    hint_delay_seconds?: number;
    study_level?: number;
    daily_goal?: number;
    reminder_hour?: number;
    /** 대표 업적 — "" = 해제 */
    featured_achievement?: string;
    primary_lang?: "ko" | "en" | "ja";
    learning_langs?: string[];
    chat_translate?: boolean;
    translate_mine?: boolean;
    translate_theirs?: boolean;
  }) =>
    request<{
      hint_delay_seconds: number;
      study_level: number;
      levels_enabled: number[];
      daily_goal: number;
      reminder_hour: number;
      featured_achievement: string | null;
      push_subscribed: boolean;
      primary_lang: "ko" | "en" | "ja";
      learning_langs: string[];
      chat_translate: boolean;
      translate_mine: boolean;
      translate_theirs: boolean;
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
  /** 내가 쓰는 말 덱 — 조회 시 lazy 동기화 (docs/specs/my-phrases.md) */
  myPhrases: () =>
    request<{
      content_id: number;
      total: number;
      added_now: number;
      recent: { en: string; ko: string }[];
    }>("/api/study/my-phrases"),
  quests: () => request<QuestBoard>("/api/study/quests"),
  stats: () => request<Stats>("/api/study/stats"),
  weeklyReport: () => request<WeeklyReport>("/api/study/weekly-report"),
  library: () => request<{ items: LibraryContent[] }>("/api/contents"),
  libraryDetail: (id: number) => request<LibraryDetail>(`/api/contents/${id}`),
  // 콘텐츠 루틴 여정 (ted-routine P1) — 구독 콘텐츠만 (비구독 404)
  routine: (contentId: number) =>
    request<ContentRoutine>(`/api/contents/${contentId}/routine`),
  setRoutineStep: (contentId: number, step: number, done: boolean) =>
    request<{ step: number; done: boolean; completed: boolean }>(
      `/api/contents/${contentId}/routine/${step}`,
      { method: "POST", body: JSON.stringify({ done }) },
    ),
  /** "이런 영상이 보고 싶어요" — 공급을 수요와 연결 (하루 5건) */
  requestContent: (text: string) =>
    request<{ saved: boolean }>("/api/contents/requests", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  submitSummary: (contentId: number, text: string) =>
    request<{ feedback: string | null }>(`/api/contents/${contentId}/summary`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  // 재청취 이해도 셀프 체크 — 같은 stage 재제출은 갱신 (effectiveness-audit P1)
  submitListenCheck: (contentId: number, stage: 1 | 2, score: number) =>
    request<{ stage: number; score: number }>(
      `/api/contents/${contentId}/listen-check`,
      { method: "POST", body: JSON.stringify({ stage, score }) },
    ),
};

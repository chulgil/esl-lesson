/** 시험 API — 요약·응시·서버 채점·랭킹 (docs/specs/library-exam.md) */

export interface ExamTopEntry {
  nickname: string;
  score: number;
  duration_ms: number;
}

export interface ExamBest {
  score: number;
  duration_ms: number;
  rank: number;
}

/** 활성 시험 요약 — exam_id null 이면 "시험 준비 중" (오류 아님) */
export interface ExamSummary {
  exam_id: number | null;
  round?: number;
  question_count?: number;
  /** 응시자 수 — 제출 완료 기준 distinct 유저 */
  attempt_count?: number;
  my_best?: ExamBest | null;
  top?: ExamTopEntry[];
  /** 진행 중(미제출) 응시 — 재진입 시 "이어서 응시" + 경과 영속 (2026-07-31) */
  my_open_attempt?: { attempt_id: number; started_at: string } | null;
}

/** 응시 문항 — 정답(answer_index)은 서버만 안다 */
export interface ExamQuestion {
  seq: number;
  quiz_mode: string;
  prompt: string;
  prompt_ko: string | null;
  choices: string[];
}

export interface ExamStart {
  attempt_id: number;
  /** 서버 저장 시작 시각 — 경과 시계의 기준 (재개해도 이어진다) */
  started_at: string;
  questions: ExamQuestion[];
}

export interface ExamResultRow {
  seq: number;
  correct: boolean;
  answer_index: number;
}

export interface ExamGraded {
  score: number;
  correct_count: number;
  duration_ms: number;
  rank: number;
  results: ExamResultRow[];
  /** 이번 제출로 얻은 XP — 제출 20 + 점수 10점당 1 (보상 체감) */
  xp_gained: number;
}

/** 열린 시험 — 학습 허브 도전 카드·라이브러리 시험 칩 (경쟁 상태 동봉) */
export interface OpenExam {
  exam_id: number;
  content_id: number;
  content_title: string;
  round: number;
  question_count: number;
  attempt_user_count: number;
  my_best: { score: number; duration_ms: number } | null;
  top_name: string | null;
}

export interface ExamRankingRow {
  rank: number;
  nickname: string;
  score: number;
  duration_ms: number;
  is_me: boolean;
}

export interface ExamRankings {
  items: ExamRankingRow[];
  me: ExamRankingRow | null;
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

export const examApi = {
  open: () => request<{ items: OpenExam[] }>("/api/exams/open"),

  summary: (contentId: number) =>
    request<ExamSummary>(`/api/contents/${contentId}/exam`),

  start: (examId: number) =>
    request<ExamStart>(`/api/exams/${examId}/attempts`, { method: "POST" }),

  resume: (examId: number, attemptId: number) =>
    request<ExamStart>(`/api/exams/${examId}/attempts/${attemptId}`),

  abandon: (examId: number, attemptId: number) =>
    request<void>(`/api/exams/${examId}/attempts/${attemptId}`, {
      method: "DELETE",
    }),

  submit: (examId: number, attemptId: number, answers: number[]) =>
    request<ExamGraded>(`/api/exams/${examId}/attempts/${attemptId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  rankings: (examId: number) =>
    request<ExamRankings>(`/api/exams/${examId}/rankings`),
};

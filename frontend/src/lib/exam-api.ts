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
  summary: (contentId: number) =>
    request<ExamSummary>(`/api/contents/${contentId}/exam`),

  start: (examId: number) =>
    request<ExamStart>(`/api/exams/${examId}/attempts`, { method: "POST" }),

  submit: (examId: number, attemptId: number, answers: number[]) =>
    request<ExamGraded>(`/api/exams/${examId}/attempts/${attemptId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  rankings: (examId: number) =>
    request<ExamRankings>(`/api/exams/${examId}/rankings`),
};

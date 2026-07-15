/** 게임 REST 클라이언트 — 전적/리더보드 (docs/specs/word-tetris.md P3 리텐션) */

export interface GameProfile {
  played: number;
  wins: number;
  losses: number;
  best_score: number;
  best_combo: number;
  best_wpm: number;
}

export interface LeaderboardEntry {
  name: string;
  score: number;
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export interface GameBests {
  tetris_best_score: number;
  quiz_best_score: number;
  typing_best_cpm: number;
  scramble_best_score: number;
}

/** 게임별 주간 최고 기록 랭킹 (P3) */
export interface WeeklyRank {
  name: string;
  value: number;
  me: boolean;
}

export interface WeeklyLeaderboards {
  tetris: WeeklyRank[];
  quiz: WeeklyRank[];
  typing: WeeklyRank[];
  scramble: WeeklyRank[];
}

export const gameApi = {
  profile: () => request<GameProfile>("/api/game/profile"),
  leaderboard: () =>
    request<{ items: LeaderboardEntry[] }>("/api/game/leaderboard"),
  leaderboards: () => request<WeeklyLeaderboards>("/api/game/leaderboards"),
  bests: () => request<GameBests>("/api/game/bests"),
};

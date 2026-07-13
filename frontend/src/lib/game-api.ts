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

export const gameApi = {
  profile: () => request<GameProfile>("/api/game/profile"),
  leaderboard: () =>
    request<{ items: LeaderboardEntry[] }>("/api/game/leaderboard"),
};

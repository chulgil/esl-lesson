/** 관전 허용 토글 기억 — 마지막 값을 localStorage 에 저장해 학습 화면
 *  진입 시 자동 복원한다 (기본값은 여전히 OFF, docs/specs/study-spectate.md
 *  §진입 경로 재설계 — "매번 다시 켜는 마찰 제거"). */

const STORAGE_KEY = "esl:study:spectate-enabled";

export function getSpectateEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setSpectateEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(enabled));
  } catch {
    // 프라이빗 모드 등 저장 실패 시에도 화면 적용은 진행
  }
}

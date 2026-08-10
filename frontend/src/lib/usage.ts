/** 사용 이벤트 파이어-앤-포겟 로깅 (P1-D — docs/specs/usage-events.md).
 *
 *  관측이 UX 를 방해하면 안 된다 — 응답을 기다리지 않고 실패는 조용히 무시.
 *  keepalive 로 페이지 이탈 직전 전송도 살린다.
 */
export function logUsage(kind: string, meta?: Record<string, string>): void {
  if (typeof window === "undefined") return;
  try {
    void fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, meta: meta ?? {} }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // 미로그인·네트워크 오류 — 관측 실패는 무시
  }
}

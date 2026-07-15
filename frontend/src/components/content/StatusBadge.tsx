/** 콘텐츠 처리 상태 공용 표기 — 사용자·백오피스가 같은 언어를 쓴다.
 *
 * 진행 중(pending/extracting)은 노랑 + 맥박 애니메이션으로 "살아있음"을,
 * 실패만 빨강으로 표시해 대기 상태가 오류로 오인되지 않게 한다.
 */

import type { ContentSummary } from "@/lib/admin-api";

export type ContentStatus = ContentSummary["status"];

export const STATUS_LABELS: Record<ContentStatus, string> = {
  pending: "준비 중",
  extracting: "만드는 중",
  ready: "완료",
  failed: "실패",
};

const STATUS_STYLES: Record<ContentStatus, string> = {
  pending: "bg-brick-yellow/30 animate-pulse",
  extracting: "bg-brick-yellow/30 animate-pulse",
  ready: "bg-brick-green/20 text-brick-green",
  failed: "bg-brick-red/15 text-brick-red",
};

export function StatusBadge({ status }: { status: ContentStatus }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLES[status] ?? "bg-ink/10"}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

import type { ReactNode } from "react";

/** 학습 탭 접기 섹션 — 누적·참고 정보는 접힌 상태가 기본
 *  (cake-benchmark-2026-08 P2 C3: 홈 잔디 접기와 같은 문법).
 *  summary 에 정보 냄새(내 순위·달성 수)를 남겨 열어볼 이유를 준다. */
export function CollapsibleSection({
  title,
  summary,
  borderClass,
  children,
}: {
  title: string;
  /** 접힌 상태에서도 보이는 한 줄 요약 (정보 냄새) */
  summary?: ReactNode;
  borderClass: string;
  children: ReactNode;
}) {
  return (
    <details
      className={`group mt-5 max-w-4xl rounded-xl border-2 ${borderClass} bg-white shadow-sm`}
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-5 py-4 [&::-webkit-details-marker]:hidden">
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="shrink-0 opacity-50 transition-transform group-open:rotate-180"
          aria-hidden
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
        <h2 className="font-hand text-2xl font-bold">{title}</h2>
        {summary && (
          <span className="ml-auto text-xs opacity-60">{summary}</span>
        )}
      </summary>
      <div className="px-5 pb-5">{children}</div>
    </details>
  );
}

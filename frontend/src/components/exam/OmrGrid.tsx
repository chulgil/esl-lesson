"use client";

/** OMR 답안 마킹 그리드 — 1~N 번호, 마킹/현재 문항 표시, 탭하면 해당 문항 이동.
 *  모바일에선 하단 고정으로 쓰인다 (docs/specs/library-exam.md 프론트 화면). */
export function OmrGrid({
  total,
  answers,
  current,
  onJump,
}: {
  total: number;
  answers: (number | null)[];
  current: number;
  onJump: (index: number) => void;
}) {
  const answered = answers.filter((a) => a != null).length;
  return (
    <div className="rounded-lg border-2 border-ink/20 bg-white p-3">
      <p className="mb-2 flex items-baseline justify-between text-xs font-bold">
        답안지
        <span className="font-normal opacity-60">
          {answered}/{total} 마킹 · 남은 {total - answered}
        </span>
      </p>
      <ol className="grid grid-cols-10 gap-1.5 sm:grid-cols-5">
        {Array.from({ length: total }, (_, idx) => {
          const marked = answers[idx] != null;
          const active = idx === current;
          return (
            <li key={idx}>
              <button
                type="button"
                onClick={() => onJump(idx)}
                aria-current={active}
                aria-label={`${idx + 1}번 문항${marked ? " (마킹됨)" : ""}`}
                className={`flex h-8 w-full items-center justify-center rounded-md border-2 text-xs font-bold transition sm:h-9 ${
                  active
                    ? "border-brick-blue bg-brick-blue/15 text-brick-blue"
                    : marked
                      ? "border-ink bg-ink text-white"
                      : "border-dashed border-ink/25 bg-white opacity-70 hover:opacity-100"
                }`}
              >
                {idx + 1}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

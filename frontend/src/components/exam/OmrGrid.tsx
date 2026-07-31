"use client";

import { useSurfaceSkin } from "@/lib/theme-surfaces";

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
  // 답안지도 테마 컨셉 — 패널·셀·명칭이 테마별 (theme-surfaces, 2026-07-31)
  const skin = useSurfaceSkin();
  return (
    <div className={`p-3 ${skin.omrPanel}`}>
      <p className="mb-2 flex items-baseline justify-between text-xs font-bold">
        {skin.omrLabel}
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
                className={`flex h-8 w-full items-center justify-center text-xs font-bold transition sm:h-9 ${
                  active
                    ? skin.omrCellActive
                    : marked
                      ? skin.omrCellMarked
                      : skin.omrCell
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

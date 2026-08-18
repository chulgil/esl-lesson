/** 콘텐츠 준비 진행 단계 — 기다림을 "지금 무슨 일이 벌어지는지"로 보여준다.
 *
 * 잡(step) 기록 기반 3단계 체크리스트. 상세 페이지의 5초 폴링으로 저절로
 * 갱신되므로 사용자는 새로고침 없이 진행을 지켜볼 수 있다.
 */

import type { Job } from "@/lib/admin-api";

interface Step {
  key: string;
  label: string;
  doing: string;
}

const YOUTUBE_STEPS: Step[] = [
  {
    key: "transcript",
    label: "자막 받아 적기",
    doing: "유튜브에서 자막을 받아 적고 있어요",
  },
  {
    key: "translate",
    label: "우리말로 옮기기",
    doing: "문장을 우리말로 옮기고 있어요",
  },
  {
    key: "extract",
    label: "학습 항목 고르기",
    doing: "외울 만한 단어와 표현을 고르고 있어요",
  },
];

// 수기 입력은 자막 단계가 없다 (파이프라인이 translate 부터 시작)
const MANUAL_STEPS = YOUTUBE_STEPS.slice(1);

export function ExtractionProgress({
  source,
  jobs,
}: {
  // chat 덱은 추출 파이프라인이 없어 이 화면에 오지 않지만, 타입 정합상 수용
  source: "youtube" | "manual" | "chat";
  jobs: Job[];
}) {
  const steps = source === "youtube" ? YOUTUBE_STEPS : MANUAL_STEPS;
  const done = new Set(
    jobs.filter((j) => j.status === "done").map((j) => j.step),
  );
  const currentIdx = steps.findIndex((s) => !done.has(s.key));
  // 모든 단계 완료 후 내부 마무리(embed) 중일 때
  const doing =
    currentIdx === -1
      ? "마무리 손질 중이에요 — 거의 다 됐어요!"
      : steps[currentIdx].doing;

  return (
    <div className="mb-6 max-w-md rounded-lg border-2 border-ink/10 bg-white p-4">
      <ol className="flex flex-col gap-1.5 text-sm">
        {steps.map((s, i) => {
          const isDone = done.has(s.key);
          const isCurrent = i === currentIdx;
          return (
            <li
              key={s.key}
              className={`flex items-center gap-2 ${
                isDone ? "opacity-60" : isCurrent ? "font-bold" : "opacity-35"
              }`}
            >
              <span
                aria-hidden
                className={`w-4 text-center ${
                  isDone
                    ? "text-brick-green"
                    : isCurrent
                      ? "animate-pulse text-brick-yellow"
                      : ""
                }`}
              >
                {isDone ? "✓" : isCurrent ? "●" : "○"}
              </span>
              {s.label}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 animate-pulse font-hand text-sm">{doing}</p>
      <p className="mt-1 text-xs opacity-50">
        보통 1~2분이면 끝나요 · 이 화면은 저절로 새로고침돼요
      </p>
    </div>
  );
}

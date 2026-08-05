"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type ContentRoutine, studyApi } from "@/lib/study-api";

/** 콘텐츠 루틴 가이드 — "이 영상 갈아 넣기" 3파트 6단계
 *  (docs/proposal/ted-routine-2026-08.md P1-1·P1-3). 카드 학습(FSRS) 위에
 *  콘텐츠 단위 여정을 얹는다. 완주 +50 XP, 요약 제출 +20 XP. */

const STEPS: {
  step: number;
  part: string;
  title: string;
  desc: string;
}[] = [
  {
    step: 1,
    part: "듣기",
    title: "자막 없이 전체 듣기",
    desc: "흐름과 주제만 — 다 알아들으려 하지 않아요",
  },
  {
    step: 2,
    part: "듣기",
    title: "중심 찾으며 다시 듣기",
    desc: '"이 사람의 메시지는 무엇인가"만 쫓아요',
  },
  {
    step: 3,
    part: "분석",
    title: "문장 직해 (구간 반복)",
    desc: "위 플레이어에서 문장 반복으로 한 문장씩 — 안 들리는 원인(단어·문법·연음)을 찾아요",
  },
  {
    step: 4,
    part: "분석",
    title: "추출 카드 학습",
    desc: "이 영상의 단어·숙어·패턴을 복습 큐로",
  },
  {
    step: 5,
    part: "체화",
    title: "섀도잉",
    desc: "느리게 → 원속도 → 자막 가리고 — 인토네이션까지",
  },
  {
    step: 6,
    part: "체화",
    title: "한 문장 요약",
    desc: "영상의 메시지를 영어 한 문장으로 — 인출해야 내 것",
  },
];

/** 재청취 이해도 1~5 — "안 들리던 게 들린다"를 재는 셀프 체크
 *  (docs/proposal/effectiveness-audit-2026-08.md P1) */
function ListenCheckRow({
  value,
  disabled,
  onPick,
}: {
  value: number | null;
  disabled: boolean;
  onPick: (score: number) => void;
}) {
  return (
    <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-bold opacity-70">얼마나 들렸나요?</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          onClick={() => onPick(n)}
          aria-pressed={value === n}
          aria-label={`들린 정도 ${n}점`}
          className={`h-6 w-6 shrink-0 cursor-pointer rounded-full border-2 text-[11px] font-bold transition ${
            value === n
              ? "border-brick-blue bg-brick-blue text-brick-label"
              : "border-ink/25 bg-white hover:border-brick-blue/60"
          }`}
        >
          {n}
        </button>
      ))}
    </span>
  );
}

export function RoutineGuide({
  contentId,
  onStartShadowing,
}: {
  contentId: number;
  onStartShadowing?: () => void;
}) {
  const [routine, setRoutine] = useState<ContentRoutine | null>(null);
  const [summaryText, setSummaryText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [busyStep, setBusyStep] = useState<number | null>(null);
  const [listenBusy, setListenBusy] = useState(false);

  useEffect(() => {
    studyApi
      .routine(contentId)
      .then(setRoutine)
      .catch(() => setRoutine(null)); // 비구독 등 — 섹션 숨김
  }, [contentId]);

  if (!routine) return null;

  const doneSet = new Set(
    routine.steps.filter((s) => s.done).map((s) => s.step),
  );

  async function toggle(step: number) {
    if (busyStep) return;
    setBusyStep(step);
    try {
      // 응답으로 로컬 갱신 — 토글마다 전체 재조회(GET)하지 않는다
      const res = await studyApi.setRoutineStep(
        contentId,
        step,
        !doneSet.has(step),
      );
      setRoutine(
        (prev) =>
          prev && {
            ...prev,
            completed: res.completed,
            steps: prev.steps.map((s) =>
              s.step === res.step ? { ...s, done: res.done } : s,
            ),
          },
      );
    } catch {
      // 실패는 조용히 — 다음 탭에서 재시도
    }
    setBusyStep(null);
  }

  async function pickListen(stage: 1 | 2, score: number) {
    if (listenBusy) return;
    setListenBusy(true);
    try {
      // 응답으로 로컬 갱신 — 전체 재조회(GET)하지 않는다
      const res = await studyApi.submitListenCheck(contentId, stage, score);
      setRoutine(
        (prev) =>
          prev && {
            ...prev,
            listen:
              stage === 1
                ? { ...prev.listen, before: res.score }
                : { ...prev.listen, after: res.score },
          },
      );
    } catch {
      // 실패는 조용히 — 다시 누르면 재시도
    }
    setListenBusy(false);
  }

  async function submitSummary() {
    if (!summaryText.trim() || submitting) return;
    setSubmitting(true);
    try {
      await studyApi.submitSummary(contentId, summaryText.trim());
      setSummaryText("");
      setRoutine(await studyApi.routine(contentId));
    } catch {
      // 실패는 조용히
    }
    setSubmitting(false);
  }

  return (
    <section className="rounded-xl border-2 border-brick-blue/40 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="font-hand text-2xl font-bold">이 영상 갈아 넣기</h2>
        <span className="text-xs opacity-60">
          듣기 → 분석 → 체화, 한 편을 끝까지
        </span>
        {routine.completed && (
          <span className="ml-auto rounded bg-brick-green/15 px-2 py-0.5 text-xs font-bold text-brick-green">
            완주! +50 XP
          </span>
        )}
      </div>

      {/* 진행 브릭 6칸 */}
      <div className="mt-3 flex gap-1" aria-label="루틴 진행">
        {STEPS.map((s) => (
          <span
            key={s.step}
            className={`h-2.5 flex-1 rounded-sm ${
              doneSet.has(s.step) ? "bg-brick-green" : "bg-ink/10"
            }`}
          />
        ))}
      </div>

      <ol className="mt-3 flex flex-col gap-1.5">
        {STEPS.map((s) => {
          const done = doneSet.has(s.step);
          return (
            <li
              key={s.step}
              className="flex items-center gap-2.5 rounded-md border-2 border-ink/10 px-3 py-2"
            >
              <button
                type="button"
                disabled={busyStep !== null || s.step === 6}
                onClick={() => toggle(s.step)}
                aria-pressed={done}
                aria-label={`${s.title} ${done ? "완료 해제" : "완료 체크"}`}
                className={`flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-full border-2 text-xs font-bold transition ${
                  done
                    ? "border-brick-green bg-brick-green text-brick-label"
                    : "border-ink/25 bg-white hover:border-brick-green/60"
                } ${s.step === 6 ? "cursor-default" : ""}`}
              >
                {done ? "v" : s.step}
              </button>
              <span className="min-w-0 flex-1">
                <span
                  className={`text-sm font-bold ${done ? "opacity-50" : ""}`}
                >
                  <span className="mr-1.5 rounded bg-ink/10 px-1 py-0.5 text-[10px]">
                    {s.part}
                  </span>
                  {s.title}
                </span>
                <span className="block text-xs opacity-60">{s.desc}</span>
                {s.step === 1 && (
                  <ListenCheckRow
                    value={routine.listen.before}
                    disabled={listenBusy}
                    onPick={(score) => pickListen(1, score)}
                  />
                )}
              </span>
              {s.step === 4 && (
                <Link
                  href={`/study/session?content=${contentId}`}
                  className="shrink-0 rounded-md border-2 border-brick-green/60 bg-white px-2.5 py-1 text-xs font-bold text-brick-green transition hover:-translate-y-0.5"
                >
                  학습
                </Link>
              )}
              {s.step === 5 && onStartShadowing && (
                <button
                  type="button"
                  onClick={onStartShadowing}
                  className="shrink-0 cursor-pointer rounded-md border-2 border-brick-blue/60 bg-white px-2.5 py-1 text-xs font-bold text-brick-blue transition hover:-translate-y-0.5"
                >
                  시작
                </button>
              )}
            </li>
          );
        })}
      </ol>

      {/* 6단계 — 한 문장 요약 (제출 시 자동 체크) */}
      <div className="mt-3 rounded-md border-2 border-dashed border-brick-blue/30 p-3">
        <p className="text-sm font-bold">
          이 영상의 메시지를 영어 한 문장으로
          <span className="ml-1.5 text-xs font-normal opacity-60">
            정답이 아니라 인출이 목적 — 틀려도 제출 +20 XP
          </span>
        </p>
        <div className="mt-2 flex gap-2">
          <input
            value={summaryText}
            onChange={(e) => setSummaryText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submitSummary();
              }
            }}
            maxLength={500}
            placeholder="The speaker says that..."
            className="min-h-11 min-w-0 flex-1 rounded border-2 border-ink/20 px-3 text-sm"
          />
          <button
            type="button"
            onClick={submitSummary}
            disabled={submitting || !summaryText.trim()}
            className="shrink-0 rounded-md border-2 border-brick-blue bg-white px-3 text-sm font-bold text-brick-blue disabled:opacity-40"
          >
            {submitting ? "피드백 받는 중..." : "제출"}
          </button>
        </div>
        {routine.summary && (
          <div className="mt-2 rounded bg-highlight/30 px-3 py-2 text-sm">
            <p className="font-medium">&ldquo;{routine.summary.text}&rdquo;</p>
            {routine.summary.feedback && (
              <p className="mt-1 text-xs opacity-70">
                {routine.summary.feedback}
              </p>
            )}
          </div>
        )}

        {/* 루틴 후 재청취 이해도 — 첫 청취와의 전후 비교가 효과의 증거 */}
        <div className="mt-3 border-t-2 border-dashed border-brick-blue/20 pt-2">
          <ListenCheckRow
            value={routine.listen.after}
            disabled={listenBusy}
            onPick={(score) => pickListen(2, score)}
          />
          {routine.listen.before !== null && routine.listen.after !== null && (
            <p className="mt-1.5 text-xs font-bold text-brick-green">
              처음 {routine.listen.before} &rarr; 지금 {routine.listen.after}
              {routine.listen.after > routine.listen.before &&
                ` (+${routine.listen.after - routine.listen.before} 만큼 더 들려요!)`}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

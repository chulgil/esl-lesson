"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { SegmentPlayer } from "@/components/media/SegmentPlayer";
import { studyApi, type AnswerResult, type Question } from "@/lib/study-api";

type Phase = "loading" | "empty" | "question" | "feedback" | "done";

export default function StudyPage() {
  const [queue, setQueue] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [hintDelay, setHintDelay] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    studyApi
      .queue()
      .then((res) => {
        setQueue(res.questions);
        setHintDelay(res.hint_delay_seconds ?? 0);
        setPhase(res.questions.length ? "question" : "empty");
        startedAt.current = Date.now();
      })
      .catch((e) => setError(e.message));
  }, []);

  const question = queue[idx];

  async function submit(answer: string) {
    if (!question) return;
    try {
      const res = await studyApi.answer({
        card_id: question.card_id,
        quiz_mode: question.quiz_mode,
        answer,
        duration_ms: Date.now() - startedAt.current,
      });
      setResult(res);
      setAnsweredCount((n) => n + 1);
      if (res.correct) {
        setCorrectCount((n) => n + 1);
      } else {
        // 오답은 세션 끝에 재출제 (docs/specs/learning.md)
        setQueue((q) => [...q, question]);
      }
      setPhase("feedback");
    } catch (e) {
      setError(e instanceof Error ? e.message : "제출 실패");
    }
  }

  function next() {
    const nextIdx = idx + 1;
    if (nextIdx >= queue.length) {
      setPhase("done");
    } else {
      setIdx(nextIdx);
      setResult(null);
      setPhase("question");
      startedAt.current = Date.now();
    }
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <Link
          href="/"
          aria-label="학습 종료하고 홈으로"
          className="inline-flex min-h-11 items-center gap-2 rounded-md border-2 border-ink/25 bg-white px-3 font-bold shadow-sm transition hover:border-brick-red hover:text-brick-red"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            aria-hidden
          >
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
          <span className="hidden sm:inline">나가기</span>
        </Link>
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">오늘의 학습</span>
        </h1>
        {(phase === "question" || phase === "feedback") && (
          <span className="ml-auto rounded-full bg-white px-3 py-1 text-sm font-bold shadow-sm">
            {Math.min(idx + 1, queue.length)} / {queue.length}
          </span>
        )}
        <button
          type="button"
          aria-label="학습 설정"
          onClick={() => setShowSettings((v) => !v)}
          className="inline-flex min-h-11 items-center rounded-md border-2 border-ink/25 bg-white px-3 font-bold shadow-sm transition hover:border-brick-blue"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
          </svg>
        </button>
      </header>

      {showSettings && (
        <div className="mb-6 flex max-w-xl items-center gap-3 rounded-lg border-2 border-ink/15 bg-white p-4 text-sm">
          <label className="flex items-center gap-2 font-bold">
            힌트까지 대기(초)
            <input
              type="number"
              min={0}
              max={120}
              value={hintDelay}
              onChange={(e) => setHintDelay(Math.max(0, Number(e.target.value)))}
              className="w-20 rounded border-2 border-ink/20 px-2 py-1.5"
            />
          </label>
          <span className="opacity-60">0 = 힌트 끄기. 시간이 지나면 정답 단어가 순차적으로 표시됩니다.</span>
          <button
            type="button"
            onClick={() => {
              studyApi.patchSettings({ hint_delay_seconds: hintDelay }).catch(() => undefined);
              setShowSettings(false);
            }}
            className="ml-auto rounded-md bg-brick-green px-4 py-2 font-bold text-white"
          >
            저장
          </button>
        </div>
      )}

      {error && <p className="text-sm text-brick-red">{error}</p>}

      {phase === "loading" && (
        <p className="text-sm opacity-60">큐를 불러오는 중...</p>
      )}

      {phase === "empty" && (
        <div className="flex flex-col items-start gap-4">
          <p>오늘 복습할 카드가 없어요. 내일 다시 만나요!</p>
          <Brick color="blue" href="/library">
            라이브러리 둘러보기
          </Brick>
        </div>
      )}

      {(phase === "question" || phase === "feedback") && question && (
        <>
          <ProgressBricks total={queue.length} done={idx} />
          <QuestionCard
            key={`${question.card_id}-${idx}`}
            question={question}
            disabled={phase === "feedback"}
            hintDelay={hintDelay}
            onSubmit={submit}
          />
          {phase === "feedback" && result && (
            <Feedback question={question} result={result} onNext={next} />
          )}
        </>
      )}

      {phase === "done" && (
        <section className="flex flex-col items-start gap-4">
          <h2 className="font-hand text-2xl">세션 완료!</h2>
          <p>
            {answeredCount}문항 중{" "}
            <b className="text-brick-green">{correctCount}개</b> 정답 (
            {answeredCount
              ? Math.round((correctCount / answeredCount) * 100)
              : 0}
            %)
          </p>
          <div className="flex gap-3">
            <Brick color="green" onClick={() => window.location.reload()}>
              이어서 학습
            </Brick>
            <Brick color="blue" href="/">
              홈으로
            </Brick>
          </div>
        </section>
      )}
    </main>
  );
}

function ProgressBricks({ total, done }: { total: number; done: number }) {
  return (
    <div
      className="mb-6 flex flex-wrap gap-1"
      aria-label={`${done}/${total} 진행`}
    >
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`h-3 w-5 rounded-sm transition-colors ${
            i < done ? "bg-brick-green" : "bg-ink/15"
          }`}
        />
      ))}
    </div>
  );
}

function QuestionCard({
  question,
  disabled,
  hintDelay,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintDelay: number;
  onSubmit: (answer: string) => void;
}) {
  // 힌트 타이머: hintDelay 초마다 정답 단어를 순차 공개 (docs/specs/learning.md)
  const [hintStep, setHintStep] = useState(0);
  useEffect(() => {
    if (!hintDelay || disabled || !question.hint_answer) return;
    const timer = setInterval(
      () => setHintStep((s) => Math.min(s + 1, 30)),
      hintDelay * 1000,
    );
    return () => clearInterval(timer);
  }, [hintDelay, disabled, question.hint_answer]);

  const highlightAnswer =
    hintStep >= 1 && question.hint_answer ? question.hint_answer : null;
  const hintWords = question.hint_answer
    ? question.hint_answer.split(/\s+/).slice(0, hintStep)
    : [];

  return (
    <div className="max-w-xl -rotate-[0.4deg] rounded-lg border-2 border-ink/10 bg-white p-6 shadow-md">
      <p className="mb-1 text-xs opacity-50">레벨 {question.level}</p>
      {(question.quiz_mode === "choice_en2ko" ||
        question.quiz_mode === "choice_ko2en" ||
        question.quiz_mode === "cloze") && (
        <ChoiceQuiz
          prompt={question.prompt!}
          sub={question.quiz_mode === "cloze" ? (question.prompt_ko ?? undefined) : undefined}
          question={question}
          disabled={disabled}
          highlight={highlightAnswer}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "pattern" && (
        <PatternQuiz
          question={question}
          disabled={disabled}
          hintWords={hintWords}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "compose" && (
        <ComposeQuiz
          question={question}
          disabled={disabled}
          hintWords={hintWords}
          onSubmit={onSubmit}
        />
      )}
      {question.media && (
        <div className="mt-5 border-t border-ink/10 pt-4">
          <SegmentPlayer media={question.media} />
        </div>
      )}
    </div>
  );
}

function ChoiceQuiz({
  prompt,
  sub,
  question,
  disabled,
  highlight,
  onSubmit,
}: {
  prompt: string;
  sub?: string;
  question: Question;
  disabled: boolean;
  highlight?: string | null;
  onSubmit: (answer: string) => void;
}) {
  return (
    <div>
      <p className="text-2xl font-bold">{prompt}</p>
      {sub && <p className="mt-1 text-sm opacity-60">{sub}</p>}
      {question.context && (
        <p className="mt-2 text-sm opacity-50">
          &quot;{question.context}&quot;
        </p>
      )}
      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {question.choices?.map((choice, i) => (
          <button
            key={choice}
            type="button"
            disabled={disabled}
            onClick={() => onSubmit(choice)}
            className={`min-h-11 rounded-md border-2 px-4 py-2 text-left font-medium transition hover:-translate-y-0.5 hover:border-brick-blue disabled:opacity-50 ${
              highlight === choice
                ? "border-brick-yellow bg-highlight/50"
                : "border-ink/15 bg-paper"
            }`}
          >
            <span className="mr-2 text-xs opacity-40">{i + 1}</span>
            {choice}
          </button>
        ))}
      </div>
    </div>
  );
}

function PatternQuiz({
  question,
  disabled,
  hintWords,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintWords: string[];
  onSubmit: (answer: string) => void;
}) {
  const [picked, setPicked] = useState<number[]>([]);
  const chips = question.chips ?? [];
  const hintSet = new Set(hintWords);

  return (
    <div>
      <p className="text-lg font-bold">{question.prompt_ko}</p>
      <p className="mt-1 font-mono text-sm opacity-60">{question.template}</p>
      <div className="mt-4 min-h-11 rounded border-2 border-dashed border-ink/20 bg-paper p-2">
        {picked.map((chipIdx, i) => (
          <button
            key={`${chipIdx}-${i}`}
            type="button"
            disabled={disabled}
            onClick={() => setPicked((p) => p.filter((_, j) => j !== i))}
            className="mb-1 mr-1 rounded bg-brick-blue px-2 py-1 text-sm font-bold text-white"
          >
            {chips[chipIdx]}
          </button>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {chips.map((chip, chipIdx) =>
          picked.includes(chipIdx) ? null : (
            <button
              key={chipIdx}
              type="button"
              disabled={disabled}
              onClick={() => setPicked((p) => [...p, chipIdx])}
              className={`rounded border-2 px-2 py-1 text-sm hover:border-brick-blue ${
                hintSet.has(chip)
                  ? "border-brick-yellow bg-highlight/60 font-bold"
                  : "border-ink/15 bg-white"
              }`}
            >
              {chip}
            </button>
          ),
        )}
      </div>
      <div className="mt-4 flex items-center gap-4">
        <Brick
          color="green"
          onClick={
            disabled || picked.length === 0
              ? undefined
              : () => onSubmit(picked.map((i) => chips[i]).join(" "))
          }
        >
          제출
        </Brick>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onSubmit("")}
          className="min-h-11 rounded-md px-3 text-sm opacity-60 hover:underline"
        >
          모르겠어요 (정답 보기)
        </button>
      </div>
    </div>
  );
}

function ComposeQuiz({
  question,
  disabled,
  hintWords,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintWords: string[];
  onSubmit: (answer: string) => void;
}) {
  const [text, setText] = useState("");
  return (
    <div>
      <p className="text-lg font-bold">{question.prompt_ko}</p>
      {question.hint_thinking && (
        <p className="mt-1 text-sm text-brick-blue">
          ({question.hint_thinking})
        </p>
      )}
      {hintWords.length > 0 && (
        <p className="mt-2 text-sm">
          힌트: <span className="hl font-bold">{hintWords.join(" ")}</span>
          <span className="opacity-40"> ...</span>
        </p>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && text.trim() && !disabled) {
            e.preventDefault();
            onSubmit(text);
          }
        }}
        disabled={disabled}
        rows={2}
        placeholder="영어로 입력하세요 (Enter 제출)"
        className="mt-4 w-full rounded border-2 border-ink/20 px-3 py-2"
      />
      <div className="mt-3 flex items-center gap-4">
        <Brick
          color="green"
          onClick={disabled || !text.trim() ? undefined : () => onSubmit(text)}
        >
          제출
        </Brick>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onSubmit("")}
          className="min-h-11 rounded-md px-3 text-sm opacity-60 hover:underline"
        >
          모르겠어요 (정답 보기)
        </button>
      </div>
    </div>
  );
}

const RATING_BUTTONS: {
  rating: number;
  label: string;
  active: string;
  idle: string;
}[] = [
  {
    rating: 1,
    label: "다시",
    active: "border-brick-red bg-brick-red text-white",
    idle: "border-brick-red/40 text-brick-red",
  },
  {
    rating: 2,
    label: "어려움",
    active: "border-brick-yellow bg-brick-yellow text-ink",
    idle: "border-brick-yellow/60 text-ink",
  },
  {
    rating: 3,
    label: "알맞음",
    active: "border-brick-green bg-brick-green text-white",
    idle: "border-brick-green/40 text-brick-green",
  },
  {
    rating: 4,
    label: "쉬움",
    active: "border-brick-blue bg-brick-blue text-white",
    idle: "border-brick-blue/40 text-brick-blue",
  },
];

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${Math.max(1, Math.round(minutes))}분`;
  if (minutes < 2880) return `${Math.round(minutes / 60)}시간`;
  return `${Math.round(minutes / 1440)}일`;
}

function Feedback({
  question,
  result,
  onNext,
}: {
  question: Question;
  result: AnswerResult;
  onNext: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  // 안키식: 등급 버튼이 곧 "다음" — 자동 산출 등급과 다르면 재평가 후 진행
  async function pick(rating: number) {
    if (submitting) return;
    setSubmitting(true);
    if (rating !== result.rating_applied) {
      await studyApi.rate(question.card_id, rating).catch(() => undefined);
    }
    onNext();
  }

  return (
    <div
      className={`mt-4 max-w-xl rounded-lg border-2 p-4 ${
        result.correct
          ? "border-brick-green bg-brick-green/10"
          : "border-brick-red bg-brick-red/10"
      }`}
    >
      <p className="font-bold">
        {result.correct ? "[O] 정답!" : "[X] 오답 — 세션 끝에 다시 나와요"}
      </p>
      <p className="mt-2 text-lg">{result.correct_answer}</p>
      <p className="text-sm opacity-70">{result.explanation.ko}</p>
      {result.explanation.thinking_ko && (
        <p className="text-sm text-brick-blue">
          ({result.explanation.thinking_ko})
        </p>
      )}
      {result.explanation.context_en && (
        <p className="mt-1 text-xs opacity-50">
          &quot;{result.explanation.context_en}&quot;
        </p>
      )}

      <p className="mt-4 text-xs opacity-60">
        기억 상태를 선택하면 다음 복습이 그 간격으로 예약됩니다 (안키 방식)
      </p>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {RATING_BUTTONS.map((btn) => {
          const isAuto = btn.rating === result.rating_applied;
          const minutes = result.interval_previews?.[String(btn.rating)];
          return (
            <button
              key={btn.rating}
              type="button"
              disabled={submitting}
              onClick={() => pick(btn.rating)}
              className={`flex min-h-14 flex-col items-center justify-center rounded-md border-2 bg-white font-bold transition hover:-translate-y-0.5 disabled:opacity-50 ${
                isAuto ? btn.active : btn.idle
              }`}
            >
              <span>{btn.label}</span>
              {minutes != null && (
                <span className={`text-xs font-normal ${isAuto ? "" : "opacity-60"}`}>
                  {formatInterval(minutes)}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

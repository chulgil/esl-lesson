"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { InsightSheet } from "@/components/study/InsightSheet";
import { SegmentPlayer } from "@/components/media/SegmentPlayer";
import { SpectateHost } from "@/components/study/SpectateHost";
import { studyApi, type AnswerResult, type Question } from "@/lib/study-api";

type Phase = "loading" | "empty" | "question" | "feedback" | "done";

const STUDY_LEVELS = [
  { level: 1, name: "입문", desc: "단어" },
  { level: 2, name: "초급", desc: "단어+숙어" },
  { level: 3, name: "중급", desc: "+패턴" },
  { level: 4, name: "고급", desc: "+문장(타이핑)" },
];

export default function StudyPage() {
  return (
    // useSearchParams 는 Suspense 경계 필요 (Next.js — watch 페이지와 동일 패턴)
    <Suspense>
      <StudySessionInner />
    </Suspense>
  );
}

function StudySessionInner() {
  // ?content=ID — 덱(콘텐츠) 한정 학습, 없으면 전체 (docs/specs/study-decks.md)
  const params = useSearchParams();
  const contentParam = params.get("content");
  const contentId = contentParam ? Number(contentParam) : undefined;

  const [queue, setQueue] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [hintDelay, setHintDelay] = useState(0);
  const [studyLevel, setStudyLevel] = useState(2);
  const [showSettings, setShowSettings] = useState(false);
  const [deckTitle, setDeckTitle] = useState<string | null>(null);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    studyApi
      .queue(contentId)
      .then((res) => {
        setQueue(res.questions);
        setHintDelay(res.hint_delay_seconds ?? 0);
        setDeckTitle(res.deck?.title ?? null);
        setPhase(res.questions.length ? "question" : "empty");
        startedAt.current = Date.now();
      })
      .catch((e) => setError(e.message));
    studyApi
      .getSettings()
      .then((s) => setStudyLevel(s.study_level))
      .catch(() => undefined);
  }, [contentId]);

  const question = queue[idx];

  // 문제 풀이 중에는 모바일 하단 탭바·마스코트 숨김 — 게임과 동일한 집중 모드 (이탈은 X 버튼으로)
  useEffect(() => {
    const active = phase === "question" || phase === "feedback";
    document.body.classList.toggle("game-focus", active);
    return () => document.body.classList.remove("game-focus");
  }, [phase]);

  // 관전자에게 릴레이할 화면 상태 — 수락된 관전자만 수신 (study-spectate.md)
  const spectateSnapshot =
    phase === "question" || phase === "feedback"
      ? {
          phase,
          index: Math.min(idx + 1, queue.length),
          total: queue.length,
          correct_count: correctCount,
          prompt: question?.prompt ?? question?.prompt_ko ?? "",
          prompt_ko:
            question?.quiz_mode === "cloze" ? question?.prompt_ko : undefined,
          template: question?.template,
          choices: question?.choices,
          result:
            phase === "feedback" && result
              ? {
                  correct: result.correct,
                  correct_answer: result.correct_answer,
                }
              : undefined,
        }
      : phase === "done"
        ? {
            phase: "done",
            total: queue.length,
            correct_count: correctCount,
            answered_count: answeredCount,
          }
        : null;

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
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-5 sm:px-16 sm:py-10">
      <header className="mb-4 flex items-center gap-3 sm:mb-6 sm:gap-4">
        <Link
          href="/study"
          aria-label="학습 종료하고 학습 홈으로"
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
        {/* 모바일 좁은 헤더에서 글자 단위 줄바꿈 방지 — 축소 폰트 + nowrap.
            덱 한정 학습이면 덱(콘텐츠) 이름 표기 — 긴 제목은 말줄임 */}
        <h1
          className={`font-hand text-xl font-bold whitespace-nowrap sm:text-3xl ${
            deckTitle ? "max-w-[38vw] truncate sm:max-w-sm" : ""
          }`}
        >
          <span className="hl">{deckTitle ?? "오늘의 학습"}</span>
        </h1>
        {(phase === "question" || phase === "feedback") && (
          <span className="ml-auto rounded-full bg-white px-3 py-1 text-sm font-bold whitespace-nowrap shadow-sm">
            {Math.min(idx + 1, queue.length)}/{queue.length}
          </span>
        )}
        <SpectateHost snapshot={spectateSnapshot} />
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
        <div className="mb-6 flex max-w-xl flex-col gap-4 rounded-lg border-2 border-ink/15 bg-white p-4 text-sm">
          <div>
            <p className="mb-2 font-bold">학습 난이도</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {STUDY_LEVELS.map((lv) => (
                <button
                  key={lv.level}
                  type="button"
                  onClick={() => setStudyLevel(lv.level)}
                  className={`flex flex-col items-start rounded-md border-2 px-3 py-2 text-left transition ${
                    studyLevel === lv.level
                      ? "border-brick-green bg-brick-green/10 font-bold"
                      : "border-ink/15 hover:border-ink/30"
                  }`}
                >
                  <span>{lv.name}</span>
                  <span className="text-xs font-normal opacity-60">
                    {lv.desc}
                  </span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs opacity-60">
              낮을수록 단어·숙어 위주의 보기 선택 문제로 시작해요. 문장 직접
              입력(타이핑)은 고급부터.
            </p>
          </div>
          <label className="flex items-center gap-2 font-bold">
            힌트까지 대기(초)
            <input
              type="number"
              min={0}
              max={120}
              value={hintDelay}
              onChange={(e) =>
                setHintDelay(Math.max(0, Number(e.target.value)))
              }
              className="w-20 rounded border-2 border-ink/20 px-2 py-1.5"
            />
            <span className="text-xs font-normal opacity-60">
              무응답이 이 시간을 넘으면 다음 한 단어를 힌트로 보여줘요 (0=끄기)
            </span>
          </label>
          <button
            type="button"
            onClick={() => {
              studyApi
                .patchSettings({
                  hint_delay_seconds: hintDelay,
                  study_level: studyLevel,
                })
                .catch(() => undefined);
              setShowSettings(false);
              window.location.reload();
            }}
            className="min-h-11 self-start rounded-md bg-brick-green px-4 py-2 font-bold text-brick-label transition-colors hover:bg-brick-green/85"
          >
            저장하고 새 난이도로 학습
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
            <Brick color="yellow" href="/study/network">
              어휘망 보기
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
  // 힌트: hintDelay 초 동안 무응답이면 힌트를 켠다. 켜진 뒤에는 시간이 아니라
  // "입력 진행"에 따라 다음 한 단어만 노출한다 (2026-07-11 사용자 피드백).
  const [hintOn, setHintOn] = useState(false);
  useEffect(() => {
    setHintOn(false);
    if (!hintDelay || disabled || !question.hint_answer) return;
    const timer = setTimeout(() => setHintOn(true), hintDelay * 1000);
    return () => clearTimeout(timer);
  }, [hintDelay, disabled, question.hint_answer, question.card_id]);

  // 선다는 정답 보기 하나만 강조(순서 개념 없음)
  const choiceHighlight =
    hintOn && question.hint_answer ? question.hint_answer : null;

  return (
    <div className="max-w-xl -rotate-[0.4deg] rounded-lg border-2 border-ink/10 bg-white p-6 shadow-md">
      <p className="mb-1 text-xs opacity-50">레벨 {question.level}</p>
      {(question.quiz_mode === "choice_en2ko" ||
        question.quiz_mode === "choice_ko2en" ||
        question.quiz_mode === "cloze") && (
        <ChoiceQuiz
          prompt={question.prompt!}
          sub={
            question.quiz_mode === "cloze"
              ? (question.prompt_ko ?? undefined)
              : undefined
          }
          question={question}
          disabled={disabled}
          highlight={choiceHighlight}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "pattern" && (
        <PatternQuiz
          question={question}
          disabled={disabled}
          hintOn={hintOn}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "compose" && (
        <ComposeQuiz
          question={question}
          disabled={disabled}
          hintOn={hintOn}
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
      {sub && (
        // 빈칸(___)이 무슨 뜻인지 명시 — 어느 부분인지 혼동 방지 (2026-07-14)
        <p className="mt-1 text-sm">
          빈칸(___)의 뜻: <span className="hl font-bold">{sub}</span>
        </p>
      )}
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
  hintOn,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintOn: boolean;
  onSubmit: (answer: string) => void;
}) {
  const [picked, setPicked] = useState<number[]>([]);
  const chips = question.chips ?? [];

  // 진행형 힌트: 지금까지 고른 칩 다음에 올 "한 단어"만 강조 (2026-07-11 피드백)
  const expected = (question.hint_answer ?? "").split(/\s+/).filter(Boolean);
  const nextWord = hintOn ? expected[picked.length] : undefined;

  return (
    <div>
      <p className="text-lg font-bold">{question.prompt_ko}</p>
      <p className="mt-1 font-mono text-sm opacity-60">{question.template}</p>
      {question.blank_ko && question.blank_ko !== question.prompt_ko && (
        // 밑줄(___) 부분이 한글 해석의 어디인지 강조 (2026-07-14 피드백)
        <p className="mt-1 text-sm">
          밑줄(___) 부분:{" "}
          <span className="hl font-bold">{question.blank_ko}</span>
        </p>
      )}
      <div className="mt-4 min-h-11 rounded border-2 border-dashed border-ink/20 bg-paper p-2">
        {picked.map((chipIdx, i) => (
          <button
            key={`${chipIdx}-${i}`}
            type="button"
            disabled={disabled}
            onClick={() => setPicked((p) => p.filter((_, j) => j !== i))}
            className="mb-1 mr-1 min-h-10 rounded-md bg-brick-blue px-3 py-1 text-sm font-bold text-white transition-colors hover:bg-brick-blue/80"
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
              className={`min-h-10 rounded-md border-2 px-3 py-1 text-sm transition hover:border-brick-blue active:scale-95 ${
                nextWord && chip === nextWord
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
  hintOn,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintOn: boolean;
  onSubmit: (answer: string) => void;
}) {
  const [text, setText] = useState("");

  // 진행형 힌트: 내가 지금까지 맞게 친 단어 다음의 "한 단어"만 노출 (2026-07-11 피드백)
  const expected = (question.hint_answer ?? "").split(/\s+/).filter(Boolean);
  const typed = text.trim().split(/\s+/).filter(Boolean);
  let correctCount = 0;
  while (
    correctCount < typed.length &&
    correctCount < expected.length &&
    typed[correctCount].toLowerCase().replace(/[^a-z']/g, "") ===
      expected[correctCount].toLowerCase().replace(/[^a-z']/g, "")
  ) {
    correctCount += 1;
  }
  const nextWord = hintOn ? expected[correctCount] : undefined;

  return (
    <div>
      <p className="text-lg font-bold">{question.prompt_ko}</p>
      {question.hint_thinking && (
        <p className="mt-1 text-sm text-brick-blue">
          ({question.hint_thinking})
        </p>
      )}
      {nextWord && (
        <p className="mt-2 text-sm">
          다음 단어 힌트: <span className="hl font-bold">{nextWord}</span>
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

// 정답일 때만 노출하는 3등급 (안키 Hard/Good/Easy). 오답은 자동 Again → 단일 버튼.
const RATING_BUTTONS: {
  rating: number;
  label: string;
  active: string;
  idle: string;
}[] = [
  {
    rating: 2,
    label: "어려움",
    active: "border-brick-yellow bg-brick-yellow text-ink",
    idle: "border-brick-yellow/60 bg-white text-ink",
  },
  {
    rating: 3,
    label: "알맞음",
    active: "border-brick-green bg-brick-green text-white",
    idle: "border-brick-green/40 bg-white text-brick-green",
  },
  {
    rating: 4,
    label: "쉬움",
    active: "border-brick-blue bg-brick-blue text-white",
    idle: "border-brick-blue/40 bg-white text-brick-blue",
  },
];

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${Math.max(1, Math.round(minutes))}분 뒤`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}시간 뒤`;
  return `${Math.round(minutes / 1440)}일 뒤`;
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
  const [showInsight, setShowInsight] = useState(false);
  const [closeAdded, setCloseAdded] = useState(false);

  // 헷갈린 유사단어를 원탭으로 학습 큐에 추가 — 어휘망 확장 루프 (P3)
  async function addCloseWord() {
    if (!result.close_match || closeAdded) return;
    try {
      await studyApi.addCard(result.close_match.item_id);
      setCloseAdded(true);
    } catch {
      // 실패는 조용히 — 다음 기회에 다시 시도 가능
    }
  }

  // 인사이트는 항목의 영어 표현 기준 (en2ko 는 문제가 영어, 그 외는 정답이 영어)
  const enWord =
    question.quiz_mode === "choice_en2ko"
      ? (question.prompt ?? result.correct_answer)
      : result.correct_answer;

  // 안키식: 등급 버튼이 곧 "다음" — 자동 산출 등급과 다르면 재평가 후 진행
  async function pick(rating: number) {
    if (submitting) return;
    setSubmitting(true);
    if (rating !== result.rating_applied) {
      await studyApi.rate(question.card_id, rating).catch(() => undefined);
    }
    onNext();
  }

  const againMin = result.interval_previews?.["1"];

  return (
    <div
      className={`mt-4 max-w-xl rounded-lg border-2 p-4 ${
        result.correct
          ? "border-brick-green bg-brick-green/10"
          : "border-brick-red bg-brick-red/10"
      }`}
    >
      <p className="font-bold">
        {result.correct ? "[O] 정답!" : "[X] 오답 — 곧 다시 나와요"}
      </p>
      <div className="mt-2 flex items-center gap-3">
        <p className="text-lg">{result.correct_answer}</p>
        {question.level <= 2 && (
          // 단어/숙어만 인사이트 제공 (패턴/문장은 문장 단위라 제외 — P1)
          <button
            type="button"
            onClick={() => setShowInsight(true)}
            className="min-h-10 cursor-pointer rounded-full border-2 border-brick-blue/40 bg-white px-3.5 py-1 text-xs font-bold text-brick-blue transition hover:border-brick-blue active:scale-95"
          >
            단어 정보
          </button>
        )}
      </div>
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

      {!result.correct && result.close_match && (
        // "아깝다" — 유사단어와 헷갈린 오답은 좌절 대신 비교 학습 기회로
        <div className="mt-3 rounded-md border-2 border-brick-yellow bg-highlight/30 p-3">
          <p className="text-sm font-bold">아깝다! 비슷한 단어와 헷갈렸어요</p>
          <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs opacity-50">내가 고른 답</p>
              <p className="font-bold">{result.close_match.en_text}</p>
              <p className="opacity-70">{result.close_match.ko_text}</p>
            </div>
            <div>
              <p className="text-xs opacity-50">정답 단어</p>
              <p className="font-bold">{enWord}</p>
              <p className="opacity-70">{result.explanation.ko}</p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {question.level <= 2 && (
              <button
                type="button"
                onClick={() => setShowInsight(true)}
                className="min-h-10 cursor-pointer rounded-full border-2 border-brick-yellow bg-white px-3.5 py-1 text-xs font-bold transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95"
              >
                두 단어 차이 자세히 보기
              </button>
            )}
            <button
              type="button"
              disabled={closeAdded}
              onClick={addCloseWord}
              className="min-h-10 cursor-pointer rounded-full border-2 border-brick-green/60 bg-white px-3.5 py-1 text-xs font-bold text-brick-green transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95 disabled:opacity-60"
            >
              {closeAdded
                ? "학습 큐에 추가됨!"
                : `"${result.close_match.en_text}" 도 학습에 추가`}
            </button>
          </div>
        </div>
      )}

      {result.correct ? (
        <>
          <p className="mt-4 text-xs opacity-60">
            얼마나 쉬웠나요? 선택하면 그 시점에 다시 복습해요 (새 단어는 짧게
            반복하며 익혀요)
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {RATING_BUTTONS.map((btn) => {
              const isAuto = btn.rating === result.rating_applied;
              const minutes = result.interval_previews?.[String(btn.rating)];
              return (
                <button
                  key={btn.rating}
                  type="button"
                  disabled={submitting}
                  onClick={() => pick(btn.rating)}
                  // bg-white 를 베이스에 두면 active 의 bg-brick-* 와 충돌해
                  // (생성 CSS 순서상 bg-white 승리) 흰 바탕+흰 글씨가 됨 → idle 에만 둔다
                  className={`flex min-h-16 flex-col items-center justify-center rounded-md border-2 font-bold transition hover:-translate-y-0.5 disabled:opacity-50 ${
                    isAuto ? btn.active : btn.idle
                  }`}
                >
                  <span>{btn.label}</span>
                  {minutes != null && (
                    <span
                      className={`text-xs font-normal ${isAuto ? "" : "opacity-60"}`}
                    >
                      {formatInterval(minutes)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      ) : (
        // 오답: 등급 선택 없이 "다시"만 (안키 — 틀리면 Again)
        <div className="mt-4">
          <button
            type="button"
            disabled={submitting}
            onClick={() => pick(1)}
            className="flex min-h-14 w-full flex-col items-center justify-center rounded-md border-2 border-brick-red bg-brick-red font-bold text-white transition hover:-translate-y-0.5 disabled:opacity-50"
          >
            <span>다시 학습</span>
            {againMin != null && (
              <span className="text-xs font-normal opacity-90">
                {formatInterval(againMin)}
              </span>
            )}
          </button>
        </div>
      )}

      {showInsight && (
        <InsightSheet
          itemId={question.item_id}
          word={enWord}
          onClose={() => setShowInsight(false)}
        />
      )}
    </div>
  );
}

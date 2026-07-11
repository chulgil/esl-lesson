"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
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
  const startedAt = useRef(Date.now());

  useEffect(() => {
    studyApi
      .queue()
      .then((res) => {
        setQueue(res.questions);
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
        <Link href="/" className="text-sm opacity-60 hover:underline">
          &lt; 홈
        </Link>
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">오늘의 학습</span>
        </h1>
      </header>

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
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  onSubmit: (answer: string) => void;
}) {
  return (
    <div className="max-w-xl -rotate-[0.4deg] rounded-lg border-2 border-ink/10 bg-white p-6 shadow-md">
      <p className="mb-1 text-xs opacity-50">레벨 {question.level}</p>
      {question.quiz_mode === "choice_en2ko" && (
        <ChoiceQuiz
          prompt={question.prompt!}
          question={question}
          disabled={disabled}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "choice_ko2en" && (
        <ChoiceQuiz
          prompt={question.prompt!}
          question={question}
          disabled={disabled}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "cloze" && (
        <ChoiceQuiz
          prompt={question.prompt!}
          sub={question.prompt_ko ?? undefined}
          question={question}
          disabled={disabled}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "pattern" && (
        <PatternQuiz
          question={question}
          disabled={disabled}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "compose" && (
        <ComposeQuiz
          question={question}
          disabled={disabled}
          onSubmit={onSubmit}
        />
      )}
    </div>
  );
}

function ChoiceQuiz({
  prompt,
  sub,
  question,
  disabled,
  onSubmit,
}: {
  prompt: string;
  sub?: string;
  question: Question;
  disabled: boolean;
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
            className="min-h-11 rounded-md border-2 border-ink/15 bg-paper px-4 py-2 text-left font-medium transition hover:-translate-y-0.5 hover:border-brick-blue disabled:opacity-50"
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
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  onSubmit: (answer: string) => void;
}) {
  const [picked, setPicked] = useState<number[]>([]);
  const chips = question.chips ?? [];

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
              className="rounded border-2 border-ink/15 bg-white px-2 py-1 text-sm hover:border-brick-blue"
            >
              {chip}
            </button>
          ),
        )}
      </div>
      <div className="mt-4">
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
      </div>
    </div>
  );
}

function ComposeQuiz({
  question,
  disabled,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
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
      <div className="mt-3">
        <Brick
          color="green"
          onClick={disabled || !text.trim() ? undefined : () => onSubmit(text)}
        >
          제출
        </Brick>
      </div>
    </div>
  );
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
  const [rated, setRated] = useState(false);
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

      {question.quiz_mode === "compose" && result.correct && !rated && (
        <div className="mt-3 flex gap-2 text-xs">
          <span className="opacity-60">체감 난이도:</span>
          {[
            { label: "어려웠어요", rating: 2 },
            { label: "괜찮아요", rating: 3 },
            { label: "쉬웠어요", rating: 4 },
          ].map((option) => (
            <button
              key={option.rating}
              type="button"
              onClick={() => {
                studyApi
                  .rate(question.card_id, option.rating)
                  .catch(() => undefined);
                setRated(true);
              }}
              className="rounded border border-ink/20 bg-white px-2 py-1 hover:border-brick-blue"
            >
              {option.label}
            </button>
          ))}
        </div>
      )}

      <div className="mt-4">
        <Brick color={result.correct ? "green" : "yellow"} onClick={onNext}>
          다음
        </Brick>
      </div>
    </div>
  );
}

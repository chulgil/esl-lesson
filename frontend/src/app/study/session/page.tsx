"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { SegmentPlayer } from "@/components/media/SegmentPlayer";
import { SessionDone } from "@/components/study/SessionDone";
import { SessionFeedback } from "@/components/study/SessionFeedback";
import { SpectateHost } from "@/components/study/SpectateHost";
import { studyApi, type AnswerResult, type Question } from "@/lib/study-api";
import { useSurfaceSkin } from "@/lib/theme-surfaces";

type Phase = "loading" | "empty" | "question" | "feedback" | "done";

// --- 세션 이어가기 스냅샷 (localStorage) ---
// 답은 제출 즉시 서버에 저장되지만, "몇 번째까지 풀었는지"의 세션 순서·진행
// 카운터는 클라이언트만 안다 — 나가기 후 재진입 시 남은 문항을 원래 순서로
// 복원해 초기화처럼 보이던 문제 해소 (2026-08-20 보고). 서버 큐가 정본이라
// 스냅샷의 문항 중 이미 답한 것(큐에 없음)은 자동 제외된다.

// 세션 종류(전체/덱/오답 정리)별 별도 키 — 하나의 키를 공유하면 덱 세션이
// 일반 세션의 이어가기를 덮어쓴다 (2026-08-20 전수 점검)
function snapshotKey(content: number | undefined, weak: boolean): string {
  return `els-study-session:${content ?? "all"}:${weak ? "weak" : "std"}`;
}

interface SessionSnapshot {
  day: string;
  content: number | null;
  weak: boolean;
  order: number[];
  idx: number;
  answered: number;
  correct: number;
  longTerm: number;
}

function kstDay(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

function loadSessionSnapshot(
  content: number | undefined,
  weak: boolean,
): SessionSnapshot | null {
  try {
    const raw = window.localStorage.getItem(snapshotKey(content, weak));
    if (!raw) return null;
    const saved = JSON.parse(raw) as SessionSnapshot;
    if (
      saved.day !== kstDay() ||
      saved.content !== (content ?? null) ||
      saved.weak !== weak ||
      !Array.isArray(saved.order) ||
      saved.answered === 0 // 아무것도 안 풀었으면 새 세션과 동일
    ) {
      return null;
    }
    return saved;
  } catch {
    return null;
  }
}

function saveSessionSnapshot(snapshot: SessionSnapshot): void {
  try {
    window.localStorage.setItem(
      snapshotKey(snapshot.content ?? undefined, snapshot.weak),
      JSON.stringify(snapshot),
    );
  } catch {
    // 저장 불가(시크릿 모드 등) — 이어가기 없이 종전 동작
  }
}

function clearSessionSnapshot(
  content: number | undefined,
  weak: boolean,
): void {
  try {
    window.localStorage.removeItem(snapshotKey(content, weak));
  } catch {
    // noop
  }
}

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
  // ?mode=weak — 오답 정리: 최근 틀린 카드만 보충 학습 (docs/specs/learning.md)
  const params = useSearchParams();
  const contentParam = params.get("content");
  const contentId = contentParam ? Number(contentParam) : undefined;
  const weakMode = params.get("mode") === "weak";

  const [queue, setQueue] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [result, setResult] = useState<AnswerResult | null>(null);
  // 정답 카드 표시 여부 — false 면 제출된 문제를 다시 본다 (문제↔정답 왕복)
  const [showFeedback, setShowFeedback] = useState(true);
  // 오늘 이미 답한 수 — 재진입 시 "이어가기" 안내 (2026-08-20 저장 오해 해소)
  const [doneToday, setDoneToday] = useState(0);
  // 이 세션에서 재진입 전에 이미 답한 수 — 진행바·카운터를 이어붙인다
  // (2026-08-20 보고: 나가기 후 재진입이 1/N 부터 다시 시작돼 초기화로 보임)
  const [prevDone, setPrevDone] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  // 이번 세션에서 장기 기억으로 굳은 카드 수 — 완료 화면 요약 (피크엔드)
  const [longTermCount, setLongTermCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [hintDelay, setHintDelay] = useState(0);
  const [studyLevel, setStudyLevel] = useState(2);
  const [showSettings, setShowSettings] = useState(false);
  const [deckTitle, setDeckTitle] = useState<string | null>(null);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    studyApi
      .queue(contentId, weakMode ? "weak" : undefined)
      .then((res) => {
        setHintDelay(res.hint_delay_seconds ?? 0);
        setDeckTitle(res.deck?.title ?? null);
        setDoneToday(res.done_today ?? 0);
        // 세션 카운터 리셋 — 완료 화면에서 오답 정리로 넘어올 때 이전 세션
        // 수치가 남지 않도록 (done -> ?mode=weak 전환이 정식 흐름이 됨)
        setIdx(0);
        setResult(null);
        // 세션 이어가기 — 같은 날 저장된 스냅샷이 있으면 남은 문항을 원래
        // 순서로 복원하고 진행바를 이어붙인다 (2026-08-20 초기화 보고)
        const saved = loadSessionSnapshot(contentId, weakMode);
        if (saved && res.questions.length) {
          const byId = new Map(res.questions.map((q) => [q.card_id, q]));
          const resumed: Question[] = [];
          for (const cardId of saved.order.slice(saved.idx)) {
            const q = byId.get(cardId);
            if (q) {
              resumed.push(q);
              byId.delete(cardId);
            }
          }
          const fresh = res.questions.filter((q) => byId.has(q.card_id));
          setQueue([...resumed, ...fresh]);
          setPrevDone(saved.answered);
          setCorrectCount(saved.correct);
          setAnsweredCount(saved.answered);
          setLongTermCount(saved.longTerm);
          setPhase(resumed.length + fresh.length ? "question" : "empty");
        } else {
          setQueue(res.questions);
          setPrevDone(0);
          setCorrectCount(0);
          setAnsweredCount(0);
          setLongTermCount(0);
          setPhase(res.questions.length ? "question" : "empty");
        }
        startedAt.current = Date.now();
      })
      .catch((e) => setError(e.message));
    studyApi
      .getSettings()
      .then((s) => setStudyLevel(s.study_level))
      .catch(() => undefined);
  }, [contentId, weakMode]);

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
      if (res.long_term_reached) {
        setLongTermCount((n) => n + 1);
      }
      if (res.correct) {
        setCorrectCount((n) => n + 1);
      } else {
        // 오답은 세션 끝에 재출제 (docs/specs/learning.md)
        setQueue((q) => [...q, question]);
      }
      setShowFeedback(true); // 새 채점마다 정답 카드가 앞으로
      setPhase("feedback");
    } catch (e) {
      setError(e instanceof Error ? e.message : "제출 실패");
    }
  }

  // 진행 스냅샷 저장 — 제출·이동마다 갱신 (이어가기 재료)
  useEffect(() => {
    if ((phase !== "question" && phase !== "feedback") || queue.length === 0) {
      return;
    }
    saveSessionSnapshot({
      day: kstDay(),
      content: contentId ?? null,
      weak: weakMode,
      order: queue.map((q) => q.card_id),
      idx,
      answered: answeredCount,
      correct: correctCount,
      longTerm: longTermCount,
    });
  }, [
    phase,
    queue,
    idx,
    answeredCount,
    correctCount,
    longTermCount,
    contentId,
    weakMode,
  ]);

  function next() {
    const nextIdx = idx + 1;
    if (nextIdx >= queue.length) {
      clearSessionSnapshot(contentId, weakMode); // 세션 완주 — 다음 진입은 새 세션
      setPhase("done");
    } else {
      setIdx(nextIdx);
      setResult(null);
      setShowFeedback(true);
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
          <span className="hl">
            {weakMode ? "오답 정리" : (deckTitle ?? "오늘의 학습")}
          </span>
        </h1>
        {(phase === "question" || phase === "feedback") && (
          <span className="ml-auto rounded-full bg-white px-3 py-1 text-sm font-bold whitespace-nowrap shadow-sm">
            {/* 재진입 시 이전 진행(prevDone)을 이어붙인 연속 카운터 */}
            {Math.min(prevDone + idx + 1, prevDone + queue.length)}/
            {prevDone + queue.length}
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
                .then(() => {
                  setShowSettings(false);
                  window.location.reload();
                })
                .catch(() =>
                  setError("설정을 저장하지 못했어요 — 다시 시도해 주세요"),
                );
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

      {phase === "empty" && weakMode && (
        <div className="flex max-w-md flex-col items-start gap-3">
          <p className="font-bold">정리할 오답이 없어요</p>
          <p className="text-sm opacity-70">
            최근 7일 동안 틀린 카드가 없다는 뜻이에요 — 아주 잘하고 있어요!
          </p>
          <Brick color="green" href="/study">
            학습 홈으로
          </Brick>
        </div>
      )}

      {phase === "empty" && !weakMode && (
        <div className="flex max-w-md flex-col items-start gap-3">
          <p className="font-bold">오늘 만날 카드가 없어요</p>
          {/* 왜 비었는지 안내 — 담기빼기 후 "없다"만 뜨면 버그로 보인다 (2026-07-30) */}
          <p className="text-sm opacity-70">
            담은 콘텐츠의 카드를 모두 만났고 다음 복습일도 아직이에요. 새
            콘텐츠를 담거나, 예전에 뺀 콘텐츠를 다시 담으면 그 카드들이 진도
            그대로 돌아와요.
          </p>
          <Brick color="blue" href="/library">
            라이브러리에서 콘텐츠 담기
          </Brick>
        </div>
      )}

      {(phase === "question" || phase === "feedback") && question && (
        <>
          <ProgressBricks
            total={prevDone + queue.length}
            done={prevDone + idx}
          />
          {/* 이어가기 안내 — 답은 제출 즉시 저장되므로 나가도 진행이 사라지지
              않는다. 재진입 카운터 리셋이 "처음부터"로 보이던 오해 해소
              (2026-08-20 보고) */}
          {(prevDone > 0 || doneToday > 0) &&
            idx === 0 &&
            phase === "question" && (
              <p className="mb-3 max-w-2xl rounded-md bg-brick-green/10 px-3 py-1.5 text-xs font-bold text-brick-green">
                {prevDone > 0
                  ? `${prevDone}번째까지 푼 세션을 이어서 진행해요 (답은 제출 즉시 저장돼요)`
                  : `오늘 이미 ${doneToday}개를 끝냈어요 — 이어서 진행해요 (답은 제출 즉시 저장돼요)`}
              </p>
            )}
          {/* 카드 플립 — 채점하면 카드가 뒤집히며 정답 면이 나온다 (플래시카드
              은유, 2026-08-20 요청). 앞면=문제, 뒷면=정답(180도 선회전 +
              backface 숨김). 문제↔정답 왕복은 뒤집기 방향만 바뀐다.
              reduced-motion 은 전환 없이 즉시 교체 */}
          <div className="grid max-w-2xl [perspective:1400px]">
            <div
              className={`col-start-1 row-start-1 grid transition-transform duration-500 [transform-style:preserve-3d] motion-reduce:transition-none ${
                phase === "feedback" && showFeedback
                  ? "[transform:rotateY(180deg)]"
                  : ""
              }`}
            >
              <div
                className="col-start-1 row-start-1 [-webkit-backface-visibility:hidden] [backface-visibility:hidden]"
                // inert — 숨은 면이 Tab 순서·스크린리더에 남지 않게 (2026-08-20 점검)
                inert={phase === "feedback" && showFeedback}
              >
                <QuestionCard
                  key={`${question.card_id}-${idx}`}
                  question={question}
                  disabled={phase === "feedback"}
                  hintDelay={hintDelay}
                  onSubmit={submit}
                />
              </div>
              {phase === "feedback" && result && (
                <div
                  className="col-start-1 row-start-1 [-webkit-backface-visibility:hidden] [backface-visibility:hidden] [transform:rotateY(180deg)]"
                  inert={!showFeedback}
                >
                  <SessionFeedback
                    question={question}
                    result={result}
                    onNext={next}
                  />
                </div>
              )}
            </div>
          </div>
          {/* 문제↔정답 왕복 — 뒤로 가면 제출된 문제를 다시 보고, 화살표로 복귀 */}
          {phase === "feedback" && (
            <div className="mt-3 flex max-w-2xl items-center justify-between gap-3">
              {showFeedback ? (
                <button
                  type="button"
                  onClick={() => setShowFeedback(false)}
                  className="inline-flex min-h-10 items-center gap-1 rounded-full border-2 border-ink/20 bg-white px-3 text-sm font-bold opacity-80 transition hover:border-ink/50 hover:opacity-100"
                >
                  ← 문제 다시 보기
                </button>
              ) : (
                <>
                  <span className="self-center text-xs opacity-60">
                    답은 이미 제출됐어요 — 문제만 다시 보는 중
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowFeedback(true)}
                    className="inline-flex min-h-10 items-center gap-1 rounded-full border-2 border-brick-blue/60 bg-white px-3 text-sm font-bold text-brick-blue transition hover:-translate-y-0.5 hover:border-brick-blue"
                  >
                    정답 확인 →
                  </button>
                </>
              )}
            </div>
          )}
        </>
      )}

      {phase === "done" && (
        <SessionDone
          weakMode={weakMode}
          answeredCount={answeredCount}
          correctCount={correctCount}
          longTermCount={longTermCount}
          onRestart={() => window.location.reload()}
        />
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
  // 힌트 정책 — 카드 숙련도로 분기 (2026-08-05 사용자 정책):
  // · 처음 학습·직전 등급 다시/어려움/알맞음(1~3): 첫 무활동 지연 후 켜지면
  //   래치 유지 — 입력 진행에 따라 다음 단어를 순차로 안내 (헤매는 카드는
  //   끊김 없이 이끈다)
  // · 직전 등급 쉬움(4)만: 단계마다 무활동 시간차 — 활동하면 힌트를 끄고
  //   타이머 리셋, 다시 지연을 기다려야 다음 한 단어 (아는 카드는 스스로
  //   떠올릴 시간을 준다)
  const paced = question.last_rating === 4;
  const [hintOn, setHintOn] = useState(false);
  const hintOnRef = useRef(false);
  const [activityTick, setActivityTick] = useState(0);
  const noteActivity = useCallback(() => setActivityTick((t) => t + 1), []);
  useEffect(() => {
    if (!hintDelay || disabled || !question.hint_answer) return;
    if (!paced && hintOnRef.current) return; // 순차 모드: 한 번 켜지면 유지
    hintOnRef.current = false;
    setHintOn(false);
    const timer = setTimeout(() => {
      hintOnRef.current = true;
      setHintOn(true);
    }, hintDelay * 1000);
    return () => clearTimeout(timer);
  }, [
    hintDelay,
    disabled,
    paced,
    question.hint_answer,
    question.card_id,
    activityTick,
  ]);

  // 선다는 정답 보기 하나만 강조(순서 개념 없음)
  const choiceHighlight =
    hintOn && question.hint_answer ? question.hint_answer : null;

  // 학습 카드도 테마 컨셉을 따른다 — 시험지와 동일 표면 스킨 (theme-surfaces)
  const skin = useSurfaceSkin();
  return (
    <div className={`max-w-xl -rotate-[0.4deg] p-6 shadow-md ${skin.section}`}>
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
          onActivity={noteActivity}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "compose" && (
        <ComposeQuiz
          question={question}
          disabled={disabled}
          hintOn={hintOn}
          onActivity={noteActivity}
          onSubmit={onSubmit}
        />
      )}
      {question.quiz_mode === "sentence_assemble" && (
        <SentenceAssembleQuiz
          question={question}
          disabled={disabled}
          hintOn={hintOn}
          onActivity={noteActivity}
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
  const skin = useSurfaceSkin();
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
            className={`min-h-11 border-2 px-4 py-2 text-left font-medium transition hover:-translate-y-0.5 disabled:opacity-50 ${skin.radius} ${
              highlight === choice
                ? "border-brick-yellow bg-highlight/50 text-ink"
                : skin.choice
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
  onActivity,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintOn: boolean;
  onActivity: () => void;
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
            onClick={() => {
              setPicked((p) => p.filter((_, j) => j !== i));
              onActivity(); // 칩을 빼도 활동 — 힌트 타이머 리셋
            }}
            className="mb-1 mr-1 min-h-10 rounded-md bg-brick-blue px-3 py-1 text-sm font-bold text-brick-label transition-colors hover:bg-brick-blue/80"
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
              onClick={() => {
                setPicked((p) => [...p, chipIdx]);
                onActivity(); // 칩을 넣으면 힌트 타이머 리셋 (2026-08-05 보고)
              }}
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

/** 내가 쓰는 말 덱 전용 — 초·중급 카드는 문장 전체를 칩 조립으로 (레벨3
 *  패턴 조립과 동일 UI 계열, docs/specs/my-phrases.md 레벨별 학습카드).
 *  문제 = 내 원문, 칩 = 번역문 단어 + 오답 2~3개. 채점은 조립 결과를 그대로
 *  기존 sentence 채점 경로(정규화+Levenshtein)에 태운다. */
function SentenceAssembleQuiz({
  question,
  disabled,
  hintOn,
  onActivity,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintOn: boolean;
  onActivity: () => void;
  onSubmit: (answer: string) => void;
}) {
  const [picked, setPicked] = useState<number[]>([]);
  const chips = question.chips ?? [];

  // 진행형 힌트: 지금까지 고른 칩 다음에 올 "한 단어"만 강조 (패턴 조립과 동일)
  const expected = (question.hint_answer ?? "").split(/\s+/).filter(Boolean);
  const nextWord = hintOn ? expected[picked.length] : undefined;

  return (
    <div>
      <p className="text-lg font-bold">{question.prompt_ko}</p>
      <div className="mt-4 min-h-11 rounded border-2 border-dashed border-ink/20 bg-paper p-2">
        {picked.map((chipIdx, i) => (
          <button
            key={`${chipIdx}-${i}`}
            type="button"
            disabled={disabled}
            onClick={() => {
              setPicked((p) => p.filter((_, j) => j !== i));
              onActivity(); // 칩을 빼도 활동 — 힌트 타이머 리셋
            }}
            className="mb-1 mr-1 min-h-10 rounded-md bg-brick-blue px-3 py-1 text-sm font-bold text-brick-label transition-colors hover:bg-brick-blue/80"
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
              onClick={() => {
                setPicked((p) => [...p, chipIdx]);
                onActivity(); // 칩을 넣으면 힌트 타이머 리셋
              }}
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
  onActivity,
  onSubmit,
}: {
  question: Question;
  disabled: boolean;
  hintOn: boolean;
  onActivity: () => void;
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
        onChange={(e) => {
          setText(e.target.value);
          onActivity(); // 타이핑 중엔 힌트 보류 — 멈춘 뒤에만 다음 단어
        }}
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

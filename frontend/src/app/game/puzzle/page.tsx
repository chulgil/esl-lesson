"use client";

import { useCallback, useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { BackLink } from "@/components/nav/BackLink";

interface PuzzleState {
  available: boolean;
  day?: string;
  length?: number;
  max_tries?: number;
  guesses?: { word: string; marks: string[] }[];
  solved?: boolean;
  finished?: boolean;
  answer?: string | null;
  answer_ko?: string | null;
  hint_ko?: string | null;
}

type Mark = "g" | "y" | "x";

const HOWTO_KEY = "esl:puzzle:howto-seen";
const FLIP_MS = 250; // 타일당 뒤집기 스태거

const MARK_STYLE: Record<Mark, string> = {
  g: "border-brick-green bg-brick-green text-brick-label",
  y: "border-brick-yellow bg-brick-yellow text-ink",
  x: "border-ink/50 bg-ink/50 text-paper",
};

const KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];

/** 데일리 단어 퍼즐 — 하루 한 단어, 전원 동일 (docs/specs/daily-puzzle.md) */
export default function DailyPuzzlePage() {
  const [state, setState] = useState<PuzzleState | null>(null);
  const [input, setInput] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revealIdx, setRevealIdx] = useState<number | null>(null);
  const [shake, setShake] = useState(0);
  const [hintOpen, setHintOpen] = useState(false);
  const [howtoOpen, setHowtoOpen] = useState(false);

  const length = state?.length ?? 5;
  const maxTries = state?.max_tries ?? 6;
  const guesses = state?.guesses ?? [];
  const playing = Boolean(state?.available && !state?.finished);

  useEffect(() => {
    fetch("/api/game/puzzle", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : { available: false }))
      .then((s: PuzzleState) => {
        setState(s);
        if (s.available && !localStorage.getItem(HOWTO_KEY)) {
          setHowtoOpen(true);
        }
      })
      .catch(() => setState({ available: false }));
  }, []);

  // 플레이 중엔 마스코트·모바일 탭바 숨김 — 다른 게임과 동일, 키보드 공간 확보
  useEffect(() => {
    document.body.classList.toggle("game-focus", playing);
    return () => document.body.classList.remove("game-focus");
  }, [playing]);

  function closeHowto() {
    localStorage.setItem(HOWTO_KEY, "1");
    setHowtoOpen(false);
  }

  function rejectInput(message: string) {
    setNote(message);
    setShake((n) => n + 1);
  }

  const submit = useCallback(async () => {
    if (!state?.length || busy) return;
    const word = input.trim().toLowerCase();
    if (word.length !== state.length) {
      rejectInput(`${state.length}글자를 모두 채워주세요`);
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      const res = await fetch("/api/game/puzzle/guess", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word }),
      });
      if (res.status === 422) {
        rejectInput("영어 알파벳만 입력할 수 있어요");
      } else if (res.ok) {
        const next: PuzzleState = await res.json();
        setState(next);
        setRevealIdx((next.guesses?.length ?? 1) - 1);
        setInput("");
      } else {
        setNote("잠시 후 다시 시도해주세요");
      }
    } catch {
      setNote("잠시 후 다시 시도해주세요");
    }
    setBusy(false);
  }, [busy, input, state?.length]);

  const pressKey = useCallback(
    (key: string) => {
      if (!playing || busy) return;
      setNote(null);
      if (key === "enter") {
        void submit();
      } else if (key === "back") {
        setInput((prev) => prev.slice(0, -1));
      } else {
        setInput((prev) => (prev.length < length ? prev + key : prev));
      }
    },
    [playing, busy, length, submit],
  );

  // 물리 키보드도 동일하게 — 모달 열림 중엔 무시
  useEffect(() => {
    if (!playing || howtoOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Enter") pressKey("enter");
      else if (e.key === "Backspace") pressKey("back");
      else if (/^[a-zA-Z]$/.test(e.key)) pressKey(e.key.toLowerCase());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playing, howtoOpen, pressKey]);

  // 키보드 글자 상태 — 시도한 글자의 최고 등급 (g > y > x)
  const letterMarks: Record<string, Mark> = {};
  for (const g of guesses) {
    g.word.split("").forEach((ch, i) => {
      const mark = g.marks[i] as Mark;
      const prev = letterMarks[ch];
      if (!prev || mark === "g" || (mark === "y" && prev === "x")) {
        letterMarks[ch] = mark;
      }
    });
  }

  const gridStyle = {
    gridTemplateColumns: `repeat(${length}, minmax(0, 1fr))`,
    maxWidth: `${length * 3.9}rem`,
  };

  const solvedRow = state?.solved ? guesses.length - 1 : null;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-4 sm:px-10 sm:py-8">
      <header className="mb-3 flex flex-wrap items-center gap-3">
        <BackLink href="/game" label="게임" />
        <h1 className="font-hand text-2xl font-bold whitespace-nowrap sm:text-3xl">
          <span className="hl">데일리 단어 퍼즐</span>
        </h1>
        <button
          type="button"
          onClick={() => setHowtoOpen(true)}
          className="ml-auto rounded-full border-2 border-ink/20 bg-white px-3 py-1 text-sm font-bold transition hover:border-brick-blue"
        >
          게임 방법
        </button>
      </header>

      {!state && <p className="text-sm opacity-60">불러오는 중...</p>}
      {state && !state.available && (
        <p className="text-sm opacity-70">
          아직 퍼즐로 낼 단어가 부족해요 — 영상이 더 등록되면 열려요.
        </p>
      )}

      {state?.available && (
        <section className="mx-auto flex max-w-md flex-col items-center gap-4">
          <p className="text-sm opacity-70">
            오늘의 <b>{length}글자</b> 영어 단어 — {maxTries}번 안에 맞혀보세요!
          </p>

          {/* 보드 */}
          <div className="flex w-full flex-col items-center gap-1.5">
            {Array.from({ length: maxTries }, (_, row) => {
              const graded = guesses[row];
              if (graded) {
                const isReveal = row === revealIdx;
                const isSolvedRow = row === solvedRow;
                return (
                  <div
                    key={row}
                    className="grid w-full gap-1.5"
                    style={gridStyle}
                  >
                    {graded.word.split("").map((ch, i) => (
                      <span
                        key={i}
                        className={isSolvedRow && isReveal ? "tile-bounce" : ""}
                        style={
                          isSolvedRow && isReveal
                            ? {
                                animationDelay: `${length * FLIP_MS + i * 90}ms`,
                              }
                            : undefined
                        }
                      >
                        <span
                          className={`flex aspect-square w-full items-center justify-center rounded-md border-2 text-2xl font-bold uppercase sm:text-3xl ${
                            MARK_STYLE[graded.marks[i] as Mark]
                          } ${isReveal ? "tile-flip" : ""}`}
                          style={
                            isReveal
                              ? { animationDelay: `${i * FLIP_MS}ms` }
                              : undefined
                          }
                        >
                          {ch}
                        </span>
                      </span>
                    ))}
                  </div>
                );
              }
              if (row === guesses.length && playing) {
                // 입력 중인 행 — 타일에 바로 타이핑
                return (
                  <div
                    key={`${row}-${shake}`}
                    className={`grid w-full gap-1.5 ${shake ? "miss-shake" : ""}`}
                    style={gridStyle}
                  >
                    {Array.from({ length }, (_, i) => (
                      <span
                        key={i}
                        className={`flex aspect-square w-full items-center justify-center rounded-md border-2 text-2xl font-bold uppercase sm:text-3xl ${
                          input[i]
                            ? "word-pop border-ink/50 bg-white"
                            : "border-ink/20 bg-white/60"
                        }`}
                      >
                        {input[i] ?? ""}
                      </span>
                    ))}
                  </div>
                );
              }
              return (
                <div
                  key={row}
                  className="grid w-full gap-1.5"
                  style={gridStyle}
                >
                  {Array.from({ length }, (_, i) => (
                    <span
                      key={i}
                      className="aspect-square w-full rounded-md border-2 border-dashed border-ink/15"
                    />
                  ))}
                </div>
              );
            })}
          </div>

          {note && <p className="text-sm font-bold text-brick-red">{note}</p>}

          {/* 뜻 힌트 — 2번 시도부터 해금 */}
          {playing &&
            (state.hint_ko ? (
              hintOpen ? (
                <p className="word-pop rounded-full border-2 border-brick-blue/40 bg-brick-blue/10 px-4 py-1.5 text-sm font-bold">
                  힌트 — 뜻: {state.hint_ko}
                </p>
              ) : (
                <button
                  type="button"
                  onClick={() => setHintOpen(true)}
                  className="rounded-full border-2 border-brick-blue bg-white px-4 py-1.5 text-sm font-bold transition hover:-translate-y-0.5"
                >
                  뜻 힌트 열기
                </button>
              )
            ) : (
              <p className="text-xs opacity-50">
                뜻 힌트는 2번 시도하면 열려요
              </p>
            ))}

          {/* 결과 */}
          {state.finished && (
            <div className="w-full rounded-lg border-2 border-ink/10 bg-white p-4">
              <p
                className={`font-hand text-3xl font-bold ${
                  state.solved ? "text-brick-green" : "text-brick-red"
                }`}
              >
                {state.solved ? `${guesses.length}번 만에 성공!` : "아쉽다!"}
              </p>
              <p className="mt-2 text-sm">
                오늘의 단어: <b className="uppercase">{state.answer}</b>
                {state.answer_ko && (
                  <span className="ml-2 opacity-70">{state.answer_ko}</span>
                )}
              </p>
              <p className="mt-1 text-xs opacity-60">
                내일 자정에 새 단어가 나와요 — 내일 또 만나요!
              </p>
              <div className="mt-3">
                <ShareResultButton
                  data={{
                    game: "데일리 단어 퍼즐",
                    headline: state.solved
                      ? `${guesses.length}/${maxTries} 성공!`
                      : "내일 다시 도전!",
                    scoreline: state.day ?? "",
                    tone: state.solved ? "win" : "neutral",
                    lines: guesses.slice(0, 4).map((g, i) => ({
                      label: `${i + 1}번째`,
                      value: g.marks
                        .map((m) =>
                          m === "g" ? "[O]" : m === "y" ? "[~]" : "[X]",
                        )
                        .join(" "),
                    })),
                  }}
                />
              </div>
            </div>
          )}

          {/* 화면 키보드 — 시도한 글자 상태 표시 */}
          {playing && (
            <div className="flex w-full flex-col items-center gap-1.5">
              {KEY_ROWS.map((row, r) => (
                <div key={row} className="flex w-full justify-center gap-1">
                  {r === 2 && (
                    <button
                      type="button"
                      onClick={() => pressKey("enter")}
                      className="min-h-11 flex-[1.6] rounded-md border-2 border-brick-green bg-brick-green/15 px-1 text-xs font-bold transition active:scale-95"
                    >
                      입력
                    </button>
                  )}
                  {row.split("").map((ch) => {
                    const mark = letterMarks[ch];
                    return (
                      <button
                        key={ch}
                        type="button"
                        onClick={() => pressKey(ch)}
                        className={`min-h-11 flex-1 rounded-md border-2 text-base font-bold uppercase transition active:scale-95 ${
                          mark
                            ? MARK_STYLE[mark]
                            : "border-ink/15 bg-white hover:border-brick-blue"
                        }`}
                      >
                        {ch}
                      </button>
                    );
                  })}
                  {r === 2 && (
                    <button
                      type="button"
                      onClick={() => pressKey("back")}
                      className="min-h-11 flex-[1.6] rounded-md border-2 border-ink/20 bg-white px-1 text-base font-bold transition active:scale-95"
                    >
                      &#9003;
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* 게임 방법 — 첫 방문 자동 표시 + 헤더 버튼 재열람 */}
      {howtoOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="word-pop w-full max-w-sm rounded-lg border-2 border-ink/15 bg-paper p-5 shadow-xl">
            <h2 className="font-hand text-2xl font-bold">게임 방법</h2>
            <p className="mt-1 text-sm opacity-80">
              하루 한 단어, 모두에게 같은 단어! <b>{maxTries}번</b> 안에 영어
              단어를 맞혀보세요. 추측할 때마다 타일 색으로 알려줘요.
            </p>
            <div className="mt-4 flex flex-col gap-3 text-sm">
              <HowtoRow
                word="BRAVE"
                marks={["g", "x", "x", "x", "x"]}
                text="B 는 자리까지 정확해요"
              />
              <HowtoRow
                word="CLOUD"
                marks={["x", "y", "x", "x", "x"]}
                text="L 은 단어에 있지만 자리가 달라요"
              />
              <HowtoRow
                word="PIANO"
                marks={["x", "x", "x", "x", "x"]}
                text="정답에 없는 글자예요"
              />
            </div>
            <p className="mt-3 text-xs opacity-60">
              막히면 2번 시도 후 <b>뜻 힌트</b>를 열 수 있어요. 새 단어는 매일
              자정(한국 시간)에!
            </p>
            <div className="mt-4">
              <Brick color="green" onClick={closeHowto}>
                시작하기
              </Brick>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function HowtoRow({
  word,
  marks,
  text,
}: {
  word: string;
  marks: Mark[];
  text: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1">
        {word.split("").map((ch, i) => (
          <span
            key={i}
            className={`flex h-8 w-8 items-center justify-center rounded border-2 text-sm font-bold ${MARK_STYLE[marks[i]]}`}
          >
            {ch}
          </span>
        ))}
      </div>
      <span className="opacity-80">{text}</span>
    </div>
  );
}

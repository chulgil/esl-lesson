"use client";

import { useEffect, useState } from "react";
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
}

/** 데일리 단어 퍼즐 — 하루 한 단어, 전원 동일 (docs/specs/daily-puzzle.md) */
export default function DailyPuzzlePage() {
  const [state, setState] = useState<PuzzleState | null>(null);
  const [input, setInput] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/game/puzzle", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : { available: false }))
      .then(setState)
      .catch(() => setState({ available: false }));
  }, []);

  async function guess() {
    const word = input.trim().toLowerCase();
    if (!word || busy || !state?.length) return;
    if (word.length !== state.length) {
      setNote(`${state.length}글자 단어여야 해요`);
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
        setNote("영어 알파벳만 입력할 수 있어요");
      } else if (res.ok) {
        setState(await res.json());
        setInput("");
      } else {
        setNote("잠시 후 다시 시도해주세요");
      }
    } catch {
      setNote("잠시 후 다시 시도해주세요");
    }
    setBusy(false);
  }

  const tiles = (word: string, marks: string[]) =>
    word.split("").map((ch, i) => (
      <span
        key={i}
        className={`word-pop flex h-11 w-11 items-center justify-center rounded-md border-2 text-lg font-bold uppercase ${
          marks[i] === "g"
            ? "border-brick-green bg-brick-green text-brick-label"
            : marks[i] === "y"
              ? "border-brick-yellow bg-brick-yellow text-ink"
              : "border-ink/15 bg-ink/10 text-ink/60"
        }`}
        style={{ animationDelay: `${i * 60}ms` }}
      >
        {ch}
      </span>
    ));

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <BackLink href="/game" label="게임" />
        <h1 className="font-hand text-2xl font-bold whitespace-nowrap sm:text-3xl">
          <span className="hl">데일리 단어 퍼즐</span>
        </h1>
      </header>

      {!state && <p className="text-sm opacity-60">불러오는 중...</p>}
      {state && !state.available && (
        <p className="text-sm opacity-70">
          아직 퍼즐로 낼 단어가 부족해요 — 영상이 더 등록되면 열려요.
        </p>
      )}

      {state?.available && (
        <section className="flex max-w-md flex-col gap-4">
          <p className="text-sm opacity-70">
            오늘의 영어 단어 <b>{state.length}글자</b> — 모두에게 같은 단어예요.{" "}
            {state.max_tries}번 안에 맞혀보세요!
            <span className="mt-1 block text-xs opacity-60">
              초록=자리까지 정확, 노랑=글자는 있는데 자리가 달라요
            </span>
          </p>

          <div className="flex flex-col gap-1.5">
            {(state.guesses ?? []).map((g, i) => (
              <div key={i} className="flex gap-1.5">
                {tiles(g.word, g.marks)}
              </div>
            ))}
            {!state.finished &&
              Array.from(
                {
                  length: (state.max_tries ?? 6) - (state.guesses?.length ?? 0),
                },
                (_, r) => (
                  <div key={`empty-${r}`} className="flex gap-1.5">
                    {Array.from({ length: state.length ?? 5 }, (_, i) => (
                      <span
                        key={i}
                        className="flex h-11 w-11 rounded-md border-2 border-dashed border-ink/15"
                      />
                    ))}
                  </div>
                ),
              )}
          </div>

          {state.finished ? (
            <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
              <p
                className={`font-hand text-3xl font-bold ${
                  state.solved ? "text-brick-green" : "text-brick-red"
                }`}
              >
                {state.solved
                  ? `${state.guesses?.length}번 만에 성공!`
                  : "아쉽다!"}
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
                      ? `${state.guesses?.length}/${state.max_tries} 성공!`
                      : "내일 다시 도전!",
                    scoreline: state.day ?? "",
                    tone: state.solved ? "win" : "neutral",
                    lines: (state.guesses ?? []).slice(0, 4).map((g, i) => ({
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
          ) : (
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) =>
                  setInput(e.target.value.replace(/[^a-zA-Z]/g, ""))
                }
                onKeyDown={(e) => e.key === "Enter" && guess()}
                maxLength={state.length}
                placeholder={`${state.length}글자 영어 단어`}
                autoCapitalize="none"
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white px-3 font-mono text-lg tracking-widest lowercase transition-colors focus:border-brick-blue focus:outline-none"
              />
              <Brick color="green" onClick={guess} disabled={busy}>
                추측
              </Brick>
            </div>
          )}
          {note && <p className="text-xs text-brick-red">{note}</p>}
        </section>
      )}
    </main>
  );
}

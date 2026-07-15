"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { InviteFriends } from "@/components/game/InviteFriends";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { BackLink } from "@/components/nav/BackLink";
import { fetchMe } from "@/lib/api";
import {
  GameSocket,
  type ScResult,
  type ScRound,
  type ServerMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "racing" | "ended";

interface Chip {
  id: number;
  word: string;
  used: boolean;
}

interface RivalRow {
  placed: number;
  total: number;
  done: boolean;
  score: number;
}

export default function ScramblePage() {
  return (
    <Suspense>
      <ScrambleInner />
    </Suspense>
  );
}

/** 어순 조립 레이스 — 섞인 단어 칩을 올바른 어순으로 (docs/specs/scramble-race.md) */
function ScrambleInner() {
  const params = useSearchParams();
  const joinCode = params.get("join");

  const [phase, setPhase] = useState<Phase>("lobby");
  const [error, setError] = useState<string | null>(null);
  const [room, setRoom] = useState<{
    code: string | null;
    host: string;
    players: string[];
  } | null>(null);
  const [myName, setMyName] = useState("나");
  const [total, setTotal] = useState(0);
  const [roundIdx, setRoundIdx] = useState(-1);
  const [chips, setChips] = useState<Chip[]>([]);
  const [placed, setPlaced] = useState(0);
  const [mistakes, setMistakes] = useState(0);
  const [wrongId, setWrongId] = useState<number | null>(null);
  const [doneRound, setDoneRound] = useState(false);
  const [myScore, setMyScore] = useState(0);
  const [lastGain, setLastGain] = useState<number | null>(null);
  const [rivals, setRivals] = useState<Record<string, RivalRow>>({});
  const [timeLeft, setTimeLeft] = useState(0);
  const [end, setEnd] = useState<{
    results: ScResult[];
    winner: string | null;
  } | null>(null);

  const socketRef = useRef<GameSocket | null>(null);
  const roundsRef = useRef<ScRound[]>([]);
  const roundIdxRef = useRef(-1);
  const secondsRef = useRef(40);
  const deadlineRef = useRef(0);
  const myNameRef = useRef("나");

  useEffect(() => {
    fetchMe().then((me) => {
      if (me) {
        setMyName(me.nickname);
        myNameRef.current = me.nickname;
      }
    });
  }, []);

  const startRound = useCallback((idx: number) => {
    const round = roundsRef.current[idx];
    if (!round) return;
    roundIdxRef.current = idx;
    setRoundIdx(idx);
    setChips(round.chips.map((word, i) => ({ id: i, word, used: false })));
    setPlaced(0);
    setMistakes(0);
    setDoneRound(false);
    setLastGain(null);
    setRivals((prev) => {
      const reset: Record<string, RivalRow> = {};
      for (const [name, row] of Object.entries(prev)) {
        reset[name] = { ...row, placed: 0, done: false };
      }
      return reset;
    });
    deadlineRef.current = Date.now() + secondsRef.current * 1000;
    setPhase("racing");
  }, []);

  const handleMessage = useCallback(
    (msg: ServerMsg) => {
      switch (msg.t) {
        case "sc.room":
          setRoom({ code: msg.code, host: msg.host, players: msg.players });
          setPhase("waiting");
          break;
        case "sc.start":
          roundsRef.current = msg.rounds;
          secondsRef.current = msg.sentence_seconds;
          setTotal(msg.total);
          setRivals(
            Object.fromEntries(
              msg.players
                .filter((n) => n !== myNameRef.current)
                .map((n) => [
                  n,
                  { placed: 0, total: 0, done: false, score: 0 },
                ]),
            ),
          );
          setPhase("countdown");
          break;
        case "sc.sentence":
          startRound(msg.idx);
          break;
        case "sc.progress":
          setRivals((prev) => ({
            ...prev,
            [msg.name]: {
              ...(prev[msg.name] ?? { done: false, score: 0 }),
              placed: msg.placed,
              total: msg.total,
            },
          }));
          break;
        case "sc.done_mark":
          if (msg.name === myNameRef.current) {
            setMyScore(msg.score);
            setLastGain(msg.gained);
          } else {
            setRivals((prev) => ({
              ...prev,
              [msg.name]: {
                ...(prev[msg.name] ?? { placed: 0, total: 0 }),
                done: true,
                score: msg.score,
              },
            }));
          }
          break;
        case "sc.end":
          setEnd({ results: msg.results, winner: msg.winner });
          setPhase("ended");
          break;
        case "error":
          setError(
            msg.code === "sentences_insufficient"
              ? "조립할 문장이 아직 부족해요 — 영상을 등록하면 문장이 쌓여요"
              : msg.code === "room_not_found"
                ? "방을 찾을 수 없어요 — 코드를 확인해주세요"
                : msg.code,
          );
          setPhase("lobby");
          break;
      }
    },
    [startRound],
  );

  // 남은 시간 게이지 (라운드별 카운트다운)
  useEffect(() => {
    if (phase !== "racing") return;
    const timer = setInterval(() => {
      setTimeLeft(Math.max(0, (deadlineRef.current - Date.now()) / 1000));
    }, 100);
    return () => clearInterval(timer);
  }, [phase, roundIdx]);

  useEffect(() => {
    return () => {
      socketRef.current?.scLeave();
      socketRef.current?.close();
    };
  }, []);

  function connect(action: (socket: GameSocket) => void) {
    setError(null);
    if (socketRef.current) {
      action(socketRef.current);
      return;
    }
    const socket = new GameSocket(handleMessage, () => setPhase("lobby"));
    socket.connect();
    socketRef.current = socket;
    setTimeout(() => action(socket), 300);
  }

  // 초대 링크(?join=) 진입 — 자동 참가
  useEffect(() => {
    if (joinCode) connect((s) => s.scJoin(joinCode));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [joinCode]);

  function tapChip(chip: Chip) {
    if (doneRound || chip.used) return;
    const round = roundsRef.current[roundIdxRef.current];
    if (!round) return;
    if (chip.word === round.answer[placed]) {
      const nextPlaced = placed + 1;
      setChips((prev) =>
        prev.map((c) => (c.id === chip.id ? { ...c, used: true } : c)),
      );
      setPlaced(nextPlaced);
      socketRef.current?.scProgress(roundIdxRef.current, nextPlaced);
      if (nextPlaced === round.answer.length) {
        setDoneRound(true);
        socketRef.current?.scDone(roundIdxRef.current, mistakes);
      }
    } else {
      setMistakes((m) => m + 1);
      setWrongId(chip.id);
      setTimeout(() => setWrongId(null), 400);
    }
  }

  const round = roundIdx >= 0 ? roundsRef.current[roundIdx] : null;
  const timeRatio = secondsRef.current > 0 ? timeLeft / secondsRef.current : 0;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <BackLink href="/game" label="게임" />
        <h1 className="font-hand text-2xl font-bold whitespace-nowrap sm:text-3xl">
          <span className="hl">어순 조립 레이스</span>
        </h1>
        {phase === "racing" && (
          <span className="ml-auto rounded-full bg-white px-3 py-1 text-sm font-bold whitespace-nowrap shadow-sm">
            {Math.min(roundIdx + 1, total)}/{total} · {myScore}점
          </span>
        )}
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {phase === "lobby" && (
        <section className="flex max-w-xl flex-col gap-5">
          <p className="text-sm opacity-80">
            섞인 단어 칩을 <b>올바른 영어 어순</b>으로 빠르게 탭하세요. 같은
            문장을 전원이 동시에 풀고, 빠르고 정확할수록 점수가 커요.
          </p>
          <div className="flex flex-wrap gap-3">
            <Brick color="green" onClick={() => connect((s) => s.scSolo())}>
              솔로 시작
            </Brick>
            <Brick color="blue" onClick={() => connect((s) => s.scCreate())}>
              방 만들기 (2~4인)
            </Brick>
          </div>
        </section>
      )}

      {phase === "waiting" && room && (
        <section className="flex max-w-xl flex-col gap-4">
          <p className="text-sm">
            방 코드{" "}
            <span className="rounded bg-highlight/60 px-2 py-0.5 font-mono text-lg font-bold">
              {room.code}
            </span>
            <span className="ml-2 opacity-60">
              친구가 게임 허브에서 이 코드로 들어올 수 있어요
            </span>
          </p>
          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-2 text-xs font-bold opacity-60">
              참가자 {room.players.length}/4
            </p>
            <div className="flex flex-wrap gap-2">
              {room.players.map((p) => (
                <span
                  key={p}
                  className="rounded-full bg-ink/5 px-3 py-1 text-sm font-bold"
                >
                  {p}
                  {p === room.host && " (방장)"}
                </span>
              ))}
            </div>
          </div>
          <InviteFriends
            onInvite={(uid) =>
              room.code && socketRef.current?.invite(uid, "scramble", room.code)
            }
          />
          {room.host === myName ? (
            <Brick
              color="green"
              disabled={room.players.length < 2}
              onClick={() => socketRef.current?.scBegin()}
            >
              {room.players.length < 2 ? "친구를 기다리는 중..." : "시작!"}
            </Brick>
          ) : (
            <p className="animate-pulse text-sm opacity-60">
              방장이 시작하면 바로 출발해요...
            </p>
          )}
        </section>
      )}

      {phase === "countdown" && (
        <p className="animate-pulse py-16 text-center font-hand text-4xl font-bold">
          곧 시작해요!
        </p>
      )}

      {phase === "racing" && round && (
        <section className="flex max-w-2xl flex-col gap-4">
          {/* 남은 시간 게이지 */}
          <div className="h-2 overflow-hidden rounded-full bg-ink/10">
            <div
              className={`h-full rounded-full transition-[width] duration-100 ${
                timeRatio < 0.25 ? "bg-brick-red" : "bg-brick-blue"
              }`}
              style={{ width: `${timeRatio * 100}%` }}
            />
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-5">
            <p className="text-sm opacity-60">이 뜻이 되도록 조립하세요</p>
            <p className="mt-1 text-lg font-bold">{round.ko || "..."}</p>

            {/* 조립 영역 */}
            <p className="mt-4 min-h-8 text-lg font-medium">
              {round.answer.slice(0, placed).join(" ")}
              <span className="opacity-30">
                {placed > 0 && placed < round.answer.length ? " " : ""}
                {Array.from(
                  { length: round.answer.length - placed },
                  () => "___",
                ).join(" ")}
              </span>
            </p>

            {doneRound ? (
              <p className="mt-4 font-bold text-brick-green">
                완성!{lastGain != null && ` +${lastGain}점`} — 다른 플레이어를
                기다려요
              </p>
            ) : (
              <div className="mt-4 flex flex-wrap gap-2">
                {chips.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    disabled={chip.used}
                    onClick={() => tapChip(chip)}
                    className={`min-h-11 rounded-md border-2 px-3 text-sm font-bold transition ${
                      chip.used
                        ? "border-ink/5 bg-ink/5 text-ink/25"
                        : "cursor-pointer border-ink/20 bg-white hover:-translate-y-0.5 hover:border-brick-blue"
                    } ${wrongId === chip.id ? "miss-shake border-brick-red" : ""}`}
                  >
                    {chip.word}
                  </button>
                ))}
              </div>
            )}
            {mistakes > 0 && !doneRound && (
              <p className="mt-2 text-xs text-brick-red">실수 {mistakes}회</p>
            )}
          </div>

          {/* 상대 진행 */}
          {Object.keys(rivals).length > 0 && (
            <div className="flex flex-col gap-1.5">
              {Object.entries(rivals).map(([name, row]) => (
                <div key={name} className="flex items-center gap-2 text-xs">
                  <span className="w-20 truncate font-bold">{name}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink/10">
                    <div
                      className="h-full rounded-full bg-brick-yellow transition-[width]"
                      style={{
                        width: `${row.total > 0 ? (row.placed / row.total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="w-14 text-right opacity-60">
                    {row.done ? `${row.score}점` : `${row.placed}칩`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {phase === "ended" && end && (
        <section className="flex max-w-md flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6">
          <h2 className="font-hand text-3xl font-bold">
            {end.winner ? (
              <span className="hl">{end.winner} 승리!</span>
            ) : end.results.length > 1 ? (
              "무승부"
            ) : (
              "기록 완료!"
            )}
          </h2>
          {[...end.results]
            .sort((a, b) => b.score - a.score)
            .map((r) => (
              <div
                key={r.name}
                className={`rounded-md border-2 p-3 ${
                  end.winner === r.name
                    ? "border-brick-yellow bg-highlight/40"
                    : "border-ink/10"
                }`}
              >
                <p className="font-bold">{r.name}</p>
                <p className="mt-1 text-sm opacity-80">
                  <b>{r.score}점</b> · 문장 {r.sentences}개 · 실수 {r.mistakes}
                  회
                </p>
              </div>
            ))}
          <div className="flex flex-wrap items-center gap-3">
            <Brick
              color="green"
              onClick={() => {
                setEnd(null);
                setMyScore(0);
                connect((s) => s.scSolo());
              }}
            >
              한 번 더
            </Brick>
            <Brick color="blue" href="/game">
              게임 메뉴로
            </Brick>
            {end.results[0] && (
              <ShareResultButton
                data={{
                  game: "어순 조립 레이스",
                  headline: end.winner
                    ? `${end.winner} 승리!`
                    : end.results.length > 1
                      ? "무승부"
                      : "기록 완료!",
                  scoreline: `${[...end.results].sort((a, b) => b.score - a.score)[0].score}점`,
                  tone: end.winner ? "win" : "neutral",
                  lines: end.results.slice(0, 4).map((r) => ({
                    label: r.name,
                    value: `${r.score}점 · 실수 ${r.mistakes}회`,
                  })),
                }}
              />
            )}
          </div>
        </section>
      )}
    </main>
  );
}

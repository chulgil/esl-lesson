"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { InviteFriends } from "@/components/game/InviteFriends";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { fetchMe } from "@/lib/api";
import {
  GameSocket,
  type ServerMsg,
  type TpResult,
  type TpStartMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "racing" | "ended";

interface Row {
  name: string;
  chars: number;
  wpm: number;
  done: boolean;
}

export default function TypingRacePage() {
  return (
    <Suspense>
      <TypingRaceInner />
    </Suspense>
  );
}

/** 영문 타자연습 — 같은 문장을 1~4인이 동시에, 전원 완성 시 다음 문장 (typing-race.md) */
function TypingRaceInner() {
  const joinCode = useSearchParams().get("join");
  const [phase, setPhase] = useState<Phase>("lobby");
  const [code, setCode] = useState("");
  const [room, setRoom] = useState<{
    code: string | null;
    host: string;
    players: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState<TpStartMsg | null>(null);
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [myDone, setMyDone] = useState(false);
  const [end, setEnd] = useState<{
    results: TpResult[];
    winner: string | null;
  } | null>(null);
  const [myName, setMyName] = useState("나");
  const socketRef = useRef<GameSocket | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const errorsRef = useRef(0);
  const prevLenRef = useRef(0);
  const lastSentRef = useRef(0);
  const myNameRef = useRef("나");

  useEffect(() => {
    fetchMe().then((me) => {
      if (me) {
        setMyName(me.name);
        myNameRef.current = me.name;
      }
    });
  }, []);

  const handleMessage = useCallback((msg: ServerMsg) => {
    switch (msg.t) {
      case "tp.room":
        setRoom({ code: msg.code, host: msg.host, players: msg.players });
        setPhase("waiting");
        break;
      case "tp.start": {
        setStart(msg);
        setEnd(null);
        setRows(
          Object.fromEntries(
            msg.players.map((name) => [
              name,
              { name, chars: 0, wpm: 0, done: false },
            ]),
          ),
        );
        setPhase("countdown");
        setTimeout(() => setPhase("racing"), msg.countdown * 1000);
        break;
      }
      case "tp.sentence":
        setIdx(msg.idx);
        setTyped("");
        setMyDone(false);
        errorsRef.current = 0;
        prevLenRef.current = 0;
        lastSentRef.current = 0;
        setRows((prev) =>
          Object.fromEntries(
            Object.values(prev).map((r) => [
              r.name,
              { ...r, chars: 0, done: false },
            ]),
          ),
        );
        break;
      case "tp.typing":
        setRows((prev) => ({
          ...prev,
          [msg.name]: {
            name: msg.name,
            chars: msg.chars,
            wpm: msg.wpm,
            done: prev[msg.name]?.done ?? false,
          },
        }));
        break;
      case "tp.done_mark":
        setRows((prev) => ({
          ...prev,
          [msg.name]: {
            name: msg.name,
            chars: prev[msg.name]?.chars ?? 0,
            wpm: msg.wpm,
            done: true,
          },
        }));
        break;
      case "tp.end":
        setEnd({ results: msg.results, winner: msg.winner });
        setPhase("ended");
        break;
      case "error":
        setPhase("lobby");
        setError(
          {
            sentences_insufficient:
              "타자연습에 쓸 문장이 부족해요 — 콘텐츠를 등록하면 문장이 쌓여요.",
            room_not_found: "방을 찾을 수 없어요.",
            room_full: "방이 가득 찼어요 (최대 4명).",
          }[msg.code] ?? msg.code,
        );
        break;
    }
  }, []);

  useEffect(() => {
    const socket = new GameSocket(handleMessage, () => {
      setError((prev) => prev ?? "연결이 끊어졌어요. 새로고침해주세요.");
    });
    socket.connect();
    socketRef.current = socket;
    // 초대 링크(?join=)로 진입 시 자동 입장
    const timer = joinCode
      ? setTimeout(() => socket.tpJoin(joinCode), 400)
      : null;
    return () => {
      if (timer) clearTimeout(timer);
      socket.close();
    };
  }, [handleMessage, joinCode]);

  useEffect(() => {
    if (phase === "racing") inputRef.current?.focus();
  }, [phase, idx]);

  const sentences = start?.sentences ?? [];
  const target = sentences[idx]?.en ?? "";
  const targetKo = sentences[idx]?.ko ?? "";

  function correctPrefixLen(value: string): number {
    let n = 0;
    while (n < value.length && value[n] === target[n]) n += 1;
    return n;
  }

  function onType(value: string) {
    if (phase !== "racing" || myDone) return;
    if (
      value.length > prevLenRef.current &&
      value[value.length - 1] !== target[value.length - 1]
    ) {
      errorsRef.current += 1;
    }
    prevLenRef.current = value.length;

    const prefix = correctPrefixLen(value);
    // 진행 중계는 2자 이상 변할 때만 — 메시지 폭주 방지
    if (Math.abs(prefix - lastSentRef.current) >= 2) {
      lastSentRef.current = prefix;
      socketRef.current?.tpTyping(idx, prefix);
    }
    setRows((prev) => ({
      ...prev,
      [myNameRef.current]: {
        name: myNameRef.current,
        chars: prefix,
        wpm: prev[myNameRef.current]?.wpm ?? 0,
        done: false,
      },
    }));

    if (value === target) {
      socketRef.current?.tpDone(idx, target.length, errorsRef.current);
      setMyDone(true);
      setTyped("");
      setRows((prev) => ({
        ...prev,
        [myNameRef.current]: {
          ...(prev[myNameRef.current] ?? {
            name: myNameRef.current,
            wpm: 0,
          }),
          name: myNameRef.current,
          chars: target.length,
          done: true,
        },
      }));
      return;
    }
    setTyped(value);
  }

  const playerRows = Object.values(rows);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        {(phase === "lobby" || phase === "ended") && (
          <BackLink href="/game" label="게임" />
        )}
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">영문 타자연습</span>
        </h1>
        {phase === "racing" && start && (
          <span className="ml-auto rounded-full bg-white px-3 py-1 text-sm font-bold shadow-sm">
            {idx + 1} / {start.total}
          </span>
        )}
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {phase === "lobby" && (
        <section className="flex max-w-lg flex-col gap-6">
          <div className="rounded-lg border-2 border-ink/10 bg-white p-4 text-sm">
            <p className="mb-2 font-bold">게임 방식</p>
            <ul className="flex flex-col gap-1 opacity-80">
              <li>
                샘플 문장 하나가 나오면 <b>모두가 같은 문장</b>을 타이핑해요
                (1~4명)
              </li>
              <li>
                <b>전원이 완성하면 다음 문장</b>으로 — 총 10문장, 문장당 최대
                30초
              </li>
              <li>
                플레이어마다 진행 줄과 <b>WPM(타속)</b>이 실시간으로 표시돼요
              </li>
              <li>승부: 완성 문장 → 정타 수 → 빠르기 순으로 가려요</li>
            </ul>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">혼자 연습 (기록 도전)</p>
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.tpSolo();
              }}
            >
              타자 연습 시작
            </Brick>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">친구와 레이스 (2~4인)</p>
            <div className="flex flex-wrap items-center gap-3">
              <Brick
                color="blue"
                onClick={() => {
                  setError(null);
                  socketRef.current?.tpCreate();
                }}
              >
                방 만들기
              </Brick>
              <div className="flex items-center gap-2">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="방 코드"
                  maxLength={6}
                  className="min-h-11 w-28 rounded-md border-2 border-ink/20 px-2 font-mono uppercase transition-colors focus:border-brick-blue focus:outline-none"
                />
                <Brick
                  color="yellow"
                  onClick={() => {
                    if (!code.trim()) return;
                    setError(null);
                    socketRef.current?.tpJoin(code.trim());
                  }}
                >
                  입장
                </Brick>
              </div>
            </div>
          </div>
        </section>
      )}

      {phase === "waiting" && room && (
        <section className="flex max-w-lg flex-col items-start gap-4 rounded-lg border-2 border-ink/10 bg-white p-5">
          <p>
            친구에게 방 코드를 알려주세요:{" "}
            <span className="rounded bg-highlight/60 px-3 py-1 font-mono text-2xl font-bold tracking-widest">
              {room.code}
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            {room.players.map((p) => (
              <span
                key={p}
                className="rounded-full border-2 border-brick-blue/40 bg-white px-3 py-1.5 text-sm font-bold"
              >
                {p}
                {p === room.host && " (방장)"}
              </span>
            ))}
            {Array.from({ length: 4 - room.players.length }, (_, i) => (
              <span
                key={`empty-${i}`}
                className="rounded-full border-2 border-dashed border-ink/15 px-3 py-1.5 text-sm opacity-40"
              >
                빈 자리
              </span>
            ))}
          </div>
          <div className="flex gap-3">
            {room.host === myName && (
              <Brick
                color="green"
                disabled={room.players.length < 2}
                onClick={() => socketRef.current?.tpBegin()}
              >
                시작하기 ({room.players.length}/4)
              </Brick>
            )}
            <Brick
              color="yellow"
              onClick={() => {
                socketRef.current?.tpLeave();
                setPhase("lobby");
              }}
            >
              나가기
            </Brick>
          </div>
          {room.host !== myName && (
            <p className="text-xs opacity-60">방장이 시작하면 바로 달려요!</p>
          )}
          <InviteFriends
            onInvite={(uid) =>
              room.code && socketRef.current?.invite(uid, "typing", room.code)
            }
          />
        </section>
      )}

      {phase === "countdown" && (
        <p className="animate-pulse font-hand text-6xl font-bold text-brick-green">
          준비...
        </p>
      )}

      {phase === "racing" && (
        <section className="flex max-w-2xl flex-col gap-4">
          {/* 샘플 문장 — 모두가 같은 문장을 침 */}
          <div className="rounded-lg border-2 border-ink/10 bg-white p-5 font-mono text-lg leading-relaxed">
            {target.split("").map((ch, i) => {
              const prefix = correctPrefixLen(typed);
              const state = myDone
                ? "correct"
                : i < prefix
                  ? "correct"
                  : i < typed.length
                    ? "wrong"
                    : i === typed.length
                      ? "cursor"
                      : "rest";
              return (
                <span
                  key={`${idx}-${i}`}
                  className={
                    state === "correct"
                      ? "text-brick-green"
                      : state === "wrong"
                        ? "bg-brick-red/20 text-brick-red"
                        : state === "cursor"
                          ? "border-b-4 border-brick-blue"
                          : "opacity-60"
                  }
                >
                  {ch}
                </span>
              );
            })}
          </div>

          {targetKo && (
            <p className="rounded-md bg-highlight/40 px-3 py-1.5 text-sm">
              뜻: <b>{targetKo}</b>
            </p>
          )}

          <input
            ref={inputRef}
            value={typed}
            onChange={(e) => onType(e.target.value)}
            disabled={myDone}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder={
              myDone ? "완료! 다른 플레이어를 기다리는 중..." : "여기에 타이핑"
            }
            className="w-full rounded-lg border-2 border-ink/30 bg-white px-4 py-3 font-mono text-lg focus:border-brick-blue focus:outline-none disabled:opacity-60"
          />

          {/* 플레이어별 실시간 진행 줄 + 개별 WPM */}
          <div className="flex flex-col gap-2">
            {playerRows.map((row) => {
              const ratio = target.length
                ? Math.min(1, row.chars / target.length)
                : 0;
              const mine = row.name === myName;
              return (
                <div
                  key={row.name}
                  className={`rounded-md border-2 p-2.5 ${
                    mine
                      ? "border-brick-blue/50 bg-white"
                      : "border-ink/10 bg-white"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-bold">
                      {row.name}
                      {mine && " (나)"}
                      {row.done && (
                        <span className="ml-1.5 text-brick-green">완성!</span>
                      )}
                    </span>
                    <span className="rounded bg-ink/5 px-1.5 py-0.5 font-mono font-bold">
                      {Math.round(row.wpm * 5)}타
                      <span className="ml-1 font-normal opacity-60">
                        {Math.round(row.wpm)}WPM
                      </span>
                    </span>
                  </div>
                  <div className="font-mono text-sm leading-snug">
                    <span
                      className={
                        row.done ? "text-brick-green" : "text-brick-blue"
                      }
                    >
                      {target.slice(0, row.chars)}
                    </span>
                    <span className="opacity-30">
                      {target.slice(row.chars)}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                    <div
                      className={`h-full rounded-full transition-[width] duration-200 ${
                        row.done ? "bg-brick-green" : "bg-brick-yellow"
                      }`}
                      style={{ width: `${ratio * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
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
          {end.results.map((r) => (
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
                평균 <b>{r.cpm}타</b> · 최고 <b>{r.peak_cpm}타</b> · {r.wpm}
                WPM
              </p>
              <p className="mt-0.5 text-xs opacity-60">
                정확도 {Math.round(r.accuracy * 100)}% · {r.sentences}문장 (
                {r.chars}자)
              </p>
            </div>
          ))}
          <div className="flex gap-3">
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.tpSolo();
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
                  game: "영문 타자연습",
                  headline: end.winner
                    ? `${end.winner} 승리!`
                    : end.results.length > 1
                      ? "무승부"
                      : "기록 완료!",
                  scoreline: `최고 ${
                    (end.winner
                      ? end.results.find((r) => r.name === end.winner)
                      : end.results[0]
                    )?.peak_cpm ?? end.results[0].peak_cpm
                  }타`,
                  tone: end.winner ? "win" : "neutral",
                  lines: end.results.slice(0, 4).map((r) => ({
                    label: r.name,
                    value: `평균 ${r.cpm}타 · 정확도 ${Math.round(r.accuracy * 100)}%`,
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

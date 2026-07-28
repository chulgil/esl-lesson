"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { InviteFriends } from "@/components/game/InviteFriends";
import { ReviewPanel } from "@/components/game/ReviewPanel";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { SegmentPlayer } from "@/components/media/SegmentPlayer";
import { BackLink } from "@/components/nav/BackLink";
import { fetchMe } from "@/lib/api";
import {
  type DtClip,
  type DtResult,
  GameSocket,
  type GameReviewItem,
  type ServerMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "racing" | "ended";

export default function DictationPage() {
  return (
    <Suspense>
      <DictationInner />
    </Suspense>
  );
}

/** 받아쓰기 배틀 — 원음 듣고 받아쓰기, 서버 채점 (docs/specs/dictation-battle.md) */
function DictationInner() {
  const params = useSearchParams();
  const joinCode = params.get("join");

  const [phase, setPhase] = useState<Phase>("lobby");
  // 결과가 화면 하단에 묻혀 안 보이는 문제(모바일) — 종료 시 결과 섹션을 상단으로 스크롤
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (phase === "ended") {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [phase]);
  const [error, setError] = useState<string | null>(null);
  const [room, setRoom] = useState<{
    code: string | null;
    host: string;
    players: string[];
  } | null>(null);
  const [myName, setMyName] = useState("나");
  const [total, setTotal] = useState(0);
  const [roundIdx, setRoundIdx] = useState(-1);
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [myScore, setMyScore] = useState(0);
  const [lastResult, setLastResult] = useState<{
    accuracy: number;
    gained: number;
  } | null>(null);
  const [reveal, setReveal] = useState<string | null>(null);
  const [countLeft, setCountLeft] = useState(3);
  const [rivalDone, setRivalDone] = useState<Record<string, number>>({});
  const [timeLeft, setTimeLeft] = useState(0);
  const [end, setEnd] = useState<{
    results: DtResult[];
    winner: string | null;
  } | null>(null);
  const [review, setReview] = useState<GameReviewItem[]>([]);

  const socketRef = useRef<GameSocket | null>(null);
  const clipsRef = useRef<DtClip[]>([]);
  const roundIdxRef = useRef(-1);
  const secondsRef = useRef(45);
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

  const handleMessage = useCallback((msg: ServerMsg) => {
    switch (msg.t) {
      case "dt.room":
        setRoom({ code: msg.code, host: msg.host, players: msg.players });
        setPhase("waiting");
        break;
      case "dt.start":
        clipsRef.current = msg.clips;
        secondsRef.current = msg.sentence_seconds;
        setTotal(msg.total);
        setCountLeft(Math.ceil(msg.countdown));
        setReview([]);
        setPhase("countdown");
        break;
      case "dt.sentence":
        roundIdxRef.current = msg.idx;
        setRoundIdx(msg.idx);
        setText("");
        setSubmitted(false);
        setLastResult(null);
        setReveal(null);
        setRivalDone({});
        deadlineRef.current = Date.now() + secondsRef.current * 1000;
        setPhase("racing");
        break;
      case "dt.done_mark":
        if (msg.name === myNameRef.current) {
          setMyScore(msg.score);
          setLastResult({ accuracy: msg.accuracy, gained: msg.gained });
        } else {
          setRivalDone((prev) => ({ ...prev, [msg.name]: msg.score }));
        }
        break;
      case "dt.reveal":
        setReveal(msg.en);
        break;
      case "dt.review":
        setReview(msg.items);
        break;
      case "dt.end":
        setEnd({ results: msg.results, winner: msg.winner });
        setPhase("ended");
        break;
      case "error":
        setError(
          msg.code === "sentences_insufficient"
            ? "받아쓸 문장이 아직 부족해요 — 유튜브 영상을 등록하면 쌓여요"
            : msg.code === "room_not_found"
              ? "방을 찾을 수 없어요 — 코드를 확인해주세요"
              : msg.code,
        );
        setPhase("lobby");
        break;
    }
  }, []);

  useEffect(() => {
    if (phase !== "countdown") return;
    const timer = setInterval(
      () => setCountLeft((v) => Math.max(0, v - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    if (phase !== "racing") return;
    const timer = setInterval(() => {
      setTimeLeft(Math.max(0, (deadlineRef.current - Date.now()) / 1000));
    }, 100);
    return () => clearInterval(timer);
  }, [phase, roundIdx]);

  useEffect(() => {
    return () => {
      socketRef.current?.dtLeave();
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

  useEffect(() => {
    if (joinCode) connect((s) => s.dtJoin(joinCode));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [joinCode]);

  function submit() {
    const value = text.trim();
    if (!value || submitted) return;
    setSubmitted(true);
    socketRef.current?.dtSubmit(roundIdxRef.current, value);
  }

  const clip = roundIdx >= 0 ? clipsRef.current[roundIdx] : null;
  const timeRatio = secondsRef.current > 0 ? timeLeft / secondsRef.current : 0;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <BackLink href="/game" label="게임" />
        <h1 className="font-hand text-2xl font-bold whitespace-nowrap sm:text-3xl">
          <span className="hl">받아쓰기 배틀</span>
        </h1>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {phase === "lobby" && (
        <section className="flex max-w-xl flex-col gap-5">
          <p className="text-sm opacity-80">
            유튜브 <b>원어민 음성</b>을 듣고 문장을 받아쓰세요. 몇 번이고 다시
            들을 수 있지만, 빠르고 정확할수록 점수가 커요.
          </p>
          <div className="flex flex-wrap gap-3">
            <Brick color="green" onClick={() => connect((s) => s.dtSolo())}>
              솔로 시작
            </Brick>
            <Brick color="blue" onClick={() => connect((s) => s.dtCreate())}>
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
              room.code &&
              socketRef.current?.invite(uid, "dictation", room.code)
            }
          />
          {room.host === myName ? (
            <Brick
              color="green"
              disabled={room.players.length < 2}
              onClick={() => socketRef.current?.dtBegin()}
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
        <div className="py-16 text-center">
          <p
            key={countLeft}
            className="word-pop font-hand text-8xl font-bold text-brick-blue"
          >
            {countLeft > 0 ? countLeft : "GO!"}
          </p>
          <p className="mt-2 text-sm opacity-60">잘 듣고 그대로 받아쓰세요</p>
        </div>
      )}

      {phase === "racing" && clip && (
        <section className="flex max-w-2xl flex-col gap-4">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-ink px-3 py-1 font-hand text-xl font-bold text-white">
              {Math.min(roundIdx + 1, total)}
              <span className="opacity-50">/{total}</span>
            </span>
            <span className="rounded-lg bg-brick-yellow px-3 py-1 font-hand text-xl font-bold text-ink">
              {myScore}점
            </span>
          </div>

          <div className="relative overflow-hidden rounded-lg border-2 border-ink/10 bg-white p-5">
            <div
              className={`water-fill ${timeRatio < 0.25 ? "low" : ""}`}
              style={{ height: `${(1 - timeRatio) * 100}%` }}
              aria-hidden
            />
            <div className="relative flex flex-col gap-3">
              <SegmentPlayer
                key={roundIdx}
                media={clip}
                label="문장 듣기 (반복 가능)"
              />

              {reveal ? (
                <div>
                  <p className="text-xs font-bold opacity-60">정답</p>
                  <p className="text-lg font-medium">{reveal}</p>
                  {lastResult && (
                    <p className="mt-1 text-sm font-bold text-brick-green">
                      정확도 {Math.round(lastResult.accuracy * 100)}% · +
                      {lastResult.gained}점
                    </p>
                  )}
                </div>
              ) : submitted ? (
                <div className="relative">
                  {lastResult ? (
                    <>
                      <p
                        className={`font-hand text-3xl font-bold ${
                          lastResult.accuracy >= 0.9
                            ? "text-brick-yellow"
                            : "text-brick-green"
                        }`}
                      >
                        {lastResult.accuracy >= 1 ? "PERFECT!" : "제출 완료!"}
                      </p>
                      <span className="score-pop absolute -top-1 left-40 font-hand text-2xl font-bold text-brick-green">
                        +{lastResult.gained}
                      </span>
                      <Burst seed={roundIdx} />
                      <p className="mt-1 text-sm opacity-70">
                        정확도 {Math.round(lastResult.accuracy * 100)}% — 정답은
                        라운드가 끝나면 공개돼요
                      </p>
                    </>
                  ) : (
                    <p className="animate-pulse text-sm opacity-60">
                      채점 중...
                    </p>
                  )}
                </div>
              ) : (
                <>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        submit();
                      }
                    }}
                    rows={2}
                    placeholder="들리는 대로 영어로 입력하세요"
                    className="w-full rounded-md border-2 border-ink/20 bg-white px-3 py-2 text-sm transition-colors focus:border-brick-blue focus:outline-none"
                  />
                  <div>
                    <Brick color="green" onClick={submit}>
                      제출
                    </Brick>
                  </div>
                </>
              )}

              {Object.keys(rivalDone).length > 0 && (
                <p className="text-xs opacity-60">
                  제출 완료:{" "}
                  {Object.entries(rivalDone)
                    .map(([n, s]) => `${n} (${s}점)`)
                    .join(" · ")}
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      {phase === "ended" && end && (
        <section
          ref={resultRef}
          className="flex max-w-md flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6"
        >
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
                  <b>{r.score}점</b> · 정확도 {Math.round(r.accuracy * 100)}% ·
                  문장 {r.sentences}개
                </p>
              </div>
            ))}
          <ReviewPanel
            items={review}
            noun="문장"
            hint="추가한 문장은 학습 큐에 들어가요 — 문장 카드는 학습 레벨 '고급'에서 출제돼요"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Brick
              color="green"
              onClick={() => {
                setEnd(null);
                setMyScore(0);
                connect((s) => s.dtSolo());
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
                  game: "받아쓰기 배틀",
                  headline: end.winner
                    ? `${end.winner} 승리!`
                    : end.results.length > 1
                      ? "무승부"
                      : "기록 완료!",
                  scoreline: `${[...end.results].sort((a, b) => b.score - a.score)[0].score}점`,
                  tone: end.winner ? "win" : "neutral",
                  lines: end.results.slice(0, 4).map((r) => ({
                    label: r.name,
                    value: `${r.score}점 · 정확도 ${Math.round(r.accuracy * 100)}%`,
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

/** 제출 파티클 — 어순 레이스와 동일 연출 */
function Burst({ seed }: { seed: number }) {
  const colors = [
    "bg-brick-red",
    "bg-brick-yellow",
    "bg-brick-blue",
    "bg-brick-green",
  ];
  return (
    <span aria-hidden className="pointer-events-none absolute top-2 left-20">
      {Array.from({ length: 10 }, (_, i) => {
        const angle = ((seed * 37 + i * 36) % 360) * (Math.PI / 180);
        const dist = 34 + ((seed + i) % 3) * 14;
        return (
          <span
            key={i}
            className={`burst-dot absolute h-2 w-2 rounded-full ${colors[i % 4]}`}
            style={
              {
                "--dx": `${Math.cos(angle) * dist}px`,
                "--dy": `${Math.sin(angle) * dist}px`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </span>
  );
}

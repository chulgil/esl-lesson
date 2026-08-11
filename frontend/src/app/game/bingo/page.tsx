"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { InviteFriends } from "@/components/game/InviteFriends";
import { PlayerBadge } from "@/components/game/PlayerBadge";
import { ReviewPanel } from "@/components/game/ReviewPanel";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { SegmentPlayer } from "@/components/media/SegmentPlayer";
import { fetchMe } from "@/lib/api";
import { speakWord } from "@/lib/speech";
import { useInviteTheme } from "@/lib/use-invite-theme";
import {
  GameSocket,
  type BgResult,
  type BgRoundMsg,
  type BgStartMsg,
  type GameReviewItem,
  type PlayerProfile,
  type ServerMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "playing" | "ended";

export default function BingoPage() {
  return (
    <Suspense>
      <BingoInner />
    </Suspense>
  );
}

/** 리스닝 빙고 — 음성으로 불러주는 단어를 4x4 보드에서 찾아 탭, 1~4인 (listening-bingo.md) */
function BingoInner() {
  const joinCode = useSearchParams().get("join");
  const [phase, setPhase] = useState<Phase>("lobby");
  // 초대 입장(?theme=)이면 게임 동안 초대자 테마 — 종료/이탈 시 자동 복원
  useInviteTheme(phase === "ended");
  // 결과가 화면 하단에 묻혀 안 보이는 문제(모바일) — 종료 시 결과 섹션을 상단으로 스크롤
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (phase === "ended") {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [phase]);
  const [code, setCode] = useState("");
  const [room, setRoom] = useState<{
    code: string | null;
    host: string;
    players: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState<BgStartMsg | null>(null);
  const [round, setRound] = useState<BgRoundMsg | null>(null);
  const [reveal, setReveal] = useState<{
    en: string;
    ko: string;
    bingo: string[];
  } | null>(null);
  const [filled, setFilled] = useState<Set<number>>(new Set());
  const [locked, setLocked] = useState(false);
  const [marks, setMarks] = useState<Record<string, number>>({});
  const [end, setEnd] = useState<{
    results: BgResult[];
    winner: string | null;
  } | null>(null);
  const [review, setReview] = useState<GameReviewItem[]>([]);
  const [profiles, setProfiles] = useState<Record<string, PlayerProfile>>({});
  const [myName, setMyName] = useState("나");
  const [timeLeft, setTimeLeft] = useState(0);
  const socketRef = useRef<GameSocket | null>(null);
  const deadlineRef = useRef(0);
  const secondsRef = useRef(10);

  useEffect(() => {
    fetchMe().then((me) => {
      if (me) setMyName(me.nickname);
    });
  }, []);

  const handleMessage = useCallback((msg: ServerMsg) => {
    switch (msg.t) {
      case "bg.room":
        setRoom({ code: msg.code, host: msg.host, players: msg.players });
        if (msg.profiles) setProfiles(msg.profiles);
        setPhase("waiting");
        break;
      case "bg.start":
        setStart(msg);
        secondsRef.current = msg.round_seconds;
        setEnd(null);
        setReview([]);
        setFilled(new Set());
        setMarks({});
        setRound(null);
        setReveal(null);
        setPhase("countdown");
        setTimeout(() => setPhase("playing"), msg.countdown * 1000);
        break;
      case "bg.round":
        setRound(msg);
        setReveal(null);
        setLocked(false);
        deadlineRef.current = Date.now() + secondsRef.current * 1000;
        setTimeLeft(secondsRef.current);
        // 문제 음성 자동 재생 (신경망 TTS, 실패 시 브라우저 TTS) — 텍스트는 비노출
        speakWord(msg.tts);
        break;
      case "bg.tap_result":
        if (msg.ok) {
          setFilled((prev) => new Set(prev).add(msg.item_id));
        } else {
          // 오답 — 1초 잠금 (난사 방지, 서버도 오답 카운트)
          setLocked(true);
          setTimeout(() => setLocked(false), 1000);
        }
        break;
      case "bg.mark":
        setMarks((prev) => ({ ...prev, [msg.name]: msg.filled }));
        break;
      case "bg.reveal":
        setReveal({ en: msg.en, ko: msg.ko, bingo: msg.bingo });
        break;
      case "bg.review":
        setReview(msg.items);
        break;
      case "bg.end":
        setEnd({ results: msg.results, winner: msg.winner });
        setPhase("ended");
        break;
      case "error":
        setPhase("lobby");
        setError(
          {
            words_insufficient:
              "빙고에 쓸 단어가 부족해요 (최소 16개) — 콘텐츠를 담고 학습을 시작하면 단어가 쌓여요.",
            room_not_found: "방을 찾을 수 없어요.",
            room_full: "방이 가득 찼어요 (최대 4명).",
            room_closed: "방장이 나가서 방이 닫혔어요.",
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
      ? setTimeout(() => socket.bgJoin(joinCode), 400)
      : null;
    return () => {
      if (timer) clearTimeout(timer);
      socket.close();
    };
  }, [handleMessage, joinCode]);

  // 라운드 카운트다운 표시 (타자연습과 동일 패턴)
  useEffect(() => {
    if (phase !== "playing") return;
    const t = setInterval(() => {
      setTimeLeft(
        Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)),
      );
    }, 250);
    return () => clearInterval(t);
  }, [phase]);

  function tapCell(itemId: number) {
    // reveal 중 잠금 (2026-08-10 리뷰) — 정답 공개를 보고 탭하는 공짜 크레딧 방지.
    // 서버도 라운드를 마감해 거부하지만, 클라이언트가 잠가야 피드백 없는 탭이 없다
    if (phase !== "playing" || locked || round === null || reveal !== null)
      return;
    if (filled.has(itemId)) return;
    socketRef.current?.bgTap(round.no, itemId);
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        {(phase === "lobby" || phase === "ended") && (
          <BackLink href="/game" label="게임" />
        )}
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">리스닝 빙고</span>
        </h1>
        {phase === "playing" && round && (
          <span className="ml-auto flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-sm font-bold shadow-sm ${
                timeLeft <= 3 ? "bg-brick-red/15 text-brick-red" : "bg-white"
              }`}
            >
              {timeLeft}초
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-sm font-bold shadow-sm">
              {round.no + 1} / {round.total}
            </span>
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
                음성으로 단어를 불러주면 <b>내 4x4 보드에서 찾아 탭</b>해요
                (텍스트 문제 없음 — 듣기가 전부)
              </li>
              <li>
                모두 <b>같은 16단어</b>, 배치만 달라요 — 가로/세로/대각{" "}
                <b>한 줄을 먼저 만들면 승리</b>
              </li>
              <li>복습할 때가 된 단어가 우선 나와요 — 한 판이 곧 복습</li>
              <li>놓친 단어는 끝나고 원탭으로 학습에 담을 수 있어요</li>
            </ul>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">혼자 연습 (듣기 기록)</p>
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.bgSolo();
              }}
            >
              빙고 시작
            </Brick>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">친구와 대결 (2~4인)</p>
            <div className="flex flex-wrap items-center gap-3">
              <Brick
                color="blue"
                onClick={() => {
                  setError(null);
                  socketRef.current?.bgCreate();
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
                    socketRef.current?.bgJoin(code.trim());
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
                <PlayerBadge
                  name={p}
                  profile={profiles[p]}
                  suffix={p === room.host ? " (방장)" : undefined}
                />
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
                onClick={() => socketRef.current?.bgBegin()}
              >
                시작하기 ({room.players.length}/4)
              </Brick>
            )}
            <Brick
              color="yellow"
              onClick={() => {
                socketRef.current?.bgLeave();
                setPhase("lobby");
              }}
            >
              나가기
            </Brick>
          </div>
          {room.host !== myName && (
            <p className="text-xs opacity-60">방장이 시작하면 바로 시작해요!</p>
          )}
          <InviteFriends
            onInvite={(uid) =>
              room.code && socketRef.current?.invite(uid, "bingo", room.code)
            }
          />
        </section>
      )}

      {phase === "countdown" && (
        <p className="animate-pulse font-hand text-6xl font-bold text-brick-blue">
          준비...
        </p>
      )}

      {phase === "playing" && start && (
        <section className="flex max-w-md flex-col gap-3">
          {/* 문제 음성 — 자동 재생 + 다시 듣기, 원어민 구간이 있으면 병행 */}
          <div className="flex flex-wrap items-center gap-2 rounded-lg border-2 border-ink/10 bg-white p-3">
            <button
              type="button"
              disabled={round === null}
              onClick={() => round && speakWord(round.tts)}
              className="min-h-11 rounded-full border-2 border-brick-blue/50 bg-white px-4 font-bold transition hover:border-brick-blue active:scale-95 disabled:opacity-50"
            >
              다시 듣기
            </button>
            {round?.media && (
              <SegmentPlayer media={round.media} label="원어민 발화로 듣기" />
            )}
            <span className="ml-auto text-xs opacity-60">
              들리는 단어를 아래에서 탭!
            </span>
          </div>

          {reveal && (
            <p className="rounded-md bg-highlight/50 px-3 py-1.5 text-center text-sm">
              정답: <b>{reveal.en}</b> — {reveal.ko}
              {reveal.bingo.length > 0 && (
                <span className="ml-2 font-bold text-brick-green">
                  {reveal.bingo.join(", ")} 빙고!
                </span>
              )}
            </p>
          )}

          <div
            className={`grid grid-cols-4 gap-1.5 sm:gap-2 ${locked ? "miss-shake" : ""}`}
          >
            {start.board.map((cell) => {
              const done = filled.has(cell.item_id);
              return (
                <button
                  key={cell.item_id}
                  type="button"
                  disabled={
                    done || locked || reveal !== null || phase !== "playing"
                  }
                  onClick={() => tapCell(cell.item_id)}
                  className={`min-h-14 rounded-md border-2 px-1 py-2 text-xs font-bold break-all transition sm:min-h-16 sm:text-sm ${
                    done
                      ? "border-brick-green bg-brick-green/20 text-brick-green"
                      : "border-ink/15 bg-white hover:-translate-y-0.5 hover:border-brick-blue active:scale-95"
                  }`}
                >
                  {done ? "✓ " : ""}
                  {cell.en}
                </button>
              );
            })}
          </div>

          {/* 다른 플레이어 진행 — 채운 칸 수 */}
          {Object.keys(marks).length > 0 && (
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(marks).map(([name, count]) => (
                <span
                  key={name}
                  className="rounded-full bg-white px-2.5 py-1 font-bold shadow-sm"
                >
                  {name} {count}칸
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {phase === "ended" && end && (
        <section
          ref={resultRef}
          className="flex max-w-md flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6"
        >
          <h2 className="font-hand text-3xl font-bold">
            {end.winner ? (
              <span className="hl">{end.winner} 빙고 승리!</span>
            ) : end.results.length > 1 ? (
              "무승부"
            ) : (
              "듣기 기록 완료!"
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
              <p className="font-bold">
                {r.name}
                {r.bingo_round !== null && (
                  <span className="ml-2 text-sm text-brick-green">
                    빙고! ({r.bingo_round + 1}라운드)
                  </span>
                )}
              </p>
              <p className="mt-1 text-sm opacity-80">
                채운 칸 <b>{r.filled}</b> / 16 · 오답 탭 {r.wrong}
              </p>
            </div>
          ))}
          <ReviewPanel
            items={review}
            source="bingo"
            hint="놓친 단어예요 — 담으면 오늘의 학습 큐에 들어가고 다음 판에도 우선 나와요"
          />
          <div className="flex flex-wrap gap-3">
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.bgSolo();
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
                  game: "리스닝 빙고",
                  headline: end.winner
                    ? `${end.winner} 빙고 승리!`
                    : "듣기 기록",
                  scoreline: `${
                    (end.winner
                      ? end.results.find((r) => r.name === end.winner)
                      : end.results[0]
                    )?.filled ?? 0
                  } / 16칸`,
                  tone: end.winner === myName ? "win" : "neutral",
                  lines: end.results.slice(0, 4).map((r) => ({
                    label: r.name,
                    value: `${r.filled}칸${r.bingo_round !== null ? " · 빙고" : ""}`,
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

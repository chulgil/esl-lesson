"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { InviteFriends } from "@/components/game/InviteFriends";
import { PlayerBadge } from "@/components/game/PlayerBadge";
import { ReviewPanel } from "@/components/game/ReviewPanel";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { BackLink } from "@/components/nav/BackLink";
import { fetchMe } from "@/lib/api";
import { useInviteTheme } from "@/lib/use-invite-theme";
import { useSurfaceSkin } from "@/lib/theme-surfaces";
import {
  GameSocket,
  type GameReviewItem,
  type PlayerProfile,
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
  // 초대 입장(?theme=)이면 게임 동안 초대자 테마 — 종료/이탈 시 자동 복원
  useInviteTheme(phase === "ended");
  // 조립창·단어 칩 — 시험지/학습과 같은 테마 표면 스킨 (2026-07-31 게임 테마화)
  const skin = useSurfaceSkin();
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
  const [chips, setChips] = useState<Chip[]>([]);
  const [placed, setPlaced] = useState(0);
  const [mistakes, setMistakes] = useState(0);
  const [wrongId, setWrongId] = useState<number | null>(null);
  const [doneRound, setDoneRound] = useState(false);
  const [myScore, setMyScore] = useState(0);
  const [lastGain, setLastGain] = useState<number | null>(null);
  const [streak, setStreak] = useState(0); // 라운드 내 연속 정답 칩 — 콤보 연출
  const [countLeft, setCountLeft] = useState(3);
  const [rivals, setRivals] = useState<Record<string, RivalRow>>({});
  const [timeLeft, setTimeLeft] = useState(0);
  const [end, setEnd] = useState<{
    results: ScResult[];
    winner: string | null;
    aborted: boolean;
  } | null>(null);
  const [review, setReview] = useState<GameReviewItem[]>([]);
  const [profiles, setProfiles] = useState<Record<string, PlayerProfile>>({});

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
    setStreak(0);
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
          if (msg.profiles) setProfiles(msg.profiles);
          // 결과 화면에서는 유지 — 재대결 대기 중 새 입장자가 와도 결과를 덮지 않는다
          setPhase((prev) => (prev === "ended" ? prev : "waiting"));
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
          setCountLeft(Math.ceil(msg.countdown));
          setReview([]);
          // 재대결로 새 판이 시작되면 이전 결과·점수를 지운다
          setEnd(null);
          setMyScore(0);
          setLastGain(null);
          setError(null);
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
        case "sc.review":
          setReview(msg.items);
          break;
        case "sc.end":
          setEnd({
            results: msg.results,
            winner: msg.winner,
            aborted: msg.aborted,
          });
          setPhase("ended");
          break;
        case "error":
          setError(
            msg.code === "sentences_insufficient"
              ? "조립할 문장이 아직 부족해요 — 영상을 등록하거나 채팅으로 모아보세요"
              : msg.code === "room_not_found"
                ? "방을 찾을 수 없어요 — 코드를 확인해주세요"
                : msg.code === "room_closed"
                  ? "방장이 나가서 방이 닫혔어요."
                  : msg.code === "room_not_enough_players"
                    ? "함께할 사람이 없어요 — 친구를 초대하거나 혼자 한 번 더로 이어가세요."
                  : msg.code,
          );
          setPhase("lobby");
          break;
      }
    },
    [startRound],
  );

  // 시작 카운트다운 3-2-1
  useEffect(() => {
    if (phase !== "countdown") return;
    const timer = setInterval(
      () => setCountLeft((v) => Math.max(0, v - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [phase]);

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
    // 끊긴 뒤에도 socketRef 가 죽은 소켓을 들고 있어 send() 가 조용히 씹혔다
    // (버그 헌트 2026-08-11) — truthy 체크 대신 isOpen() 으로 재사용 가능 여부 확인
    if (socketRef.current?.isOpen()) {
      action(socketRef.current);
      return;
    }
    // 끊겨도 화면을 로비로 되돌리지 않는다 — 소켓이 자동 재접속하고 서버 attach 가
    // 진행 중 매치를 복원한다 (2026-08-20 재대결·튕김 대응)
    const socket = new GameSocket(
      handleMessage,
      () =>
        setError((prev) => prev ?? "연결이 흔들려요 — 자동으로 다시 잇는 중…"),
      () => setError(null),
    );
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
      setStreak((v) => v + 1);
      setPlaced(nextPlaced);
      socketRef.current?.scProgress(roundIdxRef.current, nextPlaced);
      if (nextPlaced === round.answer.length) {
        setDoneRound(true);
        socketRef.current?.scDone(roundIdxRef.current, mistakes);
      }
    } else {
      setMistakes((m) => m + 1);
      setStreak(0);
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
                  <PlayerBadge
                    name={p}
                    profile={profiles[p]}
                    suffix={p === room.host ? " (방장)" : undefined}
                  />
                </span>
              ))}
            </div>
          </div>
          <InviteFriends
            onInvite={(uid) =>
              room.code && socketRef.current?.invite(uid, "scramble", room.code)
            }
          />
          <div className="flex flex-wrap items-center gap-3">
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
            <Brick
              color="yellow"
              onClick={() => {
                socketRef.current?.scLeave();
                setRoom(null);
                setPhase("lobby");
              }}
            >
              나가기
            </Brick>
          </div>
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
          <p className="mt-2 text-sm opacity-60">
            한글 뜻을 보고 영어 어순으로 조립하세요
          </p>
        </div>
      )}

      {phase === "racing" && round && (
        <section className="flex max-w-2xl flex-col gap-4">
          {/* 진행·점수 — 크게, 조립창 바로 위 (시인성 개선 2026-07-15) */}
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-ink px-3 py-1 font-hand text-xl font-bold text-white">
              {Math.min(roundIdx + 1, total)}
              <span className="opacity-50">/{total}</span>
            </span>
            <span className="rounded-lg bg-brick-yellow px-3 py-1 font-hand text-xl font-bold text-ink">
              {myScore}점
            </span>
            {streak >= 3 && !doneRound && (
              <span
                key={streak}
                className="combo-pulse rounded-full bg-brick-red px-3 py-1 text-sm font-bold text-brick-label"
              >
                x{streak} 콤보!
              </span>
            )}
          </div>

          {/* 조립창 — 물이 차오르며 시간 압박 (남으면 파랑, 촉박하면 빨강) */}
          <div className={`relative overflow-hidden ${skin.section} p-5`}>
            <div
              className={`water-fill ${timeRatio < 0.25 ? "low" : ""}`}
              style={{ height: `${(1 - timeRatio) * 100}%` }}
              aria-hidden
            />
            <div className="relative">
              <p className="text-sm opacity-60">이 뜻이 되도록 조립하세요</p>
              <p className="mt-1 text-lg font-bold">{round.ko || "..."}</p>

              {/* 조립 영역 — 방금 붙인 단어는 팝인 */}
              <p className="mt-4 min-h-8 text-lg font-medium">
                {round.answer.slice(0, Math.max(0, placed - 1)).join(" ")}
                {placed > 0 && (
                  <span key={placed} className="word-pop">
                    {placed > 1 ? " " : ""}
                    {round.answer[placed - 1]}
                  </span>
                )}
                <span className="opacity-30">
                  {placed > 0 && placed < round.answer.length ? " " : ""}
                  {Array.from(
                    { length: round.answer.length - placed },
                    () => "___",
                  ).join(" ")}
                </span>
              </p>

              {doneRound ? (
                <div className="relative mt-4">
                  <p
                    className={`font-hand text-3xl font-bold ${
                      mistakes === 0 ? "text-brick-yellow" : "text-brick-green"
                    }`}
                  >
                    {mistakes === 0 ? "PERFECT!" : "완성!"}
                  </p>
                  {lastGain != null && (
                    <span className="score-pop absolute -top-1 left-32 font-hand text-2xl font-bold text-brick-green">
                      +{lastGain}
                    </span>
                  )}
                  <Burst seed={roundIdx} />
                  <p className="mt-1 text-xs opacity-60">
                    다른 플레이어를 기다려요...
                  </p>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-2">
                  {chips.map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      disabled={chip.used}
                      onClick={() => tapChip(chip)}
                      className={`min-h-11 border-2 px-3 text-sm font-bold transition ${skin.radius} ${
                        chip.used
                          ? `${skin.choice} cursor-default opacity-30`
                          : `${skin.choice} cursor-pointer hover:-translate-y-0.5`
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
          {end.aborted && (
            <p className="text-sm font-bold text-brick-red">
              상대가 중간에 나가 대전이 종료됐어요
            </p>
          )}
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
          <ReviewPanel
            items={review}
            source="scramble"
            noun="문장"
            hint="추가한 문장은 학습 큐에 들어가요 — 문장 카드는 학습 레벨 '고급'에서 출제돼요"
          />
          <div className="flex flex-wrap items-center gap-3">
            {/* 방 게임 재대결 — 서버가 방을 유지해 재입장 없이 다음 판 (2026-08-20) */}
            {room && !end.aborted && room.host === myName && (
              <Brick
                color="green"
                onClick={() => {
                  setError(null);
                  socketRef.current?.scBegin();
                }}
              >
                같은 방에서 다시하기
              </Brick>
            )}
            {room && !end.aborted && room.host !== myName && (
              <span className="text-sm font-bold opacity-70">
                방장이 다시 시작하면 자동으로 이어져요
              </span>
            )}
            <Brick
              color={room && !end.aborted ? "yellow" : "green"}
              onClick={() => {
                setEnd(null);
                setMyScore(0);
                setRoom(null);
                connect((s) => s.scSolo());
              }}
            >
              {room ? "혼자 한 번 더" : "한 번 더"}
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

/** 완성 파티클 — CSS 버스트, 각도는 결정적 (게임다움 기획) */
function Burst({ seed }: { seed: number }) {
  const colors = [
    "bg-brick-red",
    "bg-brick-yellow",
    "bg-brick-blue",
    "bg-brick-green",
  ];
  return (
    <span aria-hidden className="pointer-events-none absolute top-2 left-16">
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

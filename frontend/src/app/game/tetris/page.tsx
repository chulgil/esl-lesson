"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  gameApi,
  type GameProfile,
  type LeaderboardEntry,
} from "@/lib/game-api";
import { useAppTheme } from "@/lib/theme";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { PlayArea } from "@/app/game/PlayArea";
import { ContentPicker } from "@/components/game/ContentPicker";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { InviteFriends } from "@/components/game/InviteFriends";
import { ItemIcon } from "@/components/game/ItemIcon";
import { ModeButton } from "@/components/game/ModeButton";
import {
  GameSocket,
  type MatchEndMsg,
  type MatchFoundMsg,
  type ServerMsg,
  type StateMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "playing" | "ended";

export default function GamePage() {
  return (
    <Suspense>
      <TetrisInner />
    </Suspense>
  );
}

function TetrisInner() {
  const joinCode = useSearchParams().get("join");
  const [phase, setPhase] = useState<Phase>("lobby");
  // 기본 Lv.2 — Lv.3(35WPM)는 실측상 초심자가 이기기 어려움 (2026-07-14 전적 데이터)
  const [botLevel, setBotLevel] = useState(2);
  const [roomCode, setRoomCode] = useState("");
  const [selectedContents, setSelectedContents] = useState<number[]>([]);
  const [myRoomCode, setMyRoomCode] = useState<string | null>(null);
  const [matchInfo, setMatchInfo] = useState<MatchFoundMsg | null>(null);
  const [gameState, setGameState] = useState<StateMsg | null>(null);
  const [endResult, setEndResult] = useState<MatchEndMsg | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [missSignal, setMissSignal] = useState(0);
  const [itemToast, setItemToast] = useState<string | null>(null);
  const [garbageTip, setGarbageTip] = useState(false);
  const appTheme = useAppTheme(); // 전역 테마(설정)를 게임 보드가 따름
  // 오피스(위장) 테마는 게임 보드 스킨이 없어 노트 보드로 폴백
  const boardTheme = appTheme === "excel" ? "note" : appTheme;
  const [profile, setProfile] = useState<GameProfile | null>(null);
  const [leaders, setLeaders] = useState<LeaderboardEntry[]>([]);
  const socketRef = useRef<GameSocket | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const garbageTipShown = useRef(false);
  const prevGarbageCount = useRef(0);

  const handleMessage = useCallback((msg: ServerMsg) => {
    switch (msg.t) {
      case "queue.waiting":
        setPhase("waiting");
        break;
      case "room.created":
        setMyRoomCode(msg.code);
        setPhase("waiting");
        break;
      case "match.found":
        setMatchInfo(msg);
        setEndResult(null);
        garbageTipShown.current = false;
        prevGarbageCount.current = 0;
        setPhase(msg.countdown > 0 ? "countdown" : "playing");
        if (msg.countdown > 0) {
          setTimeout(() => setPhase("playing"), msg.countdown * 1000);
        }
        break;
      case "state":
        setGameState(msg);
        break;
      case "clear.result":
        // 오답은 조용히 지나가면 "왜 안 없어지지?" 혼란 — 셰이크 + 콤보 리셋 표시
        if (!msg.ok && msg.effects.includes("miss")) {
          setMissSignal((n) => n + 1);
        }
        break;
      case "item.gained":
        setItemToast(msg.item);
        setTimeout(() => setItemToast(null), 2500);
        break;
      case "match.end":
        setEndResult(msg);
        setPhase("ended");
        break;
      case "item.result":
        if (msg.ok && msg.item === "hint" && msg.hint_answer) {
          setHint(msg.hint_answer);
          setTimeout(() => setHint(null), 1500);
        }
        break;
      case "error":
        setError(
          {
            room_not_found: "방을 찾을 수 없어요.",
            words_insufficient:
              "게임에 쓸 단어가 부족해요 (최소 10개). 내 콘텐츠를 등록하거나 다른 소재를 선택해주세요.",
            content_not_yours: "내 콘텐츠만 소재로 쓸 수 있어요.",
            content_not_found: "콘텐츠를 찾을 수 없어요.",
            already_in_match:
              "진행 중인 대전이 있어요. 잠시 후 자동 복귀되거나, 10초 뒤 몰수 처리 후 새로 시작할 수 있어요.",
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
      ? setTimeout(() => socket.joinRoom(joinCode), 400)
      : null;
    return () => {
      if (timer) clearTimeout(timer);
      socket.close();
    };
  }, [handleMessage, joinCode]);

  useEffect(() => {
    if (phase === "playing") inputRef.current?.focus();
  }, [phase]);

  // 대전 중에는 전역 하단 탭바를 숨겨 입력바와 겹치지 않게 (집중 모드)
  useEffect(() => {
    const active = phase === "playing" || phase === "countdown";
    document.body.classList.toggle("game-focus", active);
    return () => document.body.classList.remove("game-focus");
  }, [phase]);

  // 내 전적 + 주간 리더보드 (P3 리텐션) — 로비 진입/경기 종료 시 갱신
  useEffect(() => {
    if (phase !== "lobby" && phase !== "ended") return;
    gameApi
      .profile()
      .then(setProfile)
      .catch(() => undefined);
    gameApi
      .leaderboard()
      .then((res) => setLeaders(res.items))
      .catch(() => undefined);
  }, [phase]);

  // 첫 garbage(회색 젤리) 수신 시 1회 설명 토스트 — 정체불명 혼란 방지
  useEffect(() => {
    const count = gameState?.me?.bricks.filter((b) => b.garbage).length ?? 0;
    if (count > prevGarbageCount.current && !garbageTipShown.current) {
      garbageTipShown.current = true;
      setGarbageTip(true);
      setTimeout(() => setGarbageTip(false), 6000);
    }
    prevGarbageCount.current = count;
  }, [gameState]);

  function submitWord() {
    if (!input.trim()) return;
    socketRef.current?.submit(input.trim());
    setInput("");
  }

  function tapChip(chip: string) {
    socketRef.current?.submit(chip);
  }

  function useItem(item: string) {
    socketRef.current?.useItem(item);
  }

  // 재대결 — reload 대신 상태 리셋: PvE 는 같은 설정으로 즉시 한 판 더 (P3)
  function playAgain() {
    const wasPve = matchInfo?.mode === "pve";
    setGameState(null);
    setEndResult(null);
    setMatchInfo(null);
    setHint(null);
    setItemToast(null);
    setGarbageTip(false);
    setMissSignal(0);
    garbageTipShown.current = false;
    prevGarbageCount.current = 0;
    if (wasPve) {
      socketRef.current?.joinPve(
        "en",
        botLevel,
        selectedContents.length ? selectedContents : undefined,
      );
    } else {
      setPhase("lobby");
    }
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        {phase === "lobby" && <BackLink href="/game" label="게임" />}
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">워드 테트리스</span>
        </h1>
        {matchInfo && phase !== "lobby" && (
          <span className="text-sm opacity-60">vs {matchInfo.opponent}</span>
        )}
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {phase === "lobby" && (
        <Lobby
          botLevel={botLevel}
          setBotLevel={setBotLevel}
          roomCode={roomCode}
          setRoomCode={setRoomCode}
          selectedContents={selectedContents}
          setSelectedContents={setSelectedContents}
          profile={profile}
          leaders={leaders}
          onPve={() =>
            socketRef.current?.joinPve(
              "en",
              botLevel,
              selectedContents.length ? selectedContents : undefined,
            )
          }
          onPvp={() => socketRef.current?.joinPvp("en")}
          onCreateRoom={() =>
            socketRef.current?.createRoom(
              "en",
              selectedContents.length ? selectedContents : undefined,
            )
          }
          onJoinRoom={() =>
            roomCode.trim() && socketRef.current?.joinRoom(roomCode.trim())
          }
        />
      )}

      {phase === "waiting" && (
        <section className="flex flex-col items-start gap-4">
          {myRoomCode ? (
            <>
              <p>
                친구에게 방 코드를 알려주세요:{" "}
                <span className="rounded bg-highlight/60 px-3 py-1 font-mono text-2xl font-bold tracking-widest">
                  {myRoomCode}
                </span>
              </p>
              <p className="text-sm opacity-60">
                상대가 입장하면 자동으로 시작됩니다.
              </p>
              <InviteFriends
                onInvite={(uid) =>
                  myRoomCode &&
                  socketRef.current?.invite(uid, "tetris", myRoomCode)
                }
              />
            </>
          ) : (
            <p className="animate-pulse">상대를 찾는 중...</p>
          )}
          <Brick color="yellow" onClick={() => window.location.reload()}>
            취소
          </Brick>
        </section>
      )}

      {phase === "countdown" && (
        <p className="animate-pulse font-hand text-6xl font-bold text-brick-red">
          준비...
        </p>
      )}

      {(phase === "playing" || phase === "ended") && (
        <PlayArea
          me={gameState?.me ?? null}
          op={gameState?.op ?? null}
          elapsed={gameState?.elapsed ?? 0}
          opponentName={matchInfo?.opponent ?? "상대"}
          input={input}
          inputRef={inputRef}
          disabled={phase !== "playing"}
          hint={hint}
          missSignal={missSignal}
          itemToast={itemToast}
          garbageTip={garbageTip}
          boardTheme={boardTheme}
          onInput={setInput}
          onSubmit={submitWord}
          onTap={tapChip}
          onUseItem={useItem}
        />
      )}

      {phase === "ended" && endResult && (
        <ResultPanel
          result={endResult}
          you={matchInfo?.you ?? 1}
          opponent={matchInfo?.opponent ?? "상대"}
          onAgain={playAgain}
        />
      )}
    </main>
  );
}

function Lobby({
  botLevel,
  setBotLevel,
  roomCode,
  setRoomCode,
  selectedContents,
  setSelectedContents,
  profile,
  leaders,
  onPve,
  onPvp,
  onCreateRoom,
  onJoinRoom,
}: {
  botLevel: number;
  setBotLevel: (n: number) => void;
  roomCode: string;
  setRoomCode: (s: string) => void;
  selectedContents: number[];
  setSelectedContents: (ids: number[]) => void;
  profile: GameProfile | null;
  leaders: LeaderboardEntry[];
  onPve: () => void;
  onPvp: () => void;
  onCreateRoom: () => void;
  onJoinRoom: () => void;
}) {
  return (
    <section className="flex max-w-lg flex-col gap-6">
      <div className="rounded-lg border-2 border-ink/10 bg-white p-4 text-sm">
        <p className="mb-2 font-bold">게임 방식</p>
        <ul className="flex flex-col gap-1 opacity-80">
          <li>
            <b className="text-brick-blue">영어 → 한글</b> 구간: 영단어가
            떨어지면 하단 뜻 칩을 <b>탭</b>해서 제거
          </li>
          <li>
            <b className="text-brick-green">한글 → 영어</b> 구간: 영어로{" "}
            <b>타이핑</b> — 철자가 비슷해도 정답!
          </li>
          <li className="opacity-70">
            시간이 지날수록 빨라지고 방향 구간이 번갈아 바뀝니다
          </li>
          <li>
            <b>3콤보</b>마다 상대에게 공격 · <b>8자 이상</b> 단어 클리어도 공격
          </li>
          <li>
            회색 <b>×_× 젤리</b> = 상대의 공격 — 아무 단어나 클리어하면 1개씩
            소멸
          </li>
          <li className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <b>아이템</b> (5콤보/★브릭 클리어):
            <span className="inline-flex items-center gap-0.5">
              <ItemIcon kind="freeze" size={14} />
              3초 멈춤
            </span>
            ·
            <span className="inline-flex items-center gap-0.5">
              <ItemIcon kind="hint" size={14} />
              정답 보기
            </span>
            ·
            <span className="inline-flex items-center gap-0.5">
              <ItemIcon kind="bomb" size={14} />
              젤리 제거
            </span>
            ·
            <span className="inline-flex items-center gap-0.5">
              <ItemIcon kind="shield" size={14} />
              공격 방어
            </span>
          </li>
        </ul>
      </div>

      {((profile?.played ?? 0) > 0 || leaders.length > 0) && (
        <div className="flex flex-wrap gap-4">
          {profile && profile.played > 0 && (
            <div className="min-w-56 flex-1 rounded-lg border-2 border-ink/10 bg-white p-4">
              <p className="mb-2 text-sm font-bold">내 전적</p>
              <p className="text-sm opacity-80">
                <b>
                  {profile.wins}승 {profile.losses}패
                </b>{" "}
                · 최고 점수 <b>{profile.best_score}</b>
              </p>
              <p className="mt-1 text-xs opacity-60">
                최다 콤보 {profile.best_combo} · 최고 WPM {profile.best_wpm}
              </p>
            </div>
          )}
          {leaders.length > 0 && (
            <div className="min-w-56 flex-1 rounded-lg border-2 border-ink/10 bg-white p-4">
              <p className="mb-2 text-sm font-bold">
                주간 리더보드{" "}
                <span className="text-xs font-normal opacity-60">
                  최근 7일 합산
                </span>
              </p>
              <ol className="flex flex-col gap-1 text-sm">
                {leaders.slice(0, 5).map((l, i) => (
                  <li key={`${l.name}-${i}`} className="flex justify-between">
                    <span>
                      {i + 1}. {l.name}
                    </span>
                    <b>{l.score}</b>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      <ContentPicker
        selected={selectedContents}
        onChange={setSelectedContents}
        hint="내 콘텐츠를 고르면 그 단어로 대전 (AI 대전 · 방 만들기, 미선택 시 공용)"
      />

      <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
        <p className="mb-2 text-sm font-bold">AI 대전</p>
        <div className="mb-1 flex gap-1">
          {[1, 2, 3, 4, 5].map((level) => (
            <ModeButton
              key={level}
              active={botLevel === level}
              onClick={() => setBotLevel(level)}
            >
              Lv.{level}
            </ModeButton>
          ))}
        </div>
        <p className="mb-3 text-xs opacity-60">
          봇 타자 속도: Lv.1 느긋(15WPM) · Lv.2 무난(25) · Lv.3 빠름(35) · Lv.4
          고수(50) · Lv.5 괴물(70)
        </p>
        <Brick color="green" onClick={onPve}>
          AI와 대전 시작
        </Brick>
      </div>

      <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
        <p className="mb-3 text-sm font-bold">사람과 대전</p>
        <div className="flex flex-wrap items-center gap-3">
          <Brick color="red" onClick={onPvp}>
            빠른 대전
          </Brick>
          <Brick color="blue" onClick={onCreateRoom}>
            방 만들기
          </Brick>
          <div className="flex items-center gap-2">
            <input
              value={roomCode}
              onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
              placeholder="방 코드"
              maxLength={6}
              className="min-h-11 w-28 rounded-md border-2 border-ink/20 px-2 font-mono uppercase transition-colors focus:border-brick-blue focus:outline-none"
            />
            <Brick color="yellow" onClick={onJoinRoom}>
              입장
            </Brick>
          </div>
        </div>
      </div>
    </section>
  );
}

function ResultPanel({
  result,
  you,
  opponent,
  onAgain,
}: {
  result: MatchEndMsg;
  you: number;
  opponent: string;
  onAgain: () => void;
}) {
  const my = you === 1 ? result.stats.p1 : result.stats.p2;
  const op = you === 1 ? result.stats.p2 : result.stats.p1;
  const titles = { win: "승리!", lose: "패배...", draw: "무승부" } as const;
  const RECORD_LABELS: Record<string, string> = {
    score: "최고 점수",
    max_combo: "최다 콤보",
    wpm: "최고 WPM",
  };
  const records = result.records ?? [];
  return (
    <section className="mt-6 max-w-md rounded-lg border-2 border-ink/10 bg-white p-6">
      <h2
        className={`font-hand text-4xl font-bold ${
          result.winner === "win"
            ? "text-brick-green"
            : result.winner === "lose"
              ? "text-brick-red"
              : ""
        }`}
      >
        {titles[result.winner]}
      </h2>
      {/* 최종 점수 비교 — "왜 이 결과인지"를 한눈에 (전적 인지 버그 수정 2026-07-14) */}
      <p className="mt-2 font-hand text-3xl font-bold">
        <span
          className={result.winner === "win" ? "text-brick-green" : "text-ink"}
        >
          {my.score}
        </span>
        <span className="mx-2 opacity-30">:</span>
        <span
          className={result.winner === "lose" ? "text-brick-red" : "text-ink"}
        >
          {op.score}
        </span>
      </p>
      <p className="text-xs opacity-60">
        나 vs {opponent} — 최종 점수가 높은 쪽이 승리해요
      </p>
      {records.length > 0 && (
        // 개인 기록 경신 — "지난번의 나"를 이기는 순간을 크게 (P3 리텐션)
        <div className="mt-3 flex flex-wrap gap-2">
          {records.map((r) => (
            <span
              key={r}
              className="rounded-full bg-brick-yellow px-3 py-1 text-xs font-bold"
            >
              {RECORD_LABELS[r] ?? r} 경신!
            </span>
          ))}
        </div>
      )}
      <table className="mt-4 w-full text-sm">
        <tbody>
          <Row label="점수" value={my.score} />
          <Row label="처리 단어" value={my.cleared} />
          <Row label="최다 콤보" value={my.max_combo} />
          <Row label="WPM" value={my.wpm} />
          <Row label="정확도" value={`${Math.round(my.accuracy * 100)}%`} />
        </tbody>
      </table>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Brick color="green" onClick={onAgain}>
          다시 하기
        </Brick>
        <Brick color="blue" href="/">
          홈으로
        </Brick>
        <ShareResultButton
          data={{
            game: "워드 테트리스",
            headline: titles[result.winner],
            scoreline: `${my.score} : ${op.score}`,
            tone:
              result.winner === "win"
                ? "win"
                : result.winner === "lose"
                  ? "lose"
                  : "neutral",
            lines: [
              { label: "처리 단어", value: `${my.cleared}개` },
              { label: "최다 콤보", value: `${my.max_combo}콤보` },
              {
                label: "타속",
                value: `${Math.round(my.wpm * 5)}타 (${my.wpm}WPM)`,
              },
              { label: "정확도", value: `${Math.round(my.accuracy * 100)}%` },
            ],
          }}
        />
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: number | string }) {
  return (
    <tr className="border-b border-ink/10">
      <td className="py-1.5 opacity-60">{label}</td>
      <td className="py-1.5 text-right font-bold">{value}</td>
    </tr>
  );
}

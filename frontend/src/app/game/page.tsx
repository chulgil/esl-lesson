"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ContentSummary } from "@/lib/admin-api";
import { useAppTheme } from "@/lib/theme";
import { Brick } from "@/components/brick/Brick";
import { myApi } from "@/lib/my-api";
import { PlayArea } from "@/app/game/PlayArea";
import {
  GameSocket,
  type MatchEndMsg,
  type MatchFoundMsg,
  type ServerMsg,
  type StateMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "playing" | "ended";

export default function GamePage() {
  const [phase, setPhase] = useState<Phase>("lobby");
  const [botLevel, setBotLevel] = useState(3);
  const [roomCode, setRoomCode] = useState("");
  const [myContents, setMyContents] = useState<ContentSummary[]>([]);
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
  const boardTheme = useAppTheme(); // 전역 테마(설정)를 게임 보드가 따름
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
    return () => socket.close();
  }, [handleMessage]);

  useEffect(() => {
    if (phase === "playing") inputRef.current?.focus();
  }, [phase]);

  // 대전 중에는 전역 하단 탭바를 숨겨 입력바와 겹치지 않게 (집중 모드)
  useEffect(() => {
    const active = phase === "playing" || phase === "countdown";
    document.body.classList.toggle("game-focus", active);
    return () => document.body.classList.remove("game-focus");
  }, [phase]);

  useEffect(() => {
    myApi
      .list()
      .then((res) =>
        setMyContents(res.items.filter((c) => c.status === "ready")),
      )
      .catch(() => undefined);
  }, []);

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

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
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
          myContents={myContents}
          selectedContents={selectedContents}
          setSelectedContents={setSelectedContents}
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
        <p className="font-hand text-6xl font-bold text-brick-red">준비...</p>
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
          onAgain={() => window.location.reload()}
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
  myContents,
  selectedContents,
  setSelectedContents,
  onPve,
  onPvp,
  onCreateRoom,
  onJoinRoom,
}: {
  botLevel: number;
  setBotLevel: (n: number) => void;
  roomCode: string;
  setRoomCode: (s: string) => void;
  myContents: ContentSummary[];
  selectedContents: number[];
  setSelectedContents: (ids: number[]) => void;
  onPve: () => void;
  onPvp: () => void;
  onCreateRoom: () => void;
  onJoinRoom: () => void;
}) {
  function toggleContent(id: number) {
    setSelectedContents(
      selectedContents.includes(id)
        ? selectedContents.filter((v) => v !== id)
        : [...selectedContents, id],
    );
  }

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
          <li>
            <b>아이템</b> (5콤보/★브릭 클리어): ❄3초 멈춤 · ?정답 보기 · *젤리
            제거 · ▽공격 방어
          </li>
        </ul>
      </div>

      {myContents.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-bold">
            대전 소재
            <span className="ml-2 text-xs font-normal opacity-60">
              내 콘텐츠를 고르면 그 단어로 대전 (AI 대전 · 방 만들기, 미선택 시
              공용)
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSelectedContents([])}
              className={`rounded px-3 py-1.5 text-sm font-bold ${
                selectedContents.length === 0
                  ? "bg-ink text-white"
                  : "bg-ink/5 hover:bg-ink/10"
              }`}
            >
              공용 전체
            </button>
            {myContents.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => toggleContent(c.id)}
                className={`max-w-56 truncate rounded px-3 py-1.5 text-sm ${
                  selectedContents.includes(c.id)
                    ? "bg-brick-yellow font-bold"
                    : "bg-ink/5 hover:bg-ink/10"
                }`}
              >
                {c.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
        <p className="mb-2 text-sm font-bold">AI 대전</p>
        <div className="mb-3 flex gap-1">
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
              className="w-28 rounded border-2 border-ink/20 px-2 py-2 font-mono uppercase"
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

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-3 py-1.5 text-sm font-bold ${
        active ? "bg-ink text-white" : "bg-ink/5 hover:bg-ink/10"
      }`}
    >
      {children}
    </button>
  );
}

function ResultPanel({
  result,
  you,
  onAgain,
}: {
  result: MatchEndMsg;
  you: number;
  onAgain: () => void;
}) {
  const my = you === 1 ? result.stats.p1 : result.stats.p2;
  const titles = { win: "승리!", lose: "패배...", draw: "무승부" } as const;
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
      <table className="mt-4 w-full text-sm">
        <tbody>
          <Row label="점수" value={my.score} />
          <Row label="처리 단어" value={my.cleared} />
          <Row label="최다 콤보" value={my.max_combo} />
          <Row label="WPM" value={my.wpm} />
          <Row label="정확도" value={`${Math.round(my.accuracy * 100)}%`} />
        </tbody>
      </table>
      <div className="mt-5 flex gap-3">
        <Brick color="green" onClick={onAgain}>
          다시 하기
        </Brick>
        <Brick color="blue" href="/">
          홈으로
        </Brick>
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

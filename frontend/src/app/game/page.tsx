"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BoardCanvas } from "@/components/game/BoardCanvas";
import {
  GameSocket,
  type MatchEndMsg,
  type MatchFoundMsg,
  type ServerMsg,
  type StateMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "playing" | "ended";
type QuizMode = "en" | "ko2en";

export default function GamePage() {
  const [phase, setPhase] = useState<Phase>("lobby");
  const [quiz, setQuiz] = useState<QuizMode>("en");
  const [botLevel, setBotLevel] = useState(3);
  const [roomCode, setRoomCode] = useState("");
  const [myRoomCode, setMyRoomCode] = useState<string | null>(null);
  const [matchInfo, setMatchInfo] = useState<MatchFoundMsg | null>(null);
  const [gameState, setGameState] = useState<StateMsg | null>(null);
  const [endResult, setEndResult] = useState<MatchEndMsg | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const socketRef = useRef<GameSocket | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
        setPhase(msg.countdown > 0 ? "countdown" : "playing");
        if (msg.countdown > 0) {
          setTimeout(() => setPhase("playing"), msg.countdown * 1000);
        }
        break;
      case "state":
        setGameState(msg);
        break;
      case "match.end":
        setEndResult(msg);
        setPhase("ended");
        break;
      case "error":
        setError(
          msg.code === "room_not_found" ? "방을 찾을 수 없어요." : msg.code,
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

  function submitWord() {
    if (!input.trim()) return;
    socketRef.current?.submit(input.trim());
    setInput("");
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        <Link href="/" className="text-sm opacity-60 hover:underline">
          &lt; 홈
        </Link>
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
          quiz={quiz}
          setQuiz={setQuiz}
          botLevel={botLevel}
          setBotLevel={setBotLevel}
          roomCode={roomCode}
          setRoomCode={setRoomCode}
          onPve={() => socketRef.current?.joinPve(quiz, botLevel)}
          onPvp={() => socketRef.current?.joinPvp(quiz)}
          onCreateRoom={() => socketRef.current?.createRoom(quiz)}
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
        <section className="flex flex-col gap-4 lg:flex-row">
          <div className="flex flex-col gap-2">
            <Hud
              label="나"
              board={gameState?.me ?? null}
              elapsed={gameState?.elapsed ?? 0}
            />
            <BoardCanvas
              state={gameState?.me ?? null}
              width={340}
              height={480}
            />
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitWord();
              }}
              disabled={phase !== "playing"}
              placeholder="단어를 입력하고 Enter!"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              className="rounded-md border-2 border-ink/30 bg-white px-4 py-3 text-lg font-bold focus:border-brick-blue focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-2 opacity-90">
            <Hud
              label={matchInfo?.opponent ?? "상대"}
              board={gameState?.op ?? null}
            />
            <BoardCanvas
              state={gameState?.op ?? null}
              width={240}
              height={340}
              mirror
            />
          </div>
        </section>
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
  quiz,
  setQuiz,
  botLevel,
  setBotLevel,
  roomCode,
  setRoomCode,
  onPve,
  onPvp,
  onCreateRoom,
  onJoinRoom,
}: {
  quiz: QuizMode;
  setQuiz: (q: QuizMode) => void;
  botLevel: number;
  setBotLevel: (n: number) => void;
  roomCode: string;
  setRoomCode: (s: string) => void;
  onPve: () => void;
  onPvp: () => void;
  onCreateRoom: () => void;
  onJoinRoom: () => void;
}) {
  return (
    <section className="flex max-w-lg flex-col gap-6">
      <div>
        <p className="mb-2 text-sm font-bold">출제 모드</p>
        <div className="flex gap-2">
          <ModeButton active={quiz === "en"} onClick={() => setQuiz("en")}>
            영단어 타이핑
          </ModeButton>
          <ModeButton
            active={quiz === "ko2en"}
            onClick={() => setQuiz("ko2en")}
          >
            뜻 보고 영단어
          </ModeButton>
        </div>
      </div>

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

function Hud({
  label,
  board,
  elapsed,
}: {
  label: string;
  board: { score: number; combo: number; speed_level: number } | null;
  elapsed?: number;
}) {
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="font-bold">{label}</span>
      <span>점수 {board?.score ?? 0}</span>
      <span
        className={
          board && board.combo >= 3 ? "font-bold text-brick-yellow" : ""
        }
      >
        콤보 {board?.combo ?? 0}
      </span>
      {elapsed !== undefined && (
        <span className="ml-auto opacity-60">
          {Math.max(0, 180 - Math.floor(elapsed))}s
        </span>
      )}
    </div>
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

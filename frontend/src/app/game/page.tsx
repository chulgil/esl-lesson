"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ContentSummary } from "@/lib/admin-api";
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
type QuizMode = "en" | "ko2en";

export default function GamePage() {
  const [phase, setPhase] = useState<Phase>("lobby");
  const [quiz, setQuiz] = useState<QuizMode>("en");
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

  function submitWord() {
    if (!input.trim()) return;
    socketRef.current?.submit(input.trim());
    setInput("");
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
          quiz={quiz}
          setQuiz={setQuiz}
          botLevel={botLevel}
          setBotLevel={setBotLevel}
          roomCode={roomCode}
          setRoomCode={setRoomCode}
          myContents={myContents}
          selectedContents={selectedContents}
          setSelectedContents={setSelectedContents}
          onPve={() =>
            socketRef.current?.joinPve(
              quiz,
              botLevel,
              selectedContents.length ? selectedContents : undefined,
            )
          }
          onPvp={() => socketRef.current?.joinPvp(quiz)}
          onCreateRoom={() =>
            socketRef.current?.createRoom(
              quiz,
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
          onInput={setInput}
          onSubmit={submitWord}
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
  quiz,
  setQuiz,
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
  quiz: QuizMode;
  setQuiz: (q: QuizMode) => void;
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

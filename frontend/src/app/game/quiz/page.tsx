"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { QuizRoyale } from "@/app/game/QuizRoyale";
import { ContentPicker } from "@/components/game/ContentPicker";
import { ModeButton } from "@/components/game/ModeButton";
import { GameSocket, type QrMsg, type ServerMsg } from "@/lib/game-ws";

/** 스피드 퀴즈 로얄 — 최대 4인 버저 퀴즈 (docs/specs/quiz-royale.md) */
export default function QuizRoyalePage() {
  const [selectedContents, setSelectedContents] = useState<number[]>([]);
  const [botLevel, setBotLevel] = useState(3);
  const [bots, setBots] = useState(1);
  const [code, setCode] = useState("");
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<GameSocket | null>(null);
  const qrHandlerRef = useRef<((msg: QrMsg) => void) | null>(null);

  const registerHandler = useCallback((handler: (msg: QrMsg) => void) => {
    qrHandlerRef.current = handler;
  }, []);

  const handleMessage = useCallback((msg: ServerMsg) => {
    if (msg.t.startsWith("qr.")) {
      qrHandlerRef.current?.(msg as QrMsg);
      return;
    }
    if (msg.t === "error") {
      setPlaying(false);
      setError(
        {
          words_insufficient:
            "퀴즈에 쓸 단어가 부족해요 (최소 15개). 다른 소재를 선택해주세요.",
          room_not_found: "방을 찾을 수 없어요.",
          room_full: "방이 가득 찼어요 (최대 4명).",
        }[msg.code] ?? msg.code,
      );
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

  const contentIds = selectedContents.length ? selectedContents : undefined;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        {!playing && <BackLink href="/game" label="게임" />}
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">스피드 퀴즈 로얄</span>
        </h1>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {playing ? (
        <QuizRoyale
          registerHandler={registerHandler}
          onAnswer={(answer) => socketRef.current?.qrAnswer(answer)}
          onStart={() => socketRef.current?.qrStart()}
          onExit={() => {
            socketRef.current?.qrLeave();
            setPlaying(false);
          }}
        />
      ) : (
        <section className="flex max-w-lg flex-col gap-6">
          <div className="rounded-lg border-2 border-ink/10 bg-white p-4 text-sm">
            <p className="mb-2 font-bold">게임 방식</p>
            <ul className="flex flex-col gap-1 opacity-80">
              <li>
                4지선다 <b>10라운드</b> — 전원에게 같은 문제가 동시에 출제돼요
              </li>
              <li>
                정답 = <b>50점 + 남은 시간 보너스</b> (최대 100점) · 오답/미제출
                = 0점
              </li>
              <li>문제당 10초, 한 번 제출하면 수정할 수 없어요</li>
              <li>라운드마다 순위 공개 — 10라운드 합산 1위가 우승!</li>
            </ul>
          </div>

          <ContentPicker
            selected={selectedContents}
            onChange={setSelectedContents}
            hint="내 콘텐츠를 고르면 그 단어로 출제 (미선택 시 공용)"
          />

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-2 text-sm font-bold">AI와 퀴즈</p>
            <div className="mb-1 flex items-center gap-1">
              <span className="mr-1 text-sm opacity-70">봇 수</span>
              {[1, 2, 3].map((n) => (
                <ModeButton
                  key={n}
                  active={bots === n}
                  onClick={() => setBots(n)}
                >
                  {n}명
                </ModeButton>
              ))}
              <span className="ml-3 mr-1 text-sm opacity-70">난이도</span>
              {[1, 3, 5].map((level) => (
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
              봇이 즉시 참가해서 바로 한 판 — 혼자서도 놀 수 있어요
            </p>
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                setPlaying(true);
                socketRef.current?.qrSolo(botLevel, bots, contentIds);
              }}
            >
              AI와 퀴즈 시작
            </Brick>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">친구와 대결 (2~4인)</p>
            <div className="flex flex-wrap items-center gap-3">
              <Brick
                color="blue"
                onClick={() => {
                  setError(null);
                  setPlaying(true);
                  socketRef.current?.qrCreate(contentIds);
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
                    setPlaying(true);
                    socketRef.current?.qrJoin(code.trim());
                  }}
                >
                  입장
                </Brick>
              </div>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

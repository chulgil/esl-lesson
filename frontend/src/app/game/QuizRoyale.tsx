"use client";

import { useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { InviteFriends } from "@/components/game/InviteFriends";
import type {
  QrEndMsg,
  QrMsg,
  QrRank,
  QrRoomMsg,
  QrRoundMsg,
} from "@/lib/game-ws";

type Phase = "waiting" | "round" | "reveal" | "ended";

/** 스피드 퀴즈 로얄 — 대기실/라운드/공개/시상대 (docs/proposal/quiz-royale.md) */
export function QuizRoyale({
  registerHandler,
  onAnswer,
  onStart,
  onExit,
  onInvite,
}: {
  registerHandler: (handler: (msg: QrMsg) => void) => void;
  onAnswer: (answer: string) => void;
  onStart: () => void;
  onExit: () => void;
  onInvite?: (userId: number, code: string) => void;
}) {
  const [phase, setPhase] = useState<Phase>("waiting");
  const [room, setRoom] = useState<QrRoomMsg | null>(null);
  const [round, setRound] = useState<QrRoundMsg | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [answered, setAnswered] = useState<string[]>([]);
  const [reveal, setReveal] = useState<{
    answer: string;
    gains: Record<string, number>;
    scores: QrRank[];
  } | null>(null);
  const [end, setEnd] = useState<QrEndMsg | null>(null);
  const [timeLeft, setTimeLeft] = useState(0);
  const deadlineRef = useRef(0);

  useEffect(() => {
    registerHandler((msg) => {
      switch (msg.t) {
        case "qr.room":
          setRoom(msg);
          setPhase("waiting");
          break;
        case "qr.round":
          setRound(msg);
          setPicked(null);
          setAnswered([]);
          setReveal(null);
          deadlineRef.current = Date.now() + msg.seconds * 1000;
          setPhase("round");
          break;
        case "qr.answered":
          setAnswered((prev) =>
            prev.includes(msg.name) ? prev : [...prev, msg.name],
          );
          break;
        case "qr.reveal":
          setReveal(msg);
          setPhase("reveal");
          break;
        case "qr.end":
          setEnd(msg);
          setPhase("ended");
          break;
      }
    });
  }, [registerHandler]);

  // 남은 시간 타이머 바
  useEffect(() => {
    if (phase !== "round") return;
    const timer = setInterval(() => {
      setTimeLeft(Math.max(0, deadlineRef.current - Date.now()) / 1000);
    }, 100);
    return () => clearInterval(timer);
  }, [phase]);

  function pick(choice: string) {
    if (picked !== null || phase !== "round") return;
    setPicked(choice);
    onAnswer(choice);
  }

  const seconds = round?.seconds ?? 10;

  return (
    <section className="flex max-w-xl flex-col gap-4">
      {phase === "waiting" && room && (
        <div className="flex flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-5">
          {room.code ? (
            <p>
              친구에게 방 코드를 알려주세요:{" "}
              <span className="rounded bg-highlight/60 px-3 py-1 font-mono text-2xl font-bold tracking-widest">
                {room.code}
              </span>
            </p>
          ) : (
            <p className="font-bold">곧 시작합니다...</p>
          )}
          <div className="flex flex-wrap gap-2">
            {room.players.map((p) => (
              <span
                key={p.name}
                className={`rounded-full border-2 px-3 py-1.5 text-sm font-bold ${
                  p.is_bot
                    ? "border-dashed border-ink/30 opacity-70"
                    : "border-brick-blue/40 bg-white"
                }`}
              >
                {p.name}
                {p.name === room.host && " (방장)"}
              </span>
            ))}
            {room.code &&
              Array.from(
                { length: Math.max(0, 4 - room.players.length) },
                (_, i) => (
                  <span
                    key={`empty-${i}`}
                    className="rounded-full border-2 border-dashed border-ink/15 px-3 py-1.5 text-sm opacity-40"
                  >
                    빈 자리
                  </span>
                ),
              )}
          </div>
          <div className="flex gap-3">
            {room.code && (
              <Brick
                color="green"
                onClick={onStart}
                disabled={room.players.length < 2}
              >
                시작하기 ({room.players.length}/4)
              </Brick>
            )}
            <Brick color="yellow" onClick={onExit}>
              나가기
            </Brick>
          </div>
          {room.code && room.players.length < 2 && (
            <p className="text-xs opacity-60">
              2명 이상 모이면 방장이 시작할 수 있어요
            </p>
          )}
          {room.code && onInvite && (
            <InviteFriends onInvite={(uid) => onInvite(uid, room.code!)} />
          )}
        </div>
      )}

      {(phase === "round" || phase === "reveal") && round && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-white px-3 py-1 text-sm font-bold shadow-sm">
              {round.no} / {round.total}
            </span>
            {/* 타이머 바 — 줄어드는 형광펜 */}
            <div className="h-3 flex-1 overflow-hidden rounded-full bg-ink/10">
              <div
                className={`h-full rounded-full transition-[width] duration-100 ${
                  timeLeft / seconds < 0.3 ? "bg-brick-red" : "bg-brick-yellow"
                }`}
                style={{
                  width: `${phase === "round" ? (timeLeft / seconds) * 100 : 0}%`,
                }}
              />
            </div>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-6 text-center">
            <p className="font-hand text-4xl font-bold">{round.prompt}</p>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {round.choices.map((choice) => {
              const isAnswer = reveal?.answer === choice;
              const isPicked = picked === choice;
              return (
                <button
                  key={choice}
                  type="button"
                  disabled={picked !== null || phase === "reveal"}
                  onClick={() => pick(choice)}
                  className={`min-h-14 rounded-md border-2 px-4 py-2 text-left font-medium transition active:scale-95 ${
                    phase === "reveal"
                      ? isAnswer
                        ? "border-brick-green bg-brick-green/15 font-bold"
                        : isPicked
                          ? "border-brick-red bg-brick-red/10 opacity-70"
                          : "border-ink/10 opacity-40"
                      : isPicked
                        ? "border-brick-blue bg-brick-blue/10 font-bold"
                        : "border-ink/15 bg-white hover:-translate-y-0.5 hover:border-brick-blue disabled:opacity-60"
                  }`}
                >
                  {choice}
                </button>
              );
            })}
          </div>

          {phase === "round" && (
            <p className="text-sm opacity-60">
              {picked
                ? "제출 완료 — 다른 참가자를 기다리는 중..."
                : "빠를수록 점수가 높아요!"}
              {answered.length > 0 && ` (제출: ${answered.join(", ")})`}
            </p>
          )}

          {phase === "reveal" && reveal && (
            <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
              <ol className="flex flex-col gap-1 text-sm">
                {reveal.scores.map((s) => (
                  <li key={s.name} className="flex justify-between">
                    <span>
                      {s.rank}. {s.name}
                      {(reveal.gains[s.name] ?? 0) > 0 && (
                        <b className="ml-2 text-brick-green">
                          +{reveal.gains[s.name]}
                        </b>
                      )}
                    </span>
                    <b>{s.score}</b>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {phase === "ended" && end && (
        <div className="flex flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6">
          <h2 className="font-hand text-3xl font-bold">
            {end.ranking[0] && (
              <span className="hl">{end.ranking[0].name} 우승!</span>
            )}
          </h2>
          <ol className="flex flex-col gap-2">
            {end.ranking.map((r) => (
              <li
                key={r.name}
                className={`flex items-center justify-between rounded-md border-2 px-4 py-2 ${
                  r.rank === 1
                    ? "border-brick-yellow bg-highlight/40 font-bold"
                    : "border-ink/10"
                }`}
              >
                <span>
                  {r.rank}위 {r.name}
                  {r.is_bot && (
                    <span className="ml-1 text-xs opacity-50">(봇)</span>
                  )}
                </span>
                <b>{r.score}점</b>
              </li>
            ))}
          </ol>
          <div className="flex gap-3">
            <Brick color="blue" onClick={onExit}>
              로비로
            </Brick>
          </div>
        </div>
      )}
    </section>
  );
}

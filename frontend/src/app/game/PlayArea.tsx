"use client";

import { useEffect, useState } from "react";
import { BoardCanvas } from "@/components/game/BoardCanvas";
import type { BoardState } from "@/lib/game-ws";

function useIsDesktop(): boolean {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return desktop;
}

/** 대전 화면 레이아웃 — 데스크톱: 중앙 대형 보드 + 우측 상대/HUD, 모바일: 상대 스트립 상단 고정 + 내 보드 + 하단 입력 */
export function PlayArea({
  me,
  op,
  elapsed,
  opponentName,
  input,
  inputRef,
  disabled,
  onInput,
  onSubmit,
}: {
  me: BoardState | null;
  op: BoardState | null;
  elapsed: number;
  opponentName: string;
  input: string;
  inputRef: React.RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onInput: (v: string) => void;
  onSubmit: () => void;
}) {
  const isDesktop = useIsDesktop();
  const timeLeft = Math.max(0, 180 - Math.floor(elapsed));

  const inputBox = (
    <input
      ref={inputRef}
      value={input}
      onChange={(e) => onInput(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onSubmit();
      }}
      disabled={disabled}
      placeholder="단어 입력 후 Enter"
      autoComplete="off"
      autoCapitalize="off"
      autoCorrect="off"
      spellCheck={false}
      enterKeyHint="send"
      className="w-full rounded-lg border-2 border-ink/30 bg-white px-4 py-3 text-center text-xl font-bold shadow-sm focus:border-brick-blue focus:outline-none"
    />
  );

  if (isDesktop) {
    return (
      <section className="flex items-start justify-center gap-8">
        {/* 내 보드 (대형) */}
        <div className="flex flex-col items-center gap-3">
          <ScoreHud label="나" board={me} timeLeft={timeLeft} big />
          <BoardCanvas state={me} width={420} height={600} />
          <div className="w-[420px]">{inputBox}</div>
        </div>
        {/* 상대 + 정보 패널 */}
        <aside className="mt-9 flex w-64 flex-col gap-4">
          <div>
            <p className="mb-1 text-sm font-bold opacity-70">vs {opponentName}</p>
            <BoardCanvas state={op} width={256} height={366} mirror />
          </div>
          <ScoreHud label={opponentName} board={op} />
          <ComboMeter combo={me?.combo ?? 0} />
        </aside>
      </section>
    );
  }

  // 모바일: 상대 미니 보드 상단 고정, 내 보드 중앙, 입력 하단 고정
  return (
    <section className="flex flex-col gap-3 pb-24">
      <div className="sticky top-14 z-20 flex items-center gap-3 rounded-lg border-2 border-ink/10 bg-paper/95 p-2 backdrop-blur">
        <BoardCanvas state={op} width={90} height={128} mirror />
        <div className="flex-1">
          <p className="text-xs font-bold opacity-70">vs {opponentName}</p>
          <p className="text-sm">점수 {op?.score ?? 0}</p>
          {op?.danger && <p className="text-xs font-bold text-brick-red">상대 위기!</p>}
        </div>
        <div className="text-right">
          <p className="font-hand text-2xl font-bold">{timeLeft}</p>
          <p className="text-[10px] opacity-50">초</p>
        </div>
      </div>

      <ScoreHud label="나" board={me} timeLeft={timeLeft} hideTime />
      <div className="flex justify-center">
        <BoardCanvas state={me} width={340} height={486} />
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-ink/15 bg-white/95 p-3 backdrop-blur">
        {inputBox}
      </div>
    </section>
  );
}

function ScoreHud({
  label,
  board,
  timeLeft,
  big = false,
  hideTime = false,
}: {
  label: string;
  board: BoardState | null;
  timeLeft?: number;
  big?: boolean;
  hideTime?: boolean;
}) {
  const combo = board?.combo ?? 0;
  return (
    <div
      className={`flex w-full items-center gap-4 rounded-lg border-2 border-ink/10 bg-white px-4 py-2 ${
        big ? "text-base" : "text-sm"
      }`}
    >
      <span className="font-bold">{label}</span>
      <span>
        점수 <b>{board?.score ?? 0}</b>
      </span>
      <span
        className={
          combo >= 3
            ? "rounded bg-brick-yellow px-2 font-bold text-ink transition-transform"
            : "opacity-70"
        }
        style={combo >= 3 ? { transform: `scale(${1 + Math.min(combo, 10) * 0.03})` } : undefined}
      >
        콤보 {combo}
      </span>
      {!hideTime && timeLeft !== undefined && (
        <span className="ml-auto font-hand text-xl font-bold">{timeLeft}s</span>
      )}
    </div>
  );
}

/** 콤보 게이지 — 데스크톱 사이드 패널에서 콤보를 시각적으로 즐기게 */
function ComboMeter({ combo }: { combo: number }) {
  return (
    <div className="rounded-lg border-2 border-ink/10 bg-white p-3">
      <p className="text-xs font-bold opacity-60">콤보</p>
      <p
        className={`font-hand font-bold leading-none transition-all ${
          combo >= 6 ? "text-brick-red" : combo >= 3 ? "text-brick-yellow" : "text-ink/40"
        }`}
        style={{ fontSize: `${Math.min(64, 28 + combo * 4)}px` }}
      >
        {combo}
      </p>
      <div className="mt-2 flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={`h-2 flex-1 rounded-sm ${
              i < combo ? "bg-brick-yellow" : "bg-ink/10"
            }`}
          />
        ))}
      </div>
      <p className="mt-2 text-[11px] opacity-50">3콤보마다 상대 공격!</p>
    </div>
  );
}


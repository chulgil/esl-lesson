"use client";

import { useEffect, useState } from "react";
import { BoardCanvas, type BoardTheme } from "@/components/game/BoardCanvas";
import { ItemIcon } from "@/components/game/ItemIcon";
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
// label 에 효과를 내장 — 첫 사용자도 버튼만 보고 뭘 하는지 알게
const ITEM_META: Record<string, { label: string; desc: string }> = {
  freeze: {
    label: "3초 멈춤",
    desc: "3초간 내 보드 낙하/생성 정지",
  },
  hint: {
    label: "정답 보기",
    desc: "가장 위험한 브릭의 정답을 표시",
  },
  bomb: {
    label: "젤리 제거",
    desc: "상대가 보낸 회색 젤리 전부 제거",
  },
  shield: { label: "공격 방어", desc: "다음 공격 1회 무효화" },
};

export function PlayArea({
  me,
  op,
  elapsed,
  opponentName,
  input,
  inputRef,
  disabled,
  hint,
  missSignal,
  itemToast,
  garbageTip,
  boardTheme,
  onInput,
  onSubmit,
  onTap,
  onUseItem,
}: {
  me: BoardState | null;
  op: BoardState | null;
  elapsed: number;
  opponentName: string;
  input: string;
  inputRef: React.RefObject<HTMLInputElement | null>;
  disabled: boolean;
  hint: string | null;
  missSignal: number;
  itemToast: string | null;
  garbageTip: boolean;
  boardTheme: BoardTheme;
  onInput: (v: string) => void;
  onSubmit: () => void;
  onTap: (chip: string) => void;
  onUseItem: (item: string) => void;
}) {
  const isDesktop = useIsDesktop();
  const timeLeft = Math.max(0, 180 - Math.floor(elapsed));

  // 오답 피드백 — 셰이크 + "콤보 리셋" 표시 (조용한 실패 방지)
  const [missFlash, setMissFlash] = useState(false);
  useEffect(() => {
    if (missSignal === 0) return;
    setMissFlash(true);
    const t = setTimeout(() => setMissFlash(false), 600);
    return () => clearTimeout(t);
  }, [missSignal]);

  // 입력 방식: 칩 있는 브릭(tap) / 칩 없는 일반 브릭(type). 구간 전환 시 공존 가능.
  const hasTapBricks = (me?.bricks ?? []).some((b) => !b.garbage && b.chip);
  const hasTypeBricks = (me?.bricks ?? []).some(
    (b) => !b.garbage && !b.item && !b.chip,
  );
  const direction = me?.direction ?? "en2ko";
  const inputMode = me?.input_mode ?? "tap";

  const itemBar = (
    <ItemBar
      items={me?.items ?? []}
      disabled={disabled}
      onUse={onUseItem}
      shield={me?.shield ?? 0}
    />
  );

  const typeBox = (
    <input
      ref={inputRef}
      value={input}
      onChange={(e) => onInput(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onSubmit();
      }}
      disabled={disabled}
      placeholder="영어 단어 입력 후 Enter"
      autoComplete="off"
      autoCapitalize="off"
      autoCorrect="off"
      spellCheck={false}
      enterKeyHint="send"
      className="w-full rounded-lg border-2 border-ink/30 bg-white px-4 py-3 text-center text-xl font-bold shadow-sm focus:border-brick-blue focus:outline-none"
    />
  );

  const tapRow = (
    <div className="flex flex-wrap justify-center gap-2">
      {(me?.chips ?? []).map((chip) => (
        <button
          key={chip}
          type="button"
          disabled={disabled}
          onClick={() => onTap(chip)}
          className={`min-h-11 rounded-full border-2 px-4 py-2 font-bold shadow-sm transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95 disabled:opacity-50 ${
            hint === chip
              ? "border-brick-yellow bg-highlight/60"
              : "border-brick-blue/40 bg-white hover:border-brick-blue"
          }`}
        >
          {chip}
        </button>
      ))}
    </div>
  );

  // 입력 영역: 칩(tap) 브릭 있으면 칩, 타이핑(type) 브릭 있으면 입력. 공존 시 둘 다.
  const interact = (
    <div className={`flex flex-col gap-2 ${missFlash ? "miss-shake" : ""}`}>
      {missFlash && (
        <p className="text-center text-base font-bold text-brick-red">
          오답! 콤보 리셋
        </p>
      )}
      {itemToast && ITEM_META[itemToast] && (
        <p className="text-center text-base font-bold text-ink">
          <span className="inline-flex items-center gap-1.5 rounded bg-brick-yellow/40 px-2 py-0.5">
            + <ItemIcon kind={itemToast} size={16} />
            {ITEM_META[itemToast].label} 획득!
          </span>
        </p>
      )}
      {garbageTip && (
        <p className="rounded-md bg-brick-red/10 px-3 py-2 text-center text-sm font-bold text-brick-red">
          회색 ×_× 젤리 = 상대의 공격! 아무 단어나 클리어하면 1개씩 사라져요
        </p>
      )}
      {hint && (
        // 힌트는 아이템 사용의 결과 — 작게 보이면 소비한 보람이 없음, 크게
        <p className="rounded-md bg-highlight/60 py-1 text-center text-lg font-bold text-ink">
          힌트: {hint}
        </p>
      )}
      {hasTapBricks && tapRow}
      {hasTypeBricks && typeBox}
      {!hasTapBricks && !hasTypeBricks && inputMode === "type" && typeBox}
    </div>
  );

  if (isDesktop) {
    return (
      <section className="flex items-start justify-center gap-8">
        <div className="flex flex-col items-center gap-3">
          <ScoreHud label="나" board={me} timeLeft={timeLeft} big />
          <DirectionBadge direction={direction} inputMode={inputMode} />
          <BoardCanvas state={me} width={420} height={600} theme={boardTheme} />
          {itemBar}
          <div className="w-[440px]">{interact}</div>
        </div>
        <aside className="mt-9 flex w-64 flex-col gap-4">
          <div>
            <p className="mb-1 text-sm font-bold opacity-70">
              vs {opponentName}
            </p>
            <BoardCanvas
              state={op}
              width={256}
              height={366}
              mirror
              theme={boardTheme}
            />
          </div>
          <ScoreHud label={opponentName} board={op} />
          <ComboMeter combo={me?.combo ?? 0} />
        </aside>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3 pb-40">
      <div className="sticky top-14 z-20 flex items-center gap-3 rounded-lg border-2 border-ink/10 bg-paper/95 p-2 backdrop-blur">
        <BoardCanvas
          state={op}
          width={90}
          height={128}
          mirror
          theme={boardTheme}
        />
        <div className="flex-1">
          <p className="text-xs font-bold opacity-70">vs {opponentName}</p>
          <p className="text-sm">점수 {op?.score ?? 0}</p>
          {op?.danger && (
            <p className="text-xs font-bold text-brick-red">상대 위기!</p>
          )}
        </div>
        <div className="text-right">
          <p className="font-hand text-2xl font-bold">{timeLeft}</p>
          <p className="text-[10px] opacity-50">초</p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <ScoreHud label="나" board={me} timeLeft={timeLeft} hideTime />
      </div>
      <DirectionBadge direction={direction} inputMode={inputMode} />
      <div className="flex justify-center">
        <BoardCanvas state={me} width={340} height={486} theme={boardTheme} />
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 flex flex-col gap-2 border-t-2 border-ink/15 bg-white/95 p-3 backdrop-blur">
        {itemBar}
        {interact}
      </div>
    </section>
  );
}

function DirectionBadge({
  direction,
  inputMode,
}: {
  direction: "en2ko" | "ko2en";
  inputMode: "tap" | "type";
}) {
  const en2ko = direction === "en2ko";
  const label =
    inputMode === "type"
      ? "한글 → 영어 (타이핑, 고급)"
      : en2ko
        ? "영어 → 한글 (뜻 탭)"
        : "한글 → 영어 (단어 탭)";
  return (
    // "지금 뭘 해야 하는가"의 1차 신호 — text-base 로 키워 인지 우선
    <div
      className={`rounded-full px-5 py-1.5 text-base font-bold ${
        inputMode === "type"
          ? "bg-brick-red/15 text-brick-red"
          : en2ko
            ? "bg-brick-blue/15 text-brick-blue"
            : "bg-brick-green/15 text-brick-green"
      }`}
    >
      {label}
    </div>
  );
}

function ItemBar({
  items,
  disabled,
  shield,
  onUse,
}: {
  items: string[];
  disabled: boolean;
  shield: number;
  onUse: (item: string) => void;
}) {
  if (items.length === 0 && shield === 0) {
    return (
      <p className="text-center text-xs opacity-40">
        아이템 없음 — 5콤보 또는 ★브릭 클리어로 획득
      </p>
    );
  }
  return (
    <div className="flex items-center justify-center gap-2">
      {shield > 0 && (
        <span className="inline-flex items-center gap-1 rounded-md bg-brick-green/20 px-2 py-1 text-xs font-bold text-brick-green">
          <ItemIcon kind="shield" size={14} /> 공격 방어 x{shield}
        </span>
      )}
      {items.map((item, i) => {
        const meta = ITEM_META[item];
        return (
          <button
            key={`${item}-${i}`}
            type="button"
            disabled={disabled}
            onClick={() => onUse(item)}
            className="flex min-h-11 items-center gap-1.5 rounded-md border-2 border-brick-yellow/60 bg-brick-yellow/20 px-3 font-bold transition hover:-translate-y-0.5 hover:border-brick-yellow active:translate-y-0 active:scale-95 disabled:opacity-50"
            title={meta?.desc}
          >
            <ItemIcon kind={item} size={18} />
            <span className="text-sm">{meta?.label}</span>
          </button>
        );
      })}
    </div>
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
        style={
          combo >= 3
            ? { transform: `scale(${1 + Math.min(combo, 10) * 0.03})` }
            : undefined
        }
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
          combo >= 6
            ? "text-brick-red"
            : combo >= 3
              ? "text-brick-yellow"
              : "text-ink/40"
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

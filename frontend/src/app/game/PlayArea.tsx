"use client";

import { useEffect, useState } from "react";
import { BoardCanvas, type BoardTheme } from "@/components/game/BoardCanvas";
import { ItemIcon } from "@/components/game/ItemIcon";
import { PlayerBadge } from "@/components/game/PlayerBadge";
import type { BoardState, PlayerProfile } from "@/lib/game-ws";

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
  opponentProfile,
  disabled,
  hint,
  missSignal,
  itemToast,
  garbageTip,
  boardTheme,
  onTap,
  onUseItem,
}: {
  me: BoardState | null;
  op: BoardState | null;
  elapsed: number;
  opponentName: string;
  opponentProfile?: PlayerProfile | null;
  disabled: boolean;
  hint: string | null;
  missSignal: number;
  itemToast: string | null;
  garbageTip: boolean;
  boardTheme: BoardTheme;
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

  // 입력은 칩 탭 전용 — 타이핑 구간 폐지 (2026-08-03). 칩 없는 브릭은 garbage 뿐.
  const hasTapBricks = (me?.bricks ?? []).some((b) => !b.garbage && b.chip);
  const direction = me?.direction ?? "en2ko";

  const itemBar = (
    <ItemBar
      items={me?.items ?? []}
      disabled={disabled}
      onUse={onUseItem}
      shield={me?.shield ?? 0}
    />
  );

  // 학습카드式 보기 그룹 (3+3+2, 최대 8) — 첫 그룹 = 가장 급한 브릭의 보기.
  // chip_groups 미지원 서버(배포 스큐)면 평탄 chips 를 한 그룹으로 폴백.
  const chipGroups = me?.chip_groups ?? (me?.chips?.length ? [me.chips] : []);

  const tapRow = (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
      {chipGroups.map((group, gi) => (
        <div key={gi} className="flex flex-wrap justify-center gap-1.5">
          {group.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={disabled}
              onClick={() => onTap(chip)}
              className={`rounded-full border-2 font-bold shadow-sm transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95 disabled:opacity-50 ${
                gi === 0
                  ? // 모바일 칩을 한 단계 키움(+8px) — 하단 선택지가 좁다는 보고 (2026-08-11)
                    "min-h-12 px-3.5 py-2 text-sm sm:min-h-11 sm:px-4 sm:py-2 sm:text-base"
                  : "min-h-11 px-3 py-1.5 text-xs sm:min-h-10 sm:px-3 sm:py-1.5 sm:text-sm"
              } ${
                hint === chip
                  ? "border-brick-yellow bg-highlight/60"
                  : gi === 0
                    ? "border-brick-blue/50 bg-white hover:border-brick-blue"
                    : "border-ink/20 bg-white hover:border-brick-blue/60"
              }`}
            >
              {chip}
            </button>
          ))}
        </div>
      ))}
    </div>
  );

  // 하단 배너(오답/아이템획득/힌트/젤리안내)는 각자 독립 타이머라 동시에 여러 개가
  // 뜰 수 있었고, 쌓인 높이가 모바일 예약 여백(pb-44)을 넘으면 보드를 가렸다
  // (버그 헌트 2026-08-11) — 우선순위 1개만 렌더해 높이를 고정폭으로 예측 가능하게 만든다
  const banner = missFlash ? (
    <p className="text-center text-base font-bold text-brick-red">
      오답! 콤보 리셋
    </p>
  ) : itemToast && ITEM_META[itemToast] ? (
    <p className="text-center text-base font-bold text-ink">
      <span className="inline-flex items-center gap-1.5 rounded bg-brick-yellow/40 px-2 py-0.5">
        + <ItemIcon kind={itemToast} size={16} />
        {ITEM_META[itemToast].label} 획득!
      </span>
    </p>
  ) : hint ? (
    // 힌트는 아이템 사용의 결과 — 작게 보이면 소비한 보람이 없음, 크게
    <p className="rounded-md bg-highlight/60 py-1 text-center text-lg font-bold text-ink">
      힌트: {hint}
    </p>
  ) : garbageTip ? (
    <p className="rounded-md bg-brick-red/10 px-3 py-2 text-center text-sm font-bold text-brick-red">
      회색 ×_× 젤리 = 상대의 공격! 아무 단어나 클리어하면 1개씩 사라져요
    </p>
  ) : null;

  // 입력 영역: 급한 브릭 순 학습카드式 보기 그룹 (정답 + 오답) — 탭으로만 클리어
  const interact = (
    <div className={`flex flex-col gap-2 ${missFlash ? "miss-shake" : ""}`}>
      {banner}
      {hasTapBricks && tapRow}
    </div>
  );

  if (isDesktop) {
    return (
      <section className="flex items-start justify-center gap-8">
        <div className="flex flex-col items-center gap-3">
          <ScoreHud label="나" board={me} timeLeft={timeLeft} big />
          <DirectionBadge direction={direction} />
          <BoardCanvas state={me} width={420} height={600} theme={boardTheme} />
          {itemBar}
          <div className="w-[440px]">{interact}</div>
        </div>
        <aside className="mt-9 flex w-64 flex-col gap-4">
          <div>
            <p className="mb-1 text-sm font-bold opacity-70">
              vs <PlayerBadge name={opponentName} profile={opponentProfile} />
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
    // pb-52: 하단 고정 바가 칩 확대(+20px, 2026-08-11 보고)로 높아진 만큼 보드 여백도 확보
    <section className="flex flex-col gap-3 pb-52">
      <div className="flex items-center justify-between">
        <ScoreHud label="나" board={me} timeLeft={timeLeft} />
      </div>
      <DirectionBadge direction={direction} />
      <div className="flex justify-center">
        {/* 상대 화면은 내 보드 우상단 반투명 PiP — 상단 스트립을 없애 내 보드가
            화면을 넓게 쓴다 (2026-08-10 모바일 기획) */}
        <div className="relative">
          <BoardCanvas state={me} width={340} height={486} theme={boardTheme} />
          <div className="pointer-events-none absolute right-1.5 top-1.5 flex flex-col items-end gap-0.5 opacity-70">
            <BoardCanvas
              state={op}
              width={90}
              height={128}
              mirror
              theme={boardTheme}
            />
            <p className="rounded bg-white/85 px-1.5 py-0.5 text-[10px] font-bold leading-tight text-ink">
              <PlayerBadge name={opponentName} profile={opponentProfile} />{" "}
              {op?.score ?? 0}점
              {op?.danger && <span className="ml-1 text-brick-red">위기!</span>}
            </p>
          </div>
        </div>
      </div>

      <div
        className="fixed inset-x-0 bottom-0 z-30 flex flex-col gap-3 border-t-2 border-ink/15 bg-white/95 px-3 pt-4 backdrop-blur"
        // 홈 인디케이터/브라우저 바에 칩이 붙어 탭하기 힘들던 문제 (2026-08-11 보고)
        // — safe-area 만큼 바닥 여백을 확보한다
        style={{ paddingBottom: "max(1.25rem, env(safe-area-inset-bottom))" }}
      >
        {itemBar}
        {interact}
      </div>
    </section>
  );
}

function DirectionBadge({ direction }: { direction: "en2ko" | "ko2en" }) {
  const en2ko = direction === "en2ko";
  return (
    // "지금 뭘 해야 하는가"의 1차 신호 — text-base 로 키워 인지 우선
    <div
      className={`rounded-full px-5 py-1.5 text-base font-bold ${
        en2ko
          ? "bg-brick-blue/15 text-brick-blue"
          : "bg-brick-green/15 text-brick-green"
      }`}
    >
      {en2ko ? "영어 → 한글 (뜻 탭)" : "한글 → 영어 (단어 탭)"}
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
}: {
  label: string;
  board: BoardState | null;
  timeLeft?: number;
  big?: boolean;
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
      {timeLeft !== undefined && (
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

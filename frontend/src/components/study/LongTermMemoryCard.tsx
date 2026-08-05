import type { LongTermMemory } from "@/lib/study-api";

/** 장기 기억 카드 — stability 7일+ 카드 수를 "의미 있게" 보여준다.
 *
 *  2026-08-05 재설계 (인지심리 감사 — user-journey-motivation-2026-08.md):
 *  기존 8주 누적 막대는 항상 우상향 계단이라 변화가 안 보였고, 축·수치가
 *  없어 장식으로 스캔되고 무시됐다. 사람은 절대수보다 "변화량"과 "기준
 *  대비"를 지각한다 (듀오링고 주간 XP 막대=수치 라벨, 말해보카=비교 앵커,
 *  Apple 활동링=목표 대비 채움 사례):
 *  1) 앵커 — 만난 카드 중 몇 %가 장기 기억인지 진행바
 *  2) 변화 — 최근 4주 "주별 신규 도달" 막대 + 막대마다 +N 수치 라벨 */
export function LongTermMemoryCard({
  data,
  metCount,
}: {
  data: LongTermMemory;
  metCount: number;
}) {
  // 누적 시계열 -> 주별 신규 도달 (변화량). 최근 5주 슬라이스 -> 델타 4개
  const recent = data.weekly.slice(-5);
  const deltas = recent
    .slice(1)
    .map((w, i) => Math.max(0, w.count - recent[i].count));
  const labels = ["3주 전", "2주 전", "지난주", "이번 주"].slice(
    -deltas.length,
  );
  const maxGain = Math.max(1, ...deltas);
  const thisWeekGain = deltas.length ? deltas[deltas.length - 1] : 0;
  const pct =
    metCount > 0 ? Math.min(100, Math.round((data.count / metCount) * 100)) : 0;

  return (
    <div className="mt-4 rounded-md border-2 border-brick-green/40 bg-brick-green/5 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-sm font-bold">장기 기억</span>
        <span className="font-hand text-2xl font-bold text-brick-green">
          {data.count}개
        </span>
        {thisWeekGain > 0 && (
          <span className="rounded bg-brick-green/15 px-1.5 py-0.5 text-xs font-bold text-brick-green">
            이번 주 +{thisWeekGain}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs opacity-60">
        일주일 넘게 안 봐도 기억하는 카드 — 복습이 쌓아 올린 진짜 실력이에요
      </p>

      {/* 앵커: 만난 카드 대비 비율 — "24개"가 어느 정도인지 기준을 준다 */}
      {metCount > 0 && (
        <div className="mt-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="opacity-60">만난 카드 {metCount}개 중</span>
            <span className="font-bold text-brick-green">{pct}%</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded bg-ink/10">
            <div
              className="h-full rounded bg-brick-green transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {/* 변화: 주별 신규 도달 — 수치 라벨이 있는 막대만 읽힌다 */}
      {deltas.some((gain) => gain > 0) && (
        <div
          className="mt-3 flex items-end gap-2"
          aria-label="최근 4주 주별 장기 기억 신규 도달"
        >
          {deltas.map((gain, i) => (
            <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
              <span
                className={`text-xs font-bold ${
                  gain > 0 ? "text-brick-green" : "opacity-30"
                }`}
              >
                {gain > 0 ? `+${gain}` : "·"}
              </span>
              <div
                className={`w-full rounded-sm ${
                  gain > 0 ? "bg-brick-green/70" : "bg-ink/10"
                }`}
                style={{ height: `${Math.max(6, (gain / maxGain) * 40)}px` }}
              />
              <span className="text-[10px] opacity-50">{labels[i]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

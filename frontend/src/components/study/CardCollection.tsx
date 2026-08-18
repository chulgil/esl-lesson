"use client";

import type { Stats } from "@/lib/study-api";

/** 내 카드 컬렉션 — 누적 자산 지표. 홈(오늘)이 아니라 학습 탭(누적)에 둔다
 *  (2026-08-03 IA 정리: 오늘 행동과 누적 지표를 같은 층에 놓지 않는다).
 *
 *  막대 8칸 = 담은 콘텐츠 전체(available_items) 100%. 칸을 카드 수로 세면
 *  8장 이상이 전부 꽉 찬 막대가 되어 512/20000 과 8/8 이 같아 보인다. */

const COLLECTION_SLOTS = 8;

const LEVEL_COLORS = [
  "bg-brick-red",
  "bg-brick-yellow",
  "bg-brick-blue",
  "bg-brick-green",
];

const TYPE_LABELS: Record<string, string> = {
  word: "단어",
  idiom: "숙어",
  pattern: "패턴",
  sentence: "문장",
};

export function CardCollection({ stats }: { stats: Stats }) {
  return (
    <div className="flex flex-wrap items-end gap-6">
      {stats.levels.map((lv) => {
        const ratio =
          lv.available_items > 0 ? lv.cards / lv.available_items : 0;
        const filled =
          lv.cards === 0
            ? 0
            : Math.max(
                1,
                Math.min(
                  COLLECTION_SLOTS,
                  Math.round(ratio * COLLECTION_SLOTS),
                ),
              );
        const percent = Math.round(ratio * 100);
        // 학습 난이도로 잠긴 타입 — "콘텐츠 미완성"으로 오해되던 빈 칸에 이유를
        // 붙인다 (2026-08-11 보고: 문장 칸이 늘 0). 게임에서 담은 카드도 이때 나온다
        const locked = lv.enabled === false;
        return (
          <div
            key={lv.level}
            className={`flex flex-col items-center gap-1 ${locked ? "opacity-50" : ""}`}
            title={
              locked
                ? `${TYPE_LABELS[lv.item_type] ?? lv.item_type} 카드 ${lv.available_items}개가 준비되어 있어요 — 설정에서 학습 난이도를 올리면 출제가 시작돼요`
                : `${TYPE_LABELS[lv.item_type] ?? lv.item_type} 카드 ${lv.available_items}개 중 ${lv.cards}개를 학습했어요 (한 번이라도 푼 카드)`
            }
          >
            <div className="flex flex-col-reverse gap-0.5" aria-hidden>
              {Array.from({ length: COLLECTION_SLOTS }, (_, i) => (
                <span
                  key={i}
                  className={`h-2.5 w-8 rounded-sm ${
                    i < filled ? LEVEL_COLORS[lv.level - 1] : "bg-ink/10"
                  }`}
                />
              ))}
            </div>
            <p className="text-xs opacity-60">
              {TYPE_LABELS[lv.item_type] ?? `레벨 ${lv.level}`} · {lv.cards}/
              {lv.available_items}
              {locked ? (
                <span className="ml-1">
                  {(lv.locked_due ?? 0) > 0
                    ? `(난이도 올리면 복습 ${lv.locked_due}장 재개)`
                    : "(난이도 올리면 열려요)"}
                </span>
              ) : (
                lv.cards > 0 && (
                  <span className="ml-1">
                    ({percent === 0 ? "1% 미만" : `${percent}%`})
                  </span>
                )
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}

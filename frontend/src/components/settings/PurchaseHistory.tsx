"use client";

import { useEffect, useState } from "react";
import { MASCOT_LABELS, OUTFIT_LABELS } from "@/components/theme/mascots";
import { APP_THEMES } from "@/lib/theme";
import { SHOP_EVENT, type PurchaseRow, shopApi } from "@/lib/shop-api";

const THEME_LABELS: Record<string, string> = Object.fromEntries(
  APP_THEMES.map((t) => [t.key, t.label]),
);

const METHOD_LABELS: Record<string, string> = {
  xp: "XP",
  cash: "현금",
  card: "카드",
};

function itemLabel(itemKey: string): string {
  const [kind, key] = [
    itemKey.slice(0, itemKey.indexOf(":")),
    itemKey.slice(itemKey.indexOf(":") + 1),
  ];
  if (kind === "mascot") return `캐릭터 · ${MASCOT_LABELS[key] ?? key}`;
  if (kind === "outfit") return `악세사리 · ${OUTFIT_LABELS[key] ?? key}`;
  if (kind === "theme") return `테마 · ${THEME_LABELS[key] ?? key}`;
  if (kind === "saver") return "책갈피 충전";
  return itemKey;
}

/** 내 구매 내역 — 품목·결제수단·금액·날짜 (mascot-shop.md 구매 이력).
 *  기본은 접힘(펼칠 때만 로드), 상점 페이지는 open 으로 항상 펼침. */
export function PurchaseHistory({ open = false }: { open?: boolean }) {
  const [items, setItems] = useState<PurchaseRow[] | null>(null);
  const [failed, setFailed] = useState(false);

  function load() {
    if (items !== null) return;
    shopApi
      .purchases()
      .then((res) => setItems(res.items))
      .catch(() => setFailed(true));
  }

  useEffect(() => {
    if (open) load();
    // 구매 직후 목록에 즉시 반영 — 캐시(items) 때문에 재펼침해도 안 갱신되던
    // 버그 픽스 (버그 헌트 2026-08-11). 이미 로드된 경우에만 재조회
    const refresh = () => {
      setItems((prev) => {
        if (prev !== null)
          shopApi
            .purchases()
            .then((res) => setItems(res.items))
            .catch(() => {});
        return prev;
      });
    };
    window.addEventListener(SHOP_EVENT, refresh);
    return () => window.removeEventListener(SHOP_EVENT, refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 최초 펼침 로드만
  }, [open]);

  return (
    <details
      className="mt-4"
      open={open}
      onToggle={(e) => e.currentTarget.open && load()}
    >
      <summary className="cursor-pointer text-xs font-bold opacity-70">
        구매 내역
      </summary>
      {failed && (
        <p className="mt-2 text-xs text-brick-red">
          내역을 불러오지 못했어요 — 잠시 후 다시 열어보세요
        </p>
      )}
      {items && items.length === 0 && (
        <p className="mt-2 text-xs opacity-60">아직 구매한 항목이 없어요</p>
      )}
      {items && items.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 text-xs">
          {items.map((p) => (
            <li
              key={`${p.item_key}-${p.created_at}`}
              className="flex items-center justify-between gap-2 rounded border-2 border-ink/10 bg-white px-2.5 py-1.5"
            >
              <span className="min-w-0 truncate font-bold">
                {itemLabel(p.item_key)}
              </span>
              <span className="shrink-0 opacity-60">
                {METHOD_LABELS[p.method] ?? p.method}{" "}
                {p.amount.toLocaleString()}
                {p.currency === "XP" ? " XP" : ` ${p.currency}`}
                {" · "}
                {new Date(p.created_at).toLocaleDateString("ko-KR")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

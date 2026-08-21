"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { PurchaseConfirmDialog } from "@/components/shop/PurchaseConfirmDialog";
import { SHOP_EVENT, dispatchShopUpdated } from "@/lib/shop-api";
import { studyApi } from "@/lib/study-api";
import { APP_THEMES, setAppTheme, useAppTheme } from "@/lib/theme";
import { themeApi } from "@/lib/theme-api";

/** 상점 테마 섹션 — 구매 중심 (docs/specs/theme-mall.md XP 상점).
 *  설정의 테마 전환과 분리: 여기서는 잠긴 테마의 가격·해금 힌트·구매,
 *  구매 성공 시 즉시 그 테마로 전환(보상 체감). 지갑 갱신은 SHOP_EVENT. */
export function ThemeShopSection() {
  const theme = useAppTheme();
  // 설정 화면 "상점에서 N XP로 열기" 진입 시 그 테마로 스크롤 + 짧은 강조
  // (?highlight=<themeKey>, 2026-08-13)
  const highlightParam = useSearchParams().get("highlight");
  const [highlightKey, setHighlightKey] = useState<string | null>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [allowed, setAllowed] = useState<Set<string> | null>(null);
  const [unlocks, setUnlocks] = useState<
    Record<string, { title: string; key: string }>
  >({});
  const [progress, setProgress] = useState<
    Record<string, { current: number; target: number }>
  >({});
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [availableXp, setAvailableXp] = useState<number | null>(null);
  const [buying, setBuying] = useState<string | null>(null);
  const [buyError, setBuyError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      themeApi
        .themes()
        .then((res) => {
          setAllowed(
            new Set(res.items.filter((i) => i.allowed).map((i) => i.key)),
          );
          setUnlocks(
            Object.fromEntries(
              res.items
                .filter((i) => i.unlock && i.unlock_key)
                .map((i) => [i.key, { title: i.unlock!, key: i.unlock_key! }]),
            ),
          );
          setPrices(
            Object.fromEntries(
              res.items
                .filter((i) => i.price_xp != null)
                .map((i) => [i.key, i.price_xp!]),
            ),
          );
          setAvailableXp(res.available_xp);
        })
        .catch(() => {});
    load();
    // 캐릭터 상점에서 XP 를 써도 이쪽 잔액·버튼 활성이 즉시 맞아야 한다
    // (버그 헌트 2026-08-11: 섹션별 지갑이 따로 놀아 stale 활성 버튼 → 422)
    window.addEventListener(SHOP_EVENT, load);
    // 해금 업적 진행률 — "얼마나 남았는지" 가 보여야 행동으로 이어진다
    studyApi
      .achievements()
      .then((res) =>
        setProgress(
          Object.fromEntries(
            res.items.map((a) => [
              a.key,
              { current: a.current, target: a.target },
            ]),
          ),
        ),
      )
      .catch(() => {});
    return () => window.removeEventListener(SHOP_EVENT, load);
  }, []);

  useEffect(() => {
    if (!highlightParam) return;
    itemRefs.current[highlightParam]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
    setHighlightKey(highlightParam);
    const timer = setTimeout(() => setHighlightKey(null), 2000);
    return () => clearTimeout(timer);
  }, [highlightParam]);

  // 구매 확인 다이얼로그 — 현재 XP·가격·잔액 확인 후 확정 (2026-08-21 요청)
  const [confirmKey, setConfirmKey] = useState<{
    key: string;
    label: string;
  } | null>(null);

  // XP 구매 — 성공 시 즉시 해금 + 그 테마로 전환 (구매의 보상을 바로 체감)
  async function buyTheme(key: string) {
    if (buying) return;
    setBuying(key);
    setBuyError(null);
    try {
      const res = await themeApi.purchase(key);
      setAllowed((prev) => new Set([...(prev ?? new Set()), key]));
      setAvailableXp(res.available_xp);
      setAppTheme(key as Parameters<typeof setAppTheme>[0]);
      dispatchShopUpdated(); // 상점 페이지 상단 지갑 갱신
    } catch (e) {
      const message = e instanceof Error ? e.message : "구매 실패";
      setBuyError(
        {
          insufficient_xp: "XP가 부족해요 — 복습·게임으로 더 모을 수 있어요",
          already_owned: "이미 보유한 테마예요",
          theme_not_for_sale: "지금은 판매하지 않는 테마예요",
          theme_not_found: "존재하지 않는 테마예요",
          theme_not_restricted: "이미 사용할 수 있는 테마예요",
        }[message] ?? "구매에 실패했어요 — 잠시 후 다시 시도해주세요.",
      );
    }
    setBuying(null);
  }

  return (
    <section className="mt-8 max-w-lg">
      <p className="mb-1 text-sm font-bold">테마</p>
      <p className="mb-3 text-xs opacity-60">
        앱 전체(배경·버튼·게임 보드)의 디자인 컨셉이 바뀌어요. 사면 바로
        적용되고, 전환은 설정에서 언제든 할 수 있어요.
      </p>
      {buyError && (
        <p className="mb-3 text-xs font-bold text-brick-red">{buyError}</p>
      )}
      <div className="flex flex-col gap-3">
        {APP_THEMES.map((t) => {
          const active = theme === t.key;
          const locked = allowed !== null && !allowed.has(t.key);
          return (
            <div
              key={t.key}
              ref={(el) => {
                itemRefs.current[t.key] = el;
              }}
              className={`flex min-h-14 items-center gap-4 rounded-lg border-2 bg-white px-4 py-3 transition-shadow ${
                locked ? "border-ink/10" : "border-ink/15 shadow-sm"
              } ${highlightKey === t.key ? "ring-2 ring-brick-blue ring-offset-2" : ""}`}
            >
              <span
                className={`inline-block h-8 w-8 shrink-0 rounded-full border-2 border-ink/15 ${
                  locked ? "opacity-40" : ""
                }`}
                style={{ backgroundColor: t.swatch }}
              />
              <span className={`flex-1 ${locked ? "opacity-50" : ""}`}>
                <span className="block font-bold">{t.label}</span>
                <span className="block text-xs opacity-60">{t.desc}</span>
              </span>
              {locked ? (
                <span className="flex flex-col items-end gap-1">
                  {unlocks[t.key] ? (
                    <span className="rounded-full bg-ink/10 px-3 py-1 text-xs font-bold opacity-70">
                      {`'${unlocks[t.key].title}' 달성 시 열려요`}
                    </span>
                  ) : (
                    prices[t.key] == null && (
                      <span className="rounded-full bg-ink/10 px-3 py-1 text-xs font-bold opacity-70">
                        이벤트·지급으로 열려요
                      </span>
                    )
                  )}
                  {prices[t.key] != null && (
                    <button
                      type="button"
                      onClick={() =>
                        setConfirmKey({ key: t.key, label: `${t.label} 테마` })
                      }
                      className={`cursor-pointer rounded-full border-2 px-3 py-1 text-xs font-bold transition ${
                        availableXp !== null && availableXp >= prices[t.key]
                          ? "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                          : "border-ink/15 opacity-50"
                      }`}
                    >
                      {buying === t.key
                        ? "구매 중..."
                        : availableXp !== null && availableXp < prices[t.key]
                          ? `${prices[t.key].toLocaleString()} XP · ${(prices[t.key] - availableXp).toLocaleString()} 부족`
                          : `${prices[t.key].toLocaleString()} XP로 열기`}
                    </button>
                  )}
                  {unlocks[t.key] && progress[unlocks[t.key].key] && (
                    <span className="text-[10px] opacity-50">
                      진행 {progress[unlocks[t.key].key].current}/
                      {progress[unlocks[t.key].key].target}
                    </span>
                  )}
                </span>
              ) : (
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${
                    active
                      ? "bg-ink text-white"
                      : "bg-brick-green/10 text-brick-green"
                  }`}
                >
                  {active ? "사용 중" : "보유 중"}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* 구매 확인 — 현재 XP·가격·잔액 확인 후 확정, 부족하면 안내만 (2026-08-21) */}
      {confirmKey && prices[confirmKey.key] != null && (
        <PurchaseConfirmDialog
          label={confirmKey.label}
          priceXp={prices[confirmKey.key]}
          availableXp={availableXp ?? 0}
          busy={buying !== null}
          onConfirm={async () => {
            await buyTheme(confirmKey.key);
            setConfirmKey(null);
          }}
          onClose={() => setConfirmKey(null)}
        />
      )}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { PurchaseConfirmDialog } from "@/components/shop/PurchaseConfirmDialog";
import { MascotSvg } from "@/components/theme/mascots";
import {
  SHOP_EVENT,
  dispatchShopUpdated,
  shopApi,
  type ShopCatalog,
} from "@/lib/shop-api";

/** 캐릭터 상점 — 마스코트·악세사리·책갈피를 XP 로 구매 (docs/specs/mascot-shop.md).
 *
 *  산 캐릭터는 즉시 좌하단에 나타나고(자동 활성), 악세사리는 탭으로
 *  착용/해제한다 (2026-08-21 토글 — 구 all-on 정책 개정). 모든 구매는
 *  확인 다이얼로그를 거친다 — 현재 XP·가격·구매 후 잔액을 보고 확정. */
export function MascotShopSection() {
  const [shop, setShop] = useState<ShopCatalog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // 구매 확인 다이얼로그 — run 이 실제 구매를 실행 (마스코트·악세·책갈피 공용)
  const [confirm, setConfirm] = useState<{
    label: string;
    price: number;
    run: () => Promise<void>;
  } | null>(null);

  const load = () =>
    shopApi
      .catalog()
      .then(setShop)
      .catch(() => setShop(null));

  useEffect(() => {
    load();
    // 테마 구매로 XP 를 써도 이쪽 잔액·버튼 활성이 즉시 맞아야 한다 (버그 헌트 2026-08-11)
    window.addEventListener(SHOP_EVENT, load);
    return () => window.removeEventListener(SHOP_EVENT, load);
  }, []);

  if (!shop) return null;

  const wornOutfits = shop.outfits
    .filter((o) => o.worn ?? o.owned)
    .map((o) => o.key);

  function fail(e: unknown) {
    const code = e instanceof Error ? e.message : "실패";
    setNotice(
      {
        insufficient_xp: "XP가 부족해요 — 복습·게임으로 더 모을 수 있어요",
        already_owned: "이미 보유한 아이템이에요",
        saver_full: "책갈피는 최대 2개까지 보관돼요",
        item_not_found: "존재하지 않는 아이템이에요",
        event_only_item: "이벤트로만 받을 수 있는 아이템이에요",
        not_owned: "먼저 구매해야 착용할 수 있어요",
      }[code] ?? "구매에 실패했어요 — 잠시 후 다시 시도해주세요.",
    );
  }

  async function buy(itemKey: string) {
    setBusy(itemKey);
    setNotice(null);
    try {
      await shopApi.purchase(itemKey);
      await load();
      dispatchShopUpdated(); // 좌하단 마스코트 즉시 갱신
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function activate(key: string | null) {
    setBusy(`activate:${key}`);
    setNotice(null);
    try {
      await shopApi.setMascot(key);
      await load();
      dispatchShopUpdated();
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function toggleOutfit(key: string, worn: boolean) {
    setBusy(`wear:${key}`);
    setNotice(null);
    try {
      await shopApi.setOutfit(key, worn);
      await load();
      dispatchShopUpdated(); // 좌하단·런처의 착용 상태 즉시 갱신
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function buySaver() {
    setBusy("saver");
    setNotice(null);
    try {
      await shopApi.buySaver();
      await load();
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  return (
    <section className="mt-8">
      <p className="mb-1 text-sm font-bold">캐릭터</p>
      <p className="mb-2 text-xs opacity-60">
        XP로 캐릭터를 데려와요 — 채팅 버튼과 화면 곳곳에서 함께 공부해요.
      </p>
      {notice && <p className="mb-2 text-xs text-brick-red">{notice}</p>}

      {/* 마스코트 — 미리보기 + 구매/활성. 수집 도감식: 보유/미보유가 한눈에 */}
      {shop.mascots.length === 0 ? (
        <p className="rounded-lg border-2 border-ink/10 bg-white p-3 text-xs opacity-60">
          지금은 판매 중인 캐릭터가 없어요
        </p>
      ) : (
        <div className="flex flex-wrap gap-3">
          {shop.mascots.map((m) => {
            const active = shop.active_mascot === m.key;
            return (
              <div
                key={m.key}
                className={`flex w-40 flex-col items-center gap-2 rounded-lg border-2 bg-white p-3 ${
                  active ? "border-brick-blue" : "border-ink/10"
                }`}
              >
                <div
                  className={`origin-bottom scale-90 ${m.owned ? "" : "opacity-40 grayscale"}`}
                >
                  <MascotSvg
                    kind={m.key}
                    outfits={m.owned ? wornOutfits : []}
                  />
                </div>
                <p className="text-sm font-bold">{m.label}</p>
                {m.owned ? (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => activate(active ? null : m.key)}
                    className={`min-h-9 w-full rounded-full border-2 text-xs font-bold transition ${
                      active
                        ? "border-ink/20 bg-ink/5"
                        : "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                    }`}
                  >
                    {active ? "쉬게 하기" : "데려오기"}
                  </button>
                ) : m.sale === "event" ? (
                  <span className="grid min-h-9 w-full place-items-center rounded-full border-2 border-brick-yellow/60 bg-highlight/40 text-xs font-bold">
                    이벤트 한정
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() =>
                      setConfirm({
                        label: m.label,
                        price: m.price_xp,
                        run: () => buy(`mascot:${m.key}`),
                      })
                    }
                    className={`min-h-9 w-full rounded-full border-2 text-xs font-bold transition ${
                      shop.available_xp >= m.price_xp
                        ? "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                        : "border-ink/15 opacity-50"
                    }`}
                  >
                    {busy === `mascot:${m.key}`
                      ? "구매 중..."
                      : `${m.price_xp.toLocaleString()} XP`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 악세사리 — 보유한 것은 탭으로 착용/해제 (2026-08-21 토글) */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">
        악세사리 — 산 악세사리는 탭해서 착용하거나 벗길 수 있어요
      </p>
      {shop.outfits.length === 0 ? (
        <p className="rounded-lg border-2 border-ink/10 bg-white p-3 text-xs opacity-60">
          악세사리가 없어요
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {shop.outfits.map((o) => {
            const worn = o.worn ?? o.owned;
            return (
              <button
                key={o.key}
                type="button"
                disabled={busy !== null || (!o.owned && o.sale === "event")}
                onClick={() =>
                  o.owned
                    ? toggleOutfit(o.key, !worn)
                    : setConfirm({
                        label: `악세사리 ${o.label}`,
                        price: o.price_xp,
                        run: () => buy(`outfit:${o.key}`),
                      })
                }
                className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
                  o.owned
                    ? worn
                      ? "border-brick-green bg-brick-green/15 text-brick-green"
                      : "border-ink/25 bg-white opacity-70 hover:border-brick-green/60"
                    : o.sale === "event"
                      ? "border-brick-yellow/60 bg-highlight/40"
                      : shop.available_xp >= o.price_xp
                        ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                        : "border-ink/15 opacity-50"
                }`}
              >
                {o.label}{" "}
                {o.owned
                  ? busy === `wear:${o.key}`
                    ? "..."
                    : worn
                      ? "착용 중"
                      : "벗음"
                  : o.sale === "event"
                    ? "이벤트 한정"
                    : busy === `outfit:${o.key}`
                      ? "구매 중..."
                      : `${o.price_xp.toLocaleString()} XP`}
              </button>
            );
          })}
        </div>
      )}

      {/* 책갈피 충전 — 손실 회피 상품 (벤치마크 1순위) */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">책갈피 충전</p>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="opacity-70">
          보유 {shop.streak_saver.count}/{shop.streak_saver.max} — 놓친 날
          자동으로 끼워져 연속 학습을 지켜줘요
        </span>
        <button
          type="button"
          disabled={
            busy !== null || shop.streak_saver.count >= shop.streak_saver.max
          }
          onClick={() =>
            setConfirm({
              label: "책갈피 1개 충전",
              price: shop.streak_saver.price_xp,
              run: buySaver,
            })
          }
          className={`min-h-9 rounded-full border-2 px-3 font-bold transition ${
            shop.streak_saver.count >= shop.streak_saver.max
              ? "border-ink/15 opacity-50"
              : shop.available_xp >= shop.streak_saver.price_xp
                ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                : "border-ink/15 opacity-50"
          }`}
        >
          {busy === "saver"
            ? "구매 중..."
            : `${shop.streak_saver.price_xp} XP로 1개 충전`}
        </button>
      </div>

      {/* 구매 확인 — 현재 XP·가격·잔액 확인 후 확정, 부족하면 안내만 (2026-08-21) */}
      {confirm && (
        <PurchaseConfirmDialog
          label={confirm.label}
          priceXp={confirm.price}
          availableXp={shop.available_xp}
          busy={busy !== null}
          onConfirm={async () => {
            await confirm.run();
            setConfirm(null);
          }}
          onClose={() => setConfirm(null)}
        />
      )}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { MascotSvg } from "@/components/theme/mascots";
import {
  SHOP_EVENT,
  dispatchShopUpdated,
  shopApi,
  type ShopCatalog,
} from "@/lib/shop-api";

/** 캐릭터 상점 — 마스코트·악세사리·책갈피를 XP 로 구매 (docs/specs/mascot-shop.md).
 *
 *  산 캐릭터는 즉시 좌하단에 나타나고(자동 활성), 악세는 all-on — 보유하면
 *  활성 캐릭터에 전부 착용된다 (2026-08-11 사용자 결정). */
export function MascotShopSection() {
  const [shop, setShop] = useState<ShopCatalog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const ownedOutfits = shop.outfits.filter((o) => o.owned).map((o) => o.key);

  function fail(e: unknown) {
    const code = e instanceof Error ? e.message : "실패";
    setNotice(
      {
        insufficient_xp: "XP가 부족해요 — 복습·게임으로 더 모을 수 있어요",
        already_owned: "이미 보유한 아이템이에요",
        saver_full: "책갈피는 최대 2개까지 보관돼요",
      }[code] ?? code,
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
                <MascotSvg kind={m.key} outfits={m.owned ? ownedOutfits : []} />
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
                  onClick={() => buy(`mascot:${m.key}`)}
                  className={`min-h-9 w-full rounded-full border-2 text-xs font-bold transition ${
                    shop.available_xp >= m.price_xp
                      ? "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                      : "border-ink/15 opacity-50"
                  }`}
                >
                  {busy === `mascot:${m.key}`
                    ? "구매 중..."
                    : shop.available_xp >= m.price_xp
                      ? `${m.price_xp.toLocaleString()} XP`
                      : `${m.price_xp.toLocaleString()} XP · ${(m.price_xp - shop.available_xp).toLocaleString()} 부족`}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* 악세사리 — all-on: 사면 캐릭터가 전부 착용한다 */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">
        악세사리 — 사면 캐릭터가 바로 착용해요 (보유한 것 전부)
      </p>
      <div className="flex flex-wrap gap-2">
        {shop.outfits.map((o) => (
          <button
            key={o.key}
            type="button"
            disabled={o.owned || busy !== null || o.sale === "event"}
            onClick={() => buy(`outfit:${o.key}`)}
            className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
              o.owned
                ? "border-brick-green/50 bg-brick-green/10 text-brick-green"
                : o.sale === "event"
                  ? "border-brick-yellow/60 bg-highlight/40"
                  : shop.available_xp >= o.price_xp
                    ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                    : "border-ink/15 opacity-50"
            }`}
          >
            {o.label}{" "}
            {o.owned
              ? "착용 중"
              : o.sale === "event"
                ? "이벤트 한정"
                : busy === `outfit:${o.key}`
                  ? "구매 중..."
                  : `${o.price_xp.toLocaleString()} XP`}
          </button>
        ))}
      </div>

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
          onClick={buySaver}
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
    </section>
  );
}

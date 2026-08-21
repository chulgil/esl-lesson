/** XP 상점 API — 마스코트·악세사리·책갈피 (docs/specs/mascot-shop.md) */

import { request } from "@/lib/http";

export interface ShopItem {
  key: string;
  label: string;
  price_xp: number;
  /** "event" = 이벤트 지급 전용 — XP 구매 불가 (백오피스 설정) */
  sale: "xp" | "event";
  owned: boolean;
  /** 악세사리만 — 착용 중 여부 (2026-08-21 착용 토글). 마스코트 행엔 없음 */
  worn?: boolean;
}

export interface PurchaseRow {
  item_key: string;
  method: "xp" | "cash" | "card";
  amount: number;
  currency: string;
  created_at: string;
}

export interface ShopCatalog {
  available_xp: number;
  active_mascot: string | null;
  mascots: ShopItem[];
  outfits: ShopItem[];
  streak_saver: { price_xp: number; count: number; max: number };
}

/** 구매·활성 변경 후 발행 — 레이아웃의 MascotPeek 이 구독해 즉시 갱신 */
export const SHOP_EVENT = "esl-shop-updated";

export function dispatchShopUpdated(): void {
  window.dispatchEvent(new CustomEvent(SHOP_EVENT));
}

export const shopApi = {
  catalog: () => request<ShopCatalog>("/api/shop"),
  purchases: () => request<{ items: PurchaseRow[] }>("/api/shop/purchases"),
  purchase: (itemKey: string) =>
    request<{
      item_key: string;
      available_xp: number;
      active_mascot: string | null;
    }>("/api/shop/purchase", {
      method: "POST",
      body: JSON.stringify({ item_key: itemKey }),
    }),
  setMascot: (key: string | null) =>
    request<{ active_mascot: string | null }>("/api/shop/mascot", {
      method: "PATCH",
      body: JSON.stringify({ key }),
    }),
  /** 악세사리 착용/해제 (2026-08-21 토글) */
  setOutfit: (key: string, worn: boolean) =>
    request<{ outfits_worn: string[] }>("/api/shop/outfit", {
      method: "PATCH",
      body: JSON.stringify({ key, worn }),
    }),
  buySaver: () =>
    request<{ count: number; available_xp: number }>(
      "/api/shop/streak-saver/purchase",
      { method: "POST" },
    ),
};

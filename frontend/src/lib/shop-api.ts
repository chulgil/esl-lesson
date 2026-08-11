/** XP 상점 API — 마스코트·악세사리·책갈피 (docs/specs/mascot-shop.md) */

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    let code = `HTTP ${res.status}`;
    try {
      code = (await res.json()).detail ?? code;
    } catch {
      // 본문 없는 오류
    }
    throw new Error(code);
  }
  return (await res.json()) as T;
}

export interface ShopItem {
  key: string;
  label: string;
  price_xp: number;
  owned: boolean;
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
  buySaver: () =>
    request<{ count: number; available_xp: number }>(
      "/api/shop/streak-saver/purchase",
      { method: "POST" },
    ),
};

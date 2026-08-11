"use client";

import { useEffect, useState } from "react";
import { MascotShopSection } from "@/components/settings/MascotShopSection";
import { PurchaseHistory } from "@/components/settings/PurchaseHistory";
import { XpWallet } from "@/components/settings/XpWallet";
import { ThemeShopSection } from "@/components/shop/ThemeShopSection";
import { SHOP_EVENT, shopApi } from "@/lib/shop-api";

/** 상점 — 테마·캐릭터 구매 + 구매 내역 전용 페이지 (2026-08-11 분리 요구).
 *  설정에 섞여 있던 구매 UI 를 한곳에 모아 지갑이 항상 위에 보이게 한다.
 *  진입: 프로필 메뉴 "상점", 설정의 바로가기. */
export default function ShopPage() {
  const [availableXp, setAvailableXp] = useState<number | null>(null);

  useEffect(() => {
    const load = () =>
      shopApi
        .catalog()
        .then((s) => setAvailableXp(s.available_xp))
        .catch(() => setAvailableXp(null));
    load();
    // 테마·캐릭터 어느 쪽을 사도 상단 지갑 즉시 갱신
    window.addEventListener(SHOP_EVENT, load);
    return () => window.removeEventListener(SHOP_EVENT, load);
  }, []);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <h1 className="mb-2 font-hand text-3xl font-bold">
        <span className="hl">상점</span>
      </h1>
      <p className="mb-4 text-xs opacity-60">
        복습·게임으로 모은 XP로 테마와 캐릭터를 열 수 있어요.
      </p>
      {availableXp !== null && <XpWallet amount={availableXp} />}

      <ThemeShopSection />
      <MascotShopSection />

      <section className="mt-6 max-w-lg">
        <PurchaseHistory open />
      </section>
    </main>
  );
}

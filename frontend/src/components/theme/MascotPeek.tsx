"use client";

import { useEffect, useState } from "react";
import { MascotSvg } from "@/components/theme/mascots";
import { SHOP_EVENT, shopApi } from "@/lib/shop-api";
import { useAppTheme } from "@/lib/theme";

/** 좌하단 상시 마스코트 — 상점에서 산 캐릭터 + 보유 악세 전부 착용 (all-on).
 *
 *  벤치마크 원칙(Habitica/Forest): 꾸민 결과는 별도 화면이 아니라 매일 보는
 *  화면에 상시 노출 (proposal/xp-shop-mascot-2026-08.md). 슬롯 규정은
 *  ui-design.md — 우하단=채팅 런처 전용, 장식 마스코트=좌하단.
 *  cat 테마 하위호환: 활성 마스코트가 없어도 헤냥이 노출 (테마 정체성 유지). */
export function MascotPeek() {
  const theme = useAppTheme();
  const [state, setState] = useState<{
    active: string | null;
    outfits: string[];
  } | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      shopApi
        .catalog()
        .then((s) => {
          if (!alive) return;
          setState({
            active: s.active_mascot,
            // 착용 토글 (2026-08-21): worn 우선, 구 응답 폴백은 owned(all-on)
            outfits: s.outfits
              .filter((o) => o.worn ?? o.owned)
              .map((o) => o.key),
          });
        })
        .catch(() => {
          if (alive) setState({ active: null, outfits: [] }); // 미로그인 등 — 테마 폴백만
        });
    load();
    window.addEventListener(SHOP_EVENT, load);
    return () => {
      alive = false;
      window.removeEventListener(SHOP_EVENT, load);
    };
  }, []);

  const kind = state?.active ?? (theme === "cat" ? "henyang" : null);
  if (!kind) return null;

  return (
    <div
      aria-hidden
      // 기존 henyang-peek CSS 훅 재사용 — game-focus/chat-focus 숨김·모바일 탭바 회피
      className="henyang-peek pointer-events-none fixed bottom-16 left-1 z-30 origin-bottom-left scale-x-[-0.75] scale-y-75 sm:bottom-2 sm:left-3 sm:scale-x-[-1] sm:scale-y-100"
    >
      <MascotSvg kind={kind} outfits={state?.outfits ?? []} flip />
    </div>
  );
}

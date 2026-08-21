"use client";

import { useEffect, useState } from "react";

/** 오래 열린 탭의 구버전 번들 감지 — 배포 후에도 탭을 안 닫으면 플로팅
 *  위젯 등 루트 레이아웃 코드가 옛 사양으로 남는다 (2026-07-31 보고:
 *  "팝업 챗만 다른 사양" = 구버전 번들). 서버의 /build-version 과 내
 *  번들 SHA 를 비교해 다르면 새로고침 안내 배너를 띄운다.
 *  자동 새로고침은 하지 않는다 — 입력 중이던 채팅/시험 답안이 날아간다. */
export function BuildRefreshWatcher() {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const mine = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
    if (mine === "dev") return; // 로컬 개발은 비교 무의미
    let cancelled = false;

    const check = () => {
      fetch("/build-version", { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!cancelled && data?.sha && data.sha !== mine) setStale(true);
        })
        .catch(() => {});
    };

    const onBack = () => {
      if (!document.hidden) check();
    };
    // 탭 복귀 시 + 10분 주기 — 배포 직후 열린 탭이 하루 종일 옛 코드로 돌지 않게
    document.addEventListener("visibilitychange", onBack);
    window.addEventListener("focus", onBack);
    const timer = setInterval(check, 10 * 60 * 1000);
    check();
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onBack);
      window.removeEventListener("focus", onBack);
      clearInterval(timer);
    };
  }, []);

  if (!stale) return null;
  // 업데이트 소식으로 이동 — 무엇이 바뀌었는지 보고 [확인]으로 업데이트
  // (2026-08-21 요청: 변경 내역을 보여줘 신뢰를 높인다). /updates 는 새 문서
  // 요청이라 이동 자체가 새 번들을 받는다 — 소식 화면의 확인 버튼이 reload 마무리
  return (
    <a
      href="/updates?refresh=1"
      className="fixed bottom-4 left-4 z-50 flex min-h-11 items-center gap-2 rounded-full border-2 border-brick-blue bg-white px-4 text-sm font-bold text-brick-blue shadow-lg transition hover:-translate-y-0.5"
    >
      새 업데이트가 도착했어요 — 무엇이 바뀌었을까요?
    </a>
  );
}

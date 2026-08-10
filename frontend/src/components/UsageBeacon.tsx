"use client";

import { useEffect } from "react";
import { logUsage } from "@/lib/usage";

/** 마운트 1회 사용 이벤트 비컨 — 서버 컴포넌트 페이지에도 심는 관측 장치 (P1-D) */
export function UsageBeacon({
  kind,
  meta,
}: {
  kind: string;
  meta?: Record<string, string>;
}) {
  useEffect(() => {
    logUsage(kind, meta);
    // meta 는 호출부 리터럴 — 마운트 1회만 기록 (재렌더 중복 방지)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

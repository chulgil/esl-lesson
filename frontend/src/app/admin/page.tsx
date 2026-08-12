"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminApi, type TranslationUsage } from "@/lib/admin-api";

interface Stats {
  pending_items: number;
  failed_contents: number;
  in_progress_contents: number;
  total_contents: number;
  weekly_supply: number;
  supply_goal: number;
  levels: { beginner: number; intermediate: number; advanced: number };
}

/** 초급 확보 목표 — effectiveness-audit P0-3 (초급 5편) */
const BEGINNER_GOAL = 5;

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi
      .dashboard()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <section>
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">대시보드</span>
      </h1>
      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}
      {stats && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            label="검수 대기 항목"
            value={stats.pending_items}
            href="/admin/items"
            alert={stats.pending_items > 0}
          />
          <StatCard
            label="실패 콘텐츠"
            value={stats.failed_contents}
            href="/admin/contents?status=failed"
            alert={stats.failed_contents > 0}
          />
          <StatCard
            label="처리 중"
            value={stats.in_progress_contents}
            href="/admin/contents"
          />
          <StatCard
            label="전체 콘텐츠"
            value={stats.total_contents}
            href="/admin/contents"
          />
          {/* 공급 리듬 (P0-B) — 주 2편 약속을 사람 기억이 아니라 화면이 지킨다 */}
          <StatCard
            label="이번 주 공급 (목표 2편)"
            value={`${stats.weekly_supply}/${stats.supply_goal}`}
            href="/admin/contents/new"
            alert={stats.weekly_supply < stats.supply_goal}
          />
          <StatCard
            label={`초급 콘텐츠 (목표 ${BEGINNER_GOAL}편)`}
            value={`${stats.levels.beginner} · 중 ${stats.levels.intermediate} · 고 ${stats.levels.advanced}`}
            href="/admin/contents/new"
            alert={stats.levels.beginner < BEGINNER_GOAL}
          />
        </div>
      )}
      <TranslationUsageCard />
    </section>
  );
}

/** 번역 사용량 — 예산 소진율·엔진별 분담·오늘 호출 수 (i18n) */
function TranslationUsageCard() {
  const [usage, setUsage] = useState<TranslationUsage | null>(null);

  useEffect(() => {
    adminApi
      .translationUsage()
      .then(setUsage)
      .catch(() => undefined);
  }, []);

  if (!usage) return null;

  const pct =
    usage.budget_chars > 0
      ? Math.min(
          100,
          Math.round((usage.month_chars / usage.budget_chars) * 100),
        )
      : 0;

  return (
    <div className="mt-4 rounded-lg border-2 border-ink/10 bg-white p-4 shadow-sm">
      <p className="text-xs opacity-60">번역 사용량</p>
      <p className="mt-1 text-2xl font-bold">
        {usage.month_chars.toLocaleString()} /{" "}
        {usage.budget_chars.toLocaleString()}자
        <span className="ml-2 text-sm font-normal opacity-60">
          이번 달 · {pct}%
        </span>
      </p>
      <p className="mt-2 flex flex-wrap gap-3 text-xs opacity-70">
        <span>DeepL {usage.by_engine.deepl.toLocaleString()}자</span>
        <span>Haiku {usage.by_engine.haiku.toLocaleString()}자</span>
        <span>오늘 호출 {usage.today_calls}회</span>
      </p>
    </div>
  );
}

function StatCard({
  label,
  value,
  href,
  alert = false,
}: {
  label: string;
  value: number | string;
  href: string;
  alert?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`rounded-lg border-2 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 ${
        alert ? "border-margin-red" : "border-ink/10"
      }`}
    >
      <p className="text-xs opacity-60">{label}</p>
      <p className="mt-1 text-3xl font-bold">{value}</p>
    </Link>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";

interface Stats {
  pending_items: number;
  failed_contents: number;
  in_progress_contents: number;
  total_contents: number;
}

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
        </div>
      )}
    </section>
  );
}

function StatCard({
  label,
  value,
  href,
  alert = false,
}: {
  label: string;
  value: number;
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

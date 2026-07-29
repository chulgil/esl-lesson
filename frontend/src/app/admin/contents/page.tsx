"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Brick } from "@/components/brick/Brick";
import { STATUS_LABELS, StatusBadge } from "@/components/content/StatusBadge";
import { adminApi, type ContentSummary } from "@/lib/admin-api";

export default function AdminContentsPage() {
  return (
    <Suspense>
      <ContentsInner />
    </Suspense>
  );
}

function ContentsInner() {
  const params = useSearchParams();
  const statusFilter = params.get("status") ?? undefined;
  const [contents, setContents] = useState<ContentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi
      .listContents(statusFilter)
      .then((res) => setContents(res.items))
      .catch((e) => setError(e.message));
  }, [statusFilter]);

  useEffect(() => {
    load();
    // 파이프라인 진행 중 콘텐츠가 있으면 5초 폴링 (docs/specs/backoffice.md)
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <section>
      <div className="flex items-center justify-between">
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">콘텐츠</span>
        </h1>
        <Brick color="red" href="/admin/contents/new">
          + 콘텐츠 등록
        </Brick>
      </div>

      <div className="mt-4 flex gap-2 text-sm">
        <FilterLink
          label="전체"
          active={!statusFilter}
          href="/admin/contents"
        />
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <FilterLink
            key={key}
            label={label}
            active={statusFilter === key}
            href={`/admin/contents?status=${key}`}
          />
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}

      <div className="overflow-x-auto">
        <table className="mt-4 w-full border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b-2 border-ink/20 text-left">
              <th className="p-2">제목</th>
              <th className="p-2 w-20">소스</th>
              <th className="p-2 w-24">상태</th>
              <th className="p-2 w-40">등록일</th>
            </tr>
          </thead>
          <tbody>
            {contents.map((c) => (
              <tr key={c.id} className="border-b border-ink/10 hover:bg-paper">
                <td className="p-2">
                  <Link
                    href={`/admin/contents/${c.id}`}
                    className="hover:underline"
                  >
                    {c.title}
                  </Link>
                  {c.error_message && (
                    <p
                      className={`mt-0.5 text-xs ${
                        c.status === "failed" ? "text-brick-red" : "opacity-60"
                      }`}
                    >
                      {c.error_message}
                    </p>
                  )}
                </td>
                <td className="p-2">
                  {c.source === "youtube" ? "유튜브" : "수기"}
                  {/* 라이선스 배지 — CC/표준/미확인 한눈에 (저작권 관리) */}
                  {c.source === "youtube" && (
                    <span
                      className={`ml-1.5 rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        c.youtube_license === "creativeCommon"
                          ? "bg-brick-green/15 text-brick-green"
                          : c.youtube_license === "youtube"
                            ? "bg-ink/10 text-ink/70"
                            : "bg-brick-red/10 text-brick-red"
                      }`}
                    >
                      {c.youtube_license === "creativeCommon"
                        ? "CC BY"
                        : c.youtube_license === "youtube"
                          ? "표준"
                          : "미확인"}
                    </span>
                  )}
                </td>
                <td className="p-2">
                  <StatusBadge status={c.status} />
                </td>
                <td className="p-2 text-xs opacity-60">
                  {new Date(c.created_at).toLocaleString("ko-KR")}
                </td>
              </tr>
            ))}
            {contents.length === 0 && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-sm opacity-50">
                  콘텐츠가 없습니다. 첫 콘텐츠를 등록해보세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FilterLink({
  label,
  active,
  href,
}: {
  label: string;
  active: boolean;
  href: string;
}) {
  return (
    <Link
      href={href}
      className={`rounded px-2 py-1 ${active ? "bg-ink text-white" : "bg-white hover:bg-ink/5"}`}
    >
      {label}
    </Link>
  );
}

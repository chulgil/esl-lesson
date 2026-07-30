"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type PoolItem } from "@/lib/admin-api";

/** 전역 항목 풀 — 승인 opt-out 모델의 사후 거절 창구 (content-governance.md).
 *  추출 항목은 기본 approved 라 이 화면의 주 용도는 부적절 항목 거절/복구. */

const TYPE_LABELS: Record<string, string> = {
  word: "단어",
  idiom: "숙어",
  pattern: "패턴",
  sentence: "문장",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "대기",
  approved: "승인",
  rejected: "거절",
};

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-brick-yellow/40",
  approved: "bg-brick-green/30",
  rejected: "bg-brick-red/20 text-brick-red",
};

const PAGE_SIZE = 50;

export default function AdminItemsPage() {
  const [items, setItems] = useState<PoolItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    adminApi
      .searchItems({
        type: type || undefined,
        status: status || undefined,
        q: search || undefined,
        page,
      })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, status, search, page]);

  useEffect(load, [load]);

  async function handleStatus(item: PoolItem, next: PoolItem["review_status"]) {
    setError(null);
    try {
      await adminApi.patchItem(item.id, { review_status: next });
      load();
    } catch (err) {
      // 문장 승인은 사고 힌트 필수 — 서버 422 메시지를 그대로 노출
      setError(err instanceof Error ? err.message : "상태 변경 실패");
    }
  }

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section>
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">항목 풀</span>
      </h1>
      <p className="mt-2 text-sm opacity-70">
        추출된 학습 항목은 기본 승인이에요. 부적절한 항목은 여기서 거절하면 전
        사용자 학습에서 즉시 빠져요.
      </p>
      {error && <p className="mt-3 text-sm text-brick-red">{error}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setSearch(q.trim());
        }}
        className="mt-4 flex flex-wrap items-center gap-2"
      >
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setPage(1);
          }}
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-2 text-sm"
        >
          <option value="">전체 타입</option>
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-2 text-sm"
        >
          <option value="">전체 상태</option>
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="영어/한글 검색"
          className="min-h-11 w-56 rounded-md border-2 border-ink/20 bg-white px-3 text-sm"
        />
        <button
          type="submit"
          className="min-h-11 rounded-md bg-ink px-4 text-sm font-bold text-white transition hover:opacity-85"
        >
          검색
        </button>
        <span className="text-xs opacity-60">총 {total}건</span>
      </form>

      <div className="overflow-x-auto">
        <table className="mt-4 w-full border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b-2 border-ink/20 text-left text-xs">
              <th className="p-2 w-14">ID</th>
              <th className="p-2 w-16">타입</th>
              <th className="p-2">영어</th>
              <th className="p-2">한글</th>
              <th className="p-2 w-16">상태</th>
              <th className="p-2 w-32">액션</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-ink/10">
                <td className="p-2 text-xs opacity-60">{item.id}</td>
                <td className="p-2 text-xs">{TYPE_LABELS[item.item_type]}</td>
                <td className="p-2">{item.en_text}</td>
                <td className="p-2 text-xs opacity-80">{item.ko_text}</td>
                <td className="p-2">
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${STATUS_BADGE[item.review_status]}`}
                  >
                    {STATUS_LABELS[item.review_status]}
                  </span>
                </td>
                <td className="p-2">
                  {item.review_status !== "rejected" && (
                    <button
                      type="button"
                      onClick={() => handleStatus(item, "rejected")}
                      className="mr-2 text-xs text-brick-red hover:underline"
                    >
                      거절
                    </button>
                  )}
                  {item.review_status !== "approved" && (
                    <button
                      type="button"
                      onClick={() => handleStatus(item, "approved")}
                      className="text-xs hover:underline"
                    >
                      승인
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-xs opacity-40">
                  조건에 맞는 항목이 없어요
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center gap-3 text-sm">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-3 disabled:opacity-40"
        >
          이전
        </button>
        <span className="text-xs opacity-60">
          {page} / {lastPage}
        </span>
        <button
          type="button"
          disabled={page >= lastPage}
          onClick={() => setPage((p) => p + 1)}
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-3 disabled:opacity-40"
        >
          다음
        </button>
      </div>
    </section>
  );
}

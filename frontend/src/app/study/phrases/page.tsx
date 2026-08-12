"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { studyApi } from "@/lib/study-api";

/** 내가 쓰는 말 편집 — 문장 빼기 (docs/specs/my-phrases.md 편집).
 *  뺀 문장은 제외 원장에 기록되어 재동기화(채팅 재수집)에도 돌아오지 않는다. */
export default function MyPhrasesEditPage() {
  const [items, setItems] = useState<
    { item_id: number; en: string; ko: string }[] | null
  >(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    studyApi
      .myPhrasesItems()
      .then((res) => setItems(res.items))
      .catch(() => setError("목록을 불러오지 못했어요 — 새로고침해 주세요"));
  }, []);

  async function remove(itemId: number) {
    setBusy(itemId);
    setError(null);
    try {
      await studyApi.removeMyPhrase(itemId);
      setItems((prev) => (prev ?? []).filter((p) => p.item_id !== itemId));
    } catch {
      setError("빼기에 실패했어요 — 잠시 후 다시 시도해 주세요");
    }
    setBusy(null);
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">내가 쓰는 말 편집</span>
      </h1>
      <p className="mt-2 max-w-lg text-xs opacity-60">
        학습하고 싶지 않은 문장은 빼세요 — 뺀 문장은 복습·게임에서 사라지고,
        같은 말을 다시 채팅해도 다시 수집되지 않아요.
      </p>
      <Link
        href="/study"
        className="mt-3 inline-flex min-h-10 items-center rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold transition hover:border-ink/50"
      >
        ← 학습으로
      </Link>

      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}

      {items !== null && items.length === 0 && (
        <p className="mt-6 text-sm opacity-70">
          모인 문장이 없어요 — 채팅 자동번역을 켜고 대화하면 쌓여요.
        </p>
      )}

      {items !== null && items.length > 0 && (
        <ul className="mt-5 flex max-w-2xl flex-col gap-2">
          {items.map((p) => (
            <li
              key={p.item_id}
              className="flex items-center justify-between gap-3 rounded-md border-2 border-ink/10 bg-white px-3 py-2"
            >
              <span className="min-w-0">
                <b className="block truncate">{p.en}</b>
                <span className="block truncate text-xs opacity-60">
                  {p.ko}
                </span>
              </span>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => remove(p.item_id)}
                className="min-h-9 shrink-0 rounded-full border-2 border-brick-red/40 bg-white px-3 text-xs font-bold text-brick-red transition hover:border-brick-red disabled:opacity-50"
              >
                {busy === p.item_id ? "빼는 중..." : "빼기"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

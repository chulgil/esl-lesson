"use client";

import { useState } from "react";
import type { GameReviewItem } from "@/lib/game-ws";
import { studyApi } from "@/lib/study-api";
import { logUsage } from "@/lib/usage";

/** 게임 오답 원탭 학습 패널 — *.review 개인 메시지의 items 표시 (quiz-royale.md) */
export function ReviewPanel({
  items,
  noun = "단어",
  hint = "추가한 단어는 오늘의 학습 큐에 새 카드로 들어가요",
  source = "unknown",
  heading = "이번 판에서 틀린",
}: {
  items: GameReviewItem[];
  noun?: string;
  hint?: string;
  /** 어느 게임에서 담았는가 — 사용 이벤트 meta (P1-D) */
  source?: string;
  /** 머리말 — 타자연습은 "복습하면 좋을" (철자 한둘 실수 ≠ 틀림, 2026-08-11) */
  heading?: string;
}) {
  const [added, setAdded] = useState<Record<number, boolean>>({});
  const [failed, setFailed] = useState<Record<number, boolean>>({});

  if (items.length === 0) return null;

  async function addToStudy(itemId: number) {
    try {
      await studyApi.addCard(itemId);
      setAdded((prev) => ({ ...prev, [itemId]: true }));
      setFailed((prev) => ({ ...prev, [itemId]: false }));
      logUsage("review_add", { game: source });
    } catch {
      // 실패 시 버튼 유지 — 다시 탭해 재시도, 인라인으로 실패 안내
      setFailed((prev) => ({ ...prev, [itemId]: true }));
    }
  }

  async function addAll() {
    for (const item of items) {
      if (!added[item.item_id]) await addToStudy(item.item_id);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border-2 border-brick-red/30 bg-brick-red/5 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-bold">
          {heading} {noun} {items.length}개
        </h3>
        {items.some((i) => !added[i.item_id]) ? (
          <button
            type="button"
            onClick={addAll}
            className="min-h-11 shrink-0 rounded-md border-2 border-brick-blue bg-brick-blue/10 px-3 py-1.5 text-sm font-bold transition hover:-translate-y-0.5"
          >
            모두 학습 추가
          </button>
        ) : (
          <span className="shrink-0 text-sm font-bold text-brick-green">
            복습 큐에 담김
          </span>
        )}
      </div>
      <ul className="flex flex-col gap-1.5">
        {items.map((item) => (
          <li key={item.item_id} className="flex flex-col gap-1">
            <div className="flex items-start justify-between gap-2">
              <span className="min-w-0">
                <b>{item.en}</b>
                {item.ko && <span className="ml-2 opacity-60">{item.ko}</span>}
              </span>
              {added[item.item_id] ? (
                <span className="shrink-0 text-xs font-bold text-brick-green">
                  추가됨
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => addToStudy(item.item_id)}
                  className="min-h-11 shrink-0 rounded-md border-2 border-brick-blue/40 px-2.5 py-1 text-xs font-bold transition hover:bg-brick-blue/10"
                >
                  학습 추가
                </button>
              )}
            </div>
            {failed[item.item_id] && !added[item.item_id] && (
              <p className="text-xs text-brick-red">
                추가하지 못했어요 — 다시 탭해 주세요
              </p>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs opacity-60">{hint}</p>
    </div>
  );
}

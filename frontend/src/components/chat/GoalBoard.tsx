"use client";

import { useCallback, useEffect, useState } from "react";
import { DeleteMessageButton } from "@/components/chat/DeleteMessageButton";
import { chatApi, type GoalItem, type GoalWeekly } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";

const MAX_ITEMS = 20;

/** 함께 목표 보드 — 대화방 헤더 아래 접이식 (docs/specs/shared-goals.md).
 *  주간 달성표(자동 집계, ReviewLog 기반) + 체크리스트(수동 약속)를 상대와
 *  공유한다. 기본 접힘 — 채팅 시야를 가리지 않는다.
 *
 *  오피스 위장(excel)에서는 "공동 시트" 풍 플레인 테이블로, 그 외 테마는
 *  노트 컨셉(brick 토큰)으로 렌더한다. 두 경우 모두 말풍선·이모지·캐릭터는
 *  쓰지 않는다(docs/specs/chat.md 위장 계약) — 달성 표시는 텍스트 뱃지만. */
export function GoalBoard({
  otherId,
  excel,
  peerName,
}: {
  otherId: number;
  excel: boolean;
  peerName?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [items, setItems] = useState<GoalItem[]>([]);
  const [weekly, setWeekly] = useState<GoalWeekly>({
    target: 300,
    mine: 0,
    theirs: 0,
  });
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editingTarget, setEditingTarget] = useState(false);
  const [targetInput, setTargetInput] = useState("");

  const load = useCallback(() => {
    if (!Number.isFinite(otherId)) return;
    chatApi
      .goals(otherId)
      .then((res) => {
        setItems(res.items);
        setWeekly(res.weekly);
      })
      .catch(() => {});
  }, [otherId]);

  useEffect(() => {
    load();
    // bfcache·백그라운드 복귀 시 재조회 — 리마운트 없이 stale 상태가 남는
    // 모바일 뒤로가기 케이스 방어 (MyPhrasesCard 와 동일 패턴)
    window.addEventListener("pageshow", load);
    window.addEventListener("focus", load);
    return () => {
      window.removeEventListener("pageshow", load);
      window.removeEventListener("focus", load);
    };
  }, [load]);

  // 상대가 추가·체크·삭제·목표 수정 시 goal.sync 수신 → 재조회
  useEffect(
    () =>
      onChatEvent((msg) => {
        if (msg.t === "goal.sync") load();
      }),
    [load],
  );

  const onToggleDone = useCallback(
    (item: GoalItem) => {
      const done = !item.done;
      setItems((prev) =>
        prev.map((g) => (g.id === item.id ? { ...g, done } : g)),
      );
      chatApi
        .patchGoal(item.id, { done })
        .then(load) // done_by_name 등 서버 확정값 반영
        .catch(() => {
          setError("변경하지 못했어요");
          load();
        });
    },
    [load],
  );

  const onDelete = useCallback(
    (id: number) => {
      setItems((prev) => prev.filter((g) => g.id !== id));
      chatApi.deleteGoal(id).catch(() => {
        setError("삭제하지 못했어요");
        load();
      });
    },
    [load],
  );

  const onAdd = useCallback(() => {
    const t = text.trim();
    if (!t || t.length > 100 || items.length >= MAX_ITEMS) return;
    setText("");
    chatApi
      .addGoal(otherId, t)
      .then(load)
      .catch(() => setError("추가하지 못했어요"));
  }, [text, items.length, otherId, load]);

  const onSaveTarget = useCallback(() => {
    const v = Math.trunc(Number(targetInput));
    setEditingTarget(false);
    if (!Number.isFinite(v) || v <= 0) return;
    setWeekly((prev) => ({ ...prev, target: v }));
    chatApi
      .setWeeklyTarget(otherId, v)
      .then(load)
      .catch(() => {
        setError("목표 저장에 실패했어요");
        load();
      });
  }, [targetInput, otherId, load]);

  const doneCount = items.filter((g) => g.done).length;
  const sum = weekly.mine + weekly.theirs;
  const pct =
    weekly.target > 0
      ? Math.min(100, Math.round((sum / weekly.target) * 100))
      : 0;
  const achieved = weekly.target > 0 && sum >= weekly.target;
  const peerLabel = peerName || "상대";
  const atMax = items.length >= MAX_ITEMS;

  return (
    <section
      className={
        excel
          ? "shrink-0 border-b border-[#d8dde3] bg-white font-sans text-[13px] text-[#24292f]"
          : "shrink-0 border-b-2 border-ink/10 bg-white/70"
      }
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className={
          excel
            ? "flex min-h-11 w-full items-center gap-2 px-3 text-left hover:bg-[#f6f8f9]"
            : "flex min-h-11 w-full items-center gap-2 px-3 text-left hover:bg-white"
        }
      >
        <span className={excel ? "font-bold" : "font-hand text-base font-bold"}>
          함께 목표 {doneCount}/{items.length}
        </span>
        <span className={excel ? "text-[#666]" : "opacity-60"}>
          이번 주 {sum}/{weekly.target}회
        </span>
        {achieved && (
          <span
            className={
              excel
                ? "rounded-sm border border-[#217346] px-1 text-[11px] font-bold text-[#217346]"
                : "rounded-full border-2 border-brick-green px-1.5 text-[11px] font-bold text-brick-green"
            }
          >
            달성!
          </span>
        )}
        <span
          className={`ml-auto text-xs ${excel ? "text-[#999]" : "opacity-50"}`}
        >
          {expanded ? "[-]" : "[+]"}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-3">
          {error && (
            <p
              className={
                excel
                  ? "mb-1.5 text-xs text-[#c0504d]"
                  : "mb-1.5 text-xs text-brick-red"
              }
            >
              {error}
            </p>
          )}

          {/* 주간 달성표 (자동) */}
          <div className="mb-3">
            <div
              className={
                excel
                  ? "h-2 w-full bg-[#e4e8ec]"
                  : "h-2 w-full rounded-full bg-ink/10"
              }
            >
              <div
                className={
                  excel ? "h-2 bg-[#217346]" : "h-2 rounded-full bg-brick-green"
                }
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <span className={excel ? "text-[#666]" : "opacity-60"}>
                나 {weekly.mine} · {peerLabel} {weekly.theirs}
              </span>
              {editingTarget ? (
                <span className="ml-auto flex items-center gap-1">
                  <input
                    type="number"
                    min={1}
                    value={targetInput}
                    onChange={(e) => setTargetInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onSaveTarget();
                    }}
                    aria-label="주간 목표 횟수"
                    className={
                      excel
                        ? "min-h-8 w-16 rounded-sm border border-[#c9cfd6] px-1.5 text-xs focus:border-[#217346] focus:outline-none"
                        : "min-h-8 w-16 rounded-md border-2 border-ink/20 px-1.5 text-xs focus:border-brick-blue focus:outline-none"
                    }
                  />
                  <button
                    type="button"
                    onClick={onSaveTarget}
                    className={`font-bold underline underline-offset-2 ${excel ? "text-[#217346]" : "text-brick-blue"}`}
                  >
                    저장
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setTargetInput(String(weekly.target));
                    setEditingTarget(true);
                  }}
                  className={`ml-auto underline underline-offset-2 ${
                    excel ? "text-[#217346]" : "text-brick-blue"
                  }`}
                >
                  목표 {weekly.target}회 수정
                </button>
              )}
            </div>
          </div>

          {/* 체크리스트 (수동) */}
          <ul className="flex flex-col">
            {items.map((item) => (
              <li
                key={item.id}
                className={`flex items-center gap-2 py-1 ${
                  excel ? "border-b border-[#f0f2f4]" : "border-b border-ink/5"
                }`}
              >
                <label className="flex min-h-11 min-w-11 shrink-0 items-center justify-center">
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => onToggleDone(item)}
                    aria-label={`${item.text} 완료 체크`}
                    className={
                      excel
                        ? "h-4 w-4 accent-[#217346]"
                        : "h-5 w-5 accent-brick-green"
                    }
                  />
                </label>
                <span
                  className={`min-w-0 flex-1 text-sm break-words ${
                    item.done ? "opacity-50 line-through" : ""
                  }`}
                >
                  {item.text}
                </span>
                {item.done && item.done_by_name && (
                  <span
                    className={`shrink-0 text-[11px] ${
                      excel ? "text-[#666]" : "opacity-50"
                    }`}
                  >
                    {item.done_by_name} 달성
                  </span>
                )}
                <DeleteMessageButton
                  label="삭제"
                  confirmLabel="정말 삭제?"
                  ariaLabel={`${item.text} 삭제`}
                  onDelete={() => onDelete(item.id)}
                  className={`shrink-0 text-xs opacity-40 hover:opacity-80 ${
                    excel ? "text-[#c0504d]" : "text-brick-red"
                  }`}
                />
              </li>
            ))}
            {items.length === 0 && (
              <li
                className={`py-2 text-center text-xs ${
                  excel ? "text-[#999]" : "opacity-40"
                }`}
              >
                아직 목표가 없어요
              </li>
            )}
          </ul>

          <div className="mt-2 flex items-center gap-1.5">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onAdd();
              }}
              maxLength={100}
              placeholder={
                atMax ? "최대 20개까지 추가할 수 있어요" : "목표 추가"
              }
              aria-label="새 목표 문구"
              disabled={atMax}
              className={
                excel
                  ? "min-h-10 flex-1 rounded-sm border border-[#c9cfd6] px-2 text-xs focus:border-[#217346] focus:outline-none disabled:opacity-50"
                  : "min-h-10 flex-1 rounded-md border-2 border-ink/20 px-2 text-xs focus:border-brick-blue focus:outline-none disabled:opacity-50"
              }
            />
            <button
              type="button"
              onClick={onAdd}
              disabled={!text.trim() || atMax}
              className={
                excel
                  ? "min-h-10 shrink-0 rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-2.5 text-xs hover:bg-[#e2efda] disabled:opacity-40"
                  : "min-h-10 shrink-0 rounded-md bg-brick-blue px-2.5 text-xs font-bold text-brick-label hover:bg-brick-blue/85 disabled:opacity-40"
              }
            >
              추가
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

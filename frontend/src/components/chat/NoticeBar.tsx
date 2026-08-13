"use client";

import { useCallback, useEffect, useState, type RefObject } from "react";
import { DeleteMessageButton } from "@/components/chat/DeleteMessageButton";
import { chatApi, type ChatNotice } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";

const MAX_LEN = 500;

export interface NoticeBarHandle {
  /** 헤더 케밥 메뉴가 편집 시트를 여는 통로 — 공지 유무와 무관하게 호출 가능 */
  openEditor: () => void;
  /** 케밥 메뉴 라벨("공지 쓰기"/"공지 수정") 분기용 */
  hasNotice: boolean;
}

/** 대화방 공지 바 — 헤더 아래·GoalBoard 위 접이식 (docs/specs/chat-notice.md).
 *  공지가 없으면 렌더하지 않는다(기본 숨김). 편집 시트는 이 컴포넌트 내부
 *  상태로 관리하되, 헤더 케밥 메뉴가 apiRef.openEditor() 로 열 수 있다 —
 *  공지가 없어도 새로 쓸 수 있어야 하기 때문이다.
 *
 *  접힘 배치·재조회 패턴은 GoalBoard 를 그대로 따른다: 기본 접힘(localStorage
 *  기억), pageshow·focus 재조회, WS 로 상대 변경 신호(chat.notice) 수신 시 재조회. */
export function NoticeBar({
  otherId,
  excel,
  apiRef,
}: {
  otherId: number;
  excel: boolean;
  apiRef?: RefObject<NoticeBarHandle | null>;
}) {
  const [notice, setNotice] = useState<ChatNotice | null>(null);
  const [folded, setFolded] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const foldKey = `esl:chat-notice:fold:${otherId}`;

  useEffect(() => {
    try {
      const saved = localStorage.getItem(foldKey);
      setFolded(saved !== "0"); // 기본 접힘 — 저장값이 "0"(펼침)일 때만 펼친다
    } catch {
      setFolded(true);
    }
    // foldKey 는 otherId 파생값이라 otherId 변경 시에만 다시 읽으면 된다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otherId]);

  const load = useCallback(() => {
    if (!Number.isFinite(otherId)) return;
    chatApi
      .notice(otherId)
      .then(setNotice)
      .catch(() => {});
  }, [otherId]);

  useEffect(() => {
    load();
    // bfcache·백그라운드 복귀 시 재조회 (GoalBoard 와 동일 패턴)
    window.addEventListener("pageshow", load);
    window.addEventListener("focus", load);
    return () => {
      window.removeEventListener("pageshow", load);
      window.removeEventListener("focus", load);
    };
  }, [load]);

  // 상대가 등록·수정·내리기 시 chat.notice 수신 → 재조회 (goal.sync 와 동일 패턴)
  useEffect(
    () =>
      onChatEvent((msg) => {
        if (msg.t === "chat.notice") load();
      }),
    [load],
  );

  const openEditor = useCallback(() => {
    setDraft(notice?.text ?? "");
    setError(null);
    setEditing(true);
  }, [notice]);

  useEffect(() => {
    if (!apiRef) return;
    apiRef.current = { openEditor, hasNotice: Boolean(notice?.text) };
  }, [apiRef, openEditor, notice]);

  function persistFold(next: boolean) {
    setFolded(next);
    try {
      localStorage.setItem(foldKey, next ? "1" : "0");
    } catch {
      // 저장 실패는 무시 — 세션 내 접힘 상태는 유지된다
    }
  }

  function onSave() {
    const t = draft.trim();
    if (!t || t.length > MAX_LEN) return;
    chatApi
      .setNotice(otherId, t)
      .then((res) => {
        setNotice(res);
        setEditing(false);
        persistFold(false); // 방금 쓴 공지는 펼쳐서 바로 확인
      })
      .catch(() => setError("공지를 저장하지 못했어요"));
  }

  function onClear() {
    chatApi
      .clearNotice(otherId)
      .then(() => setNotice({ text: null }))
      .catch(() => setError("공지를 내리지 못했어요"));
  }

  const wrapClass = excel
    ? "shrink-0 border-b border-[#d8dde3] bg-white font-sans text-[13px] text-[#24292f]"
    : "shrink-0 border-b-2 border-ink/10 bg-white/70";
  const errClass = excel
    ? "mb-1.5 text-xs text-[#c0504d]"
    : "mb-1.5 text-xs text-brick-red";

  if (editing) {
    return (
      <section className={`${wrapClass} px-3 py-2`}>
        {error && <p className={errClass}>{error}</p>}
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, MAX_LEN))}
          rows={4}
          placeholder="대화방 공지를 적어보세요"
          aria-label="공지 내용"
          className={
            excel
              ? "w-full resize-none rounded-sm border border-[#c9cfd6] px-2 py-1.5 text-xs focus:border-[#217346] focus:outline-none"
              : "w-full resize-none rounded-md border-2 border-ink/20 px-2 py-1.5 text-xs focus:border-brick-blue focus:outline-none"
          }
        />
        <div className="mt-1 flex items-center gap-3">
          <span
            className={`text-[10px] ${excel ? "text-[#999]" : "opacity-50"}`}
          >
            {draft.length}/{MAX_LEN}
          </span>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className={`ml-auto text-xs ${excel ? "text-[#666] hover:text-[#333]" : "opacity-60 hover:opacity-100"}`}
          >
            취소
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!draft.trim()}
            className={`text-xs font-bold disabled:opacity-40 ${
              excel ? "text-[#217346]" : "text-brick-blue"
            }`}
          >
            저장
          </button>
        </div>
      </section>
    );
  }

  if (!notice?.text) return null;

  const firstLine = notice.text.split("\n")[0] ?? "";

  return (
    <section className={wrapClass}>
      <button
        type="button"
        onClick={() => persistFold(!folded)}
        aria-expanded={!folded}
        className={
          excel
            ? "flex min-h-11 w-full items-center gap-2 px-3 text-left hover:bg-[#f6f8f9]"
            : "flex min-h-11 w-full items-center gap-2 px-3 text-left hover:bg-white"
        }
      >
        <span className="min-w-0 flex-1 truncate text-xs">
          [공지] {firstLine}
        </span>
        <span
          className={`ml-auto shrink-0 text-xs ${excel ? "text-[#999]" : "opacity-50"}`}
        >
          {folded ? "[+]" : "[-]"}
        </span>
      </button>

      {!folded && (
        <div className="px-3 pb-3">
          {error && <p className={errClass}>{error}</p>}
          <p className="mb-2 text-sm break-words whitespace-pre-wrap">
            {notice.text}
          </p>
          <div className="flex items-center gap-3 text-xs">
            <button
              type="button"
              onClick={openEditor}
              className={`font-bold underline underline-offset-2 ${
                excel ? "text-[#217346]" : "text-brick-blue"
              }`}
            >
              수정
            </button>
            <DeleteMessageButton
              label="내리기"
              confirmLabel="정말 내리기?"
              ariaLabel="공지 내리기"
              onDelete={onClear}
              className={
                excel ? "font-bold text-[#c0504d]" : "font-bold text-brick-red"
              }
            />
          </div>
        </div>
      )}
    </section>
  );
}

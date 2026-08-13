"use client";

import { useCallback, useEffect, useState, type RefObject } from "react";
import { DeleteMessageButton } from "@/components/chat/DeleteMessageButton";
import { chatApi, type ChatNotice } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";

const MAX_LEN = 500;
const TITLE_MAX = 80;

/** 서버 에러 코드(backend/app/services/notice.py) → 사용자 문구.
 *  미매핑 코드는 호출부의 기존 일반 문구로 폴백한다. */
const NOTICE_ERROR_MESSAGES: Record<string, string> = {
  not_friends: "친구 관계가 끊어져 수정할 수 없어요",
  invalid_title: "제목을 입력해주세요",
  title_too_long: "제목이 너무 길어요",
  text_too_long: "내용이 너무 길어요",
};

function noticeErrorMessage(e: unknown, fallback: string): string {
  const code = e instanceof Error ? e.message : "";
  return NOTICE_ERROR_MESSAGES[code] ?? fallback;
}

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
  const [titleDraft, setTitleDraft] = useState("");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  // 공지 저장·내리기 요청 중 중복 클릭 방지
  const [busy, setBusy] = useState(false);

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
    // 레거시 행(제목 도입 전) 편집 시 첫 줄을 제목 후보로 승격
    const legacyFirst = notice?.title
      ? ""
      : (notice?.text?.split("\n")[0] ?? "");
    setTitleDraft(notice?.title ?? legacyFirst);
    setDraft(notice?.text ?? "");
    setError(null);
    setEditing(true);
  }, [notice]);

  useEffect(() => {
    if (!apiRef) return;
    apiRef.current = {
      openEditor,
      hasNotice: Boolean(notice?.title || notice?.text),
    };
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
    const title = titleDraft.trim();
    const t = draft.trim();
    if (!title || title.length > TITLE_MAX || t.length > MAX_LEN) return;
    setBusy(true);
    chatApi
      .setNotice(otherId, title, t)
      .then((res) => {
        setNotice(res);
        setEditing(false);
        persistFold(false); // 방금 쓴 공지는 펼쳐서 바로 확인
      })
      .catch((e) => setError(noticeErrorMessage(e, "공지를 저장하지 못했어요")))
      .finally(() => setBusy(false));
  }

  function onClear() {
    setBusy(true);
    chatApi
      .clearNotice(otherId)
      .then(() => setNotice({ title: null, text: null }))
      .catch((e) => setError(noticeErrorMessage(e, "공지를 내리지 못했어요")))
      .finally(() => setBusy(false));
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
        <input
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value.slice(0, TITLE_MAX))}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSave();
          }}
          placeholder="공지 제목"
          aria-label="공지 제목"
          className={
            excel
              ? "mb-1.5 w-full rounded-sm border border-[#c9cfd6] px-2 py-1.5 text-xs font-bold focus:border-[#217346] focus:outline-none"
              : "mb-1.5 w-full rounded-md border-2 border-ink/20 px-2 py-1.5 text-xs font-bold focus:border-brick-blue focus:outline-none"
          }
        />
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, MAX_LEN))}
          rows={4}
          placeholder="내용 (선택)"
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
            disabled={!titleDraft.trim() || busy}
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

  if (!notice?.title && !notice?.text) return null;

  // 레거시 행(제목 도입 전)은 내용 첫 줄이 제목 역할을 대신한다
  const barTitle = notice.title ?? (notice.text?.split("\n")[0] || "");

  return (
    <section className={wrapClass}>
      {/* 액션은 접기 토글 옆에 — 펼쳐야 보이는 하단 배치는 못 찾는다 (2026-08-13) */}
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => persistFold(!folded)}
          aria-expanded={!folded}
          className={
            excel
              ? "flex min-h-11 min-w-0 flex-1 items-center px-3 text-left hover:bg-[#f6f8f9]"
              : "flex min-h-11 min-w-0 flex-1 items-center px-3 text-left hover:bg-white"
          }
        >
          <span className="min-w-0 flex-1 truncate text-xs">
            [공지] <span className="font-bold">{barTitle}</span>
          </span>
        </button>
        <button
          type="button"
          onClick={openEditor}
          className={`shrink-0 text-xs font-bold underline underline-offset-2 ${
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
          disabled={busy}
          className={`ml-3 shrink-0 text-xs font-bold ${
            excel
              ? "text-[#c0504d]"
              : "text-brick-red opacity-60 hover:opacity-100"
          }`}
        />
        <button
          type="button"
          onClick={() => persistFold(!folded)}
          aria-expanded={!folded}
          aria-label={folded ? "공지 펼치기" : "공지 접기"}
          className={`min-h-11 shrink-0 px-3 text-xs ${excel ? "text-[#999]" : "opacity-50"}`}
        >
          {folded ? "[+]" : "[-]"}
        </button>
      </div>

      {!folded && (
        <div className="max-h-52 overflow-y-auto px-3 pb-3">
          {error && <p className={errClass}>{error}</p>}
          {/* 레거시 행(title null)은 text 첫 줄이 바 제목이라 본문만 보여준다 */}
          {notice.title && (
            <p className="text-sm font-bold break-words">{notice.title}</p>
          )}
          {notice.text && (
            <p className="mt-1 text-sm break-words whitespace-pre-wrap">
              {notice.text}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

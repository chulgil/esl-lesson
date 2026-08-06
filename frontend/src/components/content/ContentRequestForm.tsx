"use client";

import { useState } from "react";
import { studyApi } from "@/lib/study-api";

/** "이런 영상이 보고 싶어요" — 공급을 수요와 연결 (effectiveness-audit P0-3).
 *  요청은 백오피스 등록 화면에 모여 CC 검색의 재료가 된다. 하루 5건 제한. */
export function ContentRequestForm() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await studyApi.requestContent(text.trim());
      setText("");
      setMessage("접수됐어요! 다음 등록 때 참고할게요");
    } catch (e) {
      const detail = e instanceof Error ? e.message : "";
      setMessage(
        detail === "daily_request_limit"
          ? "오늘은 요청을 다 썼어요 — 내일 다시 부탁드려요"
          : "접수에 실패했어요 — 잠시 후 다시 시도해주세요",
      );
    }
    setBusy(false);
  }

  return (
    <section className="mt-8 max-w-2xl rounded-lg border-2 border-dashed border-ink/20 bg-white/60 p-4">
      <p className="text-sm font-bold">이런 영상이 보고 싶어요</p>
      <p className="mt-0.5 text-xs opacity-60">
        주제·채널·난이도 뭐든 좋아요 — 새 콘텐츠 등록에 참고해요
      </p>
      <div className="mt-2 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          maxLength={300}
          placeholder="예: 초급자용 쉬운 일상 회화, 요리 영상"
          className="min-h-11 min-w-0 flex-1 rounded border-2 border-ink/20 bg-white px-3 text-sm"
        />
        <button
          type="button"
          onClick={submit}
          disabled={busy || !text.trim()}
          className="shrink-0 rounded-md border-2 border-brick-blue bg-white px-3 text-sm font-bold text-brick-blue disabled:opacity-40"
        >
          {busy ? "접수 중..." : "요청"}
        </button>
      </div>
      {message && <p className="mt-2 text-xs opacity-70">{message}</p>}
    </section>
  );
}

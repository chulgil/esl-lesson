"use client";

import { useState } from "react";
import { LinkifiedText } from "@/components/chat/LinkifiedText";
import { chatApi, type Translation } from "@/lib/chat-api";

/** 방 메시지 본문 — 번역 반전 표시 (docs/specs/chat-language-rooms.md 번역 규칙).
 *  본문 = 번역문(있으면), 원문은 [원문] 토글로 하단에 확인. TTS 스피커는 표시
 *  중인 학습언어 텍스트에 붙는다(구 TranslationLine 의 스피커를 이관). 번역이
 *  없으면(대상 언어와 같거나 예산 초과로 실패) 원문만 그대로 보여준다. */
export function MessageBody({
  body,
  translation,
  variant = "note",
}: {
  body: string;
  translation: Translation | null | undefined;
  variant?: "note" | "excel";
}) {
  const [showOriginal, setShowOriginal] = useState(false);
  const [playing, setPlaying] = useState(false);
  // 한글 독음 — [읽기] 토글 지연 로드 (2026-08-21 요청: 보낸 번역문을 바로
  // 소리 내어 읽게). undefined=미조회, "loading"=조회 중, ""=실패/예산 초과
  const [showReading, setShowReading] = useState(false);
  const [reading, setReading] = useState<string | undefined>(undefined);

  const shown = translation?.text || body;
  const readable =
    translation && (translation.lang === "en" || translation.lang === "ja");

  function toggleReading() {
    if (showReading) {
      setShowReading(false);
      return;
    }
    setShowReading(true);
    if (reading === undefined && translation) {
      setReading("loading");
      chatApi
        .reading(shown, translation.lang)
        .then((res) => setReading(res.reading ?? ""))
        .catch(() => setReading(""));
    }
  }

  function play() {
    if (playing || !translation) return;
    const audio = new Audio(
      `/api/tts?text=${encodeURIComponent(shown)}&lang=${translation.lang}`,
    );
    setPlaying(true);
    const stop = () => setPlaying(false);
    audio.addEventListener("ended", stop, { once: true });
    audio.addEventListener("error", stop, { once: true });
    audio.play().catch(stop);
  }

  const hintBtnCls =
    variant === "excel"
      ? "text-[#8a8f98] hover:text-[#217346]"
      : "opacity-50 hover:opacity-90";
  const hintTextCls =
    variant === "excel"
      ? "text-[11px] text-[#8a8f98]"
      : "text-[11px] opacity-50";
  const speakerCls =
    variant === "excel"
      ? "text-[#8a8f98] hover:text-[#217346]"
      : "opacity-60 hover:opacity-100";

  return (
    <>
      <span className="break-words whitespace-pre-wrap">
        <LinkifiedText text={shown} />
      </span>
      {translation && (
        <button
          type="button"
          onClick={play}
          disabled={playing}
          aria-label="발음 듣기"
          className={`ml-1 inline-block align-middle disabled:opacity-30 ${speakerCls}`}
        >
          <SpeakerIcon />
        </button>
      )}
      {translation && (
        <div className={`mt-0.5 flex items-start gap-1.5 ${hintTextCls}`}>
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className={`shrink-0 underline-offset-2 ${hintBtnCls} ${showOriginal ? "underline" : ""}`}
          >
            [원문]
          </button>
          {showOriginal && (
            <span className="break-words whitespace-pre-wrap italic">
              {body}
            </span>
          )}
        </div>
      )}
      {/* 한글 독음 — 원문 힌트 아래 줄. 본문(외국어)을 소리 나는 대로 한글로
          (2026-08-21 요청). 뜻이 아니라 발음 — TTS 스피커와 한 쌍 */}
      {readable && (
        <div className={`mt-0.5 flex items-start gap-1.5 ${hintTextCls}`}>
          <button
            type="button"
            onClick={toggleReading}
            className={`shrink-0 underline-offset-2 ${hintBtnCls} ${showReading ? "underline" : ""}`}
          >
            [읽기]
          </button>
          {showReading && (
            <span className="break-words whitespace-pre-wrap">
              {reading === "loading"
                ? "읽는 법을 만들고 있어요..."
                : reading === ""
                  ? "지금은 읽기를 만들 수 없어요"
                  : reading}
            </span>
          )}
        </div>
      )}
    </>
  );
}

function SpeakerIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="shrink-0"
    >
      <path d="M11 5 6 9H2v6h4l5 4V5Z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a9 9 0 0 1 0 14" />
    </svg>
  );
}

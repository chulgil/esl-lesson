"use client";

import { useState } from "react";
import type { Translation } from "@/lib/chat-api";

/** 채팅 번역 줄 — 본문 아래 각주처럼 붙는 자동 번역 + 발음 재생 (3개 스킨 공용, i18n).
 *  번역이 없으면(대상 언어와 같거나 아직 미완료) 아무것도 렌더링하지 않는다.
 *  위장 테마(엑셀 등)에서도 그 스킨의 회색 메타 텍스트 톤을 따라 각주처럼 보인다. */
export function TranslationLine({
  translation,
  variant = "note",
}: {
  translation: Translation | null | undefined;
  variant?: "note" | "excel";
}) {
  const [playing, setPlaying] = useState(false);

  if (!translation) return null;
  const { text, lang } = translation;

  function play() {
    if (playing) return; // 중복 클릭 방지
    const audio = new Audio(
      `/api/tts?text=${encodeURIComponent(text)}&lang=${lang}`,
    );
    setPlaying(true);
    const stop = () => setPlaying(false);
    audio.addEventListener("ended", stop, { once: true });
    audio.addEventListener("error", stop, { once: true });
    audio.play().catch(stop);
  }

  const textCls =
    variant === "excel"
      ? "text-[11px] text-[#8a8f98]"
      : "text-[11px] opacity-50";
  const btnCls =
    variant === "excel"
      ? "text-[#8a8f98] hover:text-[#217346]"
      : "opacity-60 hover:opacity-100";

  return (
    <div className={`mt-0.5 flex items-start gap-1 ${textCls}`}>
      <span className="break-words whitespace-pre-wrap italic">{text}</span>
      <button
        type="button"
        onClick={play}
        disabled={playing}
        aria-label="번역 발음 듣기"
        className={`mt-px shrink-0 disabled:opacity-30 ${btnCls}`}
      >
        <SpeakerIcon />
      </button>
    </div>
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

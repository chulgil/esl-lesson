import { langPairLabel } from "@/lib/chat-lang";
import type { RoomMode, SupportedLang } from "@/lib/chat-api";

/** 언어쌍 배지 — ASCII 텍스트 태그("한→영")만 사용, 국기 이모지·말풍선 금지
 *  (docs/specs/chat-language-rooms.md §기획 보완 #15 위장 테마와의 충돌 회피).
 *  일반 대화 방(mode=plain)은 언어쌍 대신 중립 "일반" 태그. */
export function LangPairBadge({
  source,
  target,
  mode = "learn",
  variant = "note",
}: {
  source: SupportedLang;
  target: SupportedLang;
  mode?: RoomMode;
  variant?: "note" | "excel";
}) {
  const plain = mode === "plain";
  return (
    <span
      className={
        variant === "excel"
          ? `shrink-0 rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-1.5 py-0.5 text-[10px] font-bold ${plain ? "text-[#666]" : "text-[#217346]"}`
          : `shrink-0 rounded-full border-2 px-2 py-0.5 text-[10px] font-bold ${plain ? "border-ink/20 bg-ink/5 text-ink/60" : "border-brick-blue/30 bg-brick-blue/10 text-brick-blue"}`
      }
    >
      {plain ? "일반" : langPairLabel(source, target)}
    </span>
  );
}

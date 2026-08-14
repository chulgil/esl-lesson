import { langPairLabel } from "@/lib/chat-lang";
import type { SupportedLang } from "@/lib/chat-api";

/** 언어쌍 배지 — ASCII 텍스트 태그("한→영")만 사용, 국기 이모지·말풍선 금지
 *  (docs/specs/chat-language-rooms.md §기획 보완 #15 위장 테마와의 충돌 회피). */
export function LangPairBadge({
  source,
  target,
  variant = "note",
}: {
  source: SupportedLang;
  target: SupportedLang;
  variant?: "note" | "excel";
}) {
  return (
    <span
      className={
        variant === "excel"
          ? "shrink-0 rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-1.5 py-0.5 text-[10px] font-bold text-[#217346]"
          : "shrink-0 rounded-full border-2 border-brick-blue/30 bg-brick-blue/10 px-2 py-0.5 text-[10px] font-bold text-brick-blue"
      }
    >
      {langPairLabel(source, target)}
    </span>
  );
}

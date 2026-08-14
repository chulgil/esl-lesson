import { langPairLabel } from "@/lib/chat-lang";
import type { RoomMode, SupportedLang } from "@/lib/chat-api";

/** 방 종류 배지 — ASCII 텍스트 태그만 사용, 국기 이모지·말풍선 금지
 *  (docs/specs/chat-language-rooms.md §기획 보완 #15 위장 테마와의 충돌 회피).
 *  학습 방 = "학습 한→영"(강조색) / 일반 방 = "일반"(중립) — 언어쌍만으로는
 *  목록에서 방 종류 구분이 어렵다는 보고(2026-08-14)로 종류 접두어 명시.
 *  전 표면(전체 목록·위젯 목록·방 헤더·레거시 선택 시트)이 이 컴포넌트 공용. */
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
      {plain ? "일반" : `학습 ${langPairLabel(source, target)}`}
    </span>
  );
}

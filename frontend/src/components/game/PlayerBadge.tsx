import { MascotSvg } from "@/components/theme/mascots";
import type { PlayerProfile } from "@/lib/game-ws";

/** 플레이어 배지 — 마스코트 아바타 + 이름 + 대표 업적 칭호 (mascot-shop.md).
 *  대기실·대전·리더보드 공용: 상대의 수집 상태가 보여야 경쟁 동기가 된다. */
export function PlayerBadge({
  name,
  profile,
  suffix,
}: {
  name: string;
  profile?: PlayerProfile | null;
  /** 이름 뒤 부가 표기 — "(방장)", "(나)" 등 */
  suffix?: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 align-middle">
      {profile?.mascot && (
        <span aria-hidden className="shrink-0">
          <MascotSvg kind={profile.mascot} outfits={[]} avatar />
        </span>
      )}
      <span className="flex flex-col text-left leading-tight">
        <span>
          {name}
          {suffix}
        </span>
        {profile?.title && (
          <span className="text-[10px] font-bold text-brick-blue/80">
            {profile.title}
          </span>
        )}
      </span>
    </span>
  );
}

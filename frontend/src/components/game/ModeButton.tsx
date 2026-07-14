"use client";

/** 게임 옵션 토글 버튼 (봇 레벨/봇 수 등) — 게임 공통 */
export function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-11 rounded-md px-3 text-sm font-bold transition-colors ${
        active ? "bg-ink text-white" : "bg-ink/5 hover:bg-ink/10"
      }`}
    >
      {children}
    </button>
  );
}

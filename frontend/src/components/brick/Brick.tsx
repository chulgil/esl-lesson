import Link from "next/link";
import type { ReactNode } from "react";

type BrickColor = "red" | "yellow" | "blue" | "green";

const COLOR_CLASSES: Record<BrickColor, string> = {
  red: "bg-brick-red text-brick-red shadow-[0_6px_0_var(--color-brick-red-shadow)] active:shadow-[0_2px_0_var(--color-brick-red-shadow)]",
  yellow:
    "bg-brick-yellow text-brick-yellow shadow-[0_6px_0_var(--color-brick-yellow-shadow)] active:shadow-[0_2px_0_var(--color-brick-yellow-shadow)]",
  blue: "bg-brick-blue text-brick-blue shadow-[0_6px_0_var(--color-brick-blue-shadow)] active:shadow-[0_2px_0_var(--color-brick-blue-shadow)]",
  green:
    "bg-brick-green text-brick-green shadow-[0_6px_0_var(--color-brick-green-shadow)] active:shadow-[0_2px_0_var(--color-brick-green-shadow)]",
};

interface BrickProps {
  color?: BrickColor;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}

/** 레고 브릭 버튼 — 시그니처 컴포넌트 (docs/specs/ui-design.md) */
export function Brick({
  color = "red",
  href,
  onClick,
  disabled = false,
  children,
  className = "",
}: BrickProps) {
  // 그림자도 함께 트랜지션 — active 시 눌림이 뚝 끊기지 않게
  const classes = `brick-studs relative inline-flex min-h-11 cursor-pointer items-center justify-center rounded-md px-6 py-2.5 font-bold transition-[transform,box-shadow,opacity] duration-100 hover:-translate-y-0.5 active:translate-y-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 ${COLOR_CLASSES[color]} ${className}`;

  const inner = (
    // 라벨색은 테마 토큰 — 캔디(파스텔)에서 흰 글씨 대비 미달 교정
    <span className={color === "yellow" ? "text-ink" : "text-brick-label"}>
      {children}
    </span>
  );

  if (href) {
    return (
      <Link href={href} className={classes}>
        {inner}
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={classes}
    >
      {inner}
    </button>
  );
}

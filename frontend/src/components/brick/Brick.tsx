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
  children: ReactNode;
  className?: string;
}

/** 레고 브릭 버튼 — 시그니처 컴포넌트 (docs/specs/ui-design.md) */
export function Brick({
  color = "red",
  href,
  onClick,
  children,
  className = "",
}: BrickProps) {
  const classes = `brick-studs relative inline-flex min-h-11 items-center justify-center rounded-md px-6 py-2.5 font-bold transition-transform duration-100 hover:-translate-y-0.5 active:translate-y-1 ${COLOR_CLASSES[color]} ${className}`;

  const inner = (
    <span className={color === "yellow" ? "text-ink" : "text-white"}>
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
    <button type="button" onClick={onClick} className={classes}>
      {inner}
    </button>
  );
}

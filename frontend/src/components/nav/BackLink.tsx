import Link from "next/link";

/** 버튼형 뒤로가기 — 44px 터치 타겟, 화살표 + 목적지 라벨 (docs/specs/ui-design.md 내비게이션) */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex min-h-11 items-center gap-2 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:-translate-y-0.5 hover:border-brick-blue hover:text-brick-blue"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M19 12H5" />
        <path d="m12 19-7-7 7-7" />
      </svg>
      {label}
    </Link>
  );
}

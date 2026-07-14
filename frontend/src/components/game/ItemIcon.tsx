/** 게임 아이템 SVG 아이콘 — 유니코드 문자(❄ ? * ▽) 대체: 크기·정렬·굵기 일관 */

const PATHS: Record<string, React.ReactNode> = {
  // 눈결정 — 3초 멈춤
  freeze: (
    <>
      <path d="M12 2v20M4 5l16 14M20 5L4 19" />
      <path d="M12 6l2.5-2.5M12 6 9.5 3.5M12 18l2.5 2.5M12 18l-2.5 2.5" />
    </>
  ),
  // 전구 — 정답 보기
  hint: (
    <>
      <path d="M9 18h6M10 21h4" />
      <path d="M12 3a6 6 0 0 0-4 10.5c.8.7 1 1.5 1 2.5h6c0-1 .2-1.8 1-2.5A6 6 0 0 0 12 3Z" />
    </>
  ),
  // 버스트 — 젤리 제거
  bomb: (
    <>
      <circle cx="12" cy="13" r="5" />
      <path d="M12 8V5M8.5 9.5 6 7M15.5 9.5 18 7M12 3v1" />
    </>
  ),
  // 방패 — 공격 방어
  shield: <path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z" />,
};

export function ItemIcon({ kind, size = 18 }: { kind: string; size?: number }) {
  const path = PATHS[kind];
  if (!path) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {path}
    </svg>
  );
}

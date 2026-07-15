"use client";

import { useCallback, useRef, useState } from "react";

/** 관전 채팅·응원 플로팅 오버레이 — 위로 떠오르며 사라진다 (집중 보호 설계).
 *  고정 채팅창 없이 반투명 칩이 흘러가고, 클릭을 막지 않는다 (pointer-events-none). */

export interface FloatItem {
  id: number;
  name: string;
  text?: string;
  kind?: string;
  left: number; // 가로 위치 % (도착 순서 기반 분산 — 렌더 결정성)
}

const MAX_VISIBLE = 12;
const LIFETIME_MS = 4500;

export function useFloatingCheers() {
  const [items, setItems] = useState<FloatItem[]>([]);
  const seq = useRef(0);

  const push = useCallback(
    (m: { name: string; text?: string; kind?: string }) => {
      seq.current += 1;
      const id = seq.current;
      const item: FloatItem = { id, left: 6 + ((id * 29) % 58), ...m };
      setItems((prev) => [...prev.slice(-(MAX_VISIBLE - 1)), item]);
      setTimeout(
        () => setItems((prev) => prev.filter((i) => i.id !== id)),
        LIFETIME_MS,
      );
    },
    [],
  );

  return { items, push };
}

export function FloatingCheers({ items }: { items: FloatItem[] }) {
  if (items.length === 0) return null;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 bottom-28 z-30 h-0"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className="cheer-float absolute bottom-0 flex max-w-[70vw] items-center gap-1.5 rounded-full border border-ink/10 bg-paper/75 px-3 py-1 text-sm shadow-sm backdrop-blur-[2px]"
          style={{ left: `${item.left}%` }}
        >
          {item.kind && <CheerIcon kind={item.kind} />}
          <b className="shrink-0 text-xs opacity-70">{item.name}</b>
          {item.text && <span className="truncate">{item.text}</span>}
        </div>
      ))}
    </div>
  );
}

/** 응원 종류 — 테마 브릭 색을 따라 4종 (별/하트/폭죽/발도장) */
export const CHEER_KINDS = [
  { kind: "star", label: "별", color: "text-brick-yellow" },
  { kind: "heart", label: "하트", color: "text-brick-red" },
  { kind: "party", label: "폭죽", color: "text-brick-blue" },
  { kind: "paw", label: "발도장", color: "text-brick-green" },
];

export function CheerIcon({ kind }: { kind: string }) {
  const meta = CHEER_KINDS.find((c) => c.kind === kind) ?? CHEER_KINDS[0];
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-4 w-4 shrink-0 ${meta.color}`}
      fill="currentColor"
      stroke="currentColor"
      strokeWidth="1"
      strokeLinejoin="round"
      aria-hidden
    >
      {ICONS[meta.kind]}
    </svg>
  );
}

const ICONS: Record<string, React.ReactNode> = {
  star: (
    <path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z" />
  ),
  heart: (
    <path d="M12 21c-6-4.5-9-8-9-11.5C3 6.5 5 4.5 7.5 4.5c1.8 0 3.5 1 4.5 2.6 1-1.6 2.7-2.6 4.5-2.6C19 4.5 21 6.5 21 9.5 21 13 18 16.5 12 21z" />
  ),
  party: <path d="M4 20l4-12 8 8-12 4zm10-13l2-4m1 7l4-2m-3 5l3 1M13 4l1 2" />,
  paw: (
    <path d="M12 12c2.8 0 5.5 2 5.5 4.6 0 1.7-1.3 2.9-3 2.9-1 0-1.7-.4-2.5-.4s-1.5.4-2.5.4c-1.7 0-3-1.2-3-2.9C6.5 14 9.2 12 12 12zM7 7.5A1.9 1.9 0 118.8 9 1.9 1.9 0 017 7.5zm10 0A1.9 1.9 0 1115.2 9 1.9 1.9 0 0117 7.5zM10.2 4.5a1.8 1.8 0 111.7 1.6 1.75 1.75 0 01-1.7-1.6zm5.4 0a1.8 1.8 0 11-1.7 1.6 1.75 1.75 0 011.7-1.6z" />
  ),
};

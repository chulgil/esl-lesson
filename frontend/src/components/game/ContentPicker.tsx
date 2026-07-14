"use client";

import { useEffect, useState } from "react";
import type { ContentSummary } from "@/lib/admin-api";
import { myApi } from "@/lib/my-api";

/** 대전 소재 선택 — 내 콘텐츠 다중 선택, 미선택 시 공용 (게임 공통) */
export function ContentPicker({
  selected,
  onChange,
  hint,
}: {
  selected: number[];
  onChange: (ids: number[]) => void;
  hint?: string;
}) {
  const [contents, setContents] = useState<ContentSummary[]>([]);

  useEffect(() => {
    myApi
      .list()
      .then((res) => setContents(res.items.filter((c) => c.status === "ready")))
      .catch(() => undefined);
  }, []);

  if (contents.length === 0) return null;

  function toggle(id: number) {
    onChange(
      selected.includes(id)
        ? selected.filter((v) => v !== id)
        : [...selected, id],
    );
  }

  return (
    <div>
      <p className="mb-2 text-sm font-bold">
        대전 소재
        <span className="ml-2 text-xs font-normal opacity-60">
          {hint ?? "내 콘텐츠를 고르면 그 단어로 진행 (미선택 시 공용)"}
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChange([])}
          aria-pressed={selected.length === 0}
          className={`min-h-11 rounded-md px-3 text-sm font-bold transition-colors ${
            selected.length === 0
              ? "bg-ink text-white"
              : "bg-ink/5 hover:bg-ink/10"
          }`}
        >
          공용 전체
        </button>
        {contents.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => toggle(c.id)}
            aria-pressed={selected.includes(c.id)}
            className={`min-h-11 max-w-56 truncate rounded-md px-3 text-sm transition-colors ${
              selected.includes(c.id)
                ? "bg-brick-yellow font-bold"
                : "bg-ink/5 hover:bg-ink/10"
            }`}
          >
            {c.title}
          </button>
        ))}
      </div>
    </div>
  );
}

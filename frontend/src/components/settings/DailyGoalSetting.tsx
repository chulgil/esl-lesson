"use client";

import { useEffect, useState } from "react";
import { studyApi } from "@/lib/study-api";

const CHOICES = [
  { value: 10, label: "가볍게", desc: "하루 10개 — 바쁜 날에도 지킬 수 있게" },
  { value: 20, label: "기본", desc: "하루 20개 — 꾸준함에 딱 좋은 양" },
  { value: 50, label: "열심히", desc: "하루 50개 — 빠르게 늘리고 싶을 때" },
];

/** 오늘의 목표 설정 — 밀린 양과 무관한 달성 가능 소량 (포기 방지 기획) */
export function DailyGoalSetting() {
  const [goal, setGoal] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => setGoal(s.daily_goal))
      .catch(() => undefined);
  }, []);

  async function choose(value: number) {
    setBusy(true);
    try {
      const s = await studyApi.patchSettings({ daily_goal: value });
      setGoal(s.daily_goal);
    } catch {
      // 실패 시 기존 값 유지
    }
    setBusy(false);
  }

  if (goal === null) return null;

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">오늘의 목표</p>
      <p className="mb-3 text-xs opacity-60">
        하루에 이만큼만 하면 &ldquo;오늘 성공&rdquo;이에요. 밀린 복습이 많아도
        목표는 그대로 — 나눠서 갚으면 돼요.
      </p>
      <div className="flex flex-col gap-2">
        {CHOICES.map((c) => {
          const active = goal === c.value;
          return (
            <button
              key={c.value}
              type="button"
              disabled={busy}
              onClick={() => choose(c.value)}
              aria-pressed={active}
              className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border-2 bg-white px-4 py-2 text-left transition disabled:opacity-50 ${
                active
                  ? "border-ink shadow-md"
                  : "border-ink/15 hover:border-ink/40"
              }`}
            >
              <span className="w-14 shrink-0 text-sm font-bold">{c.label}</span>
              <span className="flex-1 text-xs opacity-60">{c.desc}</span>
              {active && (
                <span className="rounded-full bg-ink px-2.5 py-0.5 text-xs font-bold text-white">
                  사용 중
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}

"use client";

import { APP_THEMES, setAppTheme, useAppTheme } from "@/lib/theme";

export default function SettingsPage() {
  const theme = useAppTheme();

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <h1 className="mb-6 font-hand text-3xl font-bold">
        <span className="hl">설정</span>
      </h1>

      <section className="max-w-lg">
        <p className="mb-1 text-sm font-bold">테마</p>
        <p className="mb-3 text-xs opacity-60">
          앱 전체(배경·버튼·게임 보드)의 디자인 컨셉이 함께 바뀝니다
        </p>
        <div className="flex flex-col gap-3">
          {APP_THEMES.map((t) => {
            const active = theme === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setAppTheme(t.key)}
                aria-pressed={active}
                className={`flex min-h-14 cursor-pointer items-center gap-4 rounded-lg border-2 bg-white px-4 py-3 text-left transition hover:-translate-y-0.5 ${
                  active ? "border-ink shadow-md" : "border-ink/15 shadow-sm"
                }`}
              >
                <span
                  className="inline-block h-8 w-8 shrink-0 rounded-full border-2 border-ink/15"
                  style={{ backgroundColor: t.swatch }}
                />
                <span className="flex-1">
                  <span className="block font-bold">{t.label}</span>
                  <span className="block text-xs opacity-60">{t.desc}</span>
                </span>
                {active && (
                  <span className="rounded-full bg-ink px-3 py-1 text-xs font-bold text-white">
                    사용 중
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
}

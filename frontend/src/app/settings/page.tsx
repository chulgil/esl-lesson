"use client";

import Link from "next/link";
import { useState } from "react";
import { PushReminderCard } from "@/components/settings/PushReminderCard";
import { deleteMe } from "@/lib/api";
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

      <PushReminderCard />
      <DangerZone />
    </main>
  );
}

/** 회원탈퇴 — 2단계 확인 후 즉시 파기. 무엇이 지워지는지 명시해 불안 없이 결정하게 */
function DangerZone() {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    setFailed(false);
    const ok = await deleteMe().catch(() => false);
    if (ok) {
      window.location.href = "/";
      return;
    }
    setFailed(true);
    setDeleting(false);
  }

  return (
    <section className="mt-10 max-w-lg border-t-2 border-ink/10 pt-6">
      <p className="mb-1 text-sm font-bold">계정</p>
      <p className="mb-3 text-xs opacity-60">
        탈퇴하면 계정·학습 기록·게임 전적이 즉시 삭제되고 복구할 수 없어요.
        저장되는 개인정보는{" "}
        <Link href="/privacy" className="underline underline-offset-2">
          개인정보처리방침
        </Link>
        에서 확인할 수 있어요.
      </p>
      {!confirming ? (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold opacity-70 transition hover:border-brick-red hover:text-brick-red hover:opacity-100"
        >
          회원탈퇴
        </button>
      ) : (
        <div className="flex flex-wrap items-center gap-3 rounded-md border-2 border-brick-red/40 bg-white p-3">
          <p className="text-sm font-bold text-brick-red">
            정말 탈퇴할까요? 모든 데이터가 즉시 삭제돼요.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={deleting}
              onClick={handleDelete}
              className="min-h-11 rounded-md bg-brick-red px-4 text-sm font-bold text-brick-label transition-colors hover:bg-brick-red/85 disabled:opacity-50"
            >
              {deleting ? "삭제 중..." : "탈퇴하고 전부 삭제"}
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={() => setConfirming(false)}
              className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold"
            >
              취소
            </button>
          </div>
          {failed && (
            <p className="w-full text-xs text-brick-red">
              탈퇴 처리에 실패했어요 — 잠시 후 다시 시도해주세요.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

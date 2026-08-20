"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Brick } from "@/components/brick/Brick";
import { TrustNote } from "@/components/landing/TrustNote";
import { loginUrl } from "@/lib/api";

const ERROR_MESSAGES: Record<string, string> = {
  oauth: "Google 로그인에 실패했어요. 잠시 후 다시 시도해주세요.",
  unverified: "이메일 인증이 완료된 Google 계정만 사용할 수 있어요.",
};

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner() {
  const params = useSearchParams();
  const error = params.get("error");
  // 세션 게이트가 실어준 복귀 경로 — 로그인 후 보던 화면으로 (auth.md §세션 만료 라우팅)
  const next = params.get("next") ?? "/";
  const expired = params.get("reason") === "expired";

  return (
    <main className="notebook-lines notebook-margin flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <h1 className="font-hand text-4xl font-bold">
        <span className="hl">로그인</span>
      </h1>
      {expired && !error && (
        <p className="rounded-md border-2 border-ink/15 bg-white px-4 py-2 text-sm opacity-80">
          로그인이 만료됐어요 — 다시 로그인하면 보던 화면으로 돌아가요.
        </p>
      )}
      {error && (
        <p className="rounded-md border-2 border-margin-red bg-white px-4 py-2 text-sm">
          {ERROR_MESSAGES[error] ?? "로그인 중 문제가 발생했어요."}
        </p>
      )}
      <Brick color="red" href={loginUrl(next)}>
        Google로 시작하기
      </Brick>
      <TrustNote />
    </main>
  );
}

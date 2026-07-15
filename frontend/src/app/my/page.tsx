"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { StatusBadge } from "@/components/content/StatusBadge";
import type { ContentSummary } from "@/lib/admin-api";
import { myApi } from "@/lib/my-api";

type Tab = "youtube" | "manual";

export default function MyContentsPage() {
  const [contents, setContents] = useState<ContentSummary[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    myApi
      .list()
      .then((res) => setContents(res.items))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">내 콘텐츠</span>
        </h1>
        <span className="text-xs opacity-60">
          나만 보는 개인 학습 재료 (하루 10개)
        </span>
        <div className="ml-auto">
          <Brick color="red" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "닫기" : "+ 콘텐츠 등록"}
          </Brick>
        </div>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {showForm && (
        <RegisterForm
          onDone={() => {
            setShowForm(false);
            load();
          }}
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {contents.map((c, i) => (
          <Link
            key={c.id}
            href={`/my/${c.id}`}
            className={`rounded-lg border-2 border-ink/10 bg-white p-4 shadow-sm transition hover:-translate-y-1 ${
              i % 2 ? "rotate-[0.4deg]" : "-rotate-[0.4deg]"
            }`}
          >
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-50">
                {c.source === "youtube" ? "유튜브" : "수기"}
              </span>
              <StatusBadge status={c.status} />
            </div>
            <p className="mt-2 font-bold">{c.title}</p>
            {/* 진행 안내는 실패가 아니므로 빨간 에러 톤을 쓰지 않는다 */}
            {c.status === "failed" && c.error_message ? (
              <p className="mt-1 text-xs text-brick-red">{c.error_message}</p>
            ) : (
              c.status !== "ready" && (
                <p className="mt-1 text-xs opacity-50">
                  완성되면 저절로 오늘의 학습에 들어가요
                </p>
              )
            )}
          </Link>
        ))}
        {contents.length === 0 && !showForm && (
          <p className="text-sm opacity-50">
            좋아하는 유튜브 영상을 등록하면 나만의 영어 교재가 돼요.
          </p>
        )}
      </div>
    </main>
  );
}

function RegisterForm({ onDone }: { onDone: () => void }) {
  const [tab, setTab] = useState<Tab>("youtube");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [scriptEn, setScriptEn] = useState("");
  const [scriptKo, setScriptKo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      if (tab === "youtube") {
        await myApi.create({ source: "youtube", url });
      } else {
        await myApi.create({
          source: "manual",
          title,
          script_en: scriptEn,
          script_ko: scriptKo || undefined,
        });
      }
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "등록 실패");
      setSubmitting(false);
    }
  }

  return (
    <div className="mb-8 max-w-2xl rounded-lg border-2 border-ink/10 bg-white p-5">
      <div className="mb-4 flex gap-2">
        <TabButton
          label="유튜브 URL"
          active={tab === "youtube"}
          onClick={() => setTab("youtube")}
        />
        <TabButton
          label="수기 입력"
          active={tab === "manual"}
          onClick={() => setTab("manual")}
        />
      </div>

      {tab === "youtube" ? (
        <label className="flex flex-col gap-1 text-sm">
          유튜브 URL
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtu.be/..."
            className="rounded border-2 border-ink/20 px-3 py-2"
          />
          <span className="text-xs opacity-60">
            제목·스크립트·학습 항목이 자동으로 만들어져요 (보통 1~2분). 영어
            자막이 있는 영상만 등록할 수 있어요.
          </span>
        </label>
      ) : (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            제목 (필수)
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded border-2 border-ink/20 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            영어 스크립트 (필수)
            <textarea
              value={scriptEn}
              onChange={(e) => setScriptEn(e.target.value)}
              rows={6}
              className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            한글 스크립트 (비우면 AI 번역)
            <textarea
              value={scriptKo}
              onChange={(e) => setScriptKo(e.target.value)}
              rows={6}
              className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
            />
          </label>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-brick-red">{error}</p>}
      <div className="mt-4">
        <Brick color="green" onClick={submitting ? undefined : submit}>
          {submitting ? "등록 중..." : "등록"}
        </Brick>
      </div>
    </div>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-3 py-1.5 text-sm font-bold ${
        active ? "bg-ink text-white" : "bg-ink/5 hover:bg-ink/10"
      }`}
    >
      {label}
    </button>
  );
}

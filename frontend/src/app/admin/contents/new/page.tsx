"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { adminApi } from "@/lib/admin-api";

type Tab = "youtube" | "manual";

export default function NewContentPage() {
  const router = useRouter();
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
        await adminApi.createContent({ source: "youtube", url });
      } else {
        await adminApi.createContent({
          source: "manual",
          title,
          script_en: scriptEn,
          script_ko: scriptKo || undefined,
          url: url || undefined,
        });
      }
      router.push("/admin/contents");
    } catch (e) {
      setError(e instanceof Error ? e.message : "등록 실패");
      setSubmitting(false);
    }
  }

  return (
    <section className="max-w-2xl">
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">콘텐츠 등록</span>
      </h1>

      <div className="mt-4 flex gap-2">
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

      <div className="mt-4 flex flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6">
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
              제목과 영어/한글 스크립트는 자동으로 추출됩니다.
            </span>
          </label>
        ) : (
          <>
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
                rows={8}
                className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              한글 스크립트 (비우면 AI 번역)
              <textarea
                value={scriptKo}
                onChange={(e) => setScriptKo(e.target.value)}
                rows={8}
                className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              원본 URL (선택)
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
            </label>
          </>
        )}

        {error && <p className="text-sm text-brick-red">{error}</p>}

        <div>
          <Brick color="green" onClick={submitting ? undefined : submit}>
            {submitting ? "등록 중..." : "등록"}
          </Brick>
        </div>
      </div>
    </section>
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
      className={`rounded-t px-4 py-2 text-sm font-bold ${
        active
          ? "bg-white border-2 border-b-0 border-ink/10"
          : "bg-ink/5 hover:bg-ink/10"
      }`}
    >
      {label}
    </button>
  );
}

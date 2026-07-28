"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { ExtractionProgress } from "@/components/content/ExtractionProgress";
import { StatusBadge } from "@/components/content/StatusBadge";
import { BackLink } from "@/components/nav/BackLink";
import { myApi, type MyContentDetail, type MyItem } from "@/lib/my-api";

const TYPE_LABELS: Record<string, string> = {
  word: "단어",
  idiom: "숙어",
  pattern: "패턴",
  sentence: "문장",
};

export default function MyContentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const contentId = Number(id);
  const router = useRouter();
  const [detail, setDetail] = useState<MyContentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    myApi
      .get(contentId)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [contentId]);

  useEffect(() => {
    load();
    const timer = setInterval(() => {
      setDetail((d) => {
        if (d && (d.status === "pending" || d.status === "extracting")) load();
        return d;
      });
    }, 5000);
    return () => clearInterval(timer);
  }, [load]);

  if (error) return <main className="p-8 text-sm text-brick-red">{error}</main>;
  if (!detail)
    return <main className="p-8 text-sm opacity-60">불러오는 중...</main>;

  async function retry() {
    await myApi.retry(contentId).catch((e) => setError(e.message));
    load();
  }

  async function remove() {
    if (
      !confirm(
        "이 콘텐츠를 내 학습에서 뺄까요?\n학습 기록은 안전하게 보관돼요 — 다시 담으면 그대로 이어져요.",
      )
    )
      return;
    await myApi.remove(contentId).catch((e) => setError(e.message));
    router.push("/my");
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <BackLink href="/my" label="내 콘텐츠" />
        <h1 className="font-hand text-2xl font-bold">
          <span className="hl">{detail.title}</span>
        </h1>
        <StatusBadge status={detail.status} />
        {detail.status === "failed" && (
          <Brick
            color="yellow"
            onClick={retry}
            className="!min-h-8 !px-3 !py-1 text-xs"
          >
            재시도
          </Brick>
        )}
        <button
          type="button"
          onClick={remove}
          className="ml-auto text-xs text-brick-red hover:underline"
        >
          삭제
        </button>
      </header>

      {(detail.status === "pending" || detail.status === "extracting") && (
        <ExtractionProgress source={detail.source} jobs={detail.jobs} />
      )}
      {/* 진행 중 안내(자막 준비 중 등)는 위 단계 표시가 담당 — 빨간 에러는 실패일 때만 */}
      {detail.status === "failed" && detail.error_message && (
        <p className="mb-4 text-sm text-brick-red">{detail.error_message}</p>
      )}

      {detail.items.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-2 font-bold">
            추출된 학습 항목 {detail.items.length}개
            <span className="ml-2 text-xs font-normal opacity-60">
              필요 없는 항목은 &quot;학습 제외&quot;를 누르세요
            </span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse bg-white text-sm">
              <thead>
                <tr className="border-b-2 border-ink/20 text-left text-xs">
                  <th className="w-16 p-2">타입</th>
                  <th className="p-2">영어</th>
                  <th className="p-2">한글</th>
                  <th className="w-28 p-2">학습</th>
                </tr>
              </thead>
              <tbody>
                {detail.items.map((item) => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    onChanged={load}
                    onError={setError}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {detail.segments.length > 0 && (
        <section>
          <h2 className="mb-2 font-bold">스크립트</h2>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse bg-white text-sm">
              <tbody>
                {detail.segments.map((s) => (
                  <tr key={s.id} className="border-b border-ink/10 align-top">
                    <td className="w-1/2 p-2">{s.en_text}</td>
                    <td className="p-2 opacity-80">{s.ko_text ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

function ItemRow({
  item,
  onChanged,
  onError,
}: {
  item: MyItem;
  onChanged: () => void;
  onError: (msg: string) => void;
}) {
  async function toggle() {
    try {
      if (item.excluded) {
        await myApi.include(item.id);
      } else {
        await myApi.exclude(item.id);
      }
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "실패");
    }
  }

  return (
    <tr
      className={`border-b border-ink/10 align-top ${item.excluded ? "opacity-40" : ""}`}
    >
      <td className="p-2 text-xs">{TYPE_LABELS[item.item_type]}</td>
      <td className="p-2">
        {item.en_text}
        {item.context_en && (
          <p className="mt-0.5 text-xs opacity-50">
            &quot;{item.context_en}&quot;
          </p>
        )}
      </td>
      <td className="p-2">
        {item.ko_text}
        {item.hint_thinking && (
          <p className="mt-0.5 text-xs text-brick-blue">
            ({item.hint_thinking})
          </p>
        )}
      </td>
      <td className="p-2">
        <button
          type="button"
          onClick={toggle}
          className={`text-xs ${item.excluded ? "text-brick-green" : "text-brick-red"} hover:underline`}
        >
          {item.excluded ? "학습 복귀" : "학습 제외"}
        </button>
      </td>
    </tr>
  );
}

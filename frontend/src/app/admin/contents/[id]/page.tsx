"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { adminApi, type ContentDetail, type Item } from "@/lib/admin-api";

type Tab = "script" | "word" | "idiom" | "pattern" | "sentence";

const TAB_LABELS: Record<Exclude<Tab, "script">, string> = {
  word: "단어",
  idiom: "숙어",
  pattern: "패턴",
  sentence: "문장",
};

export default function ContentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const contentId = Number(id);
  const router = useRouter();
  const [detail, setDetail] = useState<ContentDetail | null>(null);
  const [tab, setTab] = useState<Tab>("script");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi
      .getContent(contentId)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [contentId]);

  useEffect(() => {
    load();
    const timer = setInterval(() => {
      // 추출 진행 중일 때만 폴링
      setDetail((d) => {
        if (d && (d.status === "pending" || d.status === "extracting")) load();
        return d;
      });
    }, 5000);
    return () => clearInterval(timer);
  }, [load]);

  if (error) return <p className="text-sm text-brick-red">{error}</p>;
  if (!detail) return <p className="text-sm opacity-60">불러오는 중...</p>;

  const itemsByType = (type: string) =>
    detail.items.filter((i) => i.item_type === type);

  async function retry() {
    await adminApi.retryContent(contentId).catch((e) => setError(e.message));
    load();
  }

  async function remove() {
    if (!confirm("콘텐츠와 연결 항목을 삭제할까요?")) return;
    await adminApi.deleteContent(contentId).catch((e) => setError(e.message));
    router.push("/admin/contents");
  }

  async function approveAll() {
    try {
      const res = await adminApi.approveAll(contentId);
      setNotice(
        `${res.approved}개 승인${res.skipped ? `, ${res.skipped}개 건너뜀 (사고 힌트 필요)` : ""}`,
      );
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "실패");
    }
  }

  return (
    <section>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-hand text-2xl font-bold">
          <span className="hl">{detail.title}</span>
        </h1>
        <span className="rounded bg-ink/10 px-2 py-0.5 text-xs">
          {detail.status}
        </span>
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
      </div>
      {detail.error_message && (
        <p className="mt-2 text-sm text-brick-red">{detail.error_message}</p>
      )}

      <div className="mt-3 flex gap-2 text-xs">
        {detail.jobs.map((j) => (
          <span
            key={j.step}
            className={`rounded px-2 py-0.5 ${
              j.status === "done"
                ? "bg-brick-green/20 text-brick-green"
                : j.status === "failed"
                  ? "bg-brick-red/15 text-brick-red"
                  : "bg-ink/10"
            }`}
            title={j.error ?? undefined}
          >
            {j.step}: {j.status}
          </span>
        ))}
      </div>

      <div className="mt-6 flex items-center gap-2 border-b-2 border-ink/10">
        <TabButton
          label="스크립트"
          active={tab === "script"}
          onClick={() => setTab("script")}
        />
        {(Object.keys(TAB_LABELS) as Exclude<Tab, "script">[]).map((t) => (
          <TabButton
            key={t}
            label={`${TAB_LABELS[t]} ${itemsByType(t).length}`}
            active={tab === t}
            onClick={() => setTab(t)}
          />
        ))}
        {detail.items.some((i) => i.review_status === "pending") && (
          <button
            type="button"
            onClick={approveAll}
            className="ml-auto mb-1 rounded bg-brick-green px-3 py-1 text-xs font-bold text-white"
          >
            pending 일괄 승인
          </button>
        )}
      </div>

      {notice && <p className="mt-2 text-xs text-brick-green">{notice}</p>}

      {tab === "script" ? (
        <ScriptTable detail={detail} />
      ) : (
        <ItemTable
          items={itemsByType(tab)}
          onChanged={load}
          onError={setError}
        />
      )}
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
      className={`px-3 py-2 text-sm ${active ? "border-b-2 border-ink font-bold" : "opacity-60 hover:opacity-100"}`}
    >
      {label}
    </button>
  );
}

function ScriptTable({ detail }: { detail: ContentDetail }) {
  return (
    <div className="overflow-x-auto">
    <table className="mt-2 w-full border-collapse bg-white text-sm">
      <tbody>
        {detail.segments.map((s) => (
          <tr key={s.id} className="border-b border-ink/10 align-top">
            <td className="w-14 p-2 text-xs opacity-40">
              {s.start_ms != null ? formatMs(s.start_ms) : s.seq}
            </td>
            <td className="w-1/2 p-2">{s.en_text}</td>
            <td className="p-2 opacity-80">{s.ko_text ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function ItemTable({
  items,
  onChanged,
  onError,
}: {
  items: Item[];
  onChanged: () => void;
  onError: (msg: string) => void;
}) {
  async function setStatus(item: Item, review_status: Item["review_status"]) {
    try {
      await adminApi.patchItem(item.id, { review_status });
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "실패");
    }
  }

  return (
    <div className="overflow-x-auto">
    <table className="mt-2 w-full border-collapse bg-white text-sm">
      <thead>
        <tr className="border-b-2 border-ink/20 text-left text-xs">
          <th className="p-2">영어</th>
          <th className="p-2">한글</th>
          <th className="p-2 w-24">난이도</th>
          <th className="p-2 w-20">상태</th>
          <th className="p-2 w-36">액션</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <ItemRow
            key={item.id}
            item={item}
            onStatus={setStatus}
            onChanged={onChanged}
            onError={onError}
          />
        ))}
        {items.length === 0 && (
          <tr>
            <td colSpan={5} className="p-6 text-center text-sm opacity-50">
              추출된 항목이 없습니다.
            </td>
          </tr>
        )}
      </tbody>
    </table>
    </div>
  );
}

function ItemRow({
  item,
  onStatus,
  onChanged,
  onError,
}: {
  item: Item;
  onStatus: (item: Item, status: Item["review_status"]) => void;
  onChanged: () => void;
  onError: (msg: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [en, setEn] = useState(item.en_text);
  const [ko, setKo] = useState(item.ko_text);
  const [hint, setHint] = useState(item.hint_thinking ?? "");

  async function save() {
    try {
      await adminApi.patchItem(item.id, {
        en_text: en,
        ko_text: ko,
        hint_thinking: hint || undefined,
        review_status: "approved",
      });
      setEditing(false);
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "저장 실패");
    }
  }

  if (editing) {
    return (
      <tr className="border-b border-ink/10 bg-paper align-top">
        <td className="p-2">
          <input
            value={en}
            onChange={(e) => setEn(e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </td>
        <td className="p-2">
          <input
            value={ko}
            onChange={(e) => setKo(e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
          {item.item_type === "sentence" && (
            <input
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              placeholder="영어식 사고 힌트 (필수)"
              className="mt-1 w-full rounded border px-2 py-1 text-xs"
            />
          )}
        </td>
        <td className="p-2 text-xs">{item.difficulty_hint}</td>
        <td className="p-2 text-xs">{item.review_status}</td>
        <td className="p-2">
          <button
            type="button"
            onClick={save}
            className="mr-2 text-xs font-bold text-brick-green"
          >
            저장+승인
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="text-xs opacity-60"
          >
            취소
          </button>
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-b border-ink/10 align-top">
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
        {item.item_type === "sentence" && (
          <p
            className={`mt-0.5 text-xs ${item.hint_thinking ? "opacity-60" : "text-brick-red"}`}
          >
            {item.hint_thinking
              ? `(${item.hint_thinking})`
              : "사고 힌트 없음 — 수정 필요"}
          </p>
        )}
      </td>
      <td className="p-2 text-xs">{item.difficulty_hint}</td>
      <td className="p-2 text-xs">
        <StatusBadge status={item.review_status} />
      </td>
      <td className="p-2 text-xs">
        {item.review_status !== "approved" && (
          <button
            type="button"
            onClick={() => onStatus(item, "approved")}
            className="mr-2 font-bold text-brick-green"
          >
            승인
          </button>
        )}
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="mr-2 text-brick-blue"
        >
          수정
        </button>
        {item.review_status !== "rejected" && (
          <button
            type="button"
            onClick={() => onStatus(item, "rejected")}
            className="text-brick-red"
          >
            제외
          </button>
        )}
      </td>
    </tr>
  );
}

function StatusBadge({ status }: { status: Item["review_status"] }) {
  const styles = {
    pending: "bg-ink/10",
    approved: "bg-brick-green/20 text-brick-green",
    rejected: "bg-brick-red/15 text-brick-red",
  } as const;
  return (
    <span className={`rounded px-2 py-0.5 ${styles[status]}`}>{status}</span>
  );
}

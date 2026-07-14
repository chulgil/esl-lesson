"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { InsightSheet } from "@/components/study/InsightSheet";
import {
  VocabGraph,
  type GraphEdge,
  type GraphNode,
} from "@/components/study/VocabGraph";
import { studyApi, type VocabNetwork } from "@/lib/study-api";

const STATE_LEGEND = [
  { state: "new", label: "새 단어", cls: "bg-brick-blue" },
  { state: "learning", label: "학습 중", cls: "bg-brick-yellow" },
  { state: "review", label: "복습", cls: "bg-brick-green" },
  { state: "relearning", label: "재학습", cls: "bg-brick-red" },
  {
    state: "ghost",
    label: "추천",
    cls: "border-2 border-dashed border-ink/50 bg-paper",
  },
];

/** 어휘망 — 내 어휘를 임베딩 근접 관계로 잇는 그래프 (word-insight P3) */
export default function VocabNetworkPage() {
  const [data, setData] = useState<VocabNetwork | null>(null);
  const [error, setError] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showInsight, setShowInsight] = useState(false);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    studyApi
      .network()
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
    const mine: GraphNode[] = data.nodes.map((n) => ({
      id: n.item_id,
      en: n.en,
      ko: n.ko,
      // 원탭 추가 직후엔 새 단어로 표시
      state: addedIds.has(n.item_id) ? "new" : n.state,
      kind: "mine",
    }));
    const ghosts: GraphNode[] = data.suggestions.map((s) => ({
      id: s.item_id,
      en: s.en,
      ko: s.ko,
      state: addedIds.has(s.item_id) ? "new" : "ghost",
      kind: addedIds.has(s.item_id) ? "mine" : "ghost",
    }));
    const ghostEdges: GraphEdge[] = data.suggestions.map((s) => ({
      source: s.near_item_id,
      target: s.item_id,
      distance: s.distance,
      ghost: !addedIds.has(s.item_id),
    }));
    return {
      nodes: [...mine, ...ghosts],
      edges: [...data.edges, ...ghostEdges],
    };
  }, [data, addedIds]);

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  const handleSelect = useCallback((id: number | null) => {
    setSelectedId(id);
  }, []);

  async function addToDeck(itemId: number) {
    setAdding(true);
    try {
      await studyApi.addCard(itemId);
      setAddedIds((prev) => new Set(prev).add(itemId));
    } catch {
      // 실패 시 상태 유지 — 버튼 다시 활성화
    } finally {
      setAdding(false);
    }
  }

  return (
    <main className="notebook-lines notebook-margin flex min-h-screen flex-col px-6 py-10 sm:px-16">
      <header className="mb-4 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">어휘망</span>
        </h1>
      </header>

      {error && (
        <p className="text-sm text-brick-red">
          어휘망을 불러오지 못했어요 — 새로고침해 주세요
        </p>
      )}

      {!data && !error && (
        <p className="text-sm opacity-60">어휘망을 그리는 중...</p>
      )}

      {data && data.nodes.length === 0 && (
        <div className="flex flex-col items-start gap-4">
          <p>
            아직 어휘망에 그릴 단어가 없어요. 학습을 시작하면 단어들이 연결되기
            시작해요!
          </p>
          <Brick color="green" href="/study">
            오늘의 학습 시작
          </Brick>
        </div>
      )}

      {data && data.nodes.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs opacity-80">
            {STATE_LEGEND.map((l) => (
              <span key={l.state} className="flex items-center gap-1.5">
                <span className={`h-3 w-3 rounded-full ${l.cls}`} />
                {l.label}
              </span>
            ))}
            <span className="opacity-60">
              단어 {data.nodes.length} · 관계 {data.edges.length}
            </span>
          </div>

          {!data.embeddings_enabled && (
            <p className="mb-3 text-xs opacity-60">
              관계선은 준비 중이에요 — 단어들이 먼저 표시돼요
            </p>
          )}

          <div className="relative min-h-[420px] flex-1 overflow-hidden rounded-lg border-2 border-ink/15 bg-white/60">
            <VocabGraph
              nodes={nodes}
              edges={edges}
              selectedId={selectedId}
              onSelect={handleSelect}
            />

            {selected && (
              <div className="absolute inset-x-3 bottom-3 flex flex-wrap items-center gap-3 rounded-lg border-2 border-ink/15 bg-paper p-3 shadow-lg">
                <div className="min-w-0">
                  <p className="font-hand text-xl font-bold">{selected.en}</p>
                  <p className="truncate text-sm opacity-70">{selected.ko}</p>
                </div>
                <div className="ml-auto flex gap-2">
                  {selected.kind === "ghost" ? (
                    <button
                      type="button"
                      disabled={adding}
                      onClick={() => addToDeck(selected.id)}
                      className="min-h-11 rounded-md bg-brick-green px-4 font-bold text-white disabled:opacity-50"
                    >
                      + 학습에 추가
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setShowInsight(true)}
                      className="min-h-11 rounded-md border-2 border-brick-blue/40 bg-white px-4 font-bold text-brick-blue"
                    >
                      단어 정보
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label="선택 해제"
                    onClick={() => setSelectedId(null)}
                    className="min-h-11 min-w-11 rounded-md text-xl opacity-50 hover:opacity-100"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {showInsight && selected && (
        <InsightSheet
          itemId={selected.id}
          word={selected.en}
          onClose={() => setShowInsight(false)}
        />
      )}
    </main>
  );
}

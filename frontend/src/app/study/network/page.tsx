"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { InsightSheet } from "@/components/study/InsightSheet";
import {
  MEMORY_TIERS,
  VocabGraph,
  type GraphEdge,
  type GraphNode,
} from "@/components/study/VocabGraph";
import { VocabLangChips } from "@/components/study/VocabLangChips";
import { fetchMe, loginUrl } from "@/lib/api";
import { myApi } from "@/lib/my-api";
import { studyApi, type VocabNetwork } from "@/lib/study-api";
import {
  isVocabLang,
  readVocabLang,
  writeVocabLang,
  type VocabLang,
} from "@/lib/vocab-lang";

/* 기억 강도 램프 범례 — 모를수록 빨강(주의), 장기 기억일수록 회색(배경으로).
   색 정의는 VocabGraph.MEMORY_TIERS 단일 근거 (2026-08-21 인지 색 재설계) */
const STATE_LEGEND = [
  ...MEMORY_TIERS.map((t) => ({ label: t.label, color: t.color as string })),
  { label: "추천 (아직 내 것 아님)", color: null },
];

/** 어휘망 — 내 어휘를 임베딩 근접 관계로 잇는 그래프 (word-insight P3).
 *  학습언어가 복수면 언어 칩으로 네트워크를 나눠 보여준다 (2026-08-14 개정,
 *  §어휘망 언어별 분리) — MyPhrasesCard 의 언어 탭과 동일한 패턴. */
export default function VocabNetworkPage() {
  const [data, setData] = useState<VocabNetwork | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [learningLangs, setLearningLangs] = useState<VocabLang[] | null>(null);
  const [lang, setLang] = useState<VocabLang | null>(null);
  const [error, setError] = useState(false);
  const [needLogin, setNeedLogin] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showInsight, setShowInsight] = useState(false);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(false);
  const [hasContents, setHasContents] = useState<boolean | null>(null);

  useEffect(() => {
    // 공유 링크로 비로그인 진입 시 에러 대신 SSO 유도 (홈 Showcase 와 동일 게이트)
    fetchMe().then((me) => {
      if (!me) {
        setNeedLogin(true);
        return;
      }
      studyApi
        .getSettings()
        .then((s) => {
          const langs = s.learning_langs.filter(isVocabLang);
          setLearningLangs(langs);
          const saved = readVocabLang();
          const initial =
            saved && langs.includes(saved) ? saved : (langs[0] ?? "en");
          setLang(initial);
          writeVocabLang(initial);
        })
        .catch(() => {
          setLearningLangs([]);
          setLang("en");
        });
    });
  }, []);

  useEffect(() => {
    if (!lang) return;
    setData(null);
    setError(false);
    studyApi
      .network(lang)
      .then((res) => {
        setData(res);
        // 구버전 API(counts 미동봉) 응답에도 깨지지 않게 — 배포 순단·캐시 대비
        setCounts(res.counts ?? {});
        // 노드 0의 원인 구분 — 담은 콘텐츠가 없으면 라이브러리 유도 문구로 분기
        if (res.nodes.length === 0) {
          myApi
            .list()
            .then((my) => setHasContents(my.total > 0))
            .catch(() => setHasContents(true)); // 판별 실패 시 기존 문구 유지
        }
      })
      .catch(() => setError(true));
  }, [lang]);

  const chooseLang = useCallback((l: VocabLang) => {
    setLang(l);
    writeVocabLang(l);
    setSelectedId(null);
    setShowInsight(false);
  }, []);

  // 칩은 학습 데이터가 있는 언어만 — counts 는 언어 무관 전체 집계라 lang
  // 전환과 무관하게 유지된다
  const activeLangs = useMemo(
    () => (learningLangs ?? []).filter((l) => (counts[l] ?? 0) > 0),
    [learningLangs, counts],
  );
  const totalCount = useMemo(
    () => Object.values(counts).reduce((a, b) => a + b, 0),
    [counts],
  );

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
    const mine: GraphNode[] = data.nodes.map((n) => ({
      id: n.item_id,
      en: n.en,
      ko: n.ko,
      // 원탭 추가 직후엔 새 단어로 표시
      state: addedIds.has(n.item_id) ? "new" : n.state,
      kind: "mine",
      stability: n.stability ?? null,
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
    setAddError(false);
    try {
      await studyApi.addCard(itemId);
      setAddedIds((prev) => new Set(prev).add(itemId));
    } catch {
      // 실패 시 상태 유지 — 버튼 다시 활성화
      setAddError(true);
    } finally {
      setAdding(false);
    }
  }

  return (
    <main className="notebook-lines notebook-margin flex min-h-screen flex-col px-6 py-10 sm:px-16">
      <header className="mb-4 flex items-center gap-4">
        <BackLink href="/study" label="학습" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">어휘망</span>
        </h1>
      </header>

      {lang && (
        <VocabLangChips langs={activeLangs} lang={lang} onChange={chooseLang} />
      )}

      {needLogin && (
        <div className="flex flex-col items-start gap-4">
          <p>
            어휘망은 로그인하면 볼 수 있어요 — 내가 학습한 단어들이 연결돼요.
          </p>
          <Brick color="red" href={loginUrl("/study/network")}>
            Google로 시작하기
          </Brick>
        </div>
      )}

      {error && (
        <p className="text-sm text-brick-red">
          어휘망을 불러오지 못했어요 — 새로고침해 주세요
        </p>
      )}

      {!data && !error && !needLogin && (
        <p className="text-sm opacity-60">어휘망을 그리는 중...</p>
      )}

      {data &&
        data.nodes.length === 0 &&
        (hasContents === false ? (
          // 담은 콘텐츠 자체가 없으면 학습 유도보다 담기 유도가 먼저다
          <div className="flex flex-col items-start gap-4">
            <p>라이브러리에서 콘텐츠를 담으면 어휘망이 자라나요.</p>
            <Brick color="blue" href="/library">
              라이브러리 구경하기
            </Brick>
          </div>
        ) : totalCount > 0 ? (
          // 다른 언어엔 어휘망이 있지만 이 언어는 아직 없는 경우
          <p className="text-sm opacity-70">
            이 언어 학습 데이터가 아직 없어요 — 위 언어 칩에서 다른 언어를
            골라보세요.
          </p>
        ) : (
          <div className="flex flex-col items-start gap-4">
            <p>
              아직 어휘망에 그릴 단어가 없어요. 학습을 시작하면 단어들이
              연결되기 시작해요!
            </p>
            <Brick color="green" href="/study">
              오늘의 학습 시작
            </Brick>
          </div>
        ))}

      {data && data.nodes.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs opacity-80">
            {STATE_LEGEND.map((l) => (
              <span key={l.label} className="flex items-center gap-1.5">
                {l.color ? (
                  <span
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: l.color }}
                  />
                ) : (
                  <span className="h-3 w-3 rounded-full border-2 border-dashed border-ink/50 bg-paper" />
                )}
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
                      className="min-h-11 rounded-md bg-brick-green px-4 font-bold text-brick-label disabled:opacity-50"
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
                {addError && (
                  <p className="w-full text-xs font-bold text-brick-red">
                    추가하지 못했어요 — 다시 시도해 주세요
                  </p>
                )}
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

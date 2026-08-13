"use client";

import { useState } from "react";
import { InsightSheet } from "@/components/study/InsightSheet";
import { studyApi, type AnswerResult, type Question } from "@/lib/study-api";
import { useSurfaceSkin } from "@/lib/theme-surfaces";

/** 채점 피드백 카드 — 문항 카드와 같은 표면 스킨으로 채점한다 (2026-08-05
 *  테마 반영: 칠판=분필 채점, 오피스=조건부 서식, 학원=채점펜).
 *  session/page.tsx 에서 분리 (800줄 규칙). */

// 정답일 때만 노출하는 3등급 (안키 Hard/Good/Easy). 오답은 자동 Again → 단일 버튼.
const RATING_BUTTONS: {
  rating: number;
  label: string;
  active: string;
  idle: string;
}[] = [
  {
    rating: 2,
    label: "어려움",
    active: "border-brick-yellow bg-brick-yellow text-ink",
    idle: "border-brick-yellow/60 bg-white text-ink",
  },
  {
    rating: 3,
    label: "알맞음",
    active: "border-brick-green bg-brick-green text-brick-label",
    idle: "border-brick-green/40 bg-white text-brick-green",
  },
  {
    rating: 4,
    label: "쉬움",
    active: "border-brick-blue bg-brick-blue text-brick-label",
    idle: "border-brick-blue/40 bg-white text-brick-blue",
  },
];

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${Math.max(1, Math.round(minutes))}분 뒤`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}시간 뒤`;
  return `${Math.round(minutes / 1440)}일 뒤`;
}

export function SessionFeedback({
  question,
  result,
  onNext,
}: {
  question: Question;
  result: AnswerResult;
  onNext: () => void;
}) {
  const skin = useSurfaceSkin();
  const [submitting, setSubmitting] = useState(false);
  const [insight, setInsight] = useState<{
    itemId: number;
    word: string;
  } | null>(null);
  const [closeAdded, setCloseAdded] = useState(false);

  // 헷갈린 유사단어를 원탭으로 학습 큐에 추가 — 어휘망 확장 루프 (P3)
  async function addCloseWord() {
    if (!result.close_match || closeAdded) return;
    try {
      await studyApi.addCard(result.close_match.item_id);
      setCloseAdded(true);
    } catch {
      // 실패는 조용히 — 다음 기회에 다시 시도 가능
    }
  }

  // 인사이트는 항목의 영어 표현 기준 (en2ko 는 문제가 영어, 그 외는 정답이 영어)
  const enWord =
    question.quiz_mode === "choice_en2ko"
      ? (question.prompt ?? result.correct_answer)
      : result.correct_answer;

  // 안키식: 등급 버튼이 곧 "다음" — 자동 산출 등급과 다르면 재평가 후 진행
  async function pick(rating: number) {
    if (submitting) return;
    setSubmitting(true);
    if (rating !== result.rating_applied) {
      await studyApi.rate(question.card_id, rating).catch(() => undefined);
    }
    onNext();
  }

  const againMin = result.interval_previews?.["1"];

  // 다른 보기 단어 정보 진입 — 정답(출제 항목)은 위 [단어 정보] 버튼이 담당
  // (2026-08-13 사용자 요청: 오답 보기 단어의 뜻도 이 자리에서 배우게)
  const otherRefs = (question.choice_refs ?? []).filter(
    (r) => r.item_id !== question.item_id,
  );

  return (
    <div
      className={`mt-4 max-w-xl p-4 ${
        result.correct ? skin.feedbackOk : skin.feedbackBad
      }`}
    >
      <p
        className={`font-bold ${
          result.correct ? skin.feedbackOkText : skin.feedbackBadText
        }`}
      >
        {result.correct ? "[O] 정답!" : "[X] 오답 — 곧 다시 나와요"}
      </p>
      {result.long_term_reached && (
        // 장기 기억 도달 마이크로 축하 — 노력이 실력이 된 순간을 그 자리에서
        // 알린다. 모달 금지 — 흐름을 끊지 않는다 (user-journey-motivation P0 ①)
        <p className="mt-1 inline-block rounded bg-brick-green/15 px-2 py-0.5 text-xs font-bold text-brick-green">
          장기 기억으로 굳었어요! 일주일 넘게 안 봐도 기억할 카드예요
        </p>
      )}
      <div className="mt-2 flex items-center gap-3">
        <p className="text-lg">{result.correct_answer}</p>
        {question.level <= 2 && (
          // 단어/숙어만 인사이트 제공 (패턴/문장은 문장 단위라 제외 — P1)
          <button
            type="button"
            onClick={() =>
              setInsight({ itemId: question.item_id, word: enWord })
            }
            className="min-h-10 cursor-pointer rounded-full border-2 border-brick-blue/40 bg-white px-3.5 py-1 text-xs font-bold text-brick-blue transition hover:border-brick-blue active:scale-95"
          >
            단어 정보
          </button>
        )}
      </div>
      <p className="text-sm opacity-70">{result.explanation.ko}</p>
      {result.explanation.thinking_ko && (
        <p className="text-sm text-brick-blue">
          ({result.explanation.thinking_ko})
        </p>
      )}
      {result.explanation.context_en && (
        <p className="mt-1 text-xs opacity-50">
          &quot;{result.explanation.context_en}&quot;
        </p>
      )}

      {!result.correct && result.close_match && (
        // "아깝다" — 유사단어와 헷갈린 오답은 좌절 대신 비교 학습 기회로
        <div className="mt-3 rounded-md border-2 border-brick-yellow bg-highlight/30 p-3">
          <p className="text-sm font-bold">아깝다! 비슷한 단어와 헷갈렸어요</p>
          <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs opacity-50">내가 고른 답</p>
              <p className="font-bold">{result.close_match.en_text}</p>
              <p className="opacity-70">{result.close_match.ko_text}</p>
            </div>
            <div>
              <p className="text-xs opacity-50">정답 단어</p>
              <p className="font-bold">{enWord}</p>
              <p className="opacity-70">{result.explanation.ko}</p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {question.level <= 2 && (
              <button
                type="button"
                onClick={() =>
                  setInsight({ itemId: question.item_id, word: enWord })
                }
                className="min-h-10 cursor-pointer rounded-full border-2 border-brick-yellow bg-white px-3.5 py-1 text-xs font-bold transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95"
              >
                두 단어 차이 자세히 보기
              </button>
            )}
            <button
              type="button"
              disabled={closeAdded}
              onClick={addCloseWord}
              className="min-h-10 cursor-pointer rounded-full border-2 border-brick-green/60 bg-white px-3.5 py-1 text-xs font-bold text-brick-green transition hover:-translate-y-0.5 active:translate-y-0 active:scale-95 disabled:opacity-60"
            >
              {closeAdded
                ? "학습 큐에 추가됨!"
                : `"${result.close_match.en_text}" 도 학습에 추가`}
            </button>
          </div>
        </div>
      )}

      {question.level <= 2 && otherRefs.length > 0 && (
        // 오답 보기도 학습 재료 — 탭하면 그 단어의 인사이트 카드로
        <div className="mt-3">
          <p className="text-xs opacity-60">다른 보기 단어도 알아보기</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {otherRefs.map((r) => (
              <button
                key={r.item_id}
                type="button"
                onClick={() =>
                  setInsight({ itemId: r.item_id, word: r.en_text })
                }
                className="min-h-10 cursor-pointer rounded-full border-2 border-ink/20 bg-white px-3.5 py-1 text-xs font-bold transition hover:border-brick-blue hover:text-brick-blue active:scale-95"
              >
                {r.en_text}
                <span className="ml-1.5 font-normal opacity-60">
                  {r.ko_text}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {result.correct ? (
        <>
          <p className="mt-4 text-xs opacity-60">
            얼마나 쉬웠나요? 선택하면 그 시점에 다시 복습해요 (새 단어는 짧게
            반복하며 익혀요)
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {RATING_BUTTONS.map((btn) => {
              const isAuto = btn.rating === result.rating_applied;
              const minutes = result.interval_previews?.[String(btn.rating)];
              return (
                <button
                  key={btn.rating}
                  type="button"
                  disabled={submitting}
                  onClick={() => pick(btn.rating)}
                  // bg-white 를 베이스에 두면 active 의 bg-brick-* 와 충돌해
                  // (생성 CSS 순서상 bg-white 승리) 흰 바탕+흰 글씨가 됨 → idle 에만 둔다
                  className={`flex min-h-16 flex-col items-center justify-center rounded-md border-2 font-bold transition hover:-translate-y-0.5 disabled:opacity-50 ${
                    isAuto ? btn.active : btn.idle
                  }`}
                >
                  <span>{btn.label}</span>
                  {minutes != null && (
                    <span
                      className={`text-xs font-normal ${isAuto ? "" : "opacity-60"}`}
                    >
                      {formatInterval(minutes)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      ) : (
        // 오답: 등급 선택 없이 "다시"만 (안키 — 틀리면 Again)
        <div className="mt-4">
          <button
            type="button"
            disabled={submitting}
            onClick={() => pick(1)}
            className="flex min-h-14 w-full flex-col items-center justify-center rounded-md border-2 border-brick-red bg-brick-red font-bold text-brick-label transition hover:-translate-y-0.5 disabled:opacity-50"
          >
            <span>다시 학습</span>
            {againMin != null && (
              <span className="text-xs font-normal opacity-90">
                {formatInterval(againMin)}
              </span>
            )}
          </button>
        </div>
      )}

      {insight && (
        <InsightSheet
          itemId={insight.itemId}
          word={insight.word}
          onClose={() => setInsight(null)}
        />
      )}
    </div>
  );
}

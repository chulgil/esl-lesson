"use client";

import { useEffect, useRef, useState } from "react";
import { logUsage } from "@/lib/usage";
import {
  bestMatch,
  normalizeWords,
  type SpeechMatch,
} from "@/lib/speech-match";

/** 발음 확인 V1 — 인식 통과형 (proposal/pronunciation-scoring-2026-08.md).
 *
 *  브라우저 내장 음성인식(Web Speech API)으로 목표 문장을 말해보고
 *  완벽/좋아요/다시 한번 3등급 판정. 점수·음소 채점이 아니다 — "인식됐는가"만.
 *  미지원 브라우저(구형 iOS 등)는 렌더하지 않는다 — 녹음-비교(RecordCompare)가
 *  폴백. 3회 시도하면 등급과 무관하게 통과 (소음 환경 좌절 방지). */

// Web Speech API 는 TS lib.dom 에 없다 — 필요한 최소만 선언
interface SRAlternative {
  transcript: string;
}
interface SRResultEvent {
  results: ArrayLike<ArrayLike<SRAlternative>>;
}
interface SREngine {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: SRResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function speechEngine(): (new () => SREngine) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SREngine;
    webkitSpeechRecognition?: new () => SREngine;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const MAX_ATTEMPTS = 3;

const GRADE_LABEL = {
  perfect: "완벽해요!",
  good: "좋아요!",
  retry: "다시 한번?",
} as const;

export function SpeechCheck({ targetText }: { targetText: string | null }) {
  const [state, setState] = useState<"idle" | "listening" | "result">("idle");
  const [match, setMatch] = useState<SpeechMatch | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const engineRef = useRef<SREngine | null>(null);

  // 문장이 바뀌면 시도 카운터·결과 리셋
  useEffect(() => {
    setState("idle");
    setMatch(null);
    setAttempts(0);
    setNotice(null);
  }, [targetText]);

  useEffect(() => () => engineRef.current?.abort(), []);

  const Engine = speechEngine();
  if (!Engine || !targetText) return null;

  function listen() {
    if (!targetText) return;
    const rec = new Engine!();
    engineRef.current = rec;
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 3;
    let got = false;
    rec.onresult = (e) => {
      got = true;
      const alts: string[] = [];
      const first = e.results[0];
      for (let i = 0; i < first.length; i++) {
        alts.push(first[i].transcript);
      }
      const m = bestMatch(targetText, alts);
      setMatch(m);
      setAttempts((n) => n + 1);
      setState("result");
      // 미션 집계 재료 — 시도 자체가 연습 (retention speak_3)
      logUsage("speech_check", { grade: m.grade });
    };
    rec.onerror = (e) => {
      setState("idle");
      setNotice(
        e.error === "not-allowed" || e.error === "service-not-allowed"
          ? "마이크 권한을 허용해야 발음 확인을 할 수 있어요"
          : "잘 안 들렸어요 — 조용한 곳에서 다시 눌러보세요",
      );
    };
    rec.onend = () => {
      // 무음 종료 (onresult 없이 끝남) — 안내만
      if (!got) {
        setState((s) => (s === "listening" ? "idle" : s));
      }
    };
    setNotice(null);
    setState("listening");
    try {
      rec.start();
    } catch {
      setState("idle");
    }
  }

  const passed = match && (match.grade !== "retry" || attempts >= MAX_ATTEMPTS);
  const targetWords = normalizeWords(targetText);

  return (
    <div className="flex flex-col items-center gap-1.5 text-sm">
      <div className="flex flex-wrap items-center justify-center gap-2">
        <span className="text-xs font-bold opacity-60">발음 확인</span>
        {state === "listening" ? (
          <button
            type="button"
            onClick={() => engineRef.current?.stop()}
            className="min-h-9 animate-pulse cursor-pointer rounded-md border-2 border-brick-green bg-brick-green/10 px-2.5 text-xs font-bold text-brick-green"
          >
            듣고 있어요 — 문장을 말해보세요
          </button>
        ) : (
          <button
            type="button"
            onClick={listen}
            className="min-h-9 cursor-pointer rounded-md border-2 border-brick-green/50 bg-white px-2.5 text-xs font-bold text-brick-green transition hover:border-brick-green"
          >
            {state === "result" ? "다시 말해보기" : "이 문장 말해보기 (인식)"}
          </button>
        )}
        {state === "result" && match && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-bold ${
              match.grade === "perfect"
                ? "bg-brick-green/15 text-brick-green"
                : match.grade === "good"
                  ? "bg-brick-blue/10 text-brick-blue"
                  : "bg-brick-yellow/30 text-ink"
            }`}
          >
            {GRADE_LABEL[match.grade]}
          </span>
        )}
      </div>

      {/* 단어별 인식 하이라이트 — 어디가 안 들렸는지 보여준다 (점수 아님) */}
      {state === "result" && match && (
        <p className="flex max-w-xl flex-wrap justify-center gap-x-1.5 gap-y-0.5 text-xs leading-relaxed">
          {targetWords.map((w, i) => (
            <span
              key={`${w}-${i}`}
              className={
                match.matched[i]
                  ? "font-bold text-brick-green"
                  : "text-brick-red underline decoration-wavy underline-offset-2"
              }
            >
              {w}
            </span>
          ))}
        </p>
      )}
      {state === "result" && match?.grade === "retry" && passed && (
        <p className="text-xs opacity-60">
          충분히 연습했어요 — 다음 문장으로 넘어가도 좋아요
        </p>
      )}
      {notice && <p className="text-xs text-brick-red">{notice}</p>}
    </div>
  );
}

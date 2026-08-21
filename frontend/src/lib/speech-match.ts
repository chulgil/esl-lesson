/** 발음 확인 V1 — 인식 통과형 매칭 (proposal/pronunciation-scoring-2026-08.md).
 *
 *  브라우저 STT 가 돌려준 문장과 목표 문장의 단어 일치율만 본다 — "점수"가
 *  아니라 "인식됐는가"의 판정. 음소 정밀 채점(V2)과 혼동 금지. */

export type SpeechGrade = "perfect" | "good" | "retry";

export interface SpeechMatch {
  /** 목표 단어 중 인식된 비율 0~1 */
  ratio: number;
  /** 목표 단어별 인식 여부 — 단어 하이라이트용 (normalizeWords(target) 순서) */
  matched: boolean[];
  grade: SpeechGrade;
}

/** 소문자화 + 구두점 제거 — STT 는 구두점을 안 돌려주는 일이 많다.
 *  아포스트로피는 양쪽에서 제거 (STT 가 don't 를 dont 로 돌려줘도 일치) */
export function normalizeWords(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/'/g, "")
    .replace(/[^a-z0-9 ]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

const PERFECT = 0.9;
const GOOD = 0.7;

export function matchSpeech(target: string, transcript: string): SpeechMatch {
  const targetWords = normalizeWords(target);
  // 다중 등장 대응 — "the ... the" 는 두 번 말해야 두 개 다 인정
  const said = new Map<string, number>();
  for (const w of normalizeWords(transcript)) {
    said.set(w, (said.get(w) ?? 0) + 1);
  }
  const matched = targetWords.map((w) => {
    const n = said.get(w) ?? 0;
    if (n > 0) {
      said.set(w, n - 1);
      return true;
    }
    return false;
  });
  const hit = matched.filter(Boolean).length;
  const ratio = targetWords.length ? hit / targetWords.length : 0;
  const grade: SpeechGrade =
    ratio >= PERFECT ? "perfect" : ratio >= GOOD ? "good" : "retry";
  return { ratio, matched, grade };
}

/** 여러 인식 후보 중 가장 잘 맞는 것 — STT maxAlternatives 대응 */
export function bestMatch(target: string, transcripts: string[]): SpeechMatch {
  let best: SpeechMatch = { ratio: 0, matched: [], grade: "retry" };
  for (const t of transcripts) {
    const m = matchSpeech(target, t);
    if (m.ratio >= best.ratio) best = m;
  }
  // 후보가 하나도 없을 때도 하이라이트가 전-미인식으로 그려지게
  if (!best.matched.length) best = matchSpeech(target, "");
  return best;
}

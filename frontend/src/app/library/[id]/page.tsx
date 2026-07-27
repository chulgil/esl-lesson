"use client";

import Link from "next/link";
import { BackLink } from "@/components/nav/BackLink";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { TranscriptWords } from "@/components/media/TranscriptWords";
import {
  studyApi,
  type LibraryDetail,
  type AlignedWord,
} from "@/lib/study-api";

/** 라이브러리 상세 — 전문(全文) 나열 대신 재생 중 문장만 동기 표시.
 *  전체 스크립트 노출은 저작권 리스크 상위라 제거 (2026-07-14 저작권 검토). */

// 자막 선행 표시 — 발화보다 먼저 읽을 준비가 되도록 (기기별 설정, localStorage)
const LEAD_STORAGE_KEY = "esl:library:subtitle-lead-ms";
const DEFAULT_LEAD_MS = 1000;
// 단어 탭 반복 구간 — 유튜브 시킹 오차(아래 playWord 주석)를 흡수하는 값
const WORD_LEAD_MS = 200; // 시킹 직후 건너뛰는 구간 보정 → 단어 첫 음절부터 들린다
const WORD_TAIL_MS = 400; // 마지막 음절 잘림 방지
const WORD_MIN_MS = 1200; // 짧은 단어도 1초 이상 들리도록 보장

const LEAD_OPTIONS = [
  { value: 0, label: "정시" },
  { value: 500, label: "0.5초 먼저" },
  { value: 1000, label: "1초 먼저" },
  { value: 1500, label: "1.5초 먼저" },
  { value: 2000, label: "2초 먼저" },
];

export default function LibraryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSeq, setCurrentSeq] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState(0);
  const [loop, setLoop] = useState(false);
  const [subtitleLead, setSubtitleLead] = useState(DEFAULT_LEAD_MS);
  const leadRef = useRef(DEFAULT_LEAD_MS);
  leadRef.current = subtitleLead;

  useEffect(() => {
    const saved = Number(localStorage.getItem(LEAD_STORAGE_KEY));
    if (LEAD_OPTIONS.some((o) => o.value === saved)) setSubtitleLead(saved);
  }, []);

  const playerRef = useRef<YTPlayer | null>(null);
  const rangeRef = useRef<{ start: number; end: number } | null>(null);
  const loopRef = useRef(false);
  const detailRef = useRef<LibraryDetail | null>(null);
  // 수동 이동 직후 시킹이 끝나기 전에 동기 타이머가 이전 위치로 덮어쓰는 레이스 방지
  const pendingSeekRef = useRef<{ seq: number; until: number } | null>(null);
  loopRef.current = loop;
  detailRef.current = detail;

  useEffect(() => {
    studyApi
      .libraryDetail(Number(id))
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [id]);

  // YouTube IFrame API 로드 + 플레이어 생성
  useEffect(() => {
    if (!detail?.youtube_video_id) return;

    function createPlayer() {
      playerRef.current = new window.YT!.Player("yt-player", {
        videoId: detail!.youtube_video_id,
        playerVars: { rel: 0 },
      });
    }

    if (window.YT?.Player) {
      createPlayer();
    } else {
      window.onYouTubeIframeAPIReady = createPlayer;
      if (!document.querySelector("script[src*='iframe_api']")) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    }
    return () => {
      playerRef.current = null;
    };
  }, [detail]);

  // 재생 감시: 현재 구간 자막 동기 + A-B 루프 (docs/specs/learning.md)
  // 폴링은 구간 시작을 항상 늦게만 감지 — 150ms 는 틱 보정, 그 위에
  // 사용자 설정 선행(기본 1초)을 더해 발화 전에 자막이 준비된다
  // (문장 표시만 선행, 루프 판정은 실시간 기준)
  useEffect(() => {
    const SYNC_TICK_MS = 100;
    const POLL_COMPENSATION_MS = 150;
    const timer = setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      try {
        const now = player.getCurrentTime() * 1000;
        setNowMs(now);
        const ahead = now + POLL_COMPENSATION_MS + leadRef.current;

        const segments = detailRef.current?.segments ?? [];
        // "마지막으로 시작한 문장" 매칭 — 범위 포함(find) 방식은 이전 문장의
        // end 가 부풀려진 과거 병합 데이터에서 3~4초 늦게 전환됐다
        let active: (typeof segments)[number] | undefined;
        for (const s of segments) {
          if (s.start_ms == null) continue;
          if (s.start_ms > ahead) break;
          active = s;
        }
        // 문장 사이 공백에서 null 로 리셋하면 이전/다음의 기준점이 사라져
        // 1번 문장으로 튀는 버그 — 활성 구간이 있을 때만 갱신 (문장은 잔류 표시)
        if (active) {
          const pending = pendingSeekRef.current;
          if (
            !pending ||
            active.seq === pending.seq ||
            Date.now() > pending.until
          ) {
            pendingSeekRef.current = null;
            setCurrentSeq(active.seq);
          }
        }

        const range = rangeRef.current;
        if (range && now >= range.end * 1000) {
          if (loopRef.current) {
            player.seekTo(range.start, true);
          } else {
            player.pauseVideo();
            rangeRef.current = null;
          }
        }
      } catch {
        // 플레이어 미초기화 등은 무시
      }
    }, SYNC_TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const playSegment = useCallback(
    (startMs: number | null, endMs: number | null) => {
      const player = playerRef.current;
      if (!player || startMs == null) return;
      const start = startMs / 1000;
      // 클램프된 데이터에 길이 0~0.5초 퇴화 구간이 존재 — 최소 1초를 보장해
      // 재생 즉시 정지·루프 시킹 반복을 막는다
      const end = Math.max((endMs ?? startMs + 5000) / 1000, start + 1);
      rangeRef.current = { start, end };
      player.seekTo(start, true);
      player.playVideo();
    },
    [],
  );

  function playWord(word: AlignedWord) {
    const player = playerRef.current;
    if (!player) return;
    // 유튜브 seekTo 계측(2026-07-27): 착지 후 300~400ms 는 버퍼링이라 소리가 없고,
    // 재생이 실제로 시작되는 지점은 목표보다 200ms 정도 뒤다. 단어 길이(300~500ms)
    // 보다 이 오차가 커서 기존 [s, s+400ms] 창은 단어가 나오기 전에 끝나버렸다.
    const start = Math.max(0, word.s - WORD_LEAD_MS) / 1000;
    const end =
      Math.max(word.e + WORD_TAIL_MS, word.s - WORD_LEAD_MS + WORD_MIN_MS) /
      1000;
    rangeRef.current = { start, end };
    setLoop(true);
    loopRef.current = true;
    player.seekTo(start, true);
    player.playVideo();
  }

  // 체크만으로 바로 반복 — 지금 화면에 보이는 문장을 반복 구간으로 설정.
  // (기존엔 이전/다음 버튼으로 구간을 만든 뒤에만 동작해 "안 된다"고 느껴짐)
  function toggleLoop(on: boolean) {
    setLoop(on);
    if (!on) {
      rangeRef.current = null; // 해제 → 자연 재생 계속
      return;
    }
    const seg = detailRef.current?.segments.find((s) => s.seq === currentSeq);
    if (seg?.start_ms != null) {
      pendingSeekRef.current = { seq: seg.seq, until: Date.now() + 1500 };
      playSegment(seg.start_ms, seg.end_ms);
    }
    // 아직 재생 전(currentSeq 없음)이면 구간 없이 대기 — 이전/다음 버튼이 구간을 만든다
  }

  function step(direction: -1 | 1) {
    const segments = detail?.segments ?? [];
    const playable = segments.filter((s) => s.start_ms != null);
    if (playable.length === 0) return;
    const idx = playable.findIndex((s) => s.seq === currentSeq);
    const next =
      idx === -1
        ? playable[0]
        : playable[Math.min(playable.length - 1, Math.max(0, idx + direction))];
    // 즉시 커서 확정 — 연타 시 다음 클릭의 기준점이 되고, 화면도 바로 전환
    pendingSeekRef.current = { seq: next.seq, until: Date.now() + 1500 };
    setCurrentSeq(next.seq);
    playSegment(next.start_ms, next.end_ms);
  }

  if (error) {
    return (
      <main className="p-8">
        <p className="text-sm text-brick-red">{error}</p>
      </main>
    );
  }
  if (!detail) {
    return (
      <main className="p-8">
        <p className="text-sm opacity-60">불러오는 중...</p>
      </main>
    );
  }

  const hasPlayer = Boolean(detail.youtube_video_id);
  const current = detail.segments.find((s) => s.seq === currentSeq) ?? null;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-5 sm:px-16 sm:py-10">
      {/* 모바일: 플레이어+현재 문장+이동 버튼이 한 화면에 들어오도록 여백 압축 (375x667 기준) */}
      <header className="mb-3 flex flex-wrap items-center gap-3 sm:mb-6 sm:gap-4">
        <BackLink href="/library" label="라이브러리" />
        <h1 className="font-hand text-xl leading-snug font-bold sm:text-2xl">
          <span className="hl">{detail.title}</span>
        </h1>
      </header>

      <div className="mx-auto flex max-w-2xl flex-col gap-3 sm:gap-4">
        {hasPlayer ? (
          <>
            <div className="aspect-video overflow-hidden rounded-lg border-2 border-ink/10 bg-black">
              <div id="yt-player" className="h-full w-full" />
            </div>

            {/* 현재 문장 — 재생과 동기화, 전문은 표시하지 않음 */}
            <div className="min-h-24 rounded-lg border-2 border-ink/10 bg-white p-4 text-center sm:min-h-28 sm:p-5">
              {current ? (
                <>
                  <p className="text-lg font-medium">
                    <TranscriptWords
                      words={current.words}
                      text={current.en_text}
                      nowMs={nowMs}
                      onWordTap={playWord}
                    />
                  </p>
                  {current.ko_text && (
                    <p className="mt-1 text-sm opacity-60">{current.ko_text}</p>
                  )}
                </>
              ) : (
                <p className="py-4 text-sm opacity-40">
                  영상을 재생하면 지금 나오는 문장이 여기 표시돼요
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center sm:justify-center sm:gap-3">
              <button
                type="button"
                onClick={() => step(-1)}
                className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:border-brick-blue"
              >
                ← 이전 문장
              </button>
              <button
                type="button"
                onClick={() => step(1)}
                className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:border-brick-blue"
              >
                다음 문장 →
              </button>
              <label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border-2 border-ink/15 bg-white px-3 text-sm sm:justify-start">
                <input
                  type="checkbox"
                  checked={loop}
                  onChange={(e) => toggleLoop(e.target.checked)}
                />
                이 문장 반복
                <span className="hidden sm:inline"> (A-B 루프)</span>
              </label>
              <label className="flex min-h-11 items-center justify-center gap-2 rounded-md border-2 border-ink/15 bg-white px-3 text-sm sm:justify-start">
                자막<span className="hidden sm:inline"> 표시</span>
                <select
                  value={subtitleLead}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    setSubtitleLead(value);
                    localStorage.setItem(LEAD_STORAGE_KEY, String(value));
                  }}
                  className="cursor-pointer bg-transparent font-bold"
                >
                  {LEAD_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <p className="text-center text-xs opacity-50">
              원저작자 보호를 위해 전체 스크립트는 제공하지 않아요 — 문장별
              학습은 [오늘의 학습]에서 이어져요 ·{" "}
              <Link href="/copyright" className="underline underline-offset-2">
                저작권 안내
              </Link>
            </p>
          </>
        ) : (
          <p className="text-sm opacity-60">
            이 콘텐츠는 재생할 영상이 없어요. 추출된 표현은 [오늘의 학습] 큐에서
            만나요.
          </p>
        )}
      </div>
    </main>
  );
}

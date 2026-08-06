"use client";

import { useEffect, useRef, useState } from "react";

/** 말하기 녹음 즉석 비교 — 내 발음 vs 원어민 (effectiveness-audit P2 격상분).
 *
 *  운동 자세를 영상으로 찍어 확인하는 것과 같은 객관화 (TED 루틴 9단계).
 *  서버 저장 없음 — 브라우저 MediaRecorder 로 녹음해 그 자리에서만 비교한다.
 *  원어민 재생은 부모(라이브러리 플레이어)의 현재 문장 재생을 재사용. */
export function RecordCompare({
  onPlayNative,
  disabled,
}: {
  /** 현재 문장을 원어민 음성으로 재생 (부모의 구간 재생 재사용) */
  onPlayNative: () => void;
  /** 재생할 현재 문장이 없으면 비활성 */
  disabled: boolean;
}) {
  const [state, setState] = useState<
    "idle" | "denied" | "recording" | "recorded"
  >("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const urlRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(
    () => () => {
      // 정리 — 스트림·오브젝트 URL 누수 방지
      recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  const supported =
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia);
  if (!supported) return null;

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.addEventListener("dataavailable", (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      });
      recorder.addEventListener("stop", () => {
        stream.getTracks().forEach((t) => t.stop());
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
        urlRef.current = URL.createObjectURL(
          new Blob(chunksRef.current, { type: recorder.mimeType }),
        );
        setState("recorded");
      });
      recorderRef.current = recorder;
      recorder.start();
      setState("recording");
    } catch {
      setState("denied"); // 마이크 권한 거부
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
  }

  function playMine() {
    if (!urlRef.current) return;
    audioRef.current?.pause();
    audioRef.current = new Audio(urlRef.current);
    audioRef.current.play().catch(() => undefined);
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 text-sm">
      <span className="text-xs font-bold opacity-60">발음 비교</span>
      {state !== "recording" ? (
        <button
          type="button"
          onClick={startRecording}
          disabled={disabled}
          className="min-h-9 cursor-pointer rounded-md border-2 border-brick-red/50 bg-white px-2.5 text-xs font-bold text-brick-red transition hover:border-brick-red disabled:opacity-40"
        >
          이 문장 따라 말하기 (녹음)
        </button>
      ) : (
        <button
          type="button"
          onClick={stopRecording}
          className="min-h-9 animate-pulse cursor-pointer rounded-md border-2 border-brick-red bg-brick-red/10 px-2.5 text-xs font-bold text-brick-red"
        >
          녹음 중 — 멈추기
        </button>
      )}
      {state === "recorded" && (
        <>
          <button
            type="button"
            onClick={playMine}
            className="min-h-9 cursor-pointer rounded-md border-2 border-ink/25 bg-white px-2.5 text-xs font-bold transition hover:border-ink/50"
          >
            내 발음 듣기
          </button>
          <button
            type="button"
            onClick={onPlayNative}
            disabled={disabled}
            className="min-h-9 cursor-pointer rounded-md border-2 border-brick-blue/50 bg-white px-2.5 text-xs font-bold text-brick-blue transition hover:border-brick-blue disabled:opacity-40"
          >
            원어민 다시 듣기
          </button>
        </>
      )}
      {state === "denied" && (
        <span className="text-xs text-brick-red">
          마이크 권한을 허용해야 녹음할 수 있어요
        </span>
      )}
    </div>
  );
}

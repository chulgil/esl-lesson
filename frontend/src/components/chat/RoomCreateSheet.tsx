"use client";

import { useEffect, useMemo, useState } from "react";
import {
  matchApi,
  roomsApi,
  type ChatRoom,
  type RoomMode,
  type SupportedLang,
} from "@/lib/chat-api";
import { LANG_LABEL, SUPPORTED_LANGS } from "@/lib/chat-lang";
import { onChatEvent } from "@/lib/chat-signals";
import { friendsApi, type FriendEntry } from "@/lib/friends-api";
import { studyApi } from "@/lib/study-api";

type Step = "peer" | "friend-pick" | "lang" | "matching";

/** 방 생성 마법사 — 바텀시트/모달 1장 (docs/specs/chat-language-rooms.md §UX).
 *  상대(친구 선택|랜덤 매칭) → 언어쌍(프리필+스왑) → 만들기/매칭.
 *  기존 방이 있으면 "방 열기"로 즉시 이동. 랜덤 매칭은 대기 화면(스피너+취소)
 *  으로 전환되고 WS chat.matched 수신 또는 폴링으로 자동 이동한다. */
export function RoomCreateSheet({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (room: ChatRoom) => void;
}) {
  const [step, setStep] = useState<Step>("peer");
  const [friends, setFriends] = useState<FriendEntry[] | null>(null);
  const [peer, setPeer] = useState<FriendEntry | null>(null);
  const [source, setSource] = useState<SupportedLang>("ko");
  const [target, setTarget] = useState<SupportedLang>("en");
  // 방 종류 — 언어 학습(기본) | 일반 대화 (스펙 §일반 대화 방)
  const [mode, setMode] = useState<RoomMode>("learn");
  const [existingRooms, setExistingRooms] = useState<ChatRoom[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 초기화 — 열릴 때마다 첫 단계로, 설정의 주언어→학습언어[0] 프리필
  useEffect(() => {
    if (!open) return;
    setStep("peer");
    setPeer(null);
    setMode("learn");
    setError(null);
    studyApi
      .getSettings()
      .then((s) => {
        setSource(s.primary_lang);
        const firstLearning = s.learning_langs.find(
          (l) => l !== s.primary_lang,
        );
        setTarget((firstLearning as SupportedLang) ?? "en");
      })
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open || step !== "friend-pick") return;
    friendsApi
      .list()
      .then((res) => setFriends(res.friends))
      .catch(() => setFriends([]));
  }, [open, step]);

  // 선택한 상대와의 기존 방 목록 — 언어쌍이 같으면 "만들기" 대신 "방 열기"
  useEffect(() => {
    if (!open || !peer) return;
    roomsApi
      .list()
      .then((rooms) =>
        setExistingRooms(rooms.filter((r) => r.peer.id === peer.user_id)),
      )
      .catch(() => setExistingRooms([]));
  }, [open, peer]);

  const existingRoom = useMemo(
    () =>
      existingRooms.find((r) =>
        mode === "plain"
          ? r.mode === "plain"
          : r.mode === "learn" &&
            r.source_lang === source &&
            r.target_lang === target,
      ) ?? null,
    [existingRooms, source, target, mode],
  );

  // 랜덤 매칭 대기 중 — WS 성사 신호 + 폴링 폴백 (chat-language-rooms.md §랜덤 매칭)
  useEffect(() => {
    if (step !== "matching") return;
    const off = onChatEvent((msg) => {
      if (msg.t === "chat.matched") onCreated(msg.room);
    });
    let cancelled = false;
    const poll = setInterval(() => {
      matchApi
        .status()
        .then((res) => {
          if (cancelled || res.waiting) return;
          // WS 유실 중 성사됨 — 방금 만들어진 매칭 방을 찾아 이동
          return roomsApi.list().then((rooms) => {
            const matched = rooms
              .filter(
                (r) =>
                  r.origin === "match" &&
                  r.mode === mode &&
                  (mode === "plain" ||
                    (r.source_lang === source && r.target_lang === target)),
              )
              .sort((a, b) => b.id - a.id)[0];
            if (matched && !cancelled) onCreated(matched);
          });
        })
        .catch(() => {});
    }, 4000);
    return () => {
      cancelled = true;
      off();
      clearInterval(poll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  if (!open) return null;

  function swap() {
    setSource(target);
    setTarget(source);
  }

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      if (peer) {
        if (existingRoom) {
          onCreated(existingRoom);
          return;
        }
        const res = await roomsApi.create(peer.user_id, source, target, mode);
        onCreated(res.room);
        return;
      }
      // 랜덤 매칭
      const res = await matchApi.join(source, target, mode);
      if ("room" in res) {
        onCreated(res.room);
      } else {
        setStep("matching");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "만들지 못했어요");
    } finally {
      setBusy(false);
    }
  }

  function cancelMatching() {
    matchApi.cancel().catch(() => {});
    setStep("lang");
  }

  return (
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center bg-black/40 sm:items-center"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-t-2xl border-2 border-ink/10 bg-white p-5 shadow-2xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center">
          <h2 className="font-hand text-xl font-bold">새 노트 만들기</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="ml-auto flex min-h-10 min-w-10 items-center justify-center text-xl opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>

        {error && <p className="mb-3 text-sm text-brick-red">{error}</p>}

        {step === "peer" && (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => setStep("friend-pick")}
              className="min-h-14 rounded-lg border-2 border-ink/15 px-4 text-left font-bold transition hover:border-brick-blue/50"
            >
              친구에서 선택
              <span className="mt-0.5 block text-xs font-normal opacity-60">
                수락된 친구와 1:1 학습 방을 만들어요
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                setPeer(null);
                setExistingRooms([]);
                setStep("lang");
              }}
              className="min-h-14 rounded-lg border-2 border-ink/15 px-4 text-left font-bold transition hover:border-brick-green/50"
            >
              랜덤 매칭
              <span className="mt-0.5 block text-xs font-normal opacity-60">
                같은 언어쌍을 배우는 낯선 상대와 매칭돼요
              </span>
            </button>
          </div>
        )}

        {step === "friend-pick" && (
          <div className="flex flex-col gap-1">
            <button
              type="button"
              onClick={() => setStep("peer")}
              className="mb-1 self-start text-xs font-bold opacity-50 hover:opacity-90"
            >
              ‹ 뒤로
            </button>
            <div className="max-h-64 overflow-y-auto">
              {friends?.map((f) => (
                <button
                  key={f.user_id}
                  type="button"
                  onClick={() => {
                    setPeer(f);
                    setStep("lang");
                  }}
                  className="flex min-h-12 w-full items-center gap-2 rounded-md px-2 text-left hover:bg-highlight/30"
                >
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      f.online ? "bg-brick-green" : "bg-ink/20"
                    }`}
                  />
                  <b className="truncate text-sm">{f.name}</b>
                </button>
              ))}
              {friends && friends.length === 0 && (
                <p className="px-2 py-6 text-center text-sm opacity-50">
                  아직 친구가 없어요
                </p>
              )}
              {friends === null && (
                <p className="px-2 py-6 text-center text-sm opacity-40">
                  불러오는 중...
                </p>
              )}
            </div>
          </div>
        )}

        {step === "lang" && (
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={() => setStep(peer ? "friend-pick" : "peer")}
              className="self-start text-xs font-bold opacity-50 hover:opacity-90"
            >
              ‹ 뒤로
            </button>
            {peer && (
              <p className="text-sm opacity-70">
                <b>{peer.name}</b> 님과의 방
              </p>
            )}
            <div className="flex gap-2">
              <ModeChip
                active={mode === "learn"}
                label="언어 학습"
                hint="쓴 글이 배우는 언어로 보여요"
                onClick={() => setMode("learn")}
              />
              <ModeChip
                active={mode === "plain"}
                label="일반 대화"
                hint="번역 없이 그대로"
                onClick={() => setMode("plain")}
              />
            </div>
            {mode === "learn" && (
              <div className="flex items-center justify-center gap-2">
                <LangPicker
                  value={source}
                  onChange={setSource}
                  exclude={target}
                />
                <button
                  type="button"
                  onClick={swap}
                  aria-label="언어 순서 바꾸기"
                  className="flex min-h-10 min-w-10 items-center justify-center rounded-full border-2 border-ink/15 text-lg hover:border-brick-blue/50"
                >
                  ⇄
                </button>
                <LangPicker
                  value={target}
                  onChange={setTarget}
                  exclude={source}
                />
              </div>
            )}
            <button
              type="button"
              onClick={submit}
              disabled={busy}
              className="mt-2 min-h-12 rounded-lg bg-brick-blue text-sm font-bold text-brick-label transition hover:bg-brick-blue/85 disabled:opacity-50"
            >
              {existingRoom ? "방 열기" : peer ? "만들기" : "랜덤 매칭 시작"}
            </button>
          </div>
        )}

        {step === "matching" && (
          <div className="flex flex-col items-center gap-3 py-6">
            <span className="h-8 w-8 animate-spin rounded-full border-4 border-brick-blue/20 border-t-brick-blue" />
            <p className="text-sm opacity-70">매칭 상대를 찾는 중...</p>
            <button
              type="button"
              onClick={cancelMatching}
              className="min-h-10 rounded-md border-2 border-ink/15 px-4 text-sm font-bold opacity-70 hover:opacity-100"
            >
              취소
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ModeChip({
  active,
  label,
  hint,
  onClick,
}: {
  active: boolean;
  label: string;
  hint: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-12 flex-1 rounded-lg border-2 px-3 text-left transition ${
        active
          ? "border-brick-blue bg-brick-blue/10"
          : "border-ink/15 hover:border-ink/40"
      }`}
    >
      <b className="block text-sm">{label}</b>
      <span className="block text-[11px] opacity-60">{hint}</span>
    </button>
  );
}

function LangPicker({
  value,
  onChange,
  exclude,
}: {
  value: SupportedLang;
  onChange: (v: SupportedLang) => void;
  exclude: SupportedLang;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as SupportedLang)}
      aria-label="언어 선택"
      className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-2 text-sm font-bold focus:border-brick-blue focus:outline-none"
    >
      {SUPPORTED_LANGS.filter((l) => l !== exclude).map((l) => (
        <option key={l} value={l}>
          {LANG_LABEL[l]}
        </option>
      ))}
    </select>
  );
}

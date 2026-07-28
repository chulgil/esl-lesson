"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChatToolsMenu } from "@/components/chat/ChatToolsMenu";
import { NotifyEnableButton } from "@/components/chat/NotifyEnableButton";
import { useChatRoom } from "@/components/chat/useChatRoom";
import { fetchMe } from "@/lib/api";
import { chatApi, type ChatConversation } from "@/lib/chat-api";
import { onChatEvent, setActiveChatRoom } from "@/lib/chat-signals";
import { useChatFloating } from "@/lib/chat-mode";
import { setFaviconBadge } from "@/lib/favicon-badge";
import { useAppTheme } from "@/lib/theme";

/** 채팅 위젯 — excelkospi 우하단 버튼 컨셉 (docs/specs/chat.md 위장 테마).
 *  설정(플로팅 체크) 에 따라 두 가지로 표시된다:
 *  - 플로팅(기본): 우하단 작은 팝업. Esc 또는 바깥 클릭으로 닫힘.
 *  - 도킹: 화면 우측에 상시 고정된 패널(닫기 없음, excelkospi 채팅 레일 컨셉).
 *  페이지(/chat)는 푸시 딥링크·모바일용으로 유지. 오피스 테마 = "메모" 패널로 위장. */
export function ChatWidget() {
  const pathname = usePathname();
  const theme = useAppTheme();
  const floating = useChatFloating();
  const [loggedIn, setLoggedIn] = useState(false);
  const [open, setOpen] = useState(false);
  const [room, setRoom] = useState<{ userId: number; name: string } | null>(
    null,
  );
  const [unread, setUnread] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);

  // 도킹은 데스크톱 전용 — 모바일에서 우측 상시 패널은 화면 전체를 덮고
  // 닫을 방법이 없다 (2026-07-28 검증에서 발견). 모바일은 항상 플로팅.
  const [isDesktop, setIsDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const apply = () => setIsDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    fetchMe().then((me) => setLoggedIn(Boolean(me)));
  }, []);

  // 안읽음 배지 — WS 이벤트 즉시 + 60초 폴링 (서버 TTL 캐시)
  useEffect(() => {
    if (!loggedIn) return;
    const load = () =>
      chatApi
        .unreadTotal()
        .then((res) => setUnread(res.total))
        .catch(() => {});
    load();
    const timer = setInterval(load, 60000);
    const off = onChatEvent((msg) => {
      if (msg.t === "chat.message" || msg.t === "chat.read") load();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  }, [loggedIn]);

  // 파비콘 배지 — 다른 탭을 보고 있어도 안읽음 개수를 인지 (2026-07-28 요청).
  // 개수 변경 외에 라우팅·창 복귀 시에도 재적용해야 한다: Next 가 head 의 원래
  // 아이콘 링크를 되살리거나 브라우저가 탭 복귀 때 캐시 파비콘으로 돌아가면
  // 개수가 그대로여도 배지가 사라진다 (같은 날 후속 보고). 재적용은 멱등(가드).
  useEffect(() => {
    setFaviconBadge(unread);
  }, [unread, pathname]);
  useEffect(() => {
    const reapply = () => setFaviconBadge(unread);
    window.addEventListener("focus", reapply);
    document.addEventListener("visibilitychange", reapply);
    return () => {
      window.removeEventListener("focus", reapply);
      document.removeEventListener("visibilitychange", reapply);
    };
  }, [unread]);

  // 도킹은 데스크톱에서만 실제 적용 — 모바일은 항상 플로팅으로 동작
  const effFloating = floating || !isDesktop;
  // 도킹 모드는 항상 열려있음(닫기 없음) — 플로팅일 때만 open 상태를 따른다
  const panelOpen = effFloating ? open : true;

  // Esc 한 번으로 즉시 닫기 — 플로팅 전용 (빠른 숨김)
  useEffect(() => {
    if (!effFloating || !open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [effFloating, open]);

  // 바깥 영역 클릭 시 닫기 — 플로팅 전용. 런처는 제외해야 한다:
  // pointerdown(닫힘) 직후 런처의 click 토글이 다시 열어 닫기가 무력화됨
  useEffect(() => {
    if (!effFloating || !open) return;
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (
        panelRef.current &&
        !panelRef.current.contains(target) &&
        !launcherRef.current?.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [effFloating, open]);

  // 열린 대화방 추적 — 전역 토스트·OS 알림 중복 억제
  useEffect(() => {
    setActiveChatRoom(panelOpen && room ? room.userId : null);
    return () => setActiveChatRoom(null);
  }, [panelOpen, room]);

  // 채팅 전체 페이지·관리자·로그인 화면에서는 숨김
  if (
    !loggedIn ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/admin") ||
    pathname === "/login"
  ) {
    return null;
  }

  const excel = theme === "excel";

  return (
    <>
      {panelOpen && (
        <div
          ref={panelRef}
          className={
            effFloating
              ? `fixed right-4 bottom-20 z-50 flex h-[30rem] w-[22.5rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-lg shadow-2xl ${
                  excel
                    ? "border border-[#c9cfd6] bg-white font-sans text-[13px] text-[#24292f]"
                    : "border-2 border-ink/15 bg-paper"
                }`
              : `dock-right-nav-safe z-40 flex w-full max-w-md flex-col overflow-hidden border-l-2 shadow-[-6px_0_20px_-10px_rgba(0,0,0,0.15)] ${
                  excel
                    ? "border-[#c9cfd6] bg-white font-sans text-[13px] text-[#24292f]"
                    : "border-ink/15 bg-paper"
                }`
          }
          style={
            effFloating
              ? { maxHeight: "min(30rem, calc(100dvh - 7rem))" }
              : undefined
          }
        >
          {/* 헤더 */}
          <div
            className={
              excel
                ? "flex items-center gap-2 bg-[#185c37] px-3 py-1.5 text-xs text-white"
                : "flex items-center gap-2 border-b-2 border-ink/10 bg-white px-3 py-2"
            }
          >
            {room ? (
              <button
                type="button"
                onClick={() => setRoom(null)}
                aria-label="목록으로"
                className="font-bold opacity-80 hover:opacity-100"
              >
                ‹
              </button>
            ) : null}
            <b className={excel ? "" : "font-hand text-base"}>
              {excel
                ? room
                  ? `${room.name}_공유.xlsx`
                  : "공유 메모"
                : room
                  ? `${room.name} 와의 교환 노트`
                  : "교환 노트"}
            </b>
            {effFloating && (
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기 (Esc)"
                className="ml-auto opacity-60 hover:opacity-100"
              >
                ×
              </button>
            )}
          </div>

          {room ? (
            <WidgetRoom userId={room.userId} excel={excel} />
          ) : (
            <WidgetList
              excel={excel}
              onPick={(c) => setRoom({ userId: c.user_id, name: c.name })}
            />
          )}
        </div>
      )}

      {/* 런처 — 도킹 모드는 상시 열려있어 런처가 필요 없다. 오피스: 메모 pill / 그 외: 연필 노트 원형.
          열기 전용(토글 아님): 토글은 바깥클릭 닫힘과의 이벤트 순서 경합으로
          "다시 열면 바로 닫히는" 간헐 증상을 만든다 (2026-07-28 보고). 닫기 = X·Esc·바깥클릭 */}
      {effFloating && (
        <button
          ref={launcherRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`대화 열기${unread > 0 ? ` — 새 글 ${unread}개` : ""}`}
          className={
            excel
              ? "fixed right-4 bottom-4 z-50 flex min-h-10 items-center gap-1.5 rounded-full bg-[#185c37] px-4 font-sans text-xs font-bold text-white shadow-lg hover:bg-[#217346]"
              : "fixed right-4 bottom-4 z-50 flex h-13 w-13 items-center justify-center rounded-full border-2 border-ink/15 bg-white shadow-lg transition hover:-translate-y-0.5"
          }
        >
          {excel ? <span>메모</span> : <PencilNoteIcon />}
          {unread > 0 && (
            <span
              className={
                excel
                  ? "rounded-full bg-white/25 px-1.5 text-[10px]"
                  : "absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-brick-red px-1 text-[10px] font-bold text-white"
              }
            >
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </button>
      )}
    </>
  );
}

/* --- 목록 뷰 ---------------------------------------------------------------- */

function WidgetList({
  excel,
  onPick,
}: {
  excel: boolean;
  onPick: (c: ChatConversation) => void;
}) {
  const [items, setItems] = useState<ChatConversation[] | null>(null);

  useEffect(() => {
    const load = () =>
      chatApi
        .conversations()
        .then((res) => setItems(res.items))
        .catch(() => setItems([]));
    load();
    return onChatEvent((msg) => {
      if (msg.t === "chat.message" || msg.t === "presence") load();
    });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto">
      {/* 브라우저 알림 허용 진입점 — 수락하면 백그라운드·오프라인에도 알림 */}
      <div className="px-3 pt-2 pb-1">
        <NotifyEnableButton
          label={excel ? "변경 알림 받기" : "새 글 알림 켜기"}
          variant={excel ? "excel" : "note"}
        />
      </div>
      {items?.map((c) => (
        <button
          key={c.conversation_id}
          type="button"
          onClick={() => onPick(c)}
          className={`flex w-full items-center gap-2 px-3 py-2 text-left ${
            excel
              ? "border-b border-[#e4e8ec] hover:bg-[#f6f8f9]"
              : "border-b border-ink/5 hover:bg-white"
          }`}
        >
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              c.online
                ? excel
                  ? "bg-[#217346]"
                  : "bg-brick-green"
                : excel
                  ? "bg-[#ccc]"
                  : "bg-ink/20"
            }`}
          />
          <span className="min-w-0 flex-1">
            <b className="block truncate text-sm">
              {excel ? `${c.name}_공유.xlsx` : c.name}
            </b>
            <span
              className={`block truncate text-xs ${excel ? "text-[#888]" : "opacity-50"}`}
            >
              {c.last_message ?? (excel ? "-" : "첫 줄을 적어보세요")}
            </span>
          </span>
          {c.unread > 0 && (
            <span
              className={
                excel
                  ? "text-xs font-bold text-[#217346]"
                  : "rounded-full bg-brick-red px-1.5 py-0.5 text-[10px] font-bold text-white"
              }
            >
              {excel ? `+${c.unread}` : c.unread}
            </span>
          )}
        </button>
      ))}
      {items && items.length === 0 && (
        <p
          className={`px-4 py-8 text-center text-xs ${excel ? "text-[#999]" : "opacity-50"}`}
        >
          {excel
            ? "공유된 문서가 없습니다"
            : "친구 화면에서 첫 노트를 시작해보세요"}
        </p>
      )}
    </div>
  );
}

/* --- 대화 뷰 (useChatRoom 재사용) -------------------------------------------- */

function WidgetRoom({ userId, excel }: { userId: number; excel: boolean }) {
  const p = useChatRoom(userId);

  return (
    <>
      <div
        ref={p.listRef}
        onScroll={p.onScroll}
        className={`flex-1 overflow-y-auto px-3 py-1.5 ${excel ? "" : "bg-white/60"}`}
      >
        {p.messages.map((m) => {
          const mine = m.sender_id === p.myId;
          return (
            <div
              key={m.id}
              className={`border-b py-1 text-[13px] leading-relaxed ${
                // 상대 글이 더 잘 읽혀야 한다 (2026-07-28 요청) — 내 글은 흐리게
                excel
                  ? `border-[#f0f2f4] ${mine ? "text-[#217346]/60" : "font-medium text-[#24292f]"}`
                  : `border-ink/5 ${mine ? "text-brick-blue/60" : "font-medium text-ink"}`
              }`}
            >
              <div
                className={`mb-0.5 flex items-baseline gap-1 text-[10px] ${
                  excel
                    ? mine
                      ? "text-[#b3b8bf]"
                      : "text-[#666]"
                    : mine
                      ? "opacity-35"
                      : "opacity-70"
                }`}
              >
                <b>{mine ? "나" : p.peerName}</b>
                {/* 전체 페이지(NoteSkin)와 동일 사양 — 시각 표기 (2026-07-28 통일 요청) */}
                {m.created_at && (
                  <span>
                    {new Date(m.created_at).toLocaleTimeString("ko-KR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                )}
                {mine && m.id > p.otherRead && (
                  <span
                    aria-label="상대가 아직 읽지 않음"
                    className={`inline-block h-1.5 w-1.5 rounded-full align-middle ${
                      excel ? "bg-[#bf8f00]" : "bg-brick-yellow"
                    }`}
                  />
                )}
              </div>
              {m.item_ref && (
                <span
                  className={`mr-1.5 rounded px-1 text-xs ${
                    excel ? "bg-[#e2efda]" : "bg-highlight/50"
                  }`}
                >
                  <b>{m.item_ref.en_text}</b> {m.item_ref.ko_text}
                </span>
              )}
              {m.image_url && (
                <a href={m.image_url} target="_blank" rel="noreferrer">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={m.image_url}
                    alt="첨부"
                    className="my-1 block max-h-28 rounded border border-ink/10"
                  />
                </a>
              )}
              <span className="break-words whitespace-pre-wrap">{m.body}</span>
            </div>
          );
        })}
        {p.pending.map((entry) => (
          <div
            key={entry.client_msg_id}
            className={`border-b py-1 text-[13px] opacity-60 ${
              excel
                ? "border-[#f0f2f4] text-[#217346]"
                : "border-ink/5 text-brick-blue"
            }`}
          >
            {entry.body || (entry.imageUrl ? "[사진]" : "")}
            {entry.failed ? (
              <button
                type="button"
                onClick={() => p.onRetry(entry)}
                className="ml-1.5 text-[10px] font-bold text-brick-red"
              >
                재시도
              </button>
            ) : (
              <span className="ml-1.5 text-[10px]">...</span>
            )}
          </div>
        ))}
        {p.typing && (
          <p
            className={`py-1 text-[11px] ${excel ? "text-[#217346]" : "opacity-45"}`}
          >
            {excel
              ? "공동 작성자가 편집 중"
              : `${p.peerName} 이(가) 적고 있어요`}
            <span className="inline-block animate-pulse">...</span>
          </p>
        )}
        {p.messages.length === 0 && p.pending.length === 0 && (
          <p
            className={`py-8 text-center text-xs ${excel ? "text-[#999]" : "opacity-40"}`}
          >
            {excel ? "기록이 없습니다" : "첫 줄을 적어보세요 (´｡• ᵕ •｡`)"}
          </p>
        )}
      </div>

      {p.error && (
        <p className="px-3 py-1 text-[11px] text-brick-red">{p.error}</p>
      )}
      {p.attachedImage && (
        <div
          className={`flex items-center gap-2 px-3 py-1 text-xs ${
            excel ? "bg-[#e2efda]" : "bg-highlight/30"
          }`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={p.attachedImage.url}
            alt=""
            className="h-7 w-7 rounded object-cover"
          />
          {p.attachedImage.uploading ? "업로드 중..." : "준비 완료"}
          <button
            type="button"
            onClick={p.onDetachImage}
            aria-label="이미지 첨부 해제"
            className="ml-auto opacity-60"
          >
            ×
          </button>
        </div>
      )}
      {p.attachedItem && (
        <div
          className={`flex items-center gap-2 px-3 py-1 text-xs ${
            excel ? "bg-[#e2efda]" : "bg-highlight/30"
          }`}
        >
          <b>{p.attachedItem.en_text}</b>
          <button
            type="button"
            onClick={p.onDetachItem}
            aria-label="첨부 해제"
            className="ml-auto opacity-60"
          >
            ×
          </button>
        </div>
      )}

      <div
        className={`flex items-center gap-1 border-t p-1.5 ${
          excel ? "border-[#d8dde3]" : "border-ink/10 bg-white"
        }`}
      >
        <ChatToolsMenu
          variant={excel ? "excel" : "note"}
          onPickItem={p.onAttachItem}
          onPickImage={p.onAttachImageFile}
          onPickKaomoji={p.onPickKaomoji}
        />
        <input
          value={p.input}
          onChange={(e) => p.onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) p.onSend();
          }}
          onPaste={(e) => {
            // 클립보드 이미지 붙여넣기 → 파일 첨부와 같은 업로드 파이프라인
            const file = Array.from(e.clipboardData.files).find((f) =>
              f.type.startsWith("image/"),
            );
            if (file) {
              e.preventDefault();
              p.onAttachImageFile(file);
            }
          }}
          placeholder={excel ? "내용 입력" : "한 줄 적기..."}
          maxLength={2000}
          className={`min-h-9 min-w-0 flex-1 px-2 text-[13px] focus:outline-none ${
            excel
              ? "rounded-sm border border-[#c9cfd6] focus:border-[#217346]"
              : "rounded-md border-2 border-ink/20 focus:border-brick-blue"
          }`}
        />
        <button
          type="button"
          onClick={p.onSend}
          disabled={
            (!p.input.trim() && !p.attachedItem && !p.attachedImage) ||
            Boolean(p.attachedImage?.uploading)
          }
          className={`min-h-9 px-2.5 text-xs font-bold disabled:opacity-40 ${
            excel
              ? "rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] hover:bg-[#e2efda]"
              : "rounded-md bg-brick-blue text-brick-label hover:bg-brick-blue/85"
          }`}
        >
          {excel ? "입력" : "적기"}
        </button>
      </div>
    </>
  );
}

function PencilNoteIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

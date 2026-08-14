"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type RefObject } from "react";
import { ChatHeaderMenu } from "@/components/chat/ChatHeaderMenu";
import { ChatToolsMenu } from "@/components/chat/ChatToolsMenu";
import { ChatTextarea } from "@/components/chat/ChatTextarea";
import { ReplyQuote } from "@/components/chat/ReplyQuote";
import { DeleteMessageButton } from "@/components/chat/DeleteMessageButton";
import { GoalBoard, type GoalBoardHandle } from "@/components/chat/GoalBoard";
import { openImage } from "@/components/chat/ImageLightbox";
import { LangPairBadge } from "@/components/chat/LangPairBadge";
import { MessageBody } from "@/components/chat/MessageBody";
import { NotifyEnableButton } from "@/components/chat/NotifyEnableButton";
import { NoticeBar, type NoticeBarHandle } from "@/components/chat/NoticeBar";
import { NoticeSystemLine } from "@/components/chat/NoticeSystemLine";
import { RoomCreateSheet } from "@/components/chat/RoomCreateSheet";
import { StudyingBadge } from "@/components/chat/StudyingBadge";
import { useChatRoom } from "@/components/chat/useChatRoom";
import { MascotSvg } from "@/components/theme/mascots";
import { fetchMe } from "@/lib/api";
import { chatApi, roomsApi, type ChatRoom } from "@/lib/chat-api";
import { roomInputPlaceholder } from "@/lib/chat-lang";
import { onChatEvent, setActiveChatRoom } from "@/lib/chat-signals";
import { useChatFloating } from "@/lib/chat-mode";
import { setFaviconBadge } from "@/lib/favicon-badge";
import { SHOP_EVENT, shopApi } from "@/lib/shop-api";
import { useAppTheme } from "@/lib/theme";

/** 채팅 위젯 — excelkospi 우하단 버튼 컨셉 (docs/specs/chat.md 위장 테마).
 *  설정(플로팅 체크) 에 따라 두 가지로 표시된다:
 *  - 플로팅(기본): 우하단 작은 팝업. Esc 또는 바깥 클릭으로 닫힘.
 *    PC 는 헤더 드래그로 위치 이동 (localStorage 유지 — 2026-08-11 요청).
 *  - 도킹: 화면 우측에 상시 고정된 패널(닫기 없음, excelkospi 채팅 레일 컨셉).
 *  페이지(/chat)는 푸시 딥링크·모바일용으로 유지. 오피스 테마 = "메모" 패널로 위장. */

// 플로팅 팝업 위치 (PC 전용)
const POS_KEY = "esl:chat:widget-pos";
const PANEL_W = 360; // sm:w-[22.5rem]
const EDGE = 8; // 화면 가장자리 여백

function clampPos(pos: { x: number; y: number }): { x: number; y: number } {
  // 팝업이 화면 밖으로 사라지지 않게 — 가로는 전체, 세로는 헤더가 항상 보이게
  const maxX = Math.max(EDGE, window.innerWidth - PANEL_W - EDGE);
  const maxY = Math.max(EDGE, window.innerHeight - 120);
  return {
    x: Math.min(Math.max(EDGE, pos.x), maxX),
    y: Math.min(Math.max(EDGE, pos.y), maxY),
  };
}

export function ChatWidget() {
  const pathname = usePathname();
  const theme = useAppTheme();
  const floating = useChatFloating();
  const [loggedIn, setLoggedIn] = useState(false);
  const [open, setOpen] = useState(false);
  const [room, setRoom] = useState<ChatRoom | null>(null);
  const [creating, setCreating] = useState(false);
  const [unread, setUnread] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const noticeRef = useRef<NoticeBarHandle>(null);
  const goalsRef = useRef<GoalBoardHandle>(null);
  // 플로팅 위치 — null = 기본(우하단). 드래그로 바뀌면 좌표 고정 + 저장
  const [panelPos, setPanelPos] = useState<{ x: number; y: number } | null>(
    null,
  );
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);
  const posRef = useRef<{ x: number; y: number } | null>(null);
  posRef.current = panelPos;

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

  // 활성 마스코트 — 있으면 연필 아이콘 대신 캐릭터가 런처가 된다 (2026-08-11 요구.
  // 원래 헤냥이가 우하단이었다가 연필 아이콘에 밀렸던 자리를 되찾는 구성)
  const [mascot, setMascot] = useState<{
    kind: string;
    outfits: string[];
  } | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      shopApi
        .catalog()
        .then((s) => {
          if (!alive) return;
          setMascot(
            s.active_mascot
              ? {
                  kind: s.active_mascot,
                  outfits: s.outfits.filter((o) => o.owned).map((o) => o.key),
                }
              : null,
          );
        })
        .catch(() => {
          if (alive) setMascot(null);
        });
    load();
    window.addEventListener(SHOP_EVENT, load);
    return () => {
      alive = false;
      window.removeEventListener(SHOP_EVENT, load);
    };
  }, []);

  // 저장된 플로팅 위치 복원 + 창 크기 변화 시 화면 안으로 재클램프
  useEffect(() => {
    try {
      const saved = localStorage.getItem(POS_KEY);
      if (saved) setPanelPos(clampPos(JSON.parse(saved)));
    } catch {
      // 손상된 저장값 — 기본 위치 사용
    }
    const onResize = () => {
      if (posRef.current) setPanelPos(clampPos(posRef.current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // 헤더 드래그 이동 (PC 플로팅 전용) — 버튼(뒤로/닫기) 클릭은 드래그로 안 잡는다
  function onHeaderPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if ((e.target as HTMLElement).closest("button")) return;
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault(); // 드래그 중 텍스트 선택 방지
  }
  function onHeaderPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    setPanelPos(
      clampPos({
        x: e.clientX - dragRef.current.dx,
        y: e.clientY - dragRef.current.dy,
      }),
    );
  }
  function onHeaderPointerUp() {
    if (!dragRef.current) return;
    dragRef.current = null;
    try {
      if (posRef.current)
        localStorage.setItem(POS_KEY, JSON.stringify(posRef.current));
    } catch {
      // 저장 실패는 무시 — 세션 내 위치는 유지된다
    }
  }

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
      if (
        msg.t === "chat.message" ||
        msg.t === "chat.read" ||
        msg.t === "chat.deleted"
      )
        load();
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

  // 위젯 자체가 안 그려지는 화면 — 아래 early return 과 동일 조건.
  // mascotLauncher 판정에도 반영해야 한다: 런처가 없는 화면에서 바디 클래스만
  // 남으면 좌하단 마스코트까지 숨어 캐릭터가 어디에도 안 보인다
  // (2026-08-11 보고 — PC /chat 등에서 마스코트 실종)
  const widgetHidden =
    !loggedIn ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/admin") ||
    pathname === "/login";

  // 마스코트가 런처를 차지하면 좌하단 상시 노출(MascotPeek)은 숨긴다 — 같은
  // 캐릭터 중복 방지. excel 위장은 "메모" pill 유지(캐릭터가 위장을 깬다)라 제외
  const mascotLauncher =
    Boolean(mascot) && effFloating && theme !== "excel" && !widgetHidden;
  useEffect(() => {
    document.body.classList.toggle("mascot-launcher", mascotLauncher);
    return () => document.body.classList.remove("mascot-launcher");
  }, [mascotLauncher]);

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

  // 열린 대화방 추적 — 전역 토스트·OS 알림 중복 억제. room id 기준이라야
  // 같은 상대의 다른 언어쌍 방과 섞이지 않는다 (2026-08-14 room 확장)
  useEffect(() => {
    setActiveChatRoom(panelOpen && room ? room.id : null);
    return () => setActiveChatRoom(null);
  }, [panelOpen, room]);

  // 모바일 전체 화면 시트가 열리면 대화방 페이지와 동일한 집중 모드
  // (하단 탭바 숨김 + 바디 스크롤 잠금 — globals.css chat-focus)
  useEffect(() => {
    if (!isDesktop && panelOpen) {
      document.body.classList.add("chat-focus");
      return () => document.body.classList.remove("chat-focus");
    }
  }, [isDesktop, panelOpen]);

  // 채팅 전체 페이지·관리자·로그인 화면에서는 숨김 (조건 정의는 widgetHidden — 위)
  if (widgetHidden) {
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
              ? // 모바일 = 전체 화면 시트 (좁은 팝업은 키보드가 열리면 못 쓴다 —
                // 2026-07-28 모바일 채팅 UX), sm 이상 = 우하단 팝업
                `fixed inset-0 z-50 flex flex-col overflow-hidden shadow-2xl sm:inset-auto sm:right-4 sm:bottom-20 sm:h-[30rem] sm:w-[22.5rem] sm:rounded-lg ${
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
            effFloating && isDesktop
              ? {
                  maxHeight: "min(30rem, calc(100dvh - 7rem))",
                  // 드래그로 옮긴 위치 — 기본(우하단) Tailwind 클래스를 덮는다
                  ...(panelPos
                    ? {
                        left: panelPos.x,
                        top: panelPos.y,
                        right: "auto",
                        bottom: "auto",
                      }
                    : {}),
                }
              : undefined
          }
        >
          {/* 헤더 — PC 플로팅은 드래그 핸들 (창 위치 이동, 2026-08-11 요청) */}
          <div
            onPointerDown={
              effFloating && isDesktop ? onHeaderPointerDown : undefined
            }
            onPointerMove={
              effFloating && isDesktop ? onHeaderPointerMove : undefined
            }
            onPointerUp={
              effFloating && isDesktop ? onHeaderPointerUp : undefined
            }
            title={
              effFloating && isDesktop ? "드래그해서 창 위치 이동" : undefined
            }
            className={`${
              excel
                ? "flex items-center gap-2 bg-[#185c37] px-3 py-1.5 text-xs text-white"
                : "flex items-center gap-2 border-b-2 border-ink/10 bg-white px-3 py-2"
            } ${effFloating && isDesktop ? "cursor-move touch-none select-none" : ""}`}
          >
            {room ? (
              <button
                type="button"
                onClick={() => setRoom(null)}
                aria-label="목록으로"
                // 44px 터치 타겟 — 글자만 있으면 모바일에서 누르기 어렵다 (2026-08-12 보고)
                className="flex min-h-11 min-w-11 items-center justify-center text-xl font-bold opacity-80 hover:opacity-100"
              >
                ‹
              </button>
            ) : null}
            <b
              className={`min-w-0 flex-1 truncate ${excel ? "" : "font-hand text-base"}`}
            >
              {excel
                ? room
                  ? `${room.peer.nickname}_공유.xlsx`
                  : "공유 메모"
                : room
                  ? `${room.peer.nickname} 와의 교환 노트`
                  : "교환 노트"}
            </b>
            {room && (
              <LangPairBadge
                source={room.source_lang}
                target={room.target_lang}
                mode={room.mode}
                variant={excel ? "excel" : "note"}
              />
            )}
            {room && (
              <StudyingBadge
                peerId={room.peer.id}
                variant={excel ? "excel" : "note"}
              />
            )}
            {room && (
              <ChatHeaderMenu
                excel={excel}
                items={[
                  {
                    label: () =>
                      noticeRef.current?.hasNotice ? "공지 수정" : "공지 쓰기",
                    onClick: () => noticeRef.current?.openEditor(),
                  },
                  {
                    label: "함께 목표",
                    onClick: () => goalsRef.current?.open(),
                  },
                ]}
              />
            )}
            {effFloating && (
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기 (Esc)"
                // 44px 터치 타겟 + 큰 글리프 — × 가 너무 작아 터치가 어렵다는
                // 보고 (2026-08-12). 시각 무게는 opacity 로 낮게 유지
                className="flex min-h-11 min-w-11 items-center justify-center text-2xl leading-none opacity-60 hover:opacity-100"
              >
                ×
              </button>
            )}
          </div>

          {room ? (
            <WidgetRoom
              roomId={room.id}
              excel={excel}
              noticeRef={noticeRef}
              goalsRef={goalsRef}
            />
          ) : (
            <WidgetList
              excel={excel}
              onPick={setRoom}
              onCreate={() => setCreating(true)}
            />
          )}
        </div>
      )}
      <RoomCreateSheet
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(r) => {
          setCreating(false);
          setRoom(r);
        }}
      />

      {/* 런처 — 도킹 모드는 상시 열려있어 런처가 필요 없다. 오피스: 메모 pill / 그 외: 연필 노트 원형.
          열기 전용(토글 아님): 토글은 바깥클릭 닫힘과의 이벤트 순서 경합으로
          "다시 열면 바로 닫히는" 간헐 증상을 만든다 (2026-07-28 보고). 닫기 = X·Esc·바깥클릭 */}
      {effFloating && (isDesktop || !open) && (
        <button
          ref={launcherRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`대화 열기${unread > 0 ? ` — 새 글 ${unread}개` : ""}`}
          className={
            excel
              ? "fixed right-4 bottom-20 z-50 flex min-h-10 items-center gap-1.5 rounded-full bg-[#185c37] px-4 font-sans text-xs font-bold text-white shadow-lg hover:bg-[#217346] sm:bottom-4"
              : mascotLauncher
                ? // 캐릭터 런처 — 산 마스코트가 버튼 자체가 된다 (연필 대체).
                  // idle 애니메이션은 새 메시지가 있을 때만 (없으면 정지, 2026-08-11).
                  // z-30: 하단 탭바(z-40) 뒤로 — 움직일 때 메뉴 위로 겹쳐 잘려
                  // 보이던 문제 (2026-08-12 보고, 좌하단 MascotPeek 와 동일 층)
                  `fixed right-1 bottom-16 z-30 origin-bottom-right scale-75 transition hover:-translate-y-0.5 sm:right-3 sm:bottom-2 sm:scale-100 ${
                    unread > 0 ? "mascot-launcher-attn" : ""
                  }`
                : `fixed right-4 bottom-20 z-50 flex h-13 w-13 items-center justify-center rounded-full border-2 border-ink/15 bg-white shadow-lg transition hover:-translate-y-0.5 sm:bottom-4 ${
                    unread > 0 ? "launcher-attn" : ""
                  }`
          }
        >
          {excel ? (
            <span>메모</span>
          ) : mascotLauncher && mascot ? (
            <MascotSvg kind={mascot.kind} outfits={mascot.outfits} />
          ) : (
            <PencilNoteIcon />
          )}
          {unread > 0 && (
            <span
              className={
                excel
                  ? "rounded-full bg-white/25 px-1.5 text-[10px]"
                  : "absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-brick-red px-1 text-[10px] font-bold text-brick-label"
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
  onCreate,
}: {
  excel: boolean;
  onPick: (r: ChatRoom) => void;
  onCreate: () => void;
}) {
  const [items, setItems] = useState<ChatRoom[] | null>(null);

  useEffect(() => {
    const load = () =>
      roomsApi
        .list()
        .then(setItems)
        .catch(() => setItems([]));
    load();
    return onChatEvent((msg) => {
      // chat.deleted: 삭제된 마지막 메시지 미리보기("삭제되었습니다") 즉시 반영.
      // chat.room_created/room_closed/chat.matched: 새 방 등장·종료 반영
      if (
        msg.t === "chat.message" ||
        msg.t === "presence" ||
        msg.t === "chat.deleted" ||
        msg.t === "chat.room_created" ||
        msg.t === "chat.room_closed" ||
        msg.t === "chat.matched"
      )
        load();
    });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto">
      {/* 브라우저 알림 허용 진입점 — 수락하면 백그라운드·오프라인에도 알림 */}
      <div className="flex items-center gap-2 px-3 pt-2 pb-1">
        <button
          type="button"
          onClick={onCreate}
          className={
            excel
              ? "rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-2 py-1 text-xs font-bold hover:bg-[#e2efda]"
              : "rounded-md border-2 border-dashed border-brick-blue/40 px-2 py-1 text-xs font-bold text-brick-blue hover:border-brick-blue/70"
          }
        >
          + 새 노트
        </button>
        <NotifyEnableButton
          label={excel ? "변경 알림 받기" : "새 글 알림 켜기"}
          variant={excel ? "excel" : "note"}
        />
      </div>
      {items?.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => onPick(r)}
          className={`flex w-full items-center gap-2 px-3 py-2 text-left ${
            r.status === "closed" ? "opacity-50" : ""
          } ${
            excel
              ? "border-b border-[#e4e8ec] hover:bg-[#f6f8f9]"
              : "border-b border-ink/5 hover:bg-white"
          }`}
        >
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              r.peer.online
                ? excel
                  ? "bg-[#217346]"
                  : "bg-brick-green"
                : excel
                  ? "bg-[#ccc]"
                  : "bg-ink/20"
            }`}
          />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5">
              <b className="truncate text-sm">
                {excel ? `${r.peer.nickname}_공유.xlsx` : r.peer.nickname}
              </b>
              <LangPairBadge
                source={r.source_lang}
                target={r.target_lang}
                mode={r.mode}
                variant={excel ? "excel" : "note"}
              />
            </span>
            <span
              className={`block truncate text-xs ${excel ? "text-[#888]" : "opacity-50"}`}
            >
              {r.preview ?? (excel ? "-" : "첫 줄을 적어보세요")}
            </span>
          </span>
          {r.unread > 0 && (
            <span
              className={
                excel
                  ? "text-xs font-bold text-[#217346]"
                  : "rounded-full bg-brick-red px-1.5 py-0.5 text-[10px] font-bold text-brick-label"
              }
            >
              {excel ? `+${r.unread}` : r.unread}
            </span>
          )}
        </button>
      ))}
      {items && items.length === 0 && (
        <p
          className={`px-4 py-8 text-center text-xs ${excel ? "text-[#999]" : "opacity-50"}`}
        >
          {excel ? "공유된 문서가 없습니다. " : "아직 노트가 없어요. "}
          <Link
            href="/friends"
            className={`font-bold ${excel ? "text-[#217346]" : "text-brick-blue"}`}
          >
            친구 목록
          </Link>
          에서 시작해보세요
        </p>
      )}
    </div>
  );
}

/* --- 대화 뷰 (useChatRoom 재사용) -------------------------------------------- */

function WidgetRoom({
  roomId,
  excel,
  noticeRef,
  goalsRef,
}: {
  roomId: number;
  excel: boolean;
  noticeRef: RefObject<NoticeBarHandle | null>;
  goalsRef: RefObject<GoalBoardHandle | null>;
}) {
  const p = useChatRoom(roomId);
  const closed = p.status === "closed";

  return (
    <>
      {p.peerId != null && (
        <>
          <NoticeBar otherId={p.peerId} excel={excel} apiRef={noticeRef} />
          <GoalBoard
            otherId={p.peerId}
            excel={excel}
            peerName={p.peerName}
            apiRef={goalsRef}
          />
        </>
      )}
      <div
        ref={p.listRef}
        onScroll={p.onScroll}
        className={`flex-1 overflow-y-auto px-3 py-1.5 ${excel ? "" : "bg-white/60"}`}
      >
        {p.messages.map((m) => {
          const mine = m.sender_id === p.myId;
          if (m.kind) {
            return (
              <NoticeSystemLine
                key={m.id}
                msg={m}
                mine={mine}
                peerName={p.peerName}
                excel={excel}
              />
            );
          }
          const imageUrl = m.image_url;
          return (
            <div
              key={m.id}
              data-mid={`m${m.id}`}
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
                {/* 답장 — 전체 페이지와 동일 사양 (2026-07-31) */}
                {!m.deleted && (
                  <button
                    type="button"
                    onClick={() => p.onReplyTo(m)}
                    className="ml-auto opacity-30 hover:opacity-80"
                  >
                    {excel ? "메모" : "답글"}
                  </button>
                )}
                {/* 내 글 삭제 — 전체 페이지와 동일 사양 (2026-07-31) */}
                {mine && !m.deleted && (
                  <DeleteMessageButton
                    label={excel ? "행 삭제" : "지우기"}
                    confirmLabel="정말 지우기?"
                    className="opacity-30 hover:opacity-80"
                    onDelete={() => p.onDeleteMessage(m.id)}
                  />
                )}
              </div>
              <ReplyQuote
                msg={m}
                messages={p.messages}
                myId={p.myId}
                peerName={p.peerName}
                className={`pl-2 text-[11px] ${
                  excel
                    ? "border-l-2 border-[#217346]/30 text-[#8a8f98] hover:text-[#217346]"
                    : "border-l-2 border-ink/20 opacity-50 hover:opacity-80"
                }`}
              />
              {m.deleted && (
                <span
                  className={`text-xs italic ${excel ? "text-[#999]" : "opacity-40"}`}
                >
                  삭제되었습니다
                </span>
              )}
              {m.item_ref && (
                <span
                  className={`mr-1.5 rounded px-1 text-xs ${
                    excel ? "bg-[#e2efda]" : "bg-highlight/50"
                  }`}
                >
                  <b>{m.item_ref.en_text}</b> {m.item_ref.ko_text}
                </span>
              )}
              {imageUrl && (
                <button
                  type="button"
                  onClick={() => openImage(imageUrl)}
                  aria-label="사진 크게 보기"
                  className="block cursor-zoom-in"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={imageUrl}
                    alt="첨부"
                    className="my-1 block max-h-28 rounded border border-ink/10"
                  />
                </button>
              )}
              {!m.deleted && (
                <MessageBody
                  body={m.body}
                  translation={m.translation}
                  variant={excel ? "excel" : "note"}
                />
              )}
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
            {entry.replyPreview && (
              <span className="mb-0.5 block truncate border-l-2 border-ink/15 pl-2 text-[11px] opacity-60">
                {entry.replyPreview}
              </span>
            )}
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

      {p.replyDraft && (
        <div
          className={`flex items-center gap-2 border-t px-2 py-1 text-[11px] ${
            excel
              ? "border-[#e3e7eb] bg-[#f6f8f9] text-[#8a8f98]"
              : "border-ink/10 bg-white opacity-80"
          }`}
        >
          <span
            className={`shrink-0 font-bold ${excel ? "text-[#217346]" : "text-brick-blue"}`}
          >
            {p.replyDraft.senderId === p.myId ? "나" : p.peerName}에게{" "}
            {excel ? "메모" : "답장"}
          </span>
          <span className="truncate">{p.replyDraft.preview}</span>
          <button
            type="button"
            onClick={p.onCancelReply}
            aria-label="답장 취소"
            className="ml-auto opacity-60 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}
      {closed ? (
        <p
          className={`border-t px-3 py-2 text-center text-xs ${
            excel ? "border-[#d8dde3] text-[#999]" : "border-ink/10 opacity-50"
          }`}
        >
          종료된 방이에요 — 더 이상 보낼 수 없어요
        </p>
      ) : (
        <div
          className={`flex items-end gap-1 border-t p-1.5 ${
            excel ? "border-[#d8dde3]" : "border-ink/10 bg-white"
          }`}
        >
          <ChatToolsMenu
            variant={excel ? "excel" : "note"}
            onPickItem={p.onAttachItem}
            onPickImage={p.onAttachImageFile}
            onPickKaomoji={p.onPickKaomoji}
          />
          <ChatTextarea
            value={p.input}
            onChange={p.onInputChange}
            onSend={p.onSend}
            onPasteImage={p.onAttachImageFile}
            placeholder={roomInputPlaceholder(p.sourceLang, p.targetLang, p.room?.mode ?? "learn")}
            className={`min-h-11 min-w-0 flex-1 px-2 py-2.5 text-base focus:outline-none sm:min-h-9 sm:py-2 sm:text-[13px] ${
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
      )}
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

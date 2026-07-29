"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMe } from "@/lib/api";
import {
  dispatchChatEvent,
  getActiveChatRoom,
  isChatInputFocused,
  setChatSocket,
} from "@/lib/chat-signals";
import { getAppTheme } from "@/lib/theme";
import { GameSocket, type ServerMsg } from "@/lib/game-ws";

const GAME_LABELS: Record<string, string> = {
  tetris: "워드 테트리스",
  quiz: "스피드 퀴즈 로얄",
  typing: "영문 타자연습",
  scramble: "어순 조립 레이스",
  dictation: "받아쓰기 배틀",
};

/** 전역 수신기 — 로그인 시 상시 연결(프레즌스 겸용).
 *  게임 초대 토스트 + 채팅 이벤트 버스 배급 + 채팅 토스트 (docs/specs/chat.md 알림). */
export function InviteToaster() {
  const router = useRouter();
  const pathname = usePathname();
  const pathRef = useRef(pathname);
  pathRef.current = pathname;

  const [invite, setInvite] = useState<{
    from: string;
    game: string;
    code: string;
  } | null>(null);
  const [chatToast, setChatToast] = useState<{
    fromId: number;
    fromName: string;
    preview: string;
  } | null>(null);

  const handleMessage = useCallback((msg: ServerMsg) => {
    if (msg.t === "iv.invited") {
      setInvite({ from: msg.from, game: msg.game, code: msg.code });
      return;
    }
    if (msg.t === "chat.message") {
      // 이벤트 버스로 배급 (대화방·위젯·네비 배지가 구독)
      dispatchChatEvent(msg);
      const viewing =
        pathRef.current === `/chat/${msg.sender_id}` ||
        getActiveChatRoom() === msg.sender_id;
      const body = msg.body || (msg.image_url ? "[사진]" : "[단어 카드]");
      // "실제로 대화 중"일 때만 알림 생략 = 그 방을 보는 중 + 탭 전면 + 창 포커스
      // + 입력창에 커서. 대화방을 켜두고 커서가 입력창 밖이면 자리 비움으로 보고
      // 알림을 보낸다 (2026-07-29 보고: 방만 켜둔 채 다른 일 하는 동안 유실).
      // hidden 만 보면 "브라우저는 보이는데 다른 앱 사용 중"도 놓친다 (07-28).
      // 오피스 테마는 문서 알림으로 위장
      const engaged =
        viewing &&
        !document.hidden &&
        document.hasFocus() &&
        isChatInputFocused();
      if (!engaged && Notification.permission === "granted") {
        const excel = getAppTheme() === "excel";
        notifyOs(
          excel ? "공유 문서" : msg.from_name,
          excel ? "변경 사항 1건" : body.slice(0, 40),
          `/chat/${msg.sender_id}`,
        );
      } else if (!viewing) {
        setChatToast({
          fromId: msg.sender_id,
          fromName: msg.from_name,
          preview: body.length > 40 ? body.slice(0, 40) + "…" : body,
        });
      }
      return;
    }
    if (
      msg.t === "chat.read" ||
      msg.t === "chat.typing" ||
      msg.t === "presence" ||
      msg.t === "notif.new"
    ) {
      dispatchChatEvent(msg);
    }
  }, []);

  useEffect(() => {
    let socket: GameSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      socket = new GameSocket(handleMessage, () => {
        setChatSocket(null);
        // 세션 만료 탭이 15초마다 403 을 만드는 것을 차단 — 재확인 후에만 재접속
        retry = setTimeout(() => {
          fetchMe().then((me) => {
            if (me) connect();
          });
        }, 15000);
      });
      socket.connect();
      setChatSocket(socket); // 대화방의 입력중 신호 전송용 (두 번째 소켓 금지)
    }
    fetchMe().then((me) => {
      if (me) connect();
    });
    return () => {
      if (retry) clearTimeout(retry);
      setChatSocket(null);
      socket?.close();
    };
  }, [handleMessage]);

  // 채팅 토스트 자동 소멸
  useEffect(() => {
    if (!chatToast) return;
    const timer = setTimeout(() => setChatToast(null), 5000);
    return () => clearTimeout(timer);
  }, [chatToast]);

  return (
    <>
      {invite && (
        <div className="fixed inset-x-4 top-16 z-50 mx-auto flex max-w-sm items-center gap-3 rounded-lg border-2 border-brick-green/60 bg-white p-3 shadow-lg">
          <p className="flex-1 text-sm">
            <b>{invite.from}</b> 님이{" "}
            <b>{GAME_LABELS[invite.game] ?? invite.game}</b>에 초대했어요!
          </p>
          <button
            type="button"
            onClick={() => {
              const target = `/game/${invite.game}?join=${invite.code}`;
              setInvite(null);
              router.push(target);
            }}
            className="min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85"
          >
            참가
          </button>
          <button
            type="button"
            onClick={() => setInvite(null)}
            aria-label="초대 닫기"
            className="min-h-10 min-w-10 rounded-md text-lg opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}

      {chatToast && (
        <button
          type="button"
          onClick={() => {
            const target = `/chat/${chatToast.fromId}`;
            setChatToast(null);
            router.push(target);
          }}
          className="fixed inset-x-4 top-28 z-50 mx-auto flex max-w-sm cursor-pointer items-center gap-3 rounded-lg border-2 border-brick-blue/60 bg-white p-3 text-left shadow-lg transition hover:-translate-y-0.5"
        >
          <ChatBubbleIcon />
          <span className="flex-1 text-sm">
            <b>{chatToast.fromName}</b>
            <span className="mt-0.5 block truncate opacity-70">
              {chatToast.preview}
            </span>
          </span>
        </button>
      )}
    </>
  );
}

/** 백그라운드 탭 OS 알림 — SW 우선, 미등록이면 페이지 Notification 폴백.
 *  renotify: 같은 tag 의 후속 알림이 소리 없이 대체되지 않고 다시 알리게 */
function notifyOs(title: string, body: string, url: string) {
  const options: NotificationOptions & { renotify?: boolean } = {
    body,
    tag: "esl-chat",
    renotify: true,
    data: { url },
  };
  navigator.serviceWorker
    ?.getRegistration()
    .then((reg) => {
      if (reg) return reg.showNotification(title, options);
      const n = new Notification(title, options);
      n.onclick = () => {
        window.focus();
        window.location.href = url;
      };
    })
    .catch(() => {});
}

function ChatBubbleIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 text-brick-blue"
      aria-hidden
    >
      <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
    </svg>
  );
}

"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMe } from "@/lib/api";
import { syncChatNotice } from "@/lib/chat-notice";
import {
  dispatchChatEvent,
  getActiveChatRoom,
  isChatInputFocused,
  isChatPanelVisible,
  setChatSocket,
} from "@/lib/chat-signals";
import {
  APP_THEMES,
  type AppTheme,
  getAppTheme,
  setAppTheme,
  useAppTheme,
} from "@/lib/theme";
import { chatNotice } from "@/lib/theme-surfaces";
import { GameSocket, type ServerMsg } from "@/lib/game-ws";

const GAME_LABELS: Record<string, string> = {
  tetris: "워드 테트리스",
  quiz: "스피드 퀴즈 로얄",
  typing: "영문 타자연습",
  scramble: "어순 조립 레이스",
  dictation: "받아쓰기 배틀",
  bingo: "리스닝 빙고",
};

/** 전역 수신기 — 로그인 시 상시 연결(프레즌스 겸용).
 *  게임 초대 토스트 + 채팅 이벤트 버스 배급 + 채팅 토스트 (docs/specs/chat.md 알림). */
export function InviteToaster() {
  const router = useRouter();
  const pathname = usePathname();
  const pathRef = useRef(pathname);
  pathRef.current = pathname;
  const theme = useAppTheme();

  // 웹푸시는 앱이 꺼진 뒤 워커만으로 뜬다 — 그때 쓸 문구를 미리 심어둔다.
  // 테마를 바꾸면 알림 위장 문구도 따라가야 하므로 theme 변경마다 갱신.
  useEffect(() => {
    void syncChatNotice();
  }, [theme]);

  const [invite, setInvite] = useState<{
    from: string;
    game: string;
    code: string;
    theme?: string | null;
  } | null>(null);
  // 테마 획득 축하 — 획득 순간이 "테마 = 업적 보상" 멘탈모델을 심는 최적 접점
  const [themeToast, setThemeToast] = useState<{
    themeKey: string;
    reason: string | null;
  } | null>(null);
  // 친구 학습 시작 알림 (docs/specs/study-spectate.md §진입 경로 #1) — 접속
  // 중 채널만, 웹푸시 폴백 없음
  const [studyToast, setStudyToast] = useState<{
    userId: number;
    nickname: string;
    code: string;
  } | null>(null);

  const handleMessage = useCallback((msg: ServerMsg) => {
    if (msg.t === "iv.invited") {
      setInvite({
        from: msg.from,
        game: msg.game,
        code: msg.code,
        theme: msg.theme,
      });
      return;
    }
    if (msg.t === "chat.message") {
      // 이벤트 버스로 배급 (대화방·위젯·네비 배지가 구독)
      dispatchChatEvent(msg);
      // 위장 접기(빈 종이/시트) 상태는 "안 보는 중" — 접힌 화면에서 알림이
      // 전부 침묵하던 버그 (2026-08-10 보고). room 기준 판정 — 같은 상대의
      // 다른 언어쌍 방과 섞이지 않게 conversation_id(=room id) 로 비교한다
      // (2026-08-14 언어 학습 방 확장)
      const viewing =
        (pathRef.current === `/chat/room/${msg.conversation_id}` ||
          getActiveChatRoom() === msg.conversation_id) &&
        isChatPanelVisible();
      // "실제로 대화 중"일 때만 알림 생략 = 그 방을 보는 중 + 탭 전면 + 창 포커스
      // + 입력창에 커서. 대화방을 켜두고 커서가 입력창 밖이면 자리 비움으로 보고
      // 알림을 보낸다 (2026-07-29 보고: 방만 켜둔 채 다른 일 하는 동안 유실).
      // hidden 만 보면 "브라우저는 보이는데 다른 앱 사용 중"도 놓친다 (07-28).
      const backgrounded = document.hidden || !document.hasFocus();
      const engaged = viewing && !backgrounded && isChatInputFocused();
      // 채널 (2026-07-31 최종): engaged = 무음 / 백그라운드 = OS 알림 /
      // 전면 자리 비움 = 파비콘·탭 제목 배지만 (미니 채팅 토스트는 사용자
      // 요청으로 제거 — 위장 화면 위에 뜨는 것 자체가 노출)
      // iOS Safari 탭은 Notification 전역 자체가 없다 — bare 참조는 throw
      if (
        !engaged &&
        backgrounded &&
        typeof Notification !== "undefined" &&
        Notification.permission === "granted"
      ) {
        // 내용 없는 알림 — 발신자·본문 대신 테마 라벨만 (2026-08-04).
        // 잠금화면·알림센터 미리보기가 위장을 무력화한다. 웹푸시 경로(sw.js)와
        // 같은 문구를 쓴다 — 두 경로가 다르면 어느 쪽이 뜨느냐에 따라 노출된다.
        // 딥링크는 room 경로로 (chat-language-rooms.md §UX 딥링크)
        notifyOs(
          chatNotice(getAppTheme()),
          `/chat/room/${msg.conversation_id}`,
        );
      }
      return;
    }
    if (
      msg.t === "chat.read" ||
      msg.t === "chat.deleted" ||
      msg.t === "chat.typing" ||
      msg.t === "presence" ||
      msg.t === "notif.new" ||
      msg.t === "goal.sync" ||
      msg.t === "chat.matched" ||
      msg.t === "chat.room_created" ||
      msg.t === "chat.room_closed"
    ) {
      dispatchChatEvent(msg);
      // 테마 지급(업적 보상·이벤트)은 벨 적재에 더해 즉시 축하 — 획득 순간 각인
      if (msg.t === "notif.new" && msg.type === "theme_granted") {
        setThemeToast({
          themeKey: String(msg.theme_key ?? ""),
          reason: msg.note ? String(msg.note) : null,
        });
      }
      return;
    }
    if (msg.t === "st.friend_studying") {
      setStudyToast({
        userId: msg.user_id,
        nickname: msg.nickname,
        code: msg.code,
      });
      return;
    }
    if (msg.t === "st.friend_study_end") {
      setStudyToast((prev) => (prev?.userId === msg.user_id ? null : prev));
    }
  }, []);

  useEffect(() => {
    let socket: GameSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    // 마지막 수신(pong 포함) 시각 — onclose 없이 조용히 죽은 소켓 감지 근거
    const lastAlive = { t: Date.now() };

    // 재접속 루프 (2026-07-31 근본 수정): 이전 구현은 fetchMe 1회 실패(배포 중
    // 서버 순단 포함)로 재시도가 영구 중단돼 "새로고침해야 복구" 를 만들었다.
    // null 이어도 백오프로 계속 재확인 — /api/me 30초 폴링은 만료 세션에도 저부하
    function scheduleRetry(delay: number) {
      if (stopped || retry) return;
      retry = setTimeout(() => {
        retry = null;
        fetchMe().then((me) => {
          if (stopped) return;
          if (me) connect();
          else scheduleRetry(30000);
        });
      }, delay);
    }

    function connect() {
      if (stopped) return;
      lastAlive.t = Date.now();
      const s = new GameSocket(
        (msg) => {
          lastAlive.t = Date.now();
          handleMessage(msg);
        },
        () => {
          if (socket !== s) return; // 교체된 옛 소켓의 잔여 close — 무시
          setChatSocket(null);
          scheduleRetry(5000);
        },
        // 재접속 성공 = 끊김 동안 메시지를 놓쳤을 수 있음 — 열린 대화방 재동기화
        () => dispatchChatEvent({ t: "chat.resync" }),
      );
      socket = s;
      s.connect();
      setChatSocket(s); // 대화방의 입력중 신호 전송용 (두 번째 소켓 금지)
    }
    fetchMe().then((me) => {
      if (stopped) return;
      if (me) connect();
      else scheduleRetry(30000);
    });

    // 하트비트 — 30초 ping(서버 좀비 판정용 last_seen 갱신), 70초 무소식이면
    // 죽은 소켓으로 보고 close → onclose 재접속 경로 (절전·네트워크 전환 회수)
    const hb = setInterval(() => {
      if (!socket?.isOpen()) return;
      if (Date.now() - lastAlive.t > 70000) socket.close();
      else socket.ping();
    }, 30000);

    // 탭 복귀·네트워크 복구 — 대기 없이 즉시 점검 (배포로 끊긴 소켓 회수)
    const ensureAlive = () => {
      if (stopped) return;
      if (socket?.isOpen()) {
        socket.ping();
        return;
      }
      socket?.close();
      if (retry) {
        clearTimeout(retry);
        retry = null;
      }
      scheduleRetry(0);
    };
    const onVisible = () => {
      if (!document.hidden) ensureAlive();
    };
    window.addEventListener("online", ensureAlive);
    window.addEventListener("focus", onVisible);
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      stopped = true;
      clearInterval(hb);
      if (retry) clearTimeout(retry);
      window.removeEventListener("online", ensureAlive);
      window.removeEventListener("focus", onVisible);
      document.removeEventListener("visibilitychange", onVisible);
      setChatSocket(null);
      socket?.close();
    };
  }, [handleMessage]);

  // 테마 축하 토스트 — 액션 유도가 목적이라 조금 길게 유지 후 자동 소멸
  useEffect(() => {
    if (!themeToast) return;
    const timer = setTimeout(() => setThemeToast(null), 10000);
    return () => clearTimeout(timer);
  }, [themeToast]);

  // 친구 학습 시작 토스트 — 초대 토스트와 동형, 8초 후 자동 소멸
  useEffect(() => {
    if (!studyToast) return;
    const timer = setTimeout(() => setStudyToast(null), 8000);
    return () => clearTimeout(timer);
  }, [studyToast]);

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
              // 초대자 테마로 게임 화면을 연다 — 종료/이탈 시 useInviteTheme 이 복원
              const themeSuffix = invite.theme ? `&theme=${invite.theme}` : "";
              const target = `/game/${invite.game}?join=${invite.code}${themeSuffix}`;
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

      {studyToast && (
        <div className="fixed inset-x-4 top-16 z-50 mx-auto flex max-w-sm items-center gap-3 rounded-lg border-2 border-brick-green/60 bg-white p-3 shadow-lg">
          <p className="flex-1 text-sm">
            <b>{studyToast.nickname}</b> 님이 학습 중이에요
          </p>
          <button
            type="button"
            onClick={() => {
              const target = `/study/watch?code=${studyToast.code}`;
              setStudyToast(null);
              router.push(target);
            }}
            className="min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85"
          >
            관전
          </button>
          <button
            type="button"
            onClick={() => setStudyToast(null)}
            aria-label="학습 중 알림 닫기"
            className="min-h-10 min-w-10 rounded-md text-lg opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}

      {themeToast && (
        <div className="fixed inset-x-4 top-16 z-50 mx-auto flex max-w-sm items-center gap-3 rounded-lg border-2 border-brick-yellow bg-highlight/40 p-3 shadow-lg backdrop-blur">
          <span
            className="inline-block h-8 w-8 shrink-0 rounded-full border-2 border-ink/20"
            style={{
              backgroundColor:
                APP_THEMES.find((t) => t.key === themeToast.themeKey)?.swatch ??
                "#fff",
            }}
          />
          <span className="flex-1 text-sm">
            <b>
              {APP_THEMES.find((t) => t.key === themeToast.themeKey)?.label ??
                themeToast.themeKey}{" "}
              테마가 열렸어요!
            </b>
            {themeToast.reason && (
              <span className="mt-0.5 block text-xs opacity-70">
                {themeToast.reason}
              </span>
            )}
          </span>
          <button
            type="button"
            onClick={() => {
              // 방금 지급받은 테마 — 엔타이틀먼트 보유 상태라 즉시 적용 안전
              setAppTheme(themeToast.themeKey as AppTheme);
              setThemeToast(null);
            }}
            className="min-h-10 rounded-md bg-ink px-3 text-sm font-bold text-white transition hover:opacity-85"
          >
            바로 적용
          </button>
          <button
            type="button"
            onClick={() => setThemeToast(null)}
            aria-label="테마 알림 닫기"
            className="min-h-10 min-w-10 rounded-md text-lg opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}

/** 백그라운드 탭 OS 알림 — SW 우선, 미등록이면 페이지 Notification 폴백.
 *  renotify: 같은 tag 의 후속 알림이 소리 없이 대체되지 않고 다시 알리게 */
function notifyOs(notice: { title: string; body: string }, url: string) {
  const { title, body } = notice;
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

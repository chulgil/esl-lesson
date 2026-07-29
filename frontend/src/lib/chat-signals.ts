/** 채팅 실시간 신호 버스 — InviteToaster 의 단일 전역 소켓을 공유 (docs/specs/chat.md).
 *
 *  두 번째 소켓을 만들지 않는다: InviteToaster 가 소켓을 등록하고 chat 이벤트를
 *  CustomEvent 로 흘리면, 대화방·네비 배지가 구독한다.
 */

import type { GameSocket, ServerMsg } from "@/lib/game-ws";

export const CHAT_EVENT = "esl-chat";

let socket: GameSocket | null = null;
let lastTypingSent = 0;
// 지금 보고 있는 대화 상대 (페이지든 위젯이든) — 토스트·OS 알림 중복 억제용
let activeRoomUserId: number | null = null;

export function setActiveChatRoom(userId: number | null): void {
  activeRoomUserId = userId;
}

export function getActiveChatRoom(): number | null {
  return activeRoomUserId;
}

/** 채팅 입력창에 커서가 있는가 — "실제로 대화 중" 판정 (docs/specs/chat.md 알림).
 *  대화방이 열려 있어도 입력창 밖이면 자리 비움으로 보고 알림을 보낸다
 *  (2026-07-29 보고: 방만 켜두고 다른 일 하는 동안 알림 유실).
 *  입력창들은 data-chat-input 마커를 단다 — 상태 배선 없이 activeElement 로 판정. */
export function isChatInputFocused(): boolean {
  return (
    typeof document !== "undefined" &&
    document.activeElement?.getAttribute("data-chat-input") === "1"
  );
}

export function setChatSocket(s: GameSocket | null): void {
  socket = s;
}

/** 입력 중 신호 — 클라 3초 스로틀 (서버도 2초 스로틀로 이중 방어) */
export function sendTyping(toUserId: number): void {
  const now = Date.now();
  if (now - lastTypingSent < 3000) return;
  lastTypingSent = now;
  socket?.sendChatTyping(toUserId);
}

export function dispatchChatEvent(msg: ServerMsg): void {
  window.dispatchEvent(new CustomEvent(CHAT_EVENT, { detail: msg }));
}

export function onChatEvent(handler: (msg: ServerMsg) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent).detail);
  window.addEventListener(CHAT_EVENT, listener);
  return () => window.removeEventListener(CHAT_EVENT, listener);
}

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

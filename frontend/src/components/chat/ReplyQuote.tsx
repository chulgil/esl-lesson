"use client";

import type { ChatMessage } from "@/lib/chat-api";

/** 답장 인용 표기 공용 (2026-07-31 카톡식 답장 — docs/specs/chat.md).
 *  원문이 목록에 로드돼 있으면 실시간 상태(삭제 즉시 반영)로, 아니면 서버가
 *  읽기 시점에 부착한 미리보기(reply_to)로 렌더. 탭하면 원문으로 스크롤. */

export function replyPreviewOf(m: ChatMessage): string {
  return m.deleted
    ? "삭제되었습니다"
    : m.body || (m.image_url ? "[사진]" : "[단어 카드]");
}

/** 원문 행으로 스크롤 — 스킨들이 메시지 행에 data-mid 를 달아둔다 */
export function jumpToMessage(id: number): void {
  document
    .querySelector(`[data-mid="m${id}"]`)
    ?.scrollIntoView({ block: "center", behavior: "smooth" });
}

export function ReplyQuote({
  msg,
  messages,
  myId,
  peerName,
  className,
}: {
  msg: ChatMessage;
  messages: ChatMessage[];
  myId: number | null;
  peerName: string;
  className: string;
}) {
  if (!msg.reply_to_id) return null;
  const original = messages.find((x) => x.id === msg.reply_to_id);
  const senderId = original?.sender_id ?? msg.reply_to?.sender_id;
  const preview = original ? replyPreviewOf(original) : msg.reply_to?.preview;
  if (preview == null) return null;
  const who = senderId === myId ? "나" : peerName;
  return (
    <button
      type="button"
      onClick={() => jumpToMessage(msg.reply_to_id!)}
      title="원문으로 이동"
      className={`mb-0.5 block w-full truncate text-left ${className}`}
    >
      {who}: {preview}
    </button>
  );
}

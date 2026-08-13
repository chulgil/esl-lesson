import type { ChatMessage } from "@/lib/chat-api";

/** 공지 변경 시스템 줄 — 말풍선 대신 중앙 정렬 회색 한 줄 (docs/specs/chat-notice.md).
 *  notice_set/notice_clear 외 kind 값은 없다. 번역·답글 인용은 붙이지 않는다. */
export function NoticeSystemLine({
  msg,
  mine,
  peerName,
  excel,
}: {
  msg: ChatMessage;
  mine: boolean;
  peerName: string;
  excel: boolean;
}) {
  const text = mine
    ? msg.kind === "notice_set"
      ? `공지를 등록했어요: ${msg.body}`
      : "공지를 내렸어요"
    : msg.kind === "notice_set"
      ? `${peerName}님이 공지를 등록했어요: ${msg.body}`
      : `${peerName}님이 공지를 내렸어요`;
  return (
    <p
      data-mid={`m${msg.id}`}
      className={`py-1.5 text-center text-[11px] ${excel ? "text-[#999]" : "opacity-45"}`}
    >
      {text}
    </p>
  );
}

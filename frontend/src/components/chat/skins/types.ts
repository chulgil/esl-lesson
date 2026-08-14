/** 대화방 스킨 공용 계약 — 컨테이너(데이터)와 표현을 분리 (docs/specs/chat.md 위장 테마).
 *  새 위장 테마 = 이 Props 를 받는 스킨 1개 추가.
 *  2026-08-14: room 기준으로 확장 — docs/specs/chat-language-rooms.md */

import type { RefObject } from "react";
import type {
  ChatMessage,
  ChatRoom,
  RoomOrigin,
  RoomStatus,
  ShareableItem,
  SupportedLang,
} from "@/lib/chat-api";
import type { AttachedImage } from "@/components/chat/useChatRoom";

export interface PendingMessage {
  client_msg_id: string;
  body: string;
  item: ShareableItem | null;
  imageId: string | null;
  imageUrl: string | null;
  failed: boolean;
  /** 답장 인용 (낙관 렌더용 — 서버 확정 시 reply_to 로 치환) */
  replyToId?: number | null;
  replyPreview?: string | null;
}

/** 답장 작성 상태 — 입력줄 위 인용 배너 (2026-07-31 카톡식 답장) */
export interface ReplyDraft {
  id: number;
  senderId: number;
  preview: string;
}

export interface ChatSkinProps {
  /** 방 메타 전체 — 로딩 중(초기 fetch 전)에는 null */
  room: ChatRoom | null;
  peerName: string;
  peerId: number | null;
  online: boolean;
  sourceLang: SupportedLang | null;
  targetLang: SupportedLang | null;
  origin: RoomOrigin | null;
  status: RoomStatus | null;
  typing: boolean;
  myId: number | null;
  messages: ChatMessage[];
  pending: PendingMessage[];
  otherRead: number;
  hasMore: boolean;
  error: string | null;
  input: string;
  attachedItem: ShareableItem | null;
  attachedImage: AttachedImage | null;
  listRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onRetry: (entry: PendingMessage) => void;
  /** 내 메시지 삭제 — 확인 후 soft delete, "삭제되었습니다" 로 치환 */
  onDeleteMessage: (id: number) => void;
  /** 방 나가기 — origin=match 방만 노출 (chat-language-rooms.md §접근 규칙) */
  onLeaveRoom: () => void;
  /** 답장 — 대상 지정 시 입력줄 위 인용 배너, 전송에 reply_to_id 포함 */
  replyDraft: ReplyDraft | null;
  onReplyTo: (msg: ChatMessage) => void;
  onCancelReply: () => void;
  onPickKaomoji: (k: string) => void;
  onAttachItem: (item: ShareableItem) => void;
  onDetachItem: () => void;
  onAttachImageFile: (file: File) => void;
  onDetachImage: () => void;
}

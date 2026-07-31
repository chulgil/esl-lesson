/** 대화방 스킨 공용 계약 — 컨테이너(데이터)와 표현을 분리 (docs/specs/chat.md 위장 테마).
 *  새 위장 테마 = 이 Props 를 받는 스킨 1개 추가. */

import type { RefObject } from "react";
import type { ChatMessage, ShareableItem } from "@/lib/chat-api";
import type { AttachedImage } from "@/components/chat/useChatRoom";

export interface PendingMessage {
  client_msg_id: string;
  body: string;
  item: ShareableItem | null;
  imageId: string | null;
  imageUrl: string | null;
  failed: boolean;
}

export interface ChatSkinProps {
  peerName: string;
  online: boolean;
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
  onPickKaomoji: (k: string) => void;
  onAttachItem: (item: ShareableItem) => void;
  onDetachItem: () => void;
  onAttachImageFile: (file: File) => void;
  onDetachImage: () => void;
}

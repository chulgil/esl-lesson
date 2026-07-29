"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";
import { ExcelSkin } from "@/components/chat/skins/ExcelSkin";
import { NoteSkin } from "@/components/chat/skins/NoteSkin";
import { fakeFilename } from "@/components/chat/skins/ExcelChrome";
import { useChatRoom } from "@/components/chat/useChatRoom";
import { useAppTheme } from "@/lib/theme";

/** 대화방 페이지 — 데이터는 useChatRoom 훅, 표현은 테마별 스킨.
 *  오피스 테마 = 스프레드시트 위장, 그 외 = 교환 노트 위장 (docs/specs/chat.md). */
export default function ChatRoomPage() {
  const { userId } = useParams<{ userId: string }>();
  const otherId = Number(userId);
  const theme = useAppTheme();
  const skinProps = useChatRoom(otherId);

  // 위장 문서 제목 — 브라우저 탭 목록에서도 업무 문서로 보이게
  useEffect(() => {
    const prev = document.title;
    document.title =
      theme === "excel"
        ? `${fakeFilename("재고관리")} - 통합 문서`
        : "교환 노트";
    return () => {
      document.title = prev;
    };
  }, [theme]);

  // 모바일 대화방 집중 모드 — 하단 탭바 숨김 + 바디 스크롤 잠금 (globals.css)
  useEffect(() => {
    document.body.classList.add("chat-focus");
    return () => document.body.classList.remove("chat-focus");
  }, []);

  if (!Number.isFinite(otherId)) {
    return (
      <main className="p-8">
        <p className="text-sm text-brick-red">잘못된 주소예요</p>
      </main>
    );
  }

  return theme === "excel" ? (
    <ExcelSkin {...skinProps} />
  ) : (
    <NoteSkin {...skinProps} />
  );
}

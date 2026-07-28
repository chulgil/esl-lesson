"use client";

import { useRouter } from "next/navigation";
import { ImageAttachButton } from "@/components/chat/ImageAttachButton";
import { KaomojiPicker } from "@/components/chat/KaomojiPicker";
import { WordSharePicker } from "@/components/chat/WordSharePicker";
import { BlankSheet, ExcelChrome, fakeFilename } from "./ExcelChrome";
import type { ChatSkinProps } from "./types";

/** 스프레드시트 위장 대화방 — excelkospi 컨셉 (docs/specs/chat.md 위장 테마).
 *  상단 엑셀 크롬(타이틀바·리본·수식줄·시트탭·상태바)은 그대로 두고, 본문은
 *  좌측(빈 시트로 위장)+우측(화면 우측 도킹 채팅 리스트) 2단 레이아웃으로 구성한다.
 *  각 메시지는 [닉네임·시각] 헤더 줄 + 그 아래 내용 줄. 입력중 = 상태바
 *  "공동 작성자가 셀을 편집하는 중", 읽음 = 메시지 헤더의 확인/미확인,
 *  Esc ×2 = 빈 시트 (ExcelChrome 보스 키). */

const COLS = ["A", "B", "C", "D"];

export function ExcelSkin(p: ChatSkinProps) {
  const router = useRouter();
  const rowBase = p.messages.length + p.pending.length;

  return (
    <ExcelChrome
      filename={fakeFilename("재고관리")}
      formula='=DATA.SYNC("공유", AUTO)'
      cellRef={`C${rowBase + 3}`}
      sheetTabs={["집계", "원본", "백업"]}
      online={p.online}
      onFilenameClick={() => router.push("/chat")}
      statusLeft={
        p.typing ? (
          <span>
            공동 작성자가 셀을 편집하는 중
            <span className="inline-block animate-pulse">...</span>
          </span>
        ) : null
      }
      statusRight={<span>행 {rowBase + 2}</span>}
      blank={<BlankSheet cols={COLS} />}
    >
      <div className="flex min-h-0 flex-1">
        {/* 좌측 — 실제 시트처럼 보이는 채움 영역 (위장, 모바일에서는 숨김) */}
        <div className="hidden flex-1 overflow-y-auto border-r border-[#d8dde3] md:block">
          <BlankSheet cols={COLS} />
        </div>

        {/* 우측 — 화면 우측 도킹 채팅 패널 */}
        <div className="flex w-full flex-col md:w-[380px] md:shrink-0">
          <div
            ref={p.listRef}
            onScroll={p.onScroll}
            className="flex-1 overflow-y-auto px-2 py-1.5"
          >
            {p.hasMore && p.messages.length > 0 && (
              <p className="py-1 text-center text-[11px] text-[#999]">
                위로 스크롤하면 이전 기록을 불러옵니다
              </p>
            )}
            {p.messages.map((m) => {
              const mine = m.sender_id === p.myId;
              return (
                <div
                  key={m.id}
                  className={`border-b border-[#f0f2f4] py-1.5 text-[13px] leading-relaxed ${
                    mine ? "text-[#217346]" : "text-[#24292f]"
                  }`}
                >
                  <div className="mb-0.5 flex items-baseline gap-1.5 text-[10px] text-[#8a8f98]">
                    <b className={mine ? "text-[#217346]" : "text-[#444]"}>
                      {mine ? "본인" : p.peerName}
                    </b>
                    {m.created_at && (
                      <span>
                        {new Date(m.created_at).toLocaleTimeString("ko-KR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                    {mine && (
                      <span className="ml-auto">
                        {m.id > p.otherRead ? "미확인" : "확인"}
                      </span>
                    )}
                  </div>
                  {m.item_ref && (
                    <span className="mr-1.5 rounded-sm bg-[#e2efda] px-1 text-xs">
                      {m.item_ref.en_text} ({m.item_ref.ko_text})
                    </span>
                  )}
                  {m.image_url && (
                    <a href={m.image_url} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={m.image_url}
                        alt="첨부"
                        className="my-0.5 block h-16 rounded-sm border border-[#d8dde3] object-cover"
                      />
                    </a>
                  )}
                  <span className="break-words whitespace-pre-wrap">
                    {m.body}
                  </span>
                </div>
              );
            })}
            {p.pending.map((entry) => (
              <div
                key={entry.client_msg_id}
                className="border-b border-[#f0f2f4] py-1.5 text-[13px] text-[#217346] opacity-70"
              >
                <div className="mb-0.5 flex items-baseline gap-1.5 text-[10px] text-[#8a8f98]">
                  <b className="text-[#217346]">본인</b>
                  {!entry.failed && <span>저장 중</span>}
                </div>
                {entry.item && (
                  <span className="mr-1.5 rounded-sm bg-[#e2efda] px-1 text-xs">
                    {entry.item.en_text}
                  </span>
                )}
                {entry.imageUrl && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={entry.imageUrl}
                    alt=""
                    className="my-0.5 block h-12 rounded-sm border border-[#d8dde3] object-cover opacity-70"
                  />
                )}
                <span className="break-words whitespace-pre-wrap">
                  {entry.body}
                </span>
                {entry.failed && (
                  <button
                    type="button"
                    onClick={() => p.onRetry(entry)}
                    className="ml-1.5 text-[11px] font-bold text-[#c0504d]"
                  >
                    재시도
                  </button>
                )}
              </div>
            ))}
            {p.messages.length === 0 && p.pending.length === 0 && (
              <p className="py-8 text-center text-xs text-[#999]">
                기록이 없습니다
              </p>
            )}
          </div>

          {p.error && (
            <p className="border-t border-[#d8dde3] bg-[#fff4f4] px-3 py-1 text-xs text-[#c0504d]">
              {p.error}
            </p>
          )}
          {p.attachedImage && (
            <div className="flex items-center gap-2 border-t border-[#d8dde3] bg-[#e2efda] px-3 py-1 text-xs">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.attachedImage.url}
                alt=""
                className="h-8 w-8 rounded-sm object-cover"
              />
              {p.attachedImage.uploading ? "업로드 중..." : "삽입 준비 완료"}
              <button
                type="button"
                onClick={p.onDetachImage}
                aria-label="이미지 첨부 해제"
                className="ml-auto opacity-60 hover:opacity-100"
              >
                ×
              </button>
            </div>
          )}
          {p.attachedItem && (
            <div className="flex items-center gap-2 border-t border-[#d8dde3] bg-[#e2efda] px-3 py-1 text-xs">
              첨부: <b>{p.attachedItem.en_text}</b>
              <span className="opacity-60">{p.attachedItem.ko_text}</span>
              <button
                type="button"
                onClick={p.onDetachItem}
                aria-label="첨부 해제"
                className="ml-auto opacity-60 hover:opacity-100"
              >
                ×
              </button>
            </div>
          )}

          {/* 입력줄 — excelkospi 의 "입력 후 Enter" 바 컨셉, 리스트 하단에 고정 */}
          <div className="flex items-center gap-1.5 border-t border-[#d8dde3] bg-white px-2 py-1.5">
            <input
              value={p.input}
              onChange={(e) => p.onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.nativeEvent.isComposing) p.onSend();
              }}
              placeholder="내용 입력 후 Enter"
              maxLength={2000}
              aria-label="내용 입력"
              className="min-h-9 flex-1 rounded-sm border border-[#c9cfd6] px-2.5 text-[13px] focus:border-[#217346] focus:outline-none"
            />
            <WordSharePicker onPick={p.onAttachItem} />
            <ImageAttachButton onPick={p.onAttachImageFile} variant="excel" />
            <KaomojiPicker onPick={p.onPickKaomoji} />
            <button
              type="button"
              onClick={p.onSend}
              disabled={
                (!p.input.trim() && !p.attachedItem && !p.attachedImage) ||
                Boolean(p.attachedImage?.uploading)
              }
              className="min-h-9 rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-3 text-xs hover:bg-[#e2efda] disabled:opacity-40"
            >
              입력
            </button>
          </div>
        </div>
      </div>
    </ExcelChrome>
  );
}

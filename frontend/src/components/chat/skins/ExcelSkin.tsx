"use client";

import { useRouter } from "next/navigation";
import { ImageAttachButton } from "@/components/chat/ImageAttachButton";
import { KaomojiPicker } from "@/components/chat/KaomojiPicker";
import { WordSharePicker } from "@/components/chat/WordSharePicker";
import { BlankSheet, ExcelChrome, fakeFilename } from "./ExcelChrome";
import type { ChatSkinProps } from "./types";

/** 스프레드시트 위장 대화방 — excelkospi 컨셉 (docs/specs/chat.md 위장 테마).
 *  메시지 = 시트 행(시간|담당|내용|상태), 입력중 = 상태바 "공동 작성자가 편집 중",
 *  읽음 = 상태열 확인/미확인, Esc ×2 = 빈 시트 (ExcelChrome 보스 키). */

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
      {/* 입력줄 — excelkospi 의 "입력 후 Enter" 바 컨셉 */}
      <div className="flex items-center gap-1.5 border-b border-[#d8dde3] bg-white px-2 py-1.5">
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

      {p.error && (
        <p className="border-b border-[#d8dde3] bg-[#fff4f4] px-3 py-1 text-xs text-[#c0504d]">
          {p.error}
        </p>
      )}
      {p.attachedImage && (
        <div className="flex items-center gap-2 border-b border-[#d8dde3] bg-[#e2efda] px-3 py-1 text-xs">
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
        <div className="flex items-center gap-2 border-b border-[#d8dde3] bg-[#e2efda] px-3 py-1 text-xs">
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

      {/* 시트 그리드 */}
      <div
        ref={p.listRef}
        onScroll={p.onScroll}
        className="flex-1 overflow-y-auto"
      >
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-[#f6f8f9]">
            <tr className="text-xs text-[#666]">
              <Th w="w-9"> </Th>
              <Th w="w-16">A</Th>
              <Th w="w-24">B</Th>
              <Th>C</Th>
              <Th w="w-16">D</Th>
            </tr>
            <tr className="bg-[#eef2ee] text-xs font-bold">
              <Td c="text-center text-[#888]">1</Td>
              <Td>시간</Td>
              <Td>담당</Td>
              <Td>내용</Td>
              <Td>상태</Td>
            </tr>
          </thead>
          <tbody>
            {p.hasMore && p.messages.length > 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="py-1 text-center text-[11px] text-[#999]"
                >
                  위로 스크롤하면 이전 행을 불러옵니다
                </td>
              </tr>
            )}
            {p.messages.map((m, i) => {
              const mine = m.sender_id === p.myId;
              return (
                <tr key={m.id} className={mine ? "bg-[#f7faf7]" : "bg-white"}>
                  <Td c="text-center text-[#888]">{i + 2}</Td>
                  <Td c="text-[#666]">
                    {m.created_at
                      ? new Date(m.created_at).toLocaleTimeString("ko-KR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : ""}
                  </Td>
                  <Td c={mine ? "text-[#217346]" : ""}>
                    {mine ? "본인" : p.peerName}
                  </Td>
                  <Td>
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
                  </Td>
                  <Td c="text-xs text-[#888]">
                    {mine ? (m.id > p.otherRead ? "미확인" : "확인") : ""}
                  </Td>
                </tr>
              );
            })}
            {p.pending.map((entry, i) => (
              <tr key={entry.client_msg_id} className="bg-[#f7faf7] opacity-70">
                <Td c="text-center text-[#888]">{p.messages.length + i + 2}</Td>
                <Td c="text-[#666]">...</Td>
                <Td c="text-[#217346]">본인</Td>
                <Td>
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
                  {entry.body}
                </Td>
                <Td c="text-xs">
                  {entry.failed ? (
                    <button
                      type="button"
                      onClick={() => p.onRetry(entry)}
                      className="font-bold text-[#c0504d]"
                    >
                      재시도
                    </button>
                  ) : (
                    <span className="text-[#888]">저장 중</span>
                  )}
                </Td>
              </tr>
            ))}
            {/* 빈 행 채우기 — 진짜 시트처럼 */}
            {Array.from({ length: Math.max(0, 16 - rowBase) }).map((_, i) => (
              <tr key={`empty-${i}`}>
                <Td c="text-center text-[#bbb]">{rowBase + i + 2}</Td>
                <Td> </Td>
                <Td> </Td>
                <Td> </Td>
                <Td> </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ExcelChrome>
  );
}

function Th({ children, w = "" }: { children: React.ReactNode; w?: string }) {
  return (
    <th className={`border border-[#d8dde3] px-1.5 py-0.5 font-normal ${w}`}>
      {children}
    </th>
  );
}

function Td({ children, c = "" }: { children: React.ReactNode; c?: string }) {
  return (
    <td className={`border border-[#e4e8ec] px-1.5 py-1 align-top ${c}`}>
      {children}
    </td>
  );
}

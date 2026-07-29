"use client";

import { ChatToolsMenu } from "@/components/chat/ChatToolsMenu";
import { BackLink } from "@/components/nav/BackLink";
import type { ChatSkinProps } from "./types";

/** 교환 노트 스킨 — 종이 테마(노트·캔디·레고·헤냥이) 공용 위장.
 *  말풍선 없이 필기 줄 형식: 힐끗 보면 학습 노트로 보인다 (docs/specs/chat.md).
 *  내 글 = 파란 잉크, 상대 글 = 검정 잉크. 창은 화면 우측에 도킹(컴팩트 max-w-md)된다. */
export function NoteSkin(p: ChatSkinProps) {
  return (
    <main className="notebook-lines notebook-margin h-dvh-nav-safe flex flex-col">
      <div className="ml-auto flex h-full w-full max-w-md flex-col border-l-2 border-ink/10 bg-paper/95 px-4 py-4 shadow-[-6px_0_20px_-10px_rgba(0,0,0,0.15)] sm:py-6">
        <header className="mb-2 flex items-center gap-3">
          <BackLink href="/chat" label="목록" />
          <h1 className="flex items-center gap-2 font-hand text-xl font-bold">
            <span className="hl">{p.peerName || "..."} 와의 교환 노트</span>
            <span
              aria-label={p.online ? "접속 중" : "미접속"}
              title={p.online ? "접속 중" : "미접속"}
              className={`h-2.5 w-2.5 rounded-full ${
                p.online ? "bg-brick-green" : "bg-ink/20"
              }`}
            />
          </h1>
        </header>

        {p.error && <p className="mb-2 text-sm text-brick-red">{p.error}</p>}

        {/* 필기 줄 목록 — 채팅 말풍선 금지 (위장 원칙) */}
        <div
          ref={p.listRef}
          onScroll={p.onScroll}
          className="flex-1 overflow-y-auto rounded-lg border-2 border-ink/10 bg-white/70 px-4 py-2"
        >
          {p.hasMore && p.messages.length > 0 && (
            <p className="py-1.5 text-center text-[11px] opacity-40">
              위로 스크롤하면 지난 페이지를 넘겨요
            </p>
          )}
          {p.messages.map((m) => {
            const mine = m.sender_id === p.myId;
            return (
              <div
                key={m.id}
                className={`border-b border-ink/5 py-1.5 text-sm leading-relaxed ${
                  // 상대 글이 더 잘 읽혀야 한다 (2026-07-28 요청) — 내 글은 흐리게
                  mine ? "text-brick-blue/60" : "font-medium text-ink"
                }`}
              >
                <div
                  className={`mb-0.5 flex items-baseline gap-1.5 text-[10px] ${
                    mine ? "opacity-40" : "opacity-70"
                  }`}
                >
                  <b>{mine ? "나" : p.peerName}</b>
                  {m.created_at && (
                    <span>
                      {new Date(m.created_at).toLocaleTimeString("ko-KR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  )}
                  {/* 상대가 아직 안 읽은 내 글 — 작은 점으로만 표시 (위장 유지) */}
                  {mine && m.id > p.otherRead && (
                    <span
                      aria-label="상대가 아직 읽지 않음"
                      className="inline-block h-1.5 w-1.5 rounded-full bg-brick-yellow align-middle"
                    />
                  )}
                </div>
                {m.item_ref && (
                  <span className="mr-2 rounded bg-highlight/50 px-1.5 py-0.5 text-xs">
                    <b>{m.item_ref.en_text}</b>
                    <span className="ml-1 opacity-70">
                      {m.item_ref.ko_text}
                    </span>
                  </span>
                )}
                {m.image_url && (
                  <a href={m.image_url} target="_blank" rel="noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={m.image_url}
                      alt="첨부 이미지"
                      className="my-1 block max-h-40 rounded-md border-2 border-ink/10"
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
              className="border-b border-ink/5 py-1.5 text-sm text-brick-blue opacity-60"
            >
              {entry.item && (
                <span className="mr-2 rounded bg-highlight/40 px-1.5 py-0.5 text-xs">
                  <b>{entry.item.en_text}</b>
                </span>
              )}
              {entry.imageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={entry.imageUrl}
                  alt=""
                  className="my-1 block max-h-32 rounded-md border-2 border-ink/10 opacity-70"
                />
              )}
              <span className="break-words">{entry.body}</span>
              {entry.failed ? (
                <button
                  type="button"
                  onClick={() => p.onRetry(entry)}
                  className="ml-2 text-[11px] font-bold text-brick-red"
                >
                  실패 — 다시 쓰기
                </button>
              ) : (
                <span className="ml-2 text-[10px] opacity-50">적는 중...</span>
              )}
            </div>
          ))}
          {p.typing && (
            <p className="py-1 text-[11px] opacity-45">
              {p.peerName} 이(가) 적고 있어요{" "}
              <span className="inline-block animate-pulse">···</span>
            </p>
          )}
          {p.messages.length === 0 && p.pending.length === 0 && (
            <p className="py-10 text-center text-sm opacity-40">
              첫 줄을 적어보세요 (´｡• ᵕ •｡`)
            </p>
          )}
        </div>

        {p.attachedImage && (
          <div className="mt-2 flex items-center gap-2 rounded-md border-2 border-brick-green/50 bg-white px-3 py-1 text-sm">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={p.attachedImage.url}
              alt=""
              className="h-10 w-10 rounded object-cover"
            />
            <span className="text-xs opacity-60">
              {p.attachedImage.uploading ? "업로드 중..." : "전송 준비 완료"}
            </span>
            <button
              type="button"
              onClick={p.onDetachImage}
              aria-label="이미지 첨부 해제"
              className="ml-auto opacity-50 hover:opacity-100"
            >
              ×
            </button>
          </div>
        )}

        {p.attachedItem && (
          <div className="mt-2 flex items-center gap-2 rounded-md border-2 border-brick-yellow/60 bg-highlight/30 px-3 py-1 text-sm">
            <b>{p.attachedItem.en_text}</b>
            <span className="opacity-60">{p.attachedItem.ko_text}</span>
            <button
              type="button"
              onClick={p.onDetachItem}
              aria-label="첨부 해제"
              className="ml-auto opacity-50 hover:opacity-100"
            >
              ×
            </button>
          </div>
        )}

        <div className="mt-2 flex items-end gap-1.5">
          <ChatToolsMenu
            onPickItem={p.onAttachItem}
            onPickImage={p.onAttachImageFile}
            onPickKaomoji={p.onPickKaomoji}
          />
          <input
            value={p.input}
            onChange={(e) => p.onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing) p.onSend();
            }}
            onPaste={(e) => {
              // 클립보드 이미지 붙여넣기 → 파일 첨부와 같은 업로드 파이프라인
              const file = Array.from(e.clipboardData.files).find((f) =>
                f.type.startsWith("image/"),
              );
              if (file) {
                e.preventDefault();
                p.onAttachImageFile(file);
              }
            }}
            data-chat-input="1"
            placeholder="한 줄 적기..."
            maxLength={2000}
            className="min-h-11 flex-1 rounded-md border-2 border-ink/20 px-3 text-base transition-colors focus:border-brick-blue focus:outline-none sm:text-sm"
          />
          <button
            type="button"
            onClick={p.onSend}
            disabled={
              (!p.input.trim() && !p.attachedItem && !p.attachedImage) ||
              Boolean(p.attachedImage?.uploading)
            }
            className="min-h-11 rounded-md bg-brick-blue px-3.5 text-sm font-bold text-brick-label transition-colors hover:bg-brick-blue/85 disabled:opacity-40"
          >
            적기
          </button>
        </div>
      </div>
    </main>
  );
}

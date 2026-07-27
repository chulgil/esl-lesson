"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** 스프레드시트 창 크롬 — excelkospi 컨셉 (docs/specs/chat.md 위장 테마).
 *
 *  타이틀바(자동저장·파일명)·리본 탭줄(접힘)·이름상자+가짜 수식줄·
 *  하단 시트 탭·상태바 + 보스 긴급키(Esc ×2 → 빈 시트로 전환).
 *  내용 영역은 children, 보스 모드일 때는 blank 를 대신 렌더한다. */

const RIBBON_TABS = [
  "파일",
  "홈",
  "삽입",
  "페이지 레이아웃",
  "수식",
  "데이터",
  "검토",
  "보기",
  "도움말",
];
const BOSS_KEY_WINDOW_MS = 600;

export function ExcelChrome({
  filename,
  formula,
  cellRef = "A1",
  sheetTabs,
  statusLeft,
  statusRight,
  online = false,
  onFilenameClick,
  blank,
  children,
}: {
  filename: string;
  formula: string;
  cellRef?: string;
  sheetTabs: string[];
  statusLeft?: ReactNode;
  statusRight?: ReactNode;
  online?: boolean;
  onFilenameClick?: () => void;
  blank: ReactNode;
  children: ReactNode;
}) {
  // 보스 긴급키 — Esc 2연타로 빈 시트 토글 (excelkospi 컨셉)
  const [bossMode, setBossMode] = useState(false);
  const lastEsc = useRef(0);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      const now = Date.now();
      if (now - lastEsc.current < BOSS_KEY_WINDOW_MS) {
        setBossMode((v) => !v);
        lastEsc.current = 0;
      } else {
        lastEsc.current = now;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-dvh flex-col bg-white font-sans text-[13px] text-[#24292f]">
      {/* 타이틀바 */}
      <div className="flex items-center gap-2.5 bg-[#185c37] px-3 py-1.5 text-white">
        <XlsIcon />
        <span className="hidden items-center gap-1.5 text-xs sm:flex">
          자동 저장
          <span className="flex h-4 w-8 items-center rounded-full bg-white/25 px-0.5">
            <span className="h-3 w-3 rounded-full bg-white" />
          </span>
          <span className="opacity-80">끔</span>
        </span>
        <SaveIcon />
        <span className="text-white/70">
          <UndoIcon />
        </span>
        <button
          type="button"
          onClick={onFilenameClick}
          disabled={!onFilenameClick}
          className="mx-auto flex min-w-0 cursor-pointer items-center gap-1 font-medium disabled:cursor-default"
          title={onFilenameClick ? "목록으로" : undefined}
        >
          <span className="truncate">{filename}</span>
          <span className="text-[10px] opacity-60">▾</span>
        </button>
        <span
          className={`h-2 w-2 rounded-full ${online ? "bg-[#7be3a5]" : "bg-white/25"}`}
          title={online ? "공동 작성 1명" : "공동 작성 0명"}
        />
        <BellIcon />
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 text-[10px]">
          H
        </span>
      </div>

      {/* 리본 탭줄 (접힌 리본) */}
      <div className="flex items-center gap-4 overflow-x-auto border-b border-[#d8dde3] bg-[#f6f8f9] px-3 text-xs whitespace-nowrap text-[#444]">
        {RIBBON_TABS.map((tab, i) => (
          <span
            key={tab}
            className={`cursor-default py-1.5 select-none ${
              i === 1
                ? "-mb-px border-b-2 border-[#217346] font-bold text-[#217346]"
                : ""
            }`}
          >
            {tab}
          </span>
        ))}
      </div>

      {/* 이름상자 + 가짜 수식줄 */}
      <div className="flex items-center gap-1.5 border-b border-[#d8dde3] bg-white px-2 py-1">
        <span className="flex w-16 items-center justify-between border border-[#d8dde3] px-1.5 py-0.5 text-xs text-[#444]">
          {cellRef} <span className="text-[9px] text-[#999]">▾</span>
        </span>
        <span
          className="px-1 text-xs italic select-none"
          style={{ color: "#888" }}
        >
          fx
        </span>
        <span className="flex-1 truncate border border-[#e4e8ec] px-2 py-0.5 text-xs text-[#333] select-none">
          {bossMode ? "" : formula}
        </span>
      </div>

      {/* 본문 (보스 모드 = 빈 시트) */}
      <div className="flex min-h-0 flex-1 flex-col">
        {bossMode ? blank : children}
      </div>

      {/* 하단 시트 탭 */}
      <div className="flex items-center gap-0.5 border-t border-[#d8dde3] bg-[#f6f8f9] px-2 text-xs text-[#555]">
        <span className="px-1 text-[#999] select-none">‹ ›</span>
        {sheetTabs.map((tab, i) => (
          <span
            key={tab}
            className={`cursor-default px-3 py-1 select-none ${
              i === 0
                ? "-mt-px border-t-2 border-[#217346] bg-white font-bold text-[#217346]"
                : "hover:bg-white/60"
            }`}
          >
            {tab}
          </span>
        ))}
        <span className="px-2 text-[#999] select-none">+</span>
      </div>

      {/* 상태바 */}
      <div className="flex items-center gap-3 border-t border-[#d8dde3] bg-[#217346] px-3 py-0.5 text-[11px] text-white/90">
        <span title="빠른 전환: Esc 두 번">준비</span>
        {!bossMode && statusLeft}
        <span className="ml-auto flex items-center gap-3">
          {!bossMode && statusRight}
          <span>100%</span>
        </span>
      </div>
    </div>
  );
}

/** 빈 시트 그리드 — 보스 모드·빈 상태 공용 */
export function BlankSheet({
  cols,
  rows = 24,
}: {
  cols: string[];
  rows?: number;
}) {
  return (
    <div className="flex-1 overflow-y-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-[#f6f8f9] text-xs text-[#666]">
            <th className="w-9 border border-[#d8dde3] px-1.5 py-0.5 font-normal">
              {" "}
            </th>
            {cols.map((c) => (
              <th
                key={c}
                className="border border-[#d8dde3] px-1.5 py-0.5 font-normal"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i}>
              <td className="w-9 border border-[#e4e8ec] px-1.5 py-1 text-center text-xs text-[#bbb]">
                {i + 1}
              </td>
              {cols.map((c) => (
                <td key={c} className="border border-[#e4e8ec] px-1.5 py-1">
                  {" "}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 오늘 날짜가 붙은 위장 파일명 — excelkospi 컨셉 (재고관리_20260727.xlsx) */
export function fakeFilename(prefix: string): string {
  const d = new Date();
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(
    d.getDate(),
  ).padStart(2, "0")}`;
  return `${prefix}_${ymd}.xlsx`;
}

function XlsIcon() {
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-white/90 text-[10px] font-bold text-[#185c37]">
      X
    </span>
  );
}

function SaveIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
      <path d="M17 21v-8H7v8M7 3v5h8" />
    </svg>
  );
}

function UndoIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M3 7v6h6" />
      <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

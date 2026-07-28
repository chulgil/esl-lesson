"use client";

/** 파비콘 안읽음 배지 — 탭이 여러 개여도 눈에 띄도록 파비콘에 안읽음 개수를 얹는다.
 *  (표기는 99 한도, 2026-07-28 요청). 아이콘(/icon-192.png)은 같은 출처라 캔버스
 *  오염 없이 다시 그릴 수 있다. 브라우저 탭 제목은 위장 테마(교환 노트/
 *  재고관리.xlsx)와 충돌하므로 건드리지 않는다. */

let originalHref: string | null = null;
let lastCount = 0;

export function setFaviconBadge(count: number): void {
  if (typeof document === "undefined") return;
  const shown = Math.min(Math.max(count, 0), 99);
  if (shown === lastCount) return;
  const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) return;

  if (shown === 0) {
    if (originalHref) link.href = originalHref;
    lastCount = 0;
    return;
  }

  if (!originalHref) originalHref = link.href;
  const img = new Image();
  img.onload = () => {
    const size = 64;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(img, 0, 0, size, size);

    // 우상단 개수 배지 — 64px 캔버스에서 두 자리까지 판독 가능한 크기
    const label = String(shown);
    const r = 15;
    const cx = size - r - 2;
    const cy = r + 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = "#d01012";
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = `bold ${label.length > 1 ? 18 : 22}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, cx, cy + 1);

    link.href = canvas.toDataURL("image/png");
    lastCount = shown;
  };
  img.src = originalHref;
}

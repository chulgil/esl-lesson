"use client";

/** 파비콘 안읽음 배지 — 탭이 여러 개여도 눈에 띄도록 파비콘에 안읽음 개수를 얹는다.
 *  (표기는 99 한도, 2026-07-28 요청)
 *
 *  주의: app/favicon.ico 가 있어 Next 가 아이콘 <link> 를 2개(ico + png) 렌더한다.
 *  기존 링크의 href 만 바꾸면 브라우저가 나머지 ico 링크를 계속 써서 배지가
 *  안 보인다 (2026-07-28 실측) — 기존 아이콘 링크를 떼어내고 전용 배지 링크를
 *  삽입하는 방식만 확실하다. 해제 시 원래 링크를 복원한다.
 *  브라우저 탭 제목은 위장 테마(교환 노트/재고관리.xlsx)와 충돌하므로 불변. */

const BADGE_ID = "favicon-unread-badge";
const ICON_SRC = "/icon-192.png"; // 같은 출처 — 캔버스 오염 없음

let lastCount = 0;
let removedLinks: HTMLLinkElement[] = [];

export function setFaviconBadge(count: number): void {
  if (typeof document === "undefined") return;
  const shown = Math.min(Math.max(count, 0), 99);
  const badge = document.getElementById(BADGE_ID);
  // Next 가 라우팅 중 원래 아이콘 링크를 되살릴 수 있어, 배지가 살아있고
  // 원래 링크가 다시 나타나지 않았을 때만 스킵한다.
  // 주의: rel*="icon" 은 남겨두는 apple-touch-icon 까지 매치해 스킵이 항상
  // 무효가 된다 — 제거 대상과 같은 셀렉터만 검사 (2026-07-28 검증에서 발견)
  const originalsBack = Boolean(
    document.querySelector(
      `link[rel="icon"]:not(#${BADGE_ID}), link[rel="shortcut icon"]`,
    ),
  );
  if (shown === lastCount && (shown === 0 || (badge && !originalsBack))) return;
  lastCount = shown;

  if (shown === 0) {
    badge?.remove();
    for (const link of removedLinks) document.head.appendChild(link);
    removedLinks = [];
    return;
  }

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
    const r = 17;
    const cx = size - r - 1;
    const cy = r + 1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = "#d01012";
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = `bold ${label.length > 1 ? 20 : 26}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, cx, cy + 1);

    // 기존 아이콘 링크 전부 제거(apple-touch 제외) 후 전용 배지 링크 삽입
    for (const link of Array.from(
      document.querySelectorAll<HTMLLinkElement>(
        'link[rel="icon"], link[rel="shortcut icon"]',
      ),
    )) {
      if (link.id !== BADGE_ID) {
        removedLinks.push(link);
        link.remove();
      }
    }
    let el = document.getElementById(BADGE_ID) as HTMLLinkElement | null;
    if (!el) {
      el = document.createElement("link");
      el.id = BADGE_ID;
      el.rel = "icon";
      el.type = "image/png";
      document.head.appendChild(el);
    }
    el.href = canvas.toDataURL("image/png");
  };
  img.src = ICON_SRC;
}

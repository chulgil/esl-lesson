"use client";

/** 파비콘 안읽음 배지 — 탭이 여러 개여도 눈에 띄도록 파비콘을 안읽음 개수로 바꾼다.
 *  (표기는 99 한도, 2026-07-28 요청)
 *
 *  형태: 풀블리드 빨간 라운드 사각형 + 큰 흰 숫자. 탭 파비콘은 16px 로 축소돼
 *  구석 배지는 판독 불가였고, 원형 배지는 뒤로 원본 아이콘 모서리가 삐져나와
 *  깨져 보였다 (2026-07-28 피드백 2건) — 원본 아이콘은 그리지 않는다.
 *
 *  주의: app/favicon.ico 가 있어 Next 가 아이콘 <link> 를 2개(ico + png) 렌더한다.
 *  기존 링크의 href 만 바꾸면 브라우저가 나머지 ico 링크를 계속 써서 배지가
 *  안 보인다 (실측) — 기존 아이콘 링크를 떼어내고 전용 배지 링크를 삽입하는
 *  방식만 확실하다. 해제 시 원래 링크를 복원한다.
 *  브라우저 탭 제목은 위장 테마(교환 노트/재고관리.xlsx)와 충돌하므로 불변. */

const BADGE_ID = "favicon-unread-badge";

let lastCount = 0;
let removedLinks: HTMLLinkElement[] = [];

function drawBadge(shown: number): string | null {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const label = String(shown);
  ctx.beginPath();
  // 모서리 반경 14 → 16px 축소 시 3.5px, 탭 슬롯에 자연스러움
  ctx.roundRect(0, 0, size, size, 14);
  ctx.fillStyle = "#d01012";
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = `bold ${label.length > 1 ? 40 : 48}px system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, size / 2, size / 2 + 3);
  return canvas.toDataURL("image/png");
}

function setTitleBadge(count: number): void {
  // 탭 제목 "(N) " 프리픽스 — OS 알림 권한이 없어도 다른 탭에서 인지 가능.
  // 문서류 제목에도 흔한 표기라 위장 훼손 없음 (2026-07-31 백그라운드 알림 보강)
  const bare = document.title.replace(/^\(\d+\) /, "");
  document.title = count > 0 ? `(${count > 99 ? "99+" : count}) ${bare}` : bare;
}

export function setFaviconBadge(count: number): void {
  setTitleBadge(count);
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

  const dataUrl = drawBadge(shown);
  if (!dataUrl) return;

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
  el.href = dataUrl;
}

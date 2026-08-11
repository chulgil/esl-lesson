/** 게임 결과 공유 이미지 — 캔버스 렌더 + Web Share API (카톡 공유용, P3) */

export interface ShareCardData {
  game: string; // 예: 워드 테트리스
  headline: string; // 예: 승리! / 우승! / 기록 완료!
  scoreline?: string; // 예: 459 : 631 / 최고 320타
  lines: { label: string; value: string }[]; // 부가 스탯 (4개 이하 권장)
  tone?: "win" | "lose" | "neutral";
}

const SIZE = 1080;

function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return v || fallback;
}

function fontVar(name: string): string {
  // next/font 가 body 에 심는 CSS 변수 — 해시된 실제 family 이름
  const v = getComputedStyle(document.body).getPropertyValue(name).trim();
  return v ? `${v}, sans-serif` : "sans-serif";
}

/** 현재 테마 색으로 1080x1080 결과 카드를 그린다 */
export async function drawShareCard(
  data: ShareCardData,
): Promise<HTMLCanvasElement> {
  await document.fonts.ready;
  const paper = cssVar("--color-paper", "#fdfbf3");
  const line = cssVar("--color-paper-line", "#c9e4f5");
  const ink = cssVar("--color-ink", "#2b2b33");
  const green = cssVar("--color-brick-green", "#237841");
  const red = cssVar("--color-brick-red", "#d01012");
  const yellow = cssVar("--color-brick-yellow", "#f5c518");
  const hand = fontVar("--font-gaegu");
  const body = fontVar("--font-body");

  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas unavailable");

  // 노트 배경 — 가로줄 + 빨간 마진선
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, SIZE, SIZE);
  ctx.strokeStyle = line;
  ctx.lineWidth = 3;
  for (let y = 200; y < SIZE; y += 84) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(SIZE, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "#f0b9b9";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(120, 0);
  ctx.lineTo(120, SIZE);
  ctx.stroke();

  // 상단: 서비스명 + 게임명
  ctx.fillStyle = ink;
  ctx.font = `bold 40px ${body}`;
  ctx.fillText("ESL Lessonaza", 160, 120);
  ctx.font = `bold 88px ${hand}`;
  ctx.fillText(data.game, 160, 260);

  // 헤드라인 (형광펜 밑줄 효과)
  const toneColor =
    data.tone === "win" ? green : data.tone === "lose" ? red : ink;
  ctx.font = `bold 120px ${hand}`;
  const headWidth = ctx.measureText(data.headline).width;
  ctx.fillStyle = yellow;
  ctx.globalAlpha = 0.5;
  ctx.fillRect(150, 350, Math.min(headWidth + 40, SIZE - 300), 60);
  ctx.globalAlpha = 1;
  ctx.fillStyle = toneColor;
  ctx.fillText(data.headline, 160, 430);

  // 점수 라인
  if (data.scoreline) {
    ctx.fillStyle = ink;
    ctx.font = `bold 150px ${hand}`;
    ctx.fillText(data.scoreline, 160, 620);
  }

  // 부가 스탯 — 4줄이 하단 URL 영역(SIZE-110)을 침범하지 않게 70px 행간
  ctx.font = `500 44px ${body}`;
  let y = data.scoreline ? 715 : 580;
  for (const item of data.lines.slice(0, 4)) {
    ctx.fillStyle = ink;
    ctx.globalAlpha = 0.55;
    ctx.fillText(item.label, 160, y);
    ctx.globalAlpha = 1;
    ctx.font = `bold 44px ${body}`;
    ctx.fillText(item.value, 500, y);
    ctx.font = `500 44px ${body}`;
    y += 70;
  }

  // 내 마스코트 — 화면 좌하단의 그 캐릭터(악세 포함)를 카드 우하단에도
  // (2026-08-11 요청: 공유에도 내 캐릭터·테마가 함께). 마스코트 미설정이면 생략
  await drawMascot(ctx);

  // 우상단 브릭 장식 (본문/스탯과 겹치지 않는 유일한 여백) + 하단 URL
  drawBrick(ctx, SIZE - 330, 100, green, ink);
  ctx.fillStyle = ink;
  ctx.font = `bold 46px ${body}`;
  ctx.fillText("esl.lessonaza.app", 160, SIZE - 100);
  ctx.globalAlpha = 0.6;
  ctx.font = `400 36px ${body}`;
  ctx.fillText("유튜브로 배우고, 잊기 전에 다시 만나는 영어", 160, SIZE - 44);
  ctx.globalAlpha = 1;
  return canvas;
}

/** 좌하단에 떠 있는 활성 마스코트(악세 착용 상태)를 카드에 복사 — DOM svg 캡처.
 *  폰트·애니메이션 클래스는 데이터 URL 에서 빠지므로 정지 포즈·기본체로 그려진다. */
async function drawMascot(ctx: CanvasRenderingContext2D): Promise<void> {
  const svg = document.querySelector<SVGSVGElement>(".henyang-peek svg");
  if (!svg) return; // 마스코트 미설정 — 카드 구성은 그대로
  let markup = svg.outerHTML;
  if (!markup.includes("xmlns=")) {
    markup = markup.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
  }
  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("mascot render failed"));
      img.src = `data:image/svg+xml;utf8,${encodeURIComponent(markup)}`;
    });
    ctx.drawImage(img, 620, 590, 104 * 3.2, 88 * 3.2);
  } catch {
    // 마스코트 렌더 실패는 카드 생성을 막지 않는다
  }
}

function drawBrick(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  fill: string,
  stroke: string,
) {
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 6;
  const w = 200;
  const h = 100;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, 16);
  ctx.fill();
  ctx.stroke();
  for (const cx of [x + 52, x + 148]) {
    ctx.beginPath();
    ctx.roundRect(cx - 28, y - 22, 56, 30, 8);
    ctx.fill();
    ctx.stroke();
  }
}

/** 공유(모바일) 또는 다운로드(데스크톱 폴백). 사용자가 취소하면 "canceled". */
export async function shareResultImage(
  data: ShareCardData,
): Promise<"shared" | "downloaded" | "canceled"> {
  const canvas = await drawShareCard(data);
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/png"),
  );
  if (!blob) throw new Error("image encoding failed");

  const file = new File([blob], "esl-result.png", { type: "image/png" });
  if (
    typeof navigator.canShare === "function" &&
    navigator.canShare({ files: [file] })
  ) {
    try {
      await navigator.share({
        files: [file],
        title: "ESL Lessonaza",
        text: `${data.game} ${data.headline} — esl.lessonaza.app`,
      });
      return "shared";
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return "canceled";
      }
      // 공유 시트 실패 — 다운로드 폴백으로 이어감
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "esl-result.png";
  a.click();
  URL.revokeObjectURL(url);
  return "downloaded";
}

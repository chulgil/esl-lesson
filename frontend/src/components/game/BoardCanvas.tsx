"use client";

import { useEffect, useRef } from "react";
import type { BoardState } from "@/lib/game-ws";

const ROWS = 12;

/** 보드 배경 테마 — 전역 앱 테마(설정 > 테마)를 따른다 */
export type BoardTheme = "candy" | "note" | "lego";

const THEME_BORDER: Record<BoardTheme, string> = {
  candy: "border-[#F0C4E0]",
  note: "border-[#E8D9A8]",
  lego: "border-[#BFD4F2]",
};

// 캔디 팔레트 — 밝은 파스텔 + 글로시 하이라이트 (Candy Crush 계열 비주얼 언어)
const CANDY_COLORS = ["#FF9EB8", "#FFB85C", "#7CC7F2", "#92DBA8", "#C9A0E8"];
const CANDY_TEXT = "#4A2545";
const GARBAGE_COLOR = "#B9BAC9"; // 회색 젤리 (상대 공격)
const GARBAGE_TEXT = "#54545E";
const ITEM_COLOR = "#FFD34E"; // 별사탕

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
  r: number;
}

interface Ring {
  x: number;
  y: number;
  life: number;
  color: string;
}

interface Popup {
  text: string;
  life: number;
  big: boolean;
}

// 앱의 손글씨 폰트(--font-hand, Gaegu)를 캔버스에서 재사용 — 1회 해석
let handFont = "sans-serif";

/** 캔디 스타일 보드 렌더러 — 60fps rAF, 서버 상태(10Hz)를 보간 */
export function BoardCanvas({
  state,
  width,
  height,
  mirror = false,
  theme = "candy",
}: {
  state: BoardState | null;
  width: number;
  height: number;
  mirror?: boolean;
  theme?: BoardTheme;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<BoardState | null>(null);
  const smoothY = useRef<Map<number, number>>(new Map());
  const particles = useRef<Particle[]>([]);
  const rings = useRef<Ring[]>([]);
  const popups = useRef<Popup[]>([]);
  const shakeUntil = useRef(0);
  const prevBrickIds = useRef<Set<number>>(new Set());
  const themeRef = useRef<BoardTheme>(theme);
  themeRef.current = theme;

  useEffect(() => {
    const fam = getComputedStyle(document.documentElement)
      .getPropertyValue("--font-hand")
      .trim();
    if (fam) handFont = fam;
  }, []);

  // 상태 갱신 감지: 사라진 브릭 = 클리어 → 버블 팝, 콤보 증가 → 팝업
  useEffect(() => {
    const prev = stateRef.current;
    stateRef.current = state;
    if (!state) return;

    const currentIds = new Set(state.bricks.map((b) => b.id));
    if (prev) {
      for (const brick of prev.bricks) {
        if (!currentIds.has(brick.id) && !brick.garbage) {
          spawnPop(
            particles.current,
            rings.current,
            width / 2,
            rowToY(brick.y, height),
            pickColor(brick.id),
          );
        }
      }
      if (state.combo >= 3 && state.combo > prev.combo) {
        popups.current.push({
          text: `COMBO x${state.combo}`,
          life: 1,
          big: state.combo >= 6,
        });
      }
      if (state.speed_level > prev.speed_level) {
        popups.current.push({ text: "SPEED UP!", life: 1, big: true });
      }
      // 구간 전환 배너 (스펙: 방향 배너) — 입력 방식이 바뀌는 순간을 크게 알림
      if (
        state.direction !== prev.direction ||
        state.input_mode !== prev.input_mode
      ) {
        const banner =
          state.input_mode === "type"
            ? "한글→영어 타이핑!"
            : state.direction === "en2ko"
              ? "영어→한글 뜻 탭!"
              : "한글→영어 단어 탭!";
        popups.current.push({ text: banner, life: 1.4, big: true });
      }
      const prevGarbage = prev.bricks.filter((b) => b.garbage).length;
      const nowGarbage = state.bricks.filter((b) => b.garbage).length;
      if (nowGarbage > prevGarbage) {
        shakeUntil.current = performance.now() + 300;
      }
    }
    prevBrickIds.current = currentIds;
  }, [state, width, height]);

  useEffect(() => {
    let raf = 0;
    const render = () => {
      raf = requestAnimationFrame(render);
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;
      draw(
        ctx,
        canvas,
        stateRef.current,
        smoothY.current,
        particles.current,
        rings.current,
        popups.current,
        shakeUntil.current,
        mirror,
        themeRef.current,
      );
    };
    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, [mirror]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ maxWidth: "100%", height: "auto" }}
      className={`rounded-2xl border-2 ${THEME_BORDER[theme]}`}
    />
  );
}

function rowToY(row: number, height: number): number {
  return (row / ROWS) * height;
}

function pickColor(id: number): string {
  return CANDY_COLORS[id % CANDY_COLORS.length];
}

/** 버블 팝 — 확장 링 + 방사형 방울 파티클 (juice 레이어링) */
function spawnPop(
  particles: Particle[],
  rings: Ring[],
  x: number,
  y: number,
  color: string,
): void {
  rings.push({ x, y, life: 1, color });
  for (let i = 0; i < 10; i++) {
    const angle = (Math.PI * 2 * i) / 10 + Math.random() * 0.5;
    const speed = 90 + Math.random() * 140;
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 60,
      life: 1,
      color: i % 3 === 0 ? "rgba(255,255,255,0.9)" : color,
      r: 2 + Math.random() * 2.5,
    });
  }
}

/** 폰트를 먼저 확정하고 측정 — 텍스트가 브릭 박스를 벗어나지 않게 축소 맞춤 */
function fitFontSize(
  ctx: CanvasRenderingContext2D,
  label: string,
  maxTextWidth: number,
  base: number,
): number {
  let size = base;
  while (size > 9) {
    ctx.font = `bold ${size}px ${handFont}`;
    if (ctx.measureText(label).width <= maxTextWidth) break;
    size -= 1;
  }
  return size;
}

function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  theme: BoardTheme,
): void {
  if (theme === "note") {
    // 크림 종이 + 괘선 + 빨간 마진선 (노트 은유)
    ctx.fillStyle = "#FFFDF2";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(125,168,208,0.3)";
    ctx.lineWidth = 1;
    for (let r = 1; r < ROWS; r++) {
      const y = rowToY(r, height);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(255,120,135,0.4)";
    ctx.beginPath();
    ctx.moveTo(16, 0);
    ctx.lineTo(16, height);
    ctx.stroke();
    return;
  }
  if (theme === "lego") {
    // 밝은 베이스플레이트 + 스터드 도트 격자
    ctx.fillStyle = "#EEF6FF";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "rgba(120,160,220,0.14)";
    const gap = 28;
    for (let gy = gap / 2; gy < height; gy += gap) {
      for (let gx = gap / 2; gx < width; gx += gap) {
        ctx.beginPath();
        ctx.arc(gx, gy, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    return;
  }
  // candy: 파스텔 그라데이션 + 은은한 버블
  const g = ctx.createLinearGradient(0, 0, 0, height);
  g.addColorStop(0, "#FFF4FA");
  g.addColorStop(1, "#E9F3FF");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "rgba(255,255,255,0.4)";
  const bubbles = [
    [0.15, 0.2, 14],
    [0.85, 0.12, 9],
    [0.75, 0.45, 18],
    [0.2, 0.7, 11],
    [0.9, 0.82, 13],
    [0.4, 0.92, 8],
  ] as const;
  for (const [bx, by, r] of bubbles) {
    ctx.beginPath();
    ctx.arc(bx * width, by * height, r, 0, Math.PI * 2);
    ctx.fill();
  }
}

function draw(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  state: BoardState | null,
  smoothY: Map<number, number>,
  particles: Particle[],
  rings: Ring[],
  popups: Popup[],
  shakeUntil: number,
  mirror: boolean,
  theme: BoardTheme,
): void {
  const { width, height } = canvas;
  ctx.save();
  ctx.clearRect(0, 0, width, height);
  drawBackground(ctx, width, height, theme);

  // 공격 수신 흔들림
  if (performance.now() < shakeUntil) {
    ctx.translate((Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8);
  }

  if (state) {
    // 콤보 글로우 — 콤보가 높을수록 가장자리가 밝게 (6+ 골드, 3+ 핑크)
    if (state.combo >= 3 && !state.ko) {
      const intensity = Math.min(1, (state.combo - 2) / 8);
      const glow = ctx.createRadialGradient(
        width / 2,
        height / 2,
        Math.min(width, height) * 0.3,
        width / 2,
        height / 2,
        Math.max(width, height) * 0.7,
      );
      const color = state.combo >= 6 ? "255,179,0" : "255,111,165";
      glow.addColorStop(0, "rgba(0,0,0,0)");
      glow.addColorStop(1, `rgba(${color},${0.25 * intensity})`);
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);
    }

    // 공격 수신 경고 — 흔들림 중 상단/하단 띠 점멸
    if (performance.now() < shakeUntil) {
      const flash = 0.4 + 0.3 * Math.sin(performance.now() / 60);
      ctx.fillStyle = `rgba(255,95,125,${flash})`;
      ctx.fillRect(0, 0, width, 6);
      ctx.fillRect(0, height - 6, width, 6);
    }

    // 위험 상태 펄스 (핑크레드 — 파스텔 배경 위에서도 경고로 읽히게)
    if (state.danger && !state.ko) {
      const pulse = 0.14 + 0.1 * Math.sin(performance.now() / 200);
      ctx.fillStyle = `rgba(255,95,125,${pulse})`;
      ctx.fillRect(0, 0, width, height);
    }

    const rowHeight = height / ROWS;
    const brickHeight = rowHeight * 0.86;
    const baseFont = Math.max(10, Math.min(18, width / 14));

    for (const brick of state.bricks) {
      // 보간: 서버 y 로 부드럽게 수렴
      const target = brick.y;
      const current = smoothY.get(brick.id) ?? target;
      const next = brick.landed ? target : current + (target - current) * 0.25;
      smoothY.set(brick.id, next);

      const y = rowToY(next, height) - brickHeight;
      // 회색 젤리(garbage)는 ×_× 얼굴, ★ 브릭도 문제 텍스트 표시
      const label = brick.garbage
        ? "×_×"
        : brick.item
          ? `★ ${brick.display}`
          : brick.display;
      const maxBrickWidth = width - 8;
      // 폰트를 먼저 확정(ctx.font 설정)한 뒤 측정 — 텍스트가 박스를 벗어나지 않음
      fitFontSize(ctx, label, maxBrickWidth - 26, baseFont);
      const textWidth = ctx.measureText(label).width;
      const brickWidth = Math.min(maxBrickWidth, Math.max(56, textWidth + 26));
      const x = (width - brickWidth) / 2;
      const radius = Math.min(brickHeight / 2, 14);
      const bodyColor = brick.garbage
        ? GARBAGE_COLOR
        : brick.item
          ? ITEM_COLOR
          : pickColor(brick.id);

      // 캔디 몸통 (아이템은 금색 글로우)
      if (brick.item) {
        ctx.save();
        ctx.shadowColor = ITEM_COLOR;
        ctx.shadowBlur = 12 + 6 * Math.sin(performance.now() / 150);
      }
      ctx.fillStyle = bodyColor;
      roundRect(ctx, x, y, brickWidth, brickHeight, radius);
      ctx.fill();
      if (brick.item) {
        ctx.restore();
      }

      // 젤리 두께감 — 아랫면 그림자
      ctx.fillStyle = "rgba(0,0,0,0.10)";
      roundRect(
        ctx,
        x,
        y + brickHeight * 0.55,
        brickWidth,
        brickHeight * 0.45,
        radius,
      );
      ctx.fill();

      // 캔디 광택 — 왼쪽 위 글로시 하이라이트
      ctx.fillStyle = "rgba(255,255,255,0.55)";
      ctx.beginPath();
      ctx.ellipse(
        x + Math.min(brickWidth * 0.25, 30),
        y + brickHeight * 0.3,
        Math.min(brickWidth * 0.18, 24),
        brickHeight * 0.16,
        -0.25,
        0,
        Math.PI * 2,
      );
      ctx.fill();

      // 텍스트 (폰트는 fitFontSize 에서 확정됨)
      ctx.fillStyle = brick.garbage ? GARBAGE_TEXT : CANDY_TEXT;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, x + brickWidth / 2, y + brickHeight / 2 + 1);
    }

    // 정리: 사라진 브릭의 보간 상태 제거
    const alive = new Set(state.bricks.map((b) => b.id));
    for (const id of smoothY.keys()) {
      if (!alive.has(id)) smoothY.delete(id);
    }

    // 시간 정지(freeze) 아이템: 얼음 톤 오버레이
    if (state.frozen) {
      ctx.fillStyle = "rgba(140,200,255,0.22)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#3E8FD8";
      ctx.font = `bold ${Math.min(20, width / 12)}px ${handFont}`;
      ctx.textAlign = "center";
      ctx.fillText("❄ FREEZE", width / 2, 22);
    }

    // KO 오버레이
    if (state.ko) {
      ctx.fillStyle = "rgba(74,37,69,0.55)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#FF6FA5";
      ctx.font = `bold ${Math.min(48, width / 5)}px ${handFont}`;
      ctx.textAlign = "center";
      ctx.fillText("K.O.", width / 2, height / 2);
    }
  }

  // 버블 팝 확장 링
  for (let i = rings.length - 1; i >= 0; i--) {
    const ring = rings[i];
    ring.life -= 0.05;
    if (ring.life <= 0) {
      rings.splice(i, 1);
      continue;
    }
    const r = 6 + (1 - ring.life) * 30;
    ctx.globalAlpha = ring.life;
    ctx.strokeStyle = ring.color;
    ctx.lineWidth = 1 + 3 * ring.life;
    ctx.beginPath();
    ctx.arc(ring.x, ring.y, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  // 방울 파티클 (원형 — 물방울)
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.life -= 0.03;
    if (p.life <= 0) {
      particles.splice(i, 1);
      continue;
    }
    p.x += p.vx / 60;
    p.y += p.vy / 60;
    p.vy += 5;
    ctx.globalAlpha = p.life;
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, Math.max(0.5, p.r * p.life), 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // 팝업 (COMBO / SPEED UP / 구간 배너) — 흰 외곽선 + 캔디 컬러
  if (!mirror) {
    for (let i = popups.length - 1; i >= 0; i--) {
      const popup = popups[i];
      popup.life -= 0.015;
      if (popup.life <= 0) {
        popups.splice(i, 1);
        continue;
      }
      const scale = 1 + (1 - popup.life) * 0.6;
      ctx.globalAlpha = Math.min(1, popup.life * 2);
      ctx.font = `bold ${(popup.big ? 30 : 22) * scale}px ${handFont}`;
      ctx.textAlign = "center";
      ctx.lineWidth = 5;
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.strokeText(popup.text, width / 2, height * 0.32);
      ctx.fillStyle = popup.big ? "#FFB300" : "#FF6FA5";
      ctx.fillText(popup.text, width / 2, height * 0.32);
      ctx.globalAlpha = 1;
    }
  }

  ctx.restore();
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

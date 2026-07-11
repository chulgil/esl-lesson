"use client";

import { useEffect, useRef } from "react";
import type { BoardState } from "@/lib/game-ws";

const ROWS = 12;

const BRICK_COLORS = ["#D01012", "#F5C518", "#0D69AB", "#237841"];
const GARBAGE_COLOR = "#6b6b74";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
}

interface Popup {
  text: string;
  life: number;
  big: boolean;
}

export interface BoardEffects {
  clearAt?: { brickId: number };
  popup?: { text: string; big?: boolean };
  shake?: boolean;
}

/** 레고 브릭 스타일 보드 렌더러 — 60fps rAF, 서버 상태(10Hz)를 보간 */
export function BoardCanvas({
  state,
  width,
  height,
  mirror = false,
}: {
  state: BoardState | null;
  width: number;
  height: number;
  mirror?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<BoardState | null>(null);
  const smoothY = useRef<Map<number, number>>(new Map());
  const particles = useRef<Particle[]>([]);
  const popups = useRef<Popup[]>([]);
  const shakeUntil = useRef(0);
  const prevBrickIds = useRef<Set<number>>(new Set());

  // 상태 갱신 감지: 사라진 브릭 = 클리어 → 파티클, 콤보 증가 → 팝업
  useEffect(() => {
    const prev = stateRef.current;
    stateRef.current = state;
    if (!state) return;

    const currentIds = new Set(state.bricks.map((b) => b.id));
    if (prev) {
      for (const brick of prev.bricks) {
        if (!currentIds.has(brick.id) && !brick.garbage) {
          spawnParticles(
            particles.current,
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
        popups.current,
        shakeUntil.current,
        mirror,
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
      className="rounded-lg border-2 border-ink/20 bg-[#1a1a22]"
    />
  );
}

function rowToY(row: number, height: number): number {
  return (row / ROWS) * height;
}

function pickColor(id: number): string {
  return BRICK_COLORS[id % BRICK_COLORS.length];
}

function spawnParticles(
  list: Particle[],
  x: number,
  y: number,
  color: string,
): void {
  for (let i = 0; i < 8; i++) {
    list.push({
      x,
      y,
      vx: (Math.random() - 0.5) * 240,
      vy: -Math.random() * 180 - 40,
      life: 1,
      color,
    });
  }
}

function draw(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  state: BoardState | null,
  smoothY: Map<number, number>,
  particles: Particle[],
  popups: Popup[],
  shakeUntil: number,
  mirror: boolean,
): void {
  const { width, height } = canvas;
  ctx.save();
  ctx.clearRect(0, 0, width, height);

  // 공격 수신 흔들림
  if (performance.now() < shakeUntil) {
    ctx.translate((Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8);
  }

  // 배경 괘선 (노트 은유의 다크 버전)
  ctx.strokeStyle = "rgba(201,228,245,0.08)";
  ctx.lineWidth = 1;
  for (let r = 1; r < ROWS; r++) {
    const y = rowToY(r, height);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  if (state) {
    // 콤보 글로우 — 콤보가 높을수록 화면 가장자리가 밝게 (즐기는 맛)
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
      const color = state.combo >= 6 ? "245,197,24" : "13,105,171";
      glow.addColorStop(0, "rgba(0,0,0,0)");
      glow.addColorStop(1, `rgba(${color},${0.25 * intensity})`);
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);
    }

    // 공격 수신 경고 — 흔들림 중 상단 붉은 띠 점멸
    if (performance.now() < shakeUntil) {
      const flash = 0.4 + 0.3 * Math.sin(performance.now() / 60);
      ctx.fillStyle = `rgba(208,16,18,${flash})`;
      ctx.fillRect(0, 0, width, 6);
      ctx.fillRect(0, height - 6, width, 6);
    }

    // 위험 상태 붉은 펄스
    if (state.danger && !state.ko) {
      const pulse = 0.18 + 0.12 * Math.sin(performance.now() / 200);
      ctx.fillStyle = `rgba(208,16,18,${pulse})`;
      ctx.fillRect(0, 0, width, height);
    }

    const rowHeight = height / ROWS;
    const brickHeight = rowHeight * 0.86;
    const fontSize = Math.max(10, Math.min(16, width / 14));

    for (const brick of state.bricks) {
      // 보간: 서버 y 로 부드럽게 수렴
      const target = brick.y;
      const current = smoothY.get(brick.id) ?? target;
      const next = brick.landed ? target : current + (target - current) * 0.25;
      smoothY.set(brick.id, next);

      const y = rowToY(next, height) - brickHeight;
      const label = brick.garbage ? "###" : brick.display;
      const textWidth = ctx.measureText(label).width;
      const brickWidth = Math.min(width - 8, Math.max(52, textWidth + 26));
      const x = (width - brickWidth) / 2;

      // 아이템(★) 브릭: 금색 + 반짝임 글로우
      if (brick.item) {
        ctx.save();
        ctx.shadowColor = "#F5C518";
        ctx.shadowBlur = 12 + 6 * Math.sin(performance.now() / 150);
        ctx.fillStyle = "#F5C518";
        roundRect(ctx, x, y, brickWidth, brickHeight, 5);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#2B2B33";
        ctx.font = `bold ${fontSize + 4}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("★", x + brickWidth / 2, y + brickHeight / 2 + 2);
        continue;
      }

      ctx.fillStyle = brick.garbage ? GARBAGE_COLOR : pickColor(brick.id);
      roundRect(ctx, x, y, brickWidth, brickHeight, 5);
      ctx.fill();
      // 레고 스터드
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      const studCount = Math.max(2, Math.floor(brickWidth / 26));
      for (let i = 0; i < studCount; i++) {
        ctx.beginPath();
        ctx.arc(
          x + ((i + 0.5) * brickWidth) / studCount,
          y + 4,
          2.6,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
      ctx.fillStyle = "#fff";
      ctx.font = `bold ${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, x + brickWidth / 2, y + brickHeight / 2 + 2);
    }

    // 시간 정지(freeze) 아이템: 얼음 톤 오버레이
    if (state.frozen) {
      ctx.fillStyle = "rgba(120,190,255,0.18)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "rgba(180,220,255,0.9)";
      ctx.font = `bold ${Math.min(20, width / 12)}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText("FROZEN", width / 2, 20);
    }

    // 정리: 사라진 브릭의 보간 상태 제거
    const alive = new Set(state.bricks.map((b) => b.id));
    for (const id of smoothY.keys()) {
      if (!alive.has(id)) smoothY.delete(id);
    }

    // KO 오버레이
    if (state.ko) {
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#D01012";
      ctx.font = `bold ${Math.min(48, width / 5)}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText("K.O.", width / 2, height / 2);
    }
  }

  // 파티클
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.life -= 0.03;
    if (p.life <= 0) {
      particles.splice(i, 1);
      continue;
    }
    p.x += p.vx / 60;
    p.y += p.vy / 60;
    p.vy += 6;
    ctx.globalAlpha = p.life;
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x - 3, p.y - 3, 6, 6);
    ctx.globalAlpha = 1;
  }

  // 팝업 (COMBO / SPEED UP)
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
      ctx.fillStyle = popup.big ? "#F5C518" : "#fff";
      ctx.font = `bold ${(popup.big ? 30 : 22) * scale}px Inter, sans-serif`;
      ctx.textAlign = "center";
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

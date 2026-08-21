"use client";

import { useEffect, useRef } from "react";

/** 그래프 노드 — 내 카드(mine) 또는 덱 밖 추천(ghost) */
export interface GraphNode {
  id: number;
  en: string;
  ko: string;
  state: string; // new | learning | review | relearning | ghost
  kind: "mine" | "ghost";
  /** FSRS stability(일) — 기억 강도 색 램프 재료. ghost/구 응답은 null */
  stability?: number | null;
}

export interface GraphEdge {
  source: number;
  target: number;
  distance: number;
  ghost?: boolean;
}

interface Sim {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const REPULSION = 2600;
const SPRING = 0.04;
const GRAVITY = 0.012;
const DAMPING = 0.85;
const NODE_RADIUS = 14;

/** id 기반 결정적 지터 — 새로고침해도 같은 초기 배치 */
function jitter(id: number, salt: number): number {
  const v = Math.sin(id * 127.1 + salt * 311.7) * 43758.5453;
  return v - Math.floor(v);
}

/** 기억 강도 색 램프 (2026-08-21 인지 색 재설계) — 모를수록 뜨겁게(빨강),
 *  장기 기억일수록 회색으로 물러난다. 주의 자원은 아직 모르는 것에 가야
 *  하고(경고색의 선주의적 포착), 끝난 처리는 배경으로(figure-ground).
 *  순서 데이터라 색상환이 아닌 채도·명도 램프 — 테마와 무관한 고정색
 *  (데이터 시각화 색은 테마 따라 흔들리면 판독 학습이 무효가 된다). */
export const MEMORY_TIERS = [
  { key: "unknown", label: "모름 (새 단어)", color: "#d0342c" },
  { key: "shaky", label: "흔들림 (틀린 기억)", color: "#e06a2b" },
  { key: "learning", label: "익히는 중", color: "#eaa13c" },
  { key: "settling", label: "자리 잡는 중", color: "#8fac74" },
  { key: "longterm", label: "장기 기억", color: "#a8adb4" },
] as const;

/** 백엔드 LONG_TERM_STABILITY_DAYS(7.0) 미러 — stats 장기 기억 판정과 동일 */
const LONG_TERM_DAYS = 7;

function memoryColor(node: {
  state: string;
  stability?: number | null;
}): string {
  const tier =
    node.state === "new"
      ? "unknown"
      : node.state === "relearning"
        ? "shaky"
        : node.state === "learning"
          ? "learning"
          : (node.stability ?? 0) >= LONG_TERM_DAYS
            ? "longterm"
            : "settling"; // review, 아직 7일 미만
  return MEMORY_TIERS.find((t) => t.key === tier)!.color;
}

/** 자체 force-directed 캔버스 그래프 — 외부 의존성 없음 (게임 캔버스와 동일 접근) */
export function VocabGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const simRef = useRef<Map<number, Sim>>(new Map());
  const viewRef = useRef({ x: 0, y: 0, scale: 1 });
  const alphaRef = useRef(1);
  const rafRef = useRef(0);
  const selectedRef = useRef<number | null>(selectedId);
  const dataRef = useRef({ nodes, edges });
  const fittedRef = useRef(false);

  selectedRef.current = selectedId;
  dataRef.current = { nodes, edges };

  // 노드 증감 시 시뮬레이션 좌표를 이어받고 새 노드만 원 위에 배치
  useEffect(() => {
    const sim = simRef.current;
    if (sim.size === 0 && nodes.length > 0) fittedRef.current = false;
    const spread = Math.max(160, nodes.length * 14);
    nodes.forEach((n, i) => {
      if (!sim.has(n.id)) {
        const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
        const r = spread * (0.4 + jitter(n.id, 1) * 0.6);
        sim.set(n.id, {
          x: Math.cos(angle) * r + (jitter(n.id, 2) - 0.5) * 40,
          y: Math.sin(angle) * r + (jitter(n.id, 3) - 0.5) * 40,
          vx: 0,
          vy: 0,
        });
      }
    });
    const alive = new Set(nodes.map((n) => n.id));
    [...sim.keys()].forEach((id) => !alive.has(id) && sim.delete(id));
    alphaRef.current = 1; // 데이터 변화 → 재가열
  }, [nodes, edges]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const css = (name: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(name).trim();

    function resize() {
      if (!canvas) return;
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    }
    resize();
    const observer = new ResizeObserver(resize);
    if (canvas.parentElement) observer.observe(canvas.parentElement);

    function tick() {
      const { nodes: ns, edges: es } = dataRef.current;
      const sim = simRef.current;
      const alpha = alphaRef.current;
      if (alpha > 0.02) {
        // 반발력 O(N²) — 노드 상한 300+12 에서 충분히 빠름
        const list = ns
          .map((n) => ({ n, s: sim.get(n.id) }))
          .filter((p): p is { n: GraphNode; s: Sim } => !!p.s);
        for (let i = 0; i < list.length; i++) {
          for (let j = i + 1; j < list.length; j++) {
            const a = list[i].s;
            const b = list[j].s;
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const d2 = Math.max(64, dx * dx + dy * dy);
            const f = (REPULSION * alpha) / d2;
            const d = Math.sqrt(d2);
            const fx = (dx / d) * f;
            const fy = (dy / d) * f;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          }
        }
        // 스프링 — 임베딩 거리가 가까울수록 짧은 관계선
        es.forEach((e) => {
          const a = sim.get(e.source);
          const b = sim.get(e.target);
          if (!a || !b) return;
          const rest = 55 + e.distance * 160;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const f = SPRING * alpha * (d - rest);
          a.vx += (dx / d) * f;
          a.vy += (dy / d) * f;
          b.vx -= (dx / d) * f;
          b.vy -= (dy / d) * f;
        });
        list.forEach(({ s }) => {
          s.vx -= s.x * GRAVITY * alpha;
          s.vy -= s.y * GRAVITY * alpha;
          s.vx *= DAMPING;
          s.vy *= DAMPING;
          s.x += s.vx;
          s.y += s.vy;
        });
        alphaRef.current = alpha * 0.985;
        // 레이아웃이 대강 안정되면 한 번만 화면에 맞춰 핏
        if (!fittedRef.current && alphaRef.current < 0.4 && list.length > 0) {
          fittedRef.current = true;
          const xs = list.map(({ s }) => s.x);
          const ys = list.map(({ s }) => s.y);
          const minX = Math.min(...xs) - 50;
          const maxX = Math.max(...xs) + 50;
          const minY = Math.min(...ys) - 50;
          const maxY = Math.max(...ys) + 60; // 라벨 여백
          const dpr = window.devicePixelRatio || 1;
          const w = canvas!.width / dpr;
          const h = canvas!.height / dpr;
          const scale = Math.min(
            1.4,
            Math.max(0.3, Math.min(w / (maxX - minX), h / (maxY - minY))),
          );
          const view = viewRef.current;
          view.scale = scale;
          view.x = (-(minX + maxX) / 2) * scale;
          view.y = (-(minY + maxY) / 2) * scale;
        }
      }
      draw();
      rafRef.current = requestAnimationFrame(tick);
    }

    function draw() {
      if (!canvas || !ctx) return;
      const { nodes: ns, edges: es } = dataRef.current;
      const sim = simRef.current;
      const view = viewRef.current;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.translate(w / 2 + view.x, h / 2 + view.y);
      ctx.scale(view.scale, view.scale);

      const ink = css("--color-ink");
      const selected = selectedRef.current;
      const neighborIds = new Set<number>();
      if (selected != null) {
        es.forEach((e) => {
          if (e.source === selected) neighborIds.add(e.target);
          if (e.target === selected) neighborIds.add(e.source);
        });
      }

      es.forEach((e) => {
        const a = sim.get(e.source);
        const b = sim.get(e.target);
        if (!a || !b) return;
        const active =
          selected == null || e.source === selected || e.target === selected;
        ctx.globalAlpha = active ? 0.5 : 0.12;
        ctx.strokeStyle = ink;
        ctx.lineWidth = e.ghost ? 1 : 1.5;
        ctx.setLineDash(e.ghost ? [4, 4] : []);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      ns.forEach((n) => {
        const s = sim.get(n.id);
        if (!s) return;
        const isSelected = n.id === selected;
        const dimmed =
          selected != null && !isSelected && !neighborIds.has(n.id);
        ctx.globalAlpha = dimmed ? 0.25 : 1;

        ctx.beginPath();
        ctx.arc(s.x, s.y, NODE_RADIUS, 0, Math.PI * 2);
        // 추천(ghost)은 내 기억 축 밖 — 종이색 + 점선 유령 유지
        ctx.fillStyle =
          n.kind === "ghost" ? css("--color-paper") : memoryColor(n);
        ctx.fill();
        if (n.kind === "ghost") {
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = ink;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.setLineDash([]);
        }
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, NODE_RADIUS + 5, 0, Math.PI * 2);
          ctx.strokeStyle = css("--color-highlight");
          ctx.lineWidth = 4;
          ctx.stroke();
        }

        if (viewRef.current.scale >= 0.55 || isSelected) {
          ctx.fillStyle = ink;
          // 버그 픽스 (2026-08-21): canvas font 는 var() 를 해석하지 않아
          // 기본 폰트로 조용히 폴백되고 있었다 — css() 로 실값을 풀어 넣는다
          ctx.font = `bold 11px ${css("--font-hand") || "sans-serif"}`;
          ctx.textAlign = "center";
          ctx.fillText(n.en, s.x, s.y + NODE_RADIUS + 13);
        }
      });
      ctx.globalAlpha = 1;
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(rafRef.current);
      observer.disconnect();
    };
  }, []);

  // 포인터 — 탭=선택, 드래그=팬, 휠/핀치=줌
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const pointers = new Map<number, { x: number; y: number }>();
    const drag = { active: false, moved: false, lastX: 0, lastY: 0, dist: 0 };

    function toWorld(clientX: number, clientY: number) {
      const rect = canvas!.getBoundingClientRect();
      const view = viewRef.current;
      return {
        x: (clientX - rect.left - rect.width / 2 - view.x) / view.scale,
        y: (clientY - rect.top - rect.height / 2 - view.y) / view.scale,
      };
    }

    function onDown(e: PointerEvent) {
      canvas!.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      drag.active = true;
      drag.moved = false;
      drag.lastX = e.clientX;
      drag.lastY = e.clientY;
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        drag.dist = Math.hypot(a.x - b.x, a.y - b.y);
      }
    }

    function onMove(e: PointerEvent) {
      if (!pointers.has(e.pointerId)) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 2) {
        // 핀치 줌
        const [a, b] = [...pointers.values()];
        const dist = Math.hypot(a.x - b.x, a.y - b.y);
        if (drag.dist > 0) {
          const view = viewRef.current;
          view.scale = Math.min(
            3,
            Math.max(0.3, view.scale * (dist / drag.dist)),
          );
        }
        drag.dist = dist;
        drag.moved = true;
        return;
      }
      if (!drag.active) return;
      const dx = e.clientX - drag.lastX;
      const dy = e.clientY - drag.lastY;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      viewRef.current.x += dx;
      viewRef.current.y += dy;
      drag.lastX = e.clientX;
      drag.lastY = e.clientY;
    }

    function onUp(e: PointerEvent) {
      pointers.delete(e.pointerId);
      if (!drag.moved) {
        const { x, y } = toWorld(e.clientX, e.clientY);
        const sim = simRef.current;
        const hitRange = Math.max(NODE_RADIUS + 6, 18 / viewRef.current.scale);
        const hit = dataRef.current.nodes
          .map((n) => {
            const s = sim.get(n.id);
            return s ? { id: n.id, d: Math.hypot(s.x - x, s.y - y) } : null;
          })
          .filter((v): v is { id: number; d: number } => !!v && v.d <= hitRange)
          .sort((a, b) => a.d - b.d)[0];
        onSelect(hit ? hit.id : null);
      }
      if (pointers.size === 0) drag.active = false;
    }

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const view = viewRef.current;
      view.scale = Math.min(
        3,
        Math.max(0.3, view.scale * (e.deltaY < 0 ? 1.1 : 0.9)),
      );
    }

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
  }, [onSelect]);

  function zoom(factor: number) {
    const view = viewRef.current;
    view.scale = Math.min(3, Math.max(0.3, view.scale * factor));
  }

  return (
    <div className="absolute inset-0 touch-none select-none">
      <canvas
        ref={canvasRef}
        className="block cursor-grab"
        aria-label="어휘망 그래프"
      />
      <div className="absolute right-3 top-3 flex flex-col gap-1.5">
        <button
          type="button"
          aria-label="확대"
          onClick={() => zoom(1.25)}
          className="flex h-11 w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white text-lg font-bold shadow-sm transition-colors hover:border-brick-blue"
        >
          +
        </button>
        <button
          type="button"
          aria-label="축소"
          onClick={() => zoom(0.8)}
          className="flex h-11 w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white text-lg font-bold shadow-sm transition-colors hover:border-brick-blue"
        >
          −
        </button>
      </div>
    </div>
  );
}

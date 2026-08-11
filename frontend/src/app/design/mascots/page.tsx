"use client";

import {
  MASCOT_LABELS,
  MascotSvg,
  OUTFIT_LABELS,
} from "@/components/theme/mascots";

/** 마스코트 QA 픽스처 — 캐릭터 x 악세 조합을 한 화면에서 시각 검증.
 *  사용자 노출 동선 없음(네비 미등록) — 새 마스코트/악세 추가 시 이 화면으로
 *  애니메이션·앵커 좌표가 어색하지 않은지 확인한다 (mascot-shop.md 검증 절차). */

const COMBOS: { name: string; outfits: string[] }[] = [
  { name: "기본", outfits: [] },
  { name: "안경", outfits: ["glasses"] },
  { name: "리본+목도리", outfits: ["ribbon", "scarf"] },
  { name: "풀장착", outfits: ["ribbon", "glasses", "scarf", "crown"] },
];

export default function MascotQaPage() {
  return (
    <main className="min-h-screen bg-paper px-8 py-10">
      <h1 className="mb-2 font-hand text-2xl font-bold">마스코트 QA</h1>
      <p className="mb-6 text-xs opacity-60">
        좌: 원본 방향 / 우: 화면 표시 방향(좌우 반전 — 좌하단 등장). 말풍선
        글자가 뒤집히면 안 된다. 악세: {Object.values(OUTFIT_LABELS).join(", ")}
      </p>
      {Object.keys(MASCOT_LABELS).map((kind) => (
        <section key={kind} className="mb-8">
          <h2 className="mb-2 font-bold">{MASCOT_LABELS[kind]}</h2>
          <div className="flex flex-wrap gap-6">
            {COMBOS.map((combo) => (
              <div
                key={combo.name}
                className="flex flex-col items-center gap-1 rounded-lg border-2 border-ink/10 bg-white p-3"
              >
                <div className="flex items-end gap-3">
                  <div className="henyang-peek">
                    <MascotSvg kind={kind} outfits={combo.outfits} />
                  </div>
                  <div className="henyang-peek scale-x-[-1]">
                    <MascotSvg kind={kind} outfits={combo.outfits} flip />
                  </div>
                  {/* 아바타(플레이어 배지) 변형 — 말풍선 없이 크롭 */}
                  <span className="rounded border border-ink/20 p-0.5">
                    <MascotSvg kind={kind} outfits={combo.outfits} avatar />
                  </span>
                </div>
                <p className="text-xs opacity-60">{combo.name}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}

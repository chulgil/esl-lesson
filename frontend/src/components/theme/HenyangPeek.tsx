"use client";

import { useAppTheme } from "@/lib/theme";

/** 헤냥이 테마 마스코트 — 우하단에서 빼꼼거리며 헤헤 웃는 장식 (클릭 통과) */
export function HenyangPeek() {
  const theme = useAppTheme();
  if (theme !== "cat") return null;

  return (
    <div
      aria-hidden
      // 플로팅 슬롯 기준(ui-design.md): 우하단=채팅 런처 전용, 장식 마스코트=좌하단.
      // 런처가 캐릭터를 가리던 문제 (2026-07-31 보고). 좌측 등장이라 좌우 반전
      className="henyang-peek pointer-events-none fixed bottom-16 left-1 z-30 origin-bottom-left scale-x-[-0.75] scale-y-75 sm:bottom-2 sm:left-3 sm:scale-x-[-1] sm:scale-y-100"
    >
      <svg width="104" height="88" viewBox="0 0 104 88" fill="none">
        {/* 말풍선: 헤헤 */}
        <g>
          <rect
            x="64"
            y="2"
            width="38"
            height="24"
            rx="12"
            fill="#fff"
            stroke="#4d3b2a"
            strokeWidth="2"
          />
          <path
            d="M74 25l-4 7 10-6"
            fill="#fff"
            stroke="#4d3b2a"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <text
            x="83"
            y="19"
            textAnchor="middle"
            fontSize="13"
            fontWeight="700"
            fill="#4d3b2a"
            fontFamily="var(--font-gaegu), sans-serif"
          >
            헤헤
          </text>
        </g>
        {/* 귀 */}
        <path
          d="M16 46 L22 18 L40 36 Z"
          fill="#ffe9cf"
          stroke="#4d3b2a"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path
          d="M76 46 L70 18 L52 36 Z"
          fill="#ffe9cf"
          stroke="#4d3b2a"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path d="M22 40 L25 26 L34 35 Z" fill="#f2b9a0" />
        <path d="M70 40 L67 26 L58 35 Z" fill="#f2b9a0" />
        {/* 얼굴 — 아래에서 빼꼼 */}
        <ellipse
          cx="46"
          cy="66"
          rx="36"
          ry="32"
          fill="#ffe9cf"
          stroke="#4d3b2a"
          strokeWidth="2.5"
        />
        {/* 헤헤 감은 눈 */}
        <path
          d="M28 58 q6 -7 12 0"
          stroke="#4d3b2a"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M52 58 q6 -7 12 0"
          stroke="#4d3b2a"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* 볼터치 */}
        <ellipse cx="26" cy="66" rx="5" ry="3" fill="#f6a08d" opacity="0.55" />
        <ellipse cx="66" cy="66" rx="5" ry="3" fill="#f6a08d" opacity="0.55" />
        {/* 입: 활짝 웃는 ω */}
        <path
          d="M38 68 q4 6 8 0 q4 6 8 0"
          stroke="#4d3b2a"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
        {/* 수염 */}
        <path
          d="M8 62 L20 63 M9 70 L20 68"
          stroke="#4d3b2a"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M84 62 L72 63 M83 70 L72 68"
          stroke="#4d3b2a"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

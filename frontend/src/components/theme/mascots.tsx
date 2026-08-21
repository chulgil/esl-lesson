/** 마스코트 SVG 3종 + 악세사리 레이어 (docs/specs/mascot-shop.md).
 *
 *  공통 캔버스 104x88, 좌하단에서 빼꼼 나오는 구도 (HenyangPeek 계승).
 *  악세는 all-on — 보유 목록을 그대로 겹쳐 그린다. 앵커 좌표는 캐릭터별로
 *  명시 배치 (공용 좌표 추상화보다 캐릭터마다 어색하지 않은 위치가 우선).
 */

const INK = "#4d3b2a";

function Crown({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <path
        d="M0 10 L4 0 L9 7 L14 -2 L19 7 L24 0 L28 10 Z"
        fill="#ffd54d"
        stroke={INK}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <circle cx="7" cy="12" r="1.6" fill="#e14b32" />
      <circle cx="14" cy="12" r="1.6" fill="#3878c7" />
      <circle cx="21" cy="12" r="1.6" fill="#3ea662" />
      <rect
        x="0"
        y="10"
        width="28"
        height="4"
        rx="1.5"
        fill="#f2b93c"
        stroke={INK}
        strokeWidth="2"
      />
    </g>
  );
}

function Ribbon({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <path
        d="M0 6 L-10 0 L-10 12 Z"
        fill="#f26d8d"
        stroke={INK}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M0 6 L10 0 L10 12 Z"
        fill="#f26d8d"
        stroke={INK}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <circle
        cx="0"
        cy="6"
        r="3.2"
        fill="#e14b6e"
        stroke={INK}
        strokeWidth="2"
      />
    </g>
  );
}

function Glasses({
  x,
  y,
  gap = 24,
  r = 7,
}: {
  x: number;
  y: number;
  gap?: number;
  r?: number;
}) {
  return (
    <g stroke={INK} strokeWidth="2.2" fill="rgba(255,255,255,0.35)">
      <circle cx={x} cy={y} r={r} />
      <circle cx={x + gap} cy={y} r={r} />
      <path d={`M${x + r} ${y} h${gap - r * 2}`} fill="none" />
    </g>
  );
}

function Scarf({ x, y, width }: { x: number; y: number; width: number }) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height="9"
        rx="4.5"
        fill="#e14b32"
        stroke={INK}
        strokeWidth="2"
      />
      <rect
        x={x + width * 0.55}
        y={y + 6}
        width="9"
        height="14"
        rx="4"
        fill="#e14b32"
        stroke={INK}
        strokeWidth="2"
      />
      <path
        d={`M${x + 6} ${y + 4.5} h${width - 12}`}
        stroke="#f2b9a0"
        strokeWidth="1.6"
        strokeDasharray="3 3"
      />
    </g>
  );
}

function Bubble({ text, flip }: { text: string; flip?: boolean }) {
  // 커스텀 문구(변경권, 최대 6자) 대응 — 글자 수에 맞춰 왼쪽으로 늘어난다
  // (오른쪽 끝 102 고정 — 캐릭터 머리 위 위치 유지)
  const width = Math.min(92, Math.max(38, 14 + text.length * 12));
  const x = 102 - width;
  return (
    // 컨테이너가 좌우 반전(scale-x -1)돼도 글자는 읽혀야 한다 — 말풍선만 역반전
    // (1차 시각 검증 2026-08-11: 화면 방향에서 "헤헤/착착/몽!" 이 뒤집혀 보임)
    <g transform={flip ? "scale(-1 1) translate(-104 0)" : undefined}>
      <rect
        x={x}
        y="2"
        width={width}
        height="24"
        rx="12"
        fill="#fff"
        stroke={INK}
        strokeWidth="2"
      />
      <path
        d="M74 25l-4 7 10-6"
        fill="#fff"
        stroke={INK}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <text
        x={x + width / 2}
        y="19"
        textAnchor="middle"
        fontSize="13"
        fontWeight="700"
        fill={INK}
        fontFamily="var(--font-gaegu), sans-serif"
      >
        {text}
      </text>
    </g>
  );
}

function Henyang({
  outfits,
  flip,
  avatar,
  message,
}: {
  outfits: string[];
  message?: string | null;
  flip?: boolean;
  avatar?: boolean;
}) {
  return (
    <svg
      width={avatar ? 34 : 104}
      height={avatar ? 30 : 88}
      viewBox={avatar ? "6 12 88 76" : "0 0 104 88"}
      fill="none"
      className={avatar ? undefined : "mascot-anim-giggle"}
    >
      {!avatar && <Bubble text={message || "헤헤"} flip={flip} />}
      {/* 귀 */}
      <path
        d="M16 46 L22 18 L40 36 Z"
        fill="#ffe9cf"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path
        d="M76 46 L70 18 L52 36 Z"
        fill="#ffe9cf"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path d="M22 40 L25 26 L34 35 Z" fill="#f2b9a0" />
      <path d="M70 40 L67 26 L58 35 Z" fill="#f2b9a0" />
      {/* 얼굴 */}
      <ellipse
        cx="46"
        cy="66"
        rx="36"
        ry="32"
        fill="#ffe9cf"
        stroke={INK}
        strokeWidth="2.5"
      />
      {/* 감은 눈 / 볼터치 / 입 / 수염 */}
      <path
        d="M28 58 q6 -7 12 0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M52 58 q6 -7 12 0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <ellipse cx="26" cy="66" rx="5" ry="3" fill="#f6a08d" opacity="0.55" />
      <ellipse cx="66" cy="66" rx="5" ry="3" fill="#f6a08d" opacity="0.55" />
      <path
        d="M38 68 q4 6 8 0 q4 6 8 0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M8 62 L20 63 M9 70 L20 68"
        stroke={INK}
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M84 62 L72 63 M83 70 L72 68"
        stroke={INK}
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* 악세 (all-on) — 안경은 눈 위, 리본은 오른귀 밑, 목도리는 턱 아래, 왕관은 정수리 */}
      {outfits.includes("glasses") && <Glasses x={34} y={57} />}
      {outfits.includes("scarf") && <Scarf x={20} y={78} width={52} />}
      {outfits.includes("ribbon") && <Ribbon x={68} y={38} scale={0.9} />}
      {outfits.includes("crown") && <Crown x={32} y={14} />}
    </svg>
  );
}

function Bricky({
  outfits,
  flip,
  avatar,
  message,
}: {
  outfits: string[];
  message?: string | null;
  flip?: boolean;
  avatar?: boolean;
}) {
  return (
    <svg
      width={avatar ? 34 : 104}
      height={avatar ? 30 : 88}
      viewBox={avatar ? "6 12 88 76" : "0 0 104 88"}
      fill="none"
      className={avatar ? undefined : "mascot-anim-bounce"}
    >
      {!avatar && <Bubble text={message || "착착"} flip={flip} />}
      {/* 스터드 2개 (레고 윗면) */}
      <rect
        x="22"
        y="26"
        width="18"
        height="10"
        rx="2"
        fill="#c73b24"
        stroke={INK}
        strokeWidth="2.5"
      />
      <rect
        x="52"
        y="26"
        width="18"
        height="10"
        rx="2"
        fill="#c73b24"
        stroke={INK}
        strokeWidth="2.5"
      />
      {/* 몸통 브릭 — 하드섀도 */}
      <rect
        x="12"
        y="36"
        width="68"
        height="52"
        rx="6"
        fill="#e14b32"
        stroke={INK}
        strokeWidth="2.5"
      />
      <rect
        x="12"
        y="36"
        width="68"
        height="10"
        rx="6"
        fill="#f2664a"
        stroke="none"
      />
      {/* 눈 — 동그란 로봇 눈 */}
      <circle
        cx="34"
        cy="58"
        r="9"
        fill="#fff"
        stroke={INK}
        strokeWidth="2.5"
      />
      <circle
        cx="58"
        cy="58"
        r="9"
        fill="#fff"
        stroke={INK}
        strokeWidth="2.5"
      />
      <circle cx="36" cy="60" r="3.5" fill={INK} className="mascot-pupil" />
      <circle cx="60" cy="60" r="3.5" fill={INK} className="mascot-pupil" />
      {/* 입 — 스마일 단자 */}
      <path
        d="M38 74 q8 7 16 0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
      {/* 볼트 볼터치 */}
      <circle cx="20" cy="70" r="2.5" fill="#8f2c1a" opacity="0.6" />
      <circle cx="72" cy="70" r="2.5" fill="#8f2c1a" opacity="0.6" />
      {outfits.includes("glasses") && <Glasses x={34} y={58} gap={24} r={10} />}
      {outfits.includes("scarf") && <Scarf x={14} y={82} width={64} />}
      {outfits.includes("ribbon") && <Ribbon x={61} y={24} scale={0.8} />}
      {outfits.includes("crown") && <Crown x={32} y={12} />}
    </svg>
  );
}

function Mongi({
  outfits,
  flip,
  avatar,
  message,
}: {
  outfits: string[];
  message?: string | null;
  flip?: boolean;
  avatar?: boolean;
}) {
  return (
    <svg
      width={avatar ? 34 : 104}
      height={avatar ? 30 : 88}
      viewBox={avatar ? "6 12 88 76" : "0 0 104 88"}
      fill="none"
      className={avatar ? undefined : "mascot-anim-float"}
    >
      {!avatar && <Bubble text={message || "몽!"} flip={flip} />}
      {/* 다리 4개 — 물결 */}
      <path
        d="M18 78 q-6 8 2 10 M34 82 q-4 8 4 6 M58 82 q4 8 -4 6 M74 78 q6 8 -2 10"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
        className="mascot-tentacle"
      />
      {/* 머리 돔 */}
      <path
        d="M12 82 Q10 34 46 32 Q82 34 80 82 Z"
        fill="#9fd4f0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path
        d="M20 48 Q30 40 44 40"
        stroke="#d6effb"
        strokeWidth="4"
        strokeLinecap="round"
        fill="none"
      />
      {/* 눈 — 크고 순한 */}
      <circle cx="34" cy="62" r="6.5" fill={INK} />
      <circle cx="58" cy="62" r="6.5" fill={INK} />
      <circle cx="36" cy="60" r="2" fill="#fff" />
      <circle cx="60" cy="60" r="2" fill="#fff" />
      {/* 볼터치 + 입 */}
      <ellipse cx="24" cy="70" rx="4.5" ry="3" fill="#f6a08d" opacity="0.6" />
      <ellipse cx="68" cy="70" rx="4.5" ry="3" fill="#f6a08d" opacity="0.6" />
      <path
        d="M42 72 q4 4 8 0"
        stroke={INK}
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
      {outfits.includes("glasses") && (
        <Glasses x={34} y={62} gap={24} r={8.5} />
      )}
      {outfits.includes("scarf") && <Scarf x={16} y={79} width={60} />}
      {outfits.includes("ribbon") && <Ribbon x={70} y={34} scale={0.9} />}
      {outfits.includes("crown") && <Crown x={32} y={16} />}
    </svg>
  );
}

export const MASCOT_LABELS: Record<string, string> = {
  henyang: "헤냥이",
  bricky: "브리키",
  mongi: "몽이",
};

export const OUTFIT_LABELS: Record<string, string> = {
  ribbon: "리본",
  glasses: "동그란 안경",
  scarf: "목도리",
  crown: "왕관",
};

export function MascotSvg({
  kind,
  outfits,
  flip = false,
  avatar = false,
  message = null,
}: {
  kind: string;
  outfits: string[];
  /** 표시 컨테이너가 좌우 반전일 때 true — 말풍선 글자를 역반전해 읽히게 한다 */
  flip?: boolean;
  /** 프로필 아바타 모드 — 말풍선 없이 크롭·축소·정지 (플레이어 배지) */
  avatar?: boolean;
  /** 말풍선 커스텀 문구 (변경권, 최대 6자) — null/빈 문자열이면 캐릭터 기본 대사 */
  message?: string | null;
}) {
  if (kind === "bricky")
    return (
      <Bricky outfits={outfits} flip={flip} avatar={avatar} message={message} />
    );
  if (kind === "mongi")
    return (
      <Mongi outfits={outfits} flip={flip} avatar={avatar} message={message} />
    );
  if (kind === "henyang")
    return (
      <Henyang
        outfits={outfits}
        flip={flip}
        avatar={avatar}
        message={message}
      />
    );
  return null;
}

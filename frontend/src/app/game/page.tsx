import Link from "next/link";
import { MyBests } from "@/components/game/MyBests";
import { RecommendedMatch } from "@/components/game/RecommendedMatch";
import { WeeklyLeaderboardsCard } from "@/components/game/WeeklyLeaderboardsCard";
import { GameLangChips } from "@/app/game/GameLangChips";

/** 게임 허브 — 종류별 카테고리 메뉴 + 게임 설명 (2026-07-14 개편)
 *
 *  스킬 라벨(단어/듣기/문장): 훈련 목적별로 고를 수 있게 카드에 칩 표시 +
 *  같은 스킬끼리 인접 정렬 (proposal/level-format-fit B안 취지 흡수 — 트랙
 *  분리 없이 라벨만, 2026-08-18). */
type GameSkill = "word" | "listening" | "sentence";

const SKILL_LABELS: Record<GameSkill, string> = {
  word: "단어",
  listening: "듣기",
  sentence: "문장",
};

const SKILL_CHIP_STYLES: Record<GameSkill, string> = {
  // 연한 배경 위 텍스트라 brick-label(진한 배경용) 대신 잉크색 — 대비 확보
  word: "bg-brick-yellow/25 text-ink/80",
  listening: "bg-brick-blue/15 text-brick-blue",
  sentence: "bg-brick-green/15 text-brick-green",
};

const GAMES: {
  href: string;
  name: string;
  tagline: string;
  players: string;
  how: string[];
  color: string;
  skill: GameSkill;
}[] = [
  {
    href: "/game/tetris",
    skill: "word",
    name: "워드 테트리스",
    tagline: "떨어지는 단어를 쳐내는 실시간 액션 대전",
    players: "1인(AI 봇) · 2인(빠른 대전/방 초대)",
    how: [
      "영어 단어 브릭이 떨어지면 한글 뜻 칩을 탭, 한글이 떨어지면 영어로 타이핑",
      "3콤보마다 상대 보드에 젤리 공격 · 아이템 4종(멈춤/힌트/제거/방어)",
      "보드가 가득 차면 KO — 3분 뒤 점수가 높은 쪽이 승리",
    ],
    color: "border-brick-red/40",
  },
  {
    href: "/game/quiz",
    skill: "word",
    name: "스피드 퀴즈 로얄",
    tagline: "같은 문제, 빠를수록 높은 점수 — 최대 4인 버저 퀴즈",
    players: "1인(봇 1~3) · 2~4인(방 초대)",
    how: [
      "4지선다 10라운드 — 전원에게 같은 문제가 동시에 출제",
      "정답이면 50점 + 남은 시간 보너스(최대 100점), 오답은 0점",
      "라운드마다 순위 공개, 10라운드 합산 1위가 우승",
    ],
    color: "border-brick-blue/40",
  },
  {
    href: "/game/puzzle",
    skill: "word",
    name: "데일리 단어 퍼즐",
    tagline: "하루 한 단어, 모두에게 같은 문제 — 6번 안에!",
    players: "1인 · 하루 한 판",
    how: [
      "오늘의 영어 단어를 6번 안에 추측 — 초록=자리 정확, 노랑=자리 다름",
      '전원 같은 단어라 친구와 "몇 번 만에 맞혔나" 자랑 대결',
      "끝나면 단어와 뜻 공개 — 자정에 새 단어가 나와요",
    ],
    color: "border-ink/25",
  },
  {
    href: "/game/dictation",
    skill: "listening",
    name: "받아쓰기 배틀",
    tagline: "원어민 음성을 듣고 그대로 받아쓰는 리스닝 대결",
    players: "1인(기록 도전) · 2~4인(방 초대)",
    how: [
      "유튜브 원음 구간을 듣고 (반복 가능) 문장을 영어로 받아쓰기",
      "서버가 단어 단위로 채점 — 정확도 90% 이상이면 시간 보너스",
      "총 6문장, 라운드마다 정답 공개 — 점수 합산 1위가 승리",
    ],
    color: "border-brick-blue/40",
  },
  {
    href: "/game/bingo",
    skill: "listening",
    name: "리스닝 빙고",
    tagline: "음성으로 불러주는 단어를 보드에서 찾는 듣기 빙고",
    players: "1인(듣기 기록) · 2~4인(방 초대)",
    how: [
      "단어를 음성으로만 불러줘요 — 내 4x4 보드에서 찾아 탭",
      "모두 같은 16단어, 배치만 달라요 — 한 줄을 먼저 만들면 빙고 승리",
      "복습할 때가 된 단어가 우선 나와요 — 놓친 단어는 원탭으로 학습 담기",
    ],
    color: "border-brick-yellow/50",
  },
  {
    href: "/game/scramble",
    skill: "sentence",
    name: "어순 조립 레이스",
    tagline: "섞인 단어를 올바른 어순으로 — 문법 감각 퍼즐",
    players: "1인(기록 도전) · 2~4인(레이스 대결)",
    how: [
      "한글 뜻을 보고 섞인 단어 칩을 올바른 영어 어순으로 탭",
      "빠르고 정확할수록 높은 점수 — 실수하면 감점, 완성 최소 점수는 보장",
      "총 8문장 — 전원이 완성하면 다음 문장, 점수 합산 1위가 승리",
    ],
    color: "border-brick-yellow/50",
  },
  {
    href: "/game/typing",
    skill: "sentence",
    name: "영문 타자연습",
    tagline: "같은 문장을 동시에 치는 타이핑 레이스",
    players: "1인(기록 도전) · 2~4인(레이스 대결)",
    how: [
      "샘플 문장 하나를 모두가 동시에 타이핑 — 전원이 완성하면 다음 문장",
      "플레이어마다 진행 줄과 WPM(타속)이 실시간으로 표시돼요",
      "총 10문장 — 완성 문장 · 정타 · 빠르기 순으로 승부",
    ],
    color: "border-brick-green/40",
  },
];

export default function GameHubPage() {
  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-2">
        <h1 className="font-hand text-4xl font-bold">
          <span className="hl">게임</span>
        </h1>
        <p className="mt-2 text-sm opacity-70">
          배운 단어와 문장이 게임 소재가 돼요 — 놀수록 복습이 됩니다.
        </p>
        <GameLangChips />
        <MyBests />
      </header>

      <RecommendedMatch />

      <div className="mt-6 grid max-w-4xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {GAMES.map((game) => (
          <div
            key={game.href}
            className={`group relative flex flex-col rounded-xl border-2 ${game.color} bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-md`}
          >
            <h2 className="font-hand text-2xl font-bold group-hover:underline group-hover:decoration-highlight group-hover:decoration-4 group-hover:underline-offset-4">
              {game.name}
            </h2>
            <p className="mt-1 text-sm font-medium opacity-80">
              {game.tagline}
            </p>
            <p className="mt-2 flex flex-wrap items-center gap-1.5 self-start">
              {/* 스킬 칩 — 훈련 목적(단어/듣기/문장)별로 고르게 (2026-08-18) */}
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-bold ${SKILL_CHIP_STYLES[game.skill]}`}
              >
                {SKILL_LABELS[game.skill]} 연습
              </span>
              <span className="rounded-full bg-ink/5 px-2.5 py-1 text-xs font-bold">
                {game.players}
              </span>
            </p>
            {/* 모바일: 게임 방법 접기 — 카드 6장 스크롤 부담 절반으로 / 데스크톱: 상시 노출 */}
            <details className="group relative z-10 mt-1 self-start sm:hidden">
              {/* inline-flex 가 ::marker 를 지우므로 펼침 화살표를 직접 그림 */}
              <summary className="inline-flex min-h-11 cursor-pointer items-center gap-1 text-xs font-bold opacity-60">
                게임 방법
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="transition group-open:rotate-180"
                  aria-hidden
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </summary>
              <HowList how={game.how} className="mb-2 flex" />
            </details>
            <HowList how={game.how} className="mt-3 hidden sm:flex" />
            <Link
              href={game.href}
              className="mt-auto self-start pt-2 text-sm font-bold text-brick-blue after:absolute after:inset-0 sm:mt-4 sm:pt-0"
            >
              플레이 →
            </Link>
          </div>
        ))}
      </div>

      {/* 게임별 주간 최고 기록 — 매주 리셋되는 경쟁 루프 (P3) */}
      <WeeklyLeaderboardsCard />
    </main>
  );
}

function HowList({ how, className }: { how: string[]; className?: string }) {
  return (
    <ul
      className={`flex-col gap-1.5 text-xs leading-relaxed opacity-70 ${className ?? ""}`}
    >
      {how.map((line) => (
        <li key={line} className="flex gap-1.5">
          <span aria-hidden>·</span>
          {line}
        </li>
      ))}
    </ul>
  );
}

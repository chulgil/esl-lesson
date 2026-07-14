import Link from "next/link";
import { MyBests } from "@/components/game/MyBests";

/** 게임 허브 — 종류별 카테고리 메뉴 + 게임 설명 (2026-07-14 개편) */
const GAMES: {
  href: string;
  name: string;
  tagline: string;
  players: string;
  how: string[];
  color: string;
}[] = [
  {
    href: "/game/tetris",
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
    href: "/game/typing",
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
        <MyBests />
      </header>

      <div className="mt-6 grid max-w-4xl gap-5 lg:grid-cols-3">
        {GAMES.map((game) => (
          <Link
            key={game.href}
            href={game.href}
            className={`group flex flex-col rounded-xl border-2 ${game.color} bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-md`}
          >
            <h2 className="font-hand text-2xl font-bold group-hover:underline group-hover:decoration-highlight group-hover:decoration-4 group-hover:underline-offset-4">
              {game.name}
            </h2>
            <p className="mt-1 text-sm font-medium opacity-80">
              {game.tagline}
            </p>
            <p className="mt-2 inline-block self-start rounded-full bg-ink/5 px-2.5 py-1 text-xs font-bold">
              {game.players}
            </p>
            <ul className="mt-3 flex flex-col gap-1.5 text-xs leading-relaxed opacity-70">
              {game.how.map((line) => (
                <li key={line} className="flex gap-1.5">
                  <span aria-hidden>·</span>
                  {line}
                </li>
              ))}
            </ul>
            <span className="mt-4 text-sm font-bold text-brick-blue">
              플레이 →
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}

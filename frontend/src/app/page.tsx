"use client";

import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { Showcase } from "@/components/landing/Showcase";
import { fetchMe, type Me } from "@/lib/api";
import { studyApi, type Stats } from "@/lib/study-api";

export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then((user) => {
      setMe(user);
      setLoading(false);
    });
  }, []);

  if (!loading && !me) {
    // 비로그인: 쇼케이스 랜딩 (타이포그래피 배경)
    return (
      <main className="notebook-lines notebook-margin min-h-screen">
        <Showcase />
      </main>
    );
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-12 sm:px-16">
      <header className="mb-12">
        <h1 className="font-hand text-5xl font-bold">
          <span className="hl">ESL Lessonaza</span>
        </h1>
        <p className="mt-2 text-lg">
          유튜브로 배우고, 잊기 전에 다시 만나는 영어.
        </p>
      </header>

      {loading || !me ? (
        <p className="text-sm opacity-60">불러오는 중...</p>
      ) : (
        <Dashboard me={me} />
      )}
    </main>
  );
}

const LEVEL_COLORS = [
  "bg-brick-red",
  "bg-brick-yellow",
  "bg-brick-blue",
  "bg-brick-green",
];

function Dashboard({ me }: { me: Me }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
  }, []);

  return (
    <section className="flex flex-col gap-8">
      <p>
        <span className="font-hand text-2xl">{me.name}</span> 님, 오늘도 한 브릭
        쌓아볼까요?
        {stats && stats.streak_days > 0 && (
          <span className="ml-2 rounded bg-highlight/60 px-2 py-0.5 text-sm">
            {stats.streak_days}일 연속 학습 중
          </span>
        )}
      </p>
      <div className="flex flex-wrap gap-4">
        <Brick color="green" href="/study/session">
          오늘의 학습 시작{stats ? ` (${stats.due_count})` : ""}
        </Brick>
        <Brick color="blue" href="/library">
          콘텐츠 라이브러리
        </Brick>
        <Brick color="yellow" href="/my">
          내 콘텐츠 등록
        </Brick>
        <Brick color="red" href="/game">
          워드 테트리스
        </Brick>
      </div>

      {stats && (
        <div className="flex flex-wrap items-end gap-6">
          {stats.levels.map((lv) => (
            <div key={lv.level} className="flex flex-col items-center gap-1">
              <div className="flex flex-col-reverse gap-0.5" aria-hidden>
                {Array.from({ length: Math.min(8, lv.cards) }, (_, i) => (
                  <span
                    key={i}
                    className={`h-2.5 w-8 rounded-sm ${LEVEL_COLORS[lv.level - 1]}`}
                  />
                ))}
                {lv.cards === 0 && (
                  <span className="h-2.5 w-8 rounded-sm bg-ink/10" />
                )}
              </div>
              <p className="text-xs opacity-60">
                레벨 {lv.level} · {lv.cards}/{lv.approved_items}
              </p>
            </div>
          ))}
          <p className="text-xs opacity-50">
            오늘 복습 {stats.reviews_today}회
          </p>
        </div>
      )}
    </section>
  );
}

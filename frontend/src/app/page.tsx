"use client";

import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { fetchMe, loginUrl, type Me } from "@/lib/api";

export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then((user) => {
      setMe(user);
      setLoading(false);
    });
  }, []);

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

      {loading ? (
        <p className="text-sm opacity-60">불러오는 중...</p>
      ) : me ? (
        <Dashboard me={me} />
      ) : (
        <section className="flex flex-col items-start gap-6">
          <p className="max-w-md">
            유튜브 영상 스크립트에서 단어 · 숙어 · 패턴 · 문장을 뽑아, 잊어버릴
            만한 순간에 퀴즈로 다시 보여드려요.
          </p>
          <Brick color="red" href={loginUrl("/")}>
            Google로 시작하기
          </Brick>
        </section>
      )}
    </main>
  );
}

function Dashboard({ me }: { me: Me }) {
  return (
    <section className="flex flex-col gap-8">
      <p>
        <span className="font-hand text-2xl">{me.name}</span> 님, 오늘도 한 브릭
        쌓아볼까요?
      </p>
      <div className="flex flex-wrap gap-4">
        <Brick color="green" href="/study">
          오늘의 학습 시작
        </Brick>
        <Brick color="blue" href="/library">
          콘텐츠 라이브러리
        </Brick>
        {me.role === "admin" && (
          <Brick color="yellow" href="/admin">
            백오피스
          </Brick>
        )}
      </div>
      <p className="text-sm opacity-60">
        학습 큐 · 통계는 다음 단계(1c)에서 연결됩니다.
      </p>
    </section>
  );
}

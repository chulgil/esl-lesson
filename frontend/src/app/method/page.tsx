import type { Metadata } from "next";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { UsageBeacon } from "@/components/UsageBeacon";

export const metadata: Metadata = {
  title: "이 앱이 영어를 늘리는 방법 — ESL Lessonaza",
};

/** 인풋 → 전환 → 아웃풋 → 증거. 영어가 느는 사슬의 고리마다 어떤 장치가
 *  붙어 있는지를 한 화면에 (docs/proposal/effectiveness-audit-2026-08.md 구멍 4).
 *  카피는 비로그인 랜딩(components/landing/Showcase.tsx) 의 재사용 — 로그인
 *  전후가 다른 이야기를 하면 방법을 믿을 근거가 흩어진다. */
const RINGS: { no: string; ring: string; title: string; body: string }[] = [
  {
    no: "1",
    ring: "인풋",
    title: "진짜 원어민 발화가 카드가 돼요",
    body: "유튜브 영상에서 중요 단어·핵심 숙어·반복 패턴·통암기 문장 4종을 뽑습니다. thank you 같은 쉬운 표현은 걸러내요. 교재용으로 만든 문장이 아니라 원어민이 실제로 한 말이라, 배운 그대로 들리고 그대로 쓰게 됩니다.",
  },
  {
    no: "2",
    ring: "전환",
    title: "망각곡선이 복습 시점을 계산해요",
    body: "외운 건 반드시 잊습니다. 그래서 FSRS가 기억이 흐려지는 시점을 카드마다 계산해, 잊어버리기 직전에 그날의 복습 큐로 올려줍니다. 안키처럼 과학적으로, 듀오링고처럼 가볍게 — 오늘 뭘 복습할지는 앱이 정해요.",
  },
  {
    no: "3",
    ring: "아웃풋",
    title: "입으로 꺼내야 내 것이 돼요",
    body: "영상 한 편을 듣기(자막 없이·중심 찾기) → 분석(문장 직해·카드 학습) → 체화(섀도잉·한 문장 요약)의 6단계로 정복합니다. 문장을 클릭하면 그 구간만 반복 재생되고, 내 발음을 녹음해 원어민 음성과 그 자리에서 비교할 수 있어요.",
  },
  {
    no: "4",
    ring: "증거",
    title: "안 들리던 영상이 들리는 걸 확인해요",
    body: "같은 영상을 처음 들었을 때와 정복을 마친 뒤에 각각 얼마나 들렸는지 스스로 체크합니다. 점수·XP 같은 앱 안의 숫자가 아니라, 어제는 안 들리던 게 오늘 들린다는 본인의 감각이 남습니다.",
  },
];

export default function MethodPage() {
  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <UsageBeacon kind="method_view" />
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold sm:text-4xl">
          <span className="hl">이 앱이 영어를 늘리는 방법</span>
        </h1>
      </header>

      <div className="flex max-w-2xl flex-col gap-5">
        <p className="rounded-lg border-2 border-brick-blue/40 bg-white p-4 text-sm leading-relaxed">
          한 줄 요약:{" "}
          <b>
            좋아하는 영상에서 뽑은 진짜 표현을, 잊기 직전에 다시 만나고, 입으로
            꺼내보고, 그 영상이 들리는지로 확인합니다.
          </b>
        </p>

        {RINGS.map((r, i) => (
          <section
            key={r.ring}
            className={`rounded-lg border-2 border-ink/10 bg-white p-5 shadow-sm ${
              i % 2 ? "rotate-[0.3deg]" : "-rotate-[0.3deg]"
            }`}
          >
            <p className="flex items-baseline gap-2">
              <span className="font-hand text-3xl font-bold text-brick-red">
                {r.no}
              </span>
              <span className="rounded bg-highlight/70 px-2 py-0.5 text-xs font-bold">
                {r.ring}
              </span>
            </p>
            <h2 className="mt-1 font-bold">{r.title}</h2>
            <p className="mt-2 text-sm leading-relaxed opacity-80">{r.body}</p>
          </section>
        ))}

        {/* 첫 주 기대치 — "얼마나 해야 하는가"를 못 박아 부담을 끊는다 */}
        <section className="rounded-lg border-2 border-brick-green/50 bg-white p-5 shadow-sm">
          <h2 className="font-hand text-2xl font-bold">
            첫 주엔 이만큼이면 돼요
          </h2>
          <p className="mt-2 text-sm leading-relaxed">
            <b>하루 15개 복습 + 영상 1편 정복 시작</b>이면 충분해요. 바쁜 날은
            줄여도 됩니다 — <b>1개만 해도 스트릭은 이어져요.</b> 복습 리마인더
            시각을 정해두면 그 시각에 알림이 도착해요.
          </p>
          <div className="mt-4">
            <Brick color="green" href="/study/session">
              학습 시작
            </Brick>
          </div>
        </section>
      </div>
    </main>
  );
}

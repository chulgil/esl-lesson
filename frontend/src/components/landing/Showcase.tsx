import { Brick } from "@/components/brick/Brick";
import { TypoBackground } from "@/components/landing/TypoBackground";
import { loginUrl } from "@/lib/api";

/** 비로그인 쇼케이스 랜딩 — "이거 영어 학습에 획기적인데?" 를 목표로 하는 페이지 */
export function Showcase() {
  return (
    <div className="relative">
      <TypoBackground />

      {/* 히어로 */}
      <section className="relative flex min-h-[70vh] flex-col items-start justify-center gap-6 px-6 py-16 sm:px-16">
        <p className="rounded-full border-2 border-ink/15 bg-white/80 px-4 py-1 text-sm font-bold">
          유튜브 영상이 나만의 영어 교재가 됩니다
        </p>
        <h1 className="font-hand text-5xl font-bold leading-tight sm:text-7xl">
          좋아하는 영상으로 배우고,
          <br />
          <span className="hl">잊기 직전에 다시 만나는</span> 영어
        </h1>
        <p className="max-w-xl text-lg leading-relaxed">
          유튜브 URL 하나면 AI가 단어·숙어·패턴·문장을 뽑아냅니다. 그리고
          망각곡선이 계산한 <b>&quot;잊어버리기 직전&quot;</b>에 퀴즈로 다시
          찾아옵니다. 안키처럼 과학적으로, 듀오링고처럼 가볍게.
        </p>
        <div className="flex flex-wrap gap-4">
          <Brick color="red" href={loginUrl("/")}>
            Google로 시작하기
          </Brick>
          <Brick color="blue" href="#how">
            어떻게 동작하나요?
          </Brick>
        </div>
      </section>

      {/* 3단계 흐름 */}
      <section id="how" className="relative px-6 py-14 sm:px-16">
        <h2 className="font-hand text-3xl font-bold">
          <span className="hl">3단계면 끝나요</span>
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <StepCard
            no="1"
            title="영상 URL 붙여넣기"
            body="제목과 영어·한글 스크립트를 자동으로 가져옵니다. 한글 자막이 없으면 AI가 번역해요."
          />
          <StepCard
            no="2"
            title="AI가 학습 재료 추출"
            body="중요 단어, 핵심 숙어, 반복되는 패턴, 통암기할 문장 4종을 뽑습니다. thank you 같은 쉬운 표현은 걸러내요."
          />
          <StepCard
            no="3"
            title="잊을 때쯤 퀴즈로"
            body="망각곡선(FSRS)이 기억이 흐려지는 시점을 계산해 그날의 복습 큐에 자동으로 올려줍니다."
          />
        </div>
      </section>

      {/* 레벨 1-4 퀴즈 쇼케이스 */}
      <section className="relative px-6 py-14 sm:px-16">
        <h2 className="font-hand text-3xl font-bold">
          <span className="hl">레벨 1부터 4까지, 브릭 쌓듯이</span>
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <QuizCard
            level={1}
            color="border-brick-red"
            label="단어"
            example={
              <>
                <p className="text-xl font-bold">resilient</p>
                <div className="mt-2 flex flex-col gap-1 text-sm">
                  <Choice text="회복력 있는" correct />
                  <Choice text="명백한" />
                  <Choice text="우연한" />
                </div>
              </>
            }
          />
          <QuizCard
            level={2}
            color="border-brick-yellow"
            label="숙어"
            example={
              <>
                <p className="text-sm">
                  Let&apos;s just <b className="text-brick-blue">___</b> and
                  move on.
                </p>
                <div className="mt-2 flex flex-col gap-1 text-sm">
                  <Choice text="get it over with" correct />
                  <Choice text="look forward to" />
                </div>
              </>
            }
          />
          <QuizCard
            level={3}
            color="border-brick-blue"
            label="패턴"
            example={
              <>
                <p className="text-sm">익숙해지는 데 시간이 걸려요</p>
                <p className="mt-1 font-mono text-xs opacity-60">
                  It takes ___ to ...
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {["It", "takes", "time", "to", "adjust"].map((chip) => (
                    <span
                      key={chip}
                      className="rounded border border-ink/20 bg-white px-1.5 py-0.5 text-xs"
                    >
                      {chip}
                    </span>
                  ))}
                </div>
              </>
            }
          />
          <QuizCard
            level={4}
            color="border-brick-green"
            label="문장 통암기"
            example={
              <>
                <p className="text-sm">저기에 나무가 한 그루 있어요</p>
                <p className="mt-1 text-xs text-brick-blue">
                  (있다, 나무 한 그루가, 저기에)
                </p>
                <p className="mt-2 rounded border-2 border-dashed border-ink/20 px-2 py-1 font-mono text-xs opacity-70">
                  There is a tree over there|
                </p>
              </>
            }
          />
        </div>
        <p className="mt-4 max-w-2xl text-sm opacity-70">
          레벨 4는 한글 문제 옆에 <b>영어식 사고 힌트</b>가 붙어요 — 영어 어순
          그대로 생각하는 훈련이라, 문장이 통째로 몸에 남습니다.
        </p>
      </section>

      {/* 구간 반복 + 게임 */}
      <section className="relative grid gap-6 px-6 py-14 sm:grid-cols-2 sm:px-16">
        <FeatureCard
          title="원어민 음성을 문장 단위로 반복"
          body="스크립트 문장을 클릭하면 유튜브에서 딱 그 구간만 재생됩니다. 구간 반복(A-B 루프)을 켜면 귀에 붙을 때까지 무한 반복."
          badge="쉐도잉에 최적"
        />
        <FeatureCard
          title="워드 테트리스로 스피드 훈련"
          body="배운 단어가 테트리스 브릭처럼 떨어집니다. 빨리 타이핑해서 쳐내고, 콤보로 상대를 공격하세요. AI 봇도, 친구 대전도 됩니다."
          badge="페이즈 2 탑재"
        />
      </section>

      {/* 마지막 CTA */}
      <section className="relative flex flex-col items-center gap-4 px-6 py-20 text-center">
        <h2 className="font-hand text-4xl font-bold">
          오늘 본 영상, <span className="hl">내일의 영어</span>가 됩니다
        </h2>
        <Brick color="green" href={loginUrl("/")}>
          무료로 시작하기 — Google 로그인
        </Brick>
      </section>
    </div>
  );
}

function StepCard({
  no,
  title,
  body,
}: {
  no: string;
  title: string;
  body: string;
}) {
  return (
    <div className="-rotate-[0.4deg] rounded-lg border-2 border-ink/10 bg-white/90 p-5 shadow-sm">
      <span className="font-hand text-4xl font-bold text-brick-red">{no}</span>
      <p className="mt-1 font-bold">{title}</p>
      <p className="mt-2 text-sm leading-relaxed opacity-80">{body}</p>
    </div>
  );
}

function QuizCard({
  level,
  color,
  label,
  example,
}: {
  level: number;
  color: string;
  label: string;
  example: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-lg border-t-4 ${color} border-2 border-ink/10 bg-white/90 p-4 shadow-sm`}
    >
      <p className="text-xs font-bold opacity-60">
        레벨 {level} · {label}
      </p>
      <div className="mt-2">{example}</div>
    </div>
  );
}

function Choice({
  text,
  correct = false,
}: {
  text: string;
  correct?: boolean;
}) {
  return (
    <span
      className={`rounded border px-2 py-1 ${
        correct
          ? "border-brick-green bg-brick-green/10 font-bold"
          : "border-ink/15"
      }`}
    >
      {text}
    </span>
  );
}

function FeatureCard({
  title,
  body,
  badge,
}: {
  title: string;
  body: string;
  badge: string;
}) {
  return (
    <div className="rotate-[0.3deg] rounded-lg border-2 border-ink/10 bg-white/90 p-6 shadow-sm">
      <span className="rounded bg-highlight/70 px-2 py-0.5 text-xs font-bold">
        {badge}
      </span>
      <p className="mt-2 font-hand text-2xl font-bold">{title}</p>
      <p className="mt-2 text-sm leading-relaxed opacity-80">{body}</p>
    </div>
  );
}

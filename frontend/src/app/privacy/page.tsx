import type { Metadata } from "next";
import Link from "next/link";
import { BackLink } from "@/components/nav/BackLink";

export const metadata: Metadata = {
  title: "개인정보처리방침 — ESL Lessonaza",
};

const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: "1. 수집하는 개인정보",
    body: (
      <>
        <p>
          Google 로그인 시 <b>이메일, 이름, 프로필 사진</b> 세 가지만 받습니다.{" "}
          <b>비밀번호는 만들지도, 저장하지도 않습니다</b> — 인증은 전적으로
          Google이 처리하며 이 서비스는 비밀번호를 알 수 없습니다.
        </p>
        <p className="mt-2">
          서비스 이용 중에는 학습 기록(복습 카드·채점 이력)과 게임
          기록(점수·승패)이 저장됩니다. 전화번호, 생년월일, 주소, 결제 정보는
          수집하지 않습니다.
        </p>
      </>
    ),
  },
  {
    title: "2. 이용 목적",
    body: (
      <p>
        로그인 식별, 망각곡선 기반 복습 스케줄 계산, 게임 전적·리더보드 표시에만
        사용합니다. 마케팅·광고에 사용하지 않습니다.
      </p>
    ),
  },
  {
    title: "3. 보관 및 파기",
    body: (
      <p>
        탈퇴 시 계정·학습 기록·게임 기록·개인 콘텐츠(다른 구독자가 없는 경우)를{" "}
        <b>즉시 삭제</b>합니다. 설정 페이지에서 언제든 직접 탈퇴할 수 있으며,
        별도 문의나 대기 기간이 없습니다.
      </p>
    ),
  },
  {
    title: "4. 제3자 제공 및 처리 위탁",
    body: (
      <>
        <p>개인정보를 제3자에게 판매하거나 제공하지 않습니다.</p>
        <p className="mt-2">
          서비스 운영을 위해 다음 인프라를 사용합니다: 서버 호스팅(Vultr, 해외
          리전), AI 콘텐츠 분석(Anthropic·Voyage AI —{" "}
          <b>
            영상 스크립트 텍스트만 전송하며 이메일 등 개인 식별 정보는 전송하지
            않습니다
          </b>
          ).
        </p>
      </>
    ),
  },
  {
    title: "5. 쿠키",
    body: (
      <p>
        로그인 세션 유지 목적의 필수 쿠키 1개만 사용합니다(httponly·secure).
        광고·추적 쿠키, 분석 스크립트는 없습니다.
      </p>
    ),
  },
  {
    title: "6. 문의",
    body: (
      <p>
        개인정보 관련 문의는 관리자 이메일(codenavi@gmail.com)로 보내주세요.
        지체 없이 답변드립니다.
      </p>
    ),
  },
];

/** 개인정보처리방침 — 최소 수집·즉시 파기 원칙을 투명하게 공개 */
export default function PrivacyPage() {
  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">개인정보처리방침</span>
        </h1>
      </header>

      <div className="flex max-w-2xl flex-col gap-5">
        <p className="rounded-lg border-2 border-brick-green/40 bg-white p-4 text-sm">
          한 줄 요약:{" "}
          <b>
            이메일·이름·프로필 사진만 받고, 비밀번호는 받지 않으며, 탈퇴하면
            즉시 전부 삭제됩니다.
          </b>
        </p>
        {SECTIONS.map((s) => (
          <section key={s.title} className="text-sm leading-relaxed">
            <h2 className="mb-1.5 font-bold">{s.title}</h2>
            {s.body}
          </section>
        ))}
        <p className="text-xs opacity-50">
          시행일: 2026-07-14 · 관련 문서:{" "}
          <Link href="/copyright" className="underline underline-offset-2">
            저작권 안내
          </Link>
        </p>
      </div>
    </main>
  );
}

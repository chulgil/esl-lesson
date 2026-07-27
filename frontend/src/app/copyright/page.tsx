import type { Metadata } from "next";
import { BackLink } from "@/components/nav/BackLink";

export const metadata: Metadata = {
  title: "저작권 안내 — ESL Lessonaza",
};

const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: "1. 원저작자 보호 원칙",
    body: (
      <>
        <p>
          영상은 항상 <b>유튜브 공식 임베드 플레이어</b>로 재생됩니다 — 조회수와
          광고 수익은 원저작자에게 그대로 귀속되며, 영상 파일을 내려받거나
          재업로드하지 않습니다.
        </p>
        <p className="mt-2">
          학습 자료는 단어·숙어·표현 단위로 추출해 출처(원본 영상 링크)와 함께
          제공하며, <b>전체 스크립트는 열람을 제공하지 않습니다</b>. 자막은 재생
          중인 문장만 화면에 표시됩니다.
        </p>
      </>
    ),
  },
  {
    title: "2. 콘텐츠 선정 — 관리자 큐레이션",
    body: (
      <>
        <p>
          학습 콘텐츠는 <b>운영자가 직접 선정해 등록</b>합니다. 회원이 임의의
          영상을 올릴 수 있는 경로는 제공하지 않습니다.
        </p>
        <p className="mt-2">
          크리에이티브 커먼즈(CC) 라이선스 영상을 우선하며, 그 외 영상은{" "}
          <b>원저작자에게 허락을 받고</b> 허락 범위(자막 저장·번역·학습 항목
          변형)와 증빙을 기록한 경우에만 등록합니다.
        </p>
      </>
    ),
  },
  {
    title: "3. 이용 목적",
    body: (
      <p>
        모든 콘텐츠는 회원 개인의 영어 학습(복습·퀴즈) 목적으로만 사용되며, 원본
        영상을 대체하는 서비스가 아닙니다. 학습 중에도 원본 영상 시청을 권장하는
        구조로 설계되어 있습니다.
      </p>
    ),
  },
  {
    title: "4. 권리자 삭제 요청 (Notice & Takedown)",
    body: (
      <>
        <p>
          본인이 권리를 가진 영상이 이 서비스에서 학습 소재로 사용되는 것을 원치
          않으시면 아래로 알려주세요.{" "}
          <b>확인 즉시 해당 콘텐츠와 파생 학습 자료를 지체 없이 삭제</b>합니다.
        </p>
        <p className="mt-2">
          이메일: <b>rimanbackend@gmail.com</b>
          <br />
          포함해 주실 내용: 해당 유튜브 영상 URL, 권리 관계를 확인할 수 있는
          간단한 소명(채널 소유 확인 등)
        </p>
      </>
    ),
  },
  {
    title: "5. 이의제기",
    body: (
      <p>
        삭제 조치에 이의가 있는 회원은 같은 이메일로 소명을 보낼 수 있으며,
        정당한 권한(권리자 허락, 라이선스 등)이 확인되면 복원됩니다.
      </p>
    ),
  },
];

/** 저작권 안내 — 관리자 큐레이션·허락 확보 + 삭제 요청 채널 (docs/specs/content-governance.md) */
export default function CopyrightPage() {
  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">저작권 안내</span>
        </h1>
      </header>

      <div className="flex max-w-2xl flex-col gap-5">
        <p className="rounded-lg border-2 border-brick-blue/40 bg-white p-4 text-sm">
          한 줄 요약:{" "}
          <b>
            운영자가 허락을 확인한 영상만 등록하고, 재생은 유튜브 임베드로만
            하며(수익은 원저작자에게), 전체 스크립트는 제공하지 않습니다.
            권리자가 요청하면 즉시 삭제합니다.
          </b>
        </p>
        {SECTIONS.map((s) => (
          <section key={s.title} className="text-sm leading-relaxed">
            <h2 className="mb-1.5 font-bold">{s.title}</h2>
            {s.body}
          </section>
        ))}
        <p className="text-xs opacity-50">시행일: 2026-07-27</p>
      </div>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type AdminExam } from "@/lib/admin-api";

/** 백오피스 시험지 패널 — 생성/재생성 + 회차 목록·문항 미리보기(정답 포함).
 *  항목 5개 미만이면 422 not_enough_items — 안내 문구로 변환한다. */
export function ExamPanel({ contentId }: { contentId: number }) {
  const [exams, setExams] = useState<AdminExam[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    adminApi
      .listExams(contentId)
      .then((res) => setExams(res.items))
      .catch((e) => setError(e.message));
  }, [contentId]);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await adminApi.createExam(contentId);
      setNotice(
        `제${res.round}회 시험지 생성 완료 (${res.question_count}문항)`,
      );
      load();
    } catch (e) {
      if (e instanceof Error && e.message === "not_enough_items") {
        setError(
          "승인된 단어/숙어/패턴이 5개 미만이라 시험지를 만들 수 없어요 — 항목을 먼저 승인해 주세요.",
        );
      } else {
        setError(e instanceof Error ? e.message : "생성 실패");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!exams) {
    return error ? (
      <p className="mt-3 text-sm text-brick-red">{error}</p>
    ) : (
      <p className="mt-3 text-sm opacity-60">불러오는 중...</p>
    );
  }

  const hasActive = exams.some((e) => e.status === "active");
  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={generate}
          disabled={busy}
          className="min-h-9 rounded bg-brick-green px-4 text-sm font-bold text-brick-label transition enabled:hover:opacity-90 disabled:opacity-50"
        >
          {busy
            ? "생성 중..."
            : hasActive
              ? "시험지 재생성 (새 회차)"
              : "시험지 생성"}
        </button>
        {hasActive && (
          <span className="text-xs opacity-60">
            재생성하면 기존 회차는 보존(archived)되고 새 회차가 노출돼요
          </span>
        )}
      </div>
      {notice && <p className="mt-2 text-xs text-brick-green">{notice}</p>}
      {error && <p className="mt-2 text-xs text-brick-red">{error}</p>}

      {exams.length === 0 ? (
        <p className="mt-4 rounded border-2 border-dashed border-ink/20 bg-white p-6 text-center text-sm opacity-60">
          아직 시험지가 없어요 — 생성하면 학습자 화면에 [시험 보기]가 열려요
        </p>
      ) : (
        <div className="mt-4 flex flex-col gap-3">
          {exams.map((exam) => (
            <ExamRound key={exam.exam_id} exam={exam} />
          ))}
        </div>
      )}
    </div>
  );
}

function ExamRound({ exam }: { exam: AdminExam }) {
  const [open, setOpen] = useState(exam.status === "active");
  return (
    <section className="rounded-lg border-2 border-ink/15 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-2 p-3 text-left text-sm"
      >
        <b className="font-hand text-base">제{exam.round}회</b>
        <span
          className={`rounded px-2 py-0.5 text-xs ${
            exam.status === "active"
              ? "bg-brick-green/20 text-brick-green"
              : "bg-ink/10 opacity-70"
          }`}
        >
          {exam.status === "active" ? "노출 중" : "보관됨"}
        </span>
        <span className="text-xs opacity-60">
          {exam.question_count}문항 · 제출 {exam.submitted_count}회
        </span>
        <span className="ml-auto text-xs opacity-40">
          {open ? "접기" : "문항 보기"}
        </span>
      </button>
      {open && (
        <ol className="border-t border-ink/10 p-3 text-sm">
          {exam.questions.map((q) => (
            <li
              key={q.seq}
              className="border-b border-ink/5 py-2 last:border-b-0"
            >
              <p className="font-medium">
                {q.seq}. {q.prompt}
                <span className="ml-2 text-xs opacity-50">({q.quiz_mode})</span>
              </p>
              {q.prompt_ko && (
                <p className="text-xs opacity-60">{q.prompt_ko}</p>
              )}
              <ol className="mt-1 flex flex-col gap-0.5 text-xs">
                {q.choices.map((choice, idx) => (
                  <li
                    key={idx}
                    className={
                      idx === q.answer_index
                        ? "font-bold text-brick-green"
                        : "opacity-70"
                    }
                  >
                    {idx + 1}) {choice}
                    {idx === q.answer_index && " [정답]"}
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

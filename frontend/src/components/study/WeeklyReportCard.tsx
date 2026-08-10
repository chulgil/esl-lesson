"use client";

import { useEffect, useState } from "react";
import { UsageBeacon } from "@/components/UsageBeacon";
import { studyApi, type WeeklyReport } from "@/lib/study-api";

/** 주간 성적표 카드 — "지난주의 나 vs 그 전주의 나" (docs/specs/weekly-report.md).
 *  절대치보다 델타. 지난주 복습 0(has_data=false)이면 카드 자체를 내지 않는다 —
 *  빈 성적표는 이탈 유발. 카피 규칙: 다음 주 제안은 딱 1줄, 최소 행동 바닥
 *  ("1개만 해도 스트릭은 이어져요") 고지는 항상. */

function fmtDelta(delta: number): string | null {
  return delta === 0 ? null : ` (${delta > 0 ? "+" : ""}${delta})`;
}

/** 다음 주 한 줄 제안 — 규칙 파생 (위에서부터 첫 일치, LLM 아님) */
function nextWeekTip(r: WeeklyReport): string {
  if (r.reviews_delta < 0) return "이번 주엔 하루 1개부터 다시 시작해요";
  if (r.routine_steps === 0)
    return "이번 주엔 영상 1편 정복을 시작해보세요";
  if (!r.listen)
    return "루틴 끝의 재청취 체크로 “들리게 됐다”는 증거를 남겨보세요";
  return "지난주 리듬 그대로 — 하루 15개면 충분해요";
}

export function WeeklyReportCard() {
  const [report, setReport] = useState<WeeklyReport | null>(null);

  useEffect(() => {
    studyApi
      .weeklyReport()
      .then(setReport)
      .catch(() => undefined);
  }, []);

  if (!report?.has_data) return null;

  const [, sm, sd] = report.week_start.split("-");
  const [, em, ed] = report.week_end.split("-");
  const stats: { label: string; value: string; delta: string | null }[] = [
    {
      label: "복습",
      value: `${report.reviews}개`,
      delta: fmtDelta(report.reviews_delta),
    },
    ...(report.accuracy !== null
      ? [
          {
            label: "정답률",
            value: `${report.accuracy}%`,
            delta:
              report.accuracy_delta === null
                ? null
                : fmtDelta(report.accuracy_delta)?.replace(")", "%p)") || null,
          },
        ]
      : []),
    {
      label: "장기 기억",
      value: `+${report.long_term_new}`,
      delta: fmtDelta(report.long_term_new_delta),
    },
    {
      label: "루틴 단계",
      value: `${report.routine_steps}칸`,
      delta: fmtDelta(report.routine_steps_delta),
    },
  ];

  return (
    <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-yellow/60 bg-white p-5 shadow-sm">
      <UsageBeacon kind="weekly_report_view" meta={{ surface: "study_tab" }} />
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="font-hand text-2xl font-bold">지난주 성적표</h2>
        <span className="text-xs opacity-60">
          {Number(sm)}/{Number(sd)} ~ {Number(em)}/{Number(ed)} · 그 전주와
          비교했어요
        </span>
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {stats.map((s) => (
          <li key={s.label}>
            <span className="opacity-60">{s.label}</span> <b>{s.value}</b>
            {s.delta && (
              <span
                className={`ml-0.5 text-xs font-bold ${
                  s.delta.includes("+") ? "text-brick-green" : "text-brick-red"
                }`}
              >
                {s.delta}
              </span>
            )}
          </li>
        ))}
      </ul>

      {/* 재청취 델타 — 앱 밖 감각의 증거라 최상위 서사로 강조 */}
      {report.listen && (
        <p className="mt-2 w-fit rounded bg-highlight/50 px-2 py-1 text-sm font-bold">
          재청취 이해도 {report.listen.delta > 0 ? "+" : ""}
          {report.listen.delta} — 영상 {report.listen.contents}편이 지난주보다
          더 들렸어요
        </p>
      )}

      <p className="mt-3 text-sm">
        <span className="font-bold text-brick-blue">다음 주 제안</span>{" "}
        {nextWeekTip(report)}
      </p>
      <p className="mt-1 text-xs opacity-60">
        바쁜 날엔 복습 1개만 해도 스트릭은 이어져요
      </p>
    </section>
  );
}

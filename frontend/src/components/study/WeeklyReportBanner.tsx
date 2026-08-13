"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { UsageBeacon } from "@/components/UsageBeacon";
import { studyApi, type WeeklyReport } from "@/lib/study-api";

/** 주간 성적표 홈 배너 — 새 성적표가 나온 주의 첫 방문에 1회
 *  (docs/specs/weekly-report.md, 복귀 감사 배너와 동일 패턴).
 *  모달 금지 — 조용한 한 줄 + 학습 탭 링크. 표시 즉시 기록(두 번 조르지 않기).
 *  이미 본 주면 API 호출 자체를 생략한다. */

const SEEN_KEY = "esl:weekly-report:seen";

/** 이번에 나올 성적표의 대상 주(지난주) 월요일 — 백엔드 last_week_start 와 동일 산식 */
function lastWeekStartKst(): string {
  const wall = new Date(Date.now() + 9 * 3_600_000); // KST 벽시계 (UTC 게터로 읽는다)
  const dow = (wall.getUTCDay() + 6) % 7; // 월=0
  wall.setUTCDate(wall.getUTCDate() - dow - 7);
  return wall.toISOString().slice(0, 10);
}

export function WeeklyReportBanner() {
  const [report, setReport] = useState<WeeklyReport | null>(null);

  useEffect(() => {
    if (localStorage.getItem(SEEN_KEY) === lastWeekStartKst()) return;
    studyApi
      .weeklyReport()
      .then((r) => {
        if (!r.has_data) return; // 빈 성적표는 조르지 않는다 — 마킹도 안 함
        if (localStorage.getItem(SEEN_KEY) === r.week_start) return;
        localStorage.setItem(SEEN_KEY, r.week_start);
        setReport(r);
      })
      .catch(() => undefined);
  }, []);

  if (!report) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border-2 border-brick-yellow/60 bg-highlight/30 px-4 py-2.5 text-sm">
      <UsageBeacon
        kind="weekly_report_view"
        meta={{ surface: "home_banner" }}
      />
      <span>
        지난주 성적표가 나왔어요 — 복습 <b>{report.reviews}개</b>
        {report.reviews_delta !== 0 && (
          <>
            , 그 전주보다{" "}
            <b>
              {report.reviews_delta > 0 ? "+" : ""}
              {report.reviews_delta}
            </b>
          </>
        )}
      </span>
      <Link
        href="/study"
        className="font-bold text-brick-blue underline-offset-2 hover:underline"
      >
        성적표 보기 →
      </Link>
      <button
        type="button"
        aria-label="닫기"
        onClick={() => setReport(null)}
        className="ml-auto flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink/50 hover:text-ink"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

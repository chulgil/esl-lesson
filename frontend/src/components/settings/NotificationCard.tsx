"use client";

import { useEffect, useState } from "react";
import {
  getPushState,
  PUSH_CHANGED_EVENT,
  type PushState,
  sendTestPush,
  showLocalTestNotification,
  subscribePush,
  unsubscribePush,
} from "@/lib/push";
import { studyApi } from "@/lib/study-api";

const REMINDER_HOURS = Array.from({ length: 19 }, (_, i) => i + 5); // 5~23시

function fmtHour(h: number): string {
  if (h < 12) return `오전 ${h}시`;
  if (h === 12) return `낮 12시`;
  return `저녁 ${h - 12}시`;
}

/** 알림 통합 카드 — 기기(브라우저) 단위 마스터 스위치 하나.
 *
 *  서버 푸시 구독(VAPID)은 기기당 1개뿐이라 종류별 스위치는 허상이었다 —
 *  이전의 "복습 리마인더"(알림 섹션)와 "새 글 알림"(채팅창 섹션) 두 토글이
 *  같은 구독을 다른 이름으로 켜고 꺼 사용자를 헷갈리게 했다 (2026-07-31
 *  보고). 스위치는 하나로 두고, 이 스위치로 받게 되는 알림 종류를 목록으로
 *  보여준다. */
export function NotificationCard() {
  const [state, setState] = useState<PushState | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // 복습 리마인더 시각 — 사용자의 생활 리듬에 맞춘다 (실행 의도,
  // user-journey-motivation-2026-08.md P1). null = 로딩 전
  const [reminderHour, setReminderHour] = useState<number | null>(null);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => setReminderHour(s.reminder_hour))
      .catch(() => undefined);
  }, []);

  async function changeReminderHour(hour: number) {
    const prev = reminderHour;
    setReminderHour(hour); // 낙관적 반영
    try {
      await studyApi.patchSettings({ reminder_hour: hour });
    } catch {
      setReminderHour(prev);
      setMessage(
        "리마인더 시각 저장에 실패했어요 — 잠시 후 다시 시도해주세요.",
      );
    }
  }

  useEffect(() => {
    const refresh = () =>
      getPushState()
        .then(setState)
        .catch(() => setState("unsupported"));
    refresh();
    // 온보딩 가이드·대화 목록 버튼에서 구독이 바뀌면 카드도 즉시 갱신
    window.addEventListener(PUSH_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(PUSH_CHANGED_EVENT, refresh);
  }, []);

  async function toggle() {
    setBusy(true);
    setMessage(null);
    try {
      if (state === "subscribed") {
        await unsubscribePush();
        setState("idle");
      } else {
        setState(await subscribePush());
      }
    } catch {
      setMessage("설정에 실패했어요 — 잠시 후 다시 시도해주세요.");
    }
    setBusy(false);
  }

  async function handleTest() {
    setBusy(true);
    setMessage(null);
    // 로컬(서버 무관) + 서버 푸시를 함께 쏴서 어느 구간이 막혔는지 분리 진단
    const localShown = await showLocalTestNotification();
    try {
      const { sent, errors } = await sendTestPush();
      if (sent > 0) {
        setMessage(
          localShown
            ? "테스트 알림 2개(로컬·서버)를 보냈어요 — 하나도 안 보이면 OS 알림 설정(macOS: 시스템 설정 > 알림, Windows: 설정 > 알림)에서 이 브라우저를 허용하고 방해금지 모드를 꺼주세요."
            : "서버 발송은 됐지만 로컬 표시가 실패했어요 — 브라우저 알림 권한을 확인해주세요.",
        );
      } else if (errors > 0) {
        setMessage(
          "서버에서 푸시 발송에 실패했어요 — 서버 알림 설정(VAPID) 점검이 필요해요. 로컬 알림이 보였다면 브라우저 쪽은 정상이에요.",
        );
      } else {
        setMessage("등록된 기기가 없어요 — 알림을 다시 켜주세요.");
      }
    } catch {
      setMessage("테스트 발송에 실패했어요.");
    }
    setBusy(false);
  }

  if (state === "loading" || state === "disabled") return null;

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">알림</p>
      <p className="mb-3 text-xs opacity-60">
        이 기기(브라우저)에서 받는 알림을 한 번에 켜고 꺼요. 탭이 백그라운드거나
        브라우저를 닫아도 도착해요.
      </p>

      {state === "unsupported" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          이 브라우저는 푸시 알림을 지원하지 않아요. iPhone은 사파리 공유 →
          &ldquo;홈 화면에 추가&rdquo; 후 앱에서 켤 수 있어요.
        </p>
      )}
      {state === "denied" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          알림이 차단되어 있어요 — 브라우저 주소창의 사이트 설정에서 알림을
          허용한 뒤 다시 시도해주세요.
        </p>
      )}

      {(state === "idle" || state === "subscribed") && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={toggle}
              aria-pressed={state === "subscribed"}
              className={`min-h-11 rounded-md border-2 px-4 text-sm font-bold transition disabled:opacity-50 ${
                state === "subscribed"
                  ? "border-brick-green bg-brick-green/10 text-brick-green"
                  : "border-ink/20 bg-white hover:border-ink/50"
              }`}
            >
              {state === "subscribed"
                ? "이 기기에서 알림 받는 중"
                : "이 기기에서 알림 받기"}
            </button>
            {state === "subscribed" && (
              <button
                type="button"
                disabled={busy}
                onClick={handleTest}
                className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50 disabled:opacity-50"
              >
                테스트 알림 보내기
              </button>
            )}
          </div>

          {/* 이 스위치 하나로 받게 되는 것들 — 종류별 스위치가 아니라 안내 목록 */}
          <ul className="mt-3 flex flex-col gap-1 rounded-md border-2 border-ink/10 bg-white p-3 text-xs">
            <li className="mb-1 font-bold opacity-70">이 알림으로 받아요</li>
            <li>· 채팅 새 글 — 친구가 보낸 메시지</li>
            <li>· 게임 초대 — 친구의 대전 초대</li>
            <li>
              · 복습 리마인더 — 매일 {fmtHour(reminderHour ?? 20)}, 밀린 복습이
              있을 때만
            </li>
            <li className="mt-1 opacity-50">
              접속 중 소식(시험 1위 탈환 등)은 상단 벨로 도착해요
            </li>
          </ul>

          {/* 언제 공부하는 사람인지는 사용자가 안다 — 리마인더 시각을 생활
              리듬에 맞춘다 (기본 저녁 8시) */}
          {reminderHour != null && (
            <label className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className="font-bold">복습 리마인더 시각</span>
              <select
                value={reminderHour}
                disabled={busy}
                onChange={(e) => changeReminderHour(Number(e.target.value))}
                className="min-h-9 rounded-md border-2 border-ink/20 bg-white px-2 font-bold"
              >
                {REMINDER_HOURS.map((h) => (
                  <option key={h} value={h}>
                    {fmtHour(h)}
                  </option>
                ))}
              </select>
              <span className="opacity-50">내 공부 시간에 맞춰 도착해요</span>
            </label>
          )}
        </>
      )}
      {message && <p className="mt-2 text-xs opacity-70">{message}</p>}
      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event("esl-open-notif-guide"))}
        className="mt-3 text-xs font-bold text-brick-blue hover:underline"
      >
        알림이 안 와요 — 설정 가이드 보기 (Mac/Windows/모바일)
      </button>
    </section>
  );
}

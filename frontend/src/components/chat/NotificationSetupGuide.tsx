"use client";

import { useEffect, useState } from "react";
import { fetchMe } from "@/lib/api";
import {
  getPushState,
  PUSH_CHANGED_EVENT,
  type PushState,
  showLocalTestNotification,
  subscribePush,
} from "@/lib/push";

/** 알림 설정 온보딩 — 1회 팝업 (2026-07-31 요청, Slack/Notion 프라이머 참고).
 *
 *  백그라운드(다른 탭·다른 앱·모바일)에선 OS 알림/웹푸시가 유일한 채널인데
 *  권한·OS 설정 두 단계가 다 필요해 사용자가 놓친다. 플랫폼(맥/윈도우/안드/iOS)
 *  을 감지해 해당 안내만 보여주고, [알림 켜기]가 권한 요청 + 푸시 구독을
 *  한 번에 처리한다. Mac/Windows 는 실제 OS 알림 설정 화면 딥링크 버튼 제공,
 *  권한이 이미 있으면 [테스트 알림]으로 OS 차단 여부를 즉석 진단 (2차 피드백).
 *  노출 1회 (localStorage), 설정에서 다시 열기 이벤트 지원. */

const SEEN_KEY = "notif-guide-seen";
export const OPEN_GUIDE_EVENT = "esl-open-notif-guide";

type Platform = "mac" | "windows" | "android" | "ios" | "other";

function detectPlatform(): Platform {
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/.test(ua)) return "ios";
  if (/Android/.test(ua)) return "android";
  if (/Macintosh/.test(ua)) return "mac";
  if (/Windows/.test(ua)) return "windows";
  return "other";
}

/** iOS Safari 탭 등 Notification 전역이 없는 환경에서 bare 참조는 throw */
function notifPermission(): NotificationPermission | "unsupported" {
  return typeof Notification === "undefined"
    ? "unsupported"
    : Notification.permission;
}

const OS_STEPS: Record<
  Platform,
  {
    title: string;
    steps: string[];
    // OS 알림 설정 화면 딥링크 — 브라우저가 "설정 앱을 열까요?" 확인 후 이동
    settings?: { label: string; uri: string };
  }
> = {
  mac: {
    title: "Mac 사용 중이시네요",
    steps: [
      "아래 [알림 켜기]를 누르고 브라우저 요청에서 '허용'을 선택하세요",
      "아래 [Mac 알림 설정 열기]에서 사용 중인 브라우저(Chrome/Safari)를 찾아 '알림 허용'을 켜주세요",
      "집중 모드(방해금지)가 켜져 있으면 알림이 조용히 숨겨져요 — 확인!",
    ],
    settings: {
      label: "Mac 알림 설정 열기",
      uri: "x-apple.systempreferences:com.apple.preference.notifications",
    },
  },
  windows: {
    title: "Windows 사용 중이시네요",
    steps: [
      "아래 [알림 켜기]를 누르고 브라우저 요청에서 '허용'을 선택하세요",
      "아래 [Windows 알림 설정 열기]에서 브라우저 알림이 켜져 있는지 확인하세요",
      "집중 지원(방해 금지 모드)이 켜져 있으면 알림이 숨겨져요 — 확인!",
    ],
    settings: {
      label: "Windows 알림 설정 열기",
      uri: "ms-settings:notifications",
    },
  },
  android: {
    title: "Android 사용 중이시네요",
    steps: [
      "아래 [알림 켜기]를 누르고 '허용'을 선택하세요",
      "Android 설정 > 애플리케이션 > Chrome > 알림이 켜져 있어야 해요",
      "절전 모드가 세면 알림이 늦을 수 있어요 — Chrome 배터리 제한 해제 권장",
    ],
  },
  ios: {
    title: "iPhone/iPad 사용 중이시네요",
    steps: [
      "iOS 는 홈 화면에 추가한 앱만 알림을 받을 수 있어요 (Apple 정책)",
      "Safari 공유 버튼 > '홈 화면에 추가'를 눌러 설치하세요",
      "홈 화면 아이콘으로 연 뒤, 이 안내에서 [알림 켜기]를 눌러주세요",
    ],
  },
  other: {
    title: "알림 설정",
    steps: [
      "아래 [알림 켜기]를 누르고 브라우저 요청에서 '허용'을 선택하세요",
      "OS 알림 설정에서 브라우저 알림이 켜져 있는지 확인하세요",
    ],
  },
};

/** 차단(denied) 해제 경로 — 기종별. 웹에서 Android/iOS 설정 딥링크는 불가 */
const DENIED_STEPS: Record<Platform, string[]> = {
  mac: [
    "주소창 왼쪽 자물쇠 > 알림을 [허용]으로 바꾼 뒤 새로고침",
    "그래도 안 되면 아래 [Mac 알림 설정 열기]에서 브라우저 알림 허용",
  ],
  windows: [
    "주소창 왼쪽 자물쇠 > 알림을 [허용]으로 바꾼 뒤 새로고침",
    "그래도 안 되면 아래 [Windows 알림 설정 열기]에서 브라우저 알림 허용",
  ],
  android: [
    "주소창 왼쪽 자물쇠(또는 ⓘ) > 권한 > 알림을 허용으로",
    "안 보이면 Chrome ⋮ 메뉴 > 설정 > 사이트 설정 > 알림 > 이 사이트 허용",
    "Android 설정 > 애플리케이션 > Chrome > 알림도 켜져 있어야 해요",
    "바꾼 뒤 [다시 시도]를 눌러주세요",
  ],
  ios: [
    "홈 화면에 추가한 앱으로 열었는지 확인하세요 (Safari 탭은 알림 불가)",
    "iOS 설정 > 알림에서 이 앱을 허용으로",
    "바꾼 뒤 [다시 시도]를 눌러주세요",
  ],
  other: ["브라우저 사이트 설정에서 알림을 허용한 뒤 [다시 시도]를 눌러주세요"],
};

export function NotificationSetupGuide() {
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState<Platform>("other");
  const [phase, setPhase] = useState<"ask" | "denied" | "done">("ask");
  const [testResult, setTestResult] = useState<"sent" | "blocked" | null>(null);
  // 버튼 분기 기준은 권한이 아니라 "구독" — 권한 granted + 구독 해제 상태에서
  // [알림 켜기]가 사라지면 재구독 경로가 없다 (2026-07-31 재검토)
  const [pushState, setPushState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  // "아무 반응 없음" 방지 — unsupported/disabled/오류도 반드시 눈에 보이는 결과로
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    const detected = detectPlatform();
    setPlatform(detected);
    // 설정 화면의 "가이드 다시 보기" — 언제든 재오픈
    const refreshPush = () =>
      getPushState()
        .then(setPushState)
        .catch(() => setPushState("unsupported"));
    refreshPush();
    window.addEventListener(PUSH_CHANGED_EVENT, refreshPush);
    const reopen = () => {
      setTestResult(null);
      refreshPush();
      setPhase(notifPermission() === "denied" ? "denied" : "ask");
      setOpen(true);
    };
    window.addEventListener(OPEN_GUIDE_EVENT, reopen);

    // 1회 자동 노출 — 로그인 + 권한 미허용 + 처음.
    // Notification 전역이 없어도 iOS 는 노출한다 — "홈 화면에 추가" 안내가
    // 가장 필요한 대상이 바로 API 없는 iOS Safari 탭이다 (2026-07-31 재검토)
    const permission = notifPermission();
    const autoShow =
      permission !== "granted" &&
      (permission !== "unsupported" || detected === "ios") &&
      !localStorage.getItem(SEEN_KEY);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (autoShow) {
      timer = setTimeout(() => {
        fetchMe().then((me) => {
          if (me && !cancelled) {
            setPhase(notifPermission() === "denied" ? "denied" : "ask");
            setOpen(true);
          }
        });
      }, 2500);
    }
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener(PUSH_CHANGED_EVENT, refreshPush);
      window.removeEventListener(OPEN_GUIDE_EVENT, reopen);
    };
  }, []);

  function dismiss() {
    localStorage.setItem(SEEN_KEY, "1");
    setOpen(false);
  }

  async function enable() {
    setBusy(true);
    setFeedback(null);
    try {
      const state = await subscribePush();
      setPushState(state);
      if (state === "subscribed") {
        setPhase("done");
        setTimeout(dismiss, 2500);
      } else if (state === "denied") {
        setPhase("denied");
      } else if (state === "unsupported") {
        setFeedback(
          platform === "ios"
            ? "이 Safari 탭에서는 알림을 켤 수 없어요 — 위 단계대로 홈 화면에 추가한 앱에서 켜주세요."
            : "이 브라우저는 웹 알림을 지원하지 않아요 — 다른 브라우저(Chrome 등)를 사용해주세요.",
        );
      } else if (state === "disabled") {
        setFeedback("서버 알림 설정이 꺼져 있어요 — 관리자에게 문의해주세요.");
      }
    } catch {
      if (notifPermission() === "denied") setPhase("denied");
      else setFeedback("알림 켜기에 실패했어요 — 잠시 후 다시 시도해주세요.");
    }
    setBusy(false);
  }

  async function sendTest() {
    // 권한은 있는데 알림이 안 보이는 원인 분리 — 로컬 표시가 실패하면
    // 서버가 아니라 OS/브라우저 설정 문제다 (push.ts 진단 헬퍼 재사용)
    const shown = await showLocalTestNotification();
    setTestResult(shown ? "sent" : "blocked");
  }

  if (!open) return null;
  const guide = OS_STEPS[platform];
  const settingsLink = guide.settings;
  const subscribed = pushState === "subscribed";

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/30 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-lg border-2 border-ink/15 bg-white p-5 shadow-xl">
        {phase === "done" ? (
          <p className="py-4 text-center font-bold text-brick-green">
            알림이 켜졌어요! 이제 다른 탭·앱에 있어도 소식을 받아요
          </p>
        ) : (
          <>
            <p className="font-hand text-xl font-bold">
              알림을 켜면 놓치지 않아요
            </p>
            <p className="mt-1 text-sm opacity-70">
              채팅·게임 초대·시험 1위 탈환 소식 — 다른 탭이나 앱에 있어도
              알려드려요. {guide.title}:
            </p>
            <ol className="mt-3 flex flex-col gap-1.5 text-sm">
              {guide.steps.map((step, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="font-bold text-brick-blue">{idx + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            {phase === "denied" && (
              <div className="mt-3 rounded-md bg-brick-red/10 p-2 text-xs text-brick-red">
                <p className="font-bold">알림이 차단된 상태예요 — 해제 방법:</p>
                <ol className="mt-1 flex flex-col gap-0.5">
                  {DENIED_STEPS[platform].map((step, idx) => (
                    <li key={idx}>
                      {idx + 1}. {step}
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {feedback && (
              <p className="mt-3 rounded-md bg-brick-red/10 p-2 text-xs text-brick-red">
                {feedback}
              </p>
            )}
            {testResult === "sent" && (
              <p className="mt-3 rounded-md bg-brick-green/10 p-2 text-xs text-brick-green">
                테스트 알림을 보냈어요 — 화면 구석에 안 보이면 OS 알림 설정에서
                브라우저가 허용돼 있는지 확인해주세요.
              </p>
            )}
            {testResult === "blocked" && (
              <p className="mt-3 rounded-md bg-brick-red/10 p-2 text-xs text-brick-red">
                브라우저가 알림을 표시하지 못했어요 — OS 알림 설정에서 사용 중인
                브라우저를 허용으로 켜주세요.
              </p>
            )}
            {settingsLink && (
              <button
                type="button"
                onClick={() => {
                  // 커스텀 스킴 — 브라우저가 "설정 앱을 열까요?" 확인 후
                  // 실제 OS 알림 설정 화면으로 이동 (페이지는 유지됨)
                  window.location.href = settingsLink.uri;
                }}
                className="mt-3 flex min-h-10 w-full items-center justify-center rounded-md border-2 border-brick-blue/50 bg-brick-blue/5 text-sm font-bold text-brick-blue transition hover:bg-brick-blue/10"
              >
                {settingsLink.label}
              </button>
            )}
            <div className="mt-3 flex gap-2">
              {subscribed && phase !== "denied" ? (
                <button
                  type="button"
                  onClick={sendTest}
                  className="min-h-11 flex-1 rounded-md bg-brick-green font-bold text-brick-label transition hover:opacity-90"
                >
                  테스트 알림 보내기
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  onClick={enable}
                  className="min-h-11 flex-1 rounded-md bg-brick-green font-bold text-brick-label transition hover:opacity-90 disabled:opacity-50"
                >
                  {busy
                    ? "켜는 중..."
                    : phase === "denied"
                      ? "다시 시도"
                      : "알림 켜기"}
                </button>
              )}
              <button
                type="button"
                onClick={dismiss}
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white font-bold"
              >
                {subscribed ? "닫기" : "나중에"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

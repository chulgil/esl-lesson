"use client";

import { useEffect, useState } from "react";
import { fetchMe } from "@/lib/api";
import { subscribePush } from "@/lib/push";

/** 알림 설정 온보딩 — 1회 팝업 (2026-07-31 요청, Slack/Notion 프라이머 참고).
 *
 *  백그라운드(다른 탭·다른 앱·모바일)에선 OS 알림/웹푸시가 유일한 채널인데
 *  권한·OS 설정 두 단계가 다 필요해 사용자가 놓친다. 플랫폼(맥/윈도우/안드/iOS)
 *  을 감지해 해당 안내만 보여주고, [알림 켜기]가 권한 요청 + 푸시 구독을
 *  한 번에 처리한다. 노출 1회 (localStorage), 설정에서 다시 열기 이벤트 지원. */

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

const OS_STEPS: Record<Platform, { title: string; steps: string[] }> = {
  mac: {
    title: "Mac 사용 중이시네요",
    steps: [
      "아래 [알림 켜기]를 누르고 브라우저 요청에서 '허용'을 선택하세요",
      "Mac 시스템 설정 > 알림 > 사용 중인 브라우저를 '허용'으로 켜주세요",
      "집중 모드(방해금지)가 켜져 있으면 알림이 조용히 숨겨져요 — 확인!",
    ],
  },
  windows: {
    title: "Windows 사용 중이시네요",
    steps: [
      "아래 [알림 켜기]를 누르고 브라우저 요청에서 '허용'을 선택하세요",
      "Windows 설정 > 시스템 > 알림에서 브라우저 알림을 켜주세요",
      "집중 지원(방해 금지 모드)이 켜져 있으면 알림이 숨겨져요 — 확인!",
    ],
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

export function NotificationSetupGuide() {
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState<Platform>("other");
  const [phase, setPhase] = useState<"ask" | "denied" | "done">("ask");

  useEffect(() => {
    setPlatform(detectPlatform());
    // 설정 화면의 "가이드 다시 보기" — 언제든 재오픈
    const reopen = () => {
      setPhase(
        typeof Notification !== "undefined" &&
          Notification.permission === "denied"
          ? "denied"
          : "ask",
      );
      setOpen(true);
    };
    window.addEventListener(OPEN_GUIDE_EVENT, reopen);

    // 1회 자동 노출 — 로그인 + 권한 미허용 + 처음
    if (typeof Notification === "undefined") return; // 미지원(iOS Safari 탭 등)도 안내는 가치有 — 단 API 없으면 자동노출 생략
    if (Notification.permission === "granted") return;
    if (localStorage.getItem(SEEN_KEY)) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchMe().then((me) => {
        if (me && !cancelled) {
          setPhase(Notification.permission === "denied" ? "denied" : "ask");
          setOpen(true);
        }
      });
    }, 2500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      window.removeEventListener(OPEN_GUIDE_EVENT, reopen);
    };
  }, []);

  function dismiss() {
    localStorage.setItem(SEEN_KEY, "1");
    setOpen(false);
  }

  async function enable() {
    try {
      const state = await subscribePush();
      if (state === "subscribed" || Notification.permission === "granted") {
        setPhase("done");
        setTimeout(dismiss, 2500);
      } else {
        setPhase("denied");
      }
    } catch {
      setPhase(Notification.permission === "denied" ? "denied" : "ask");
    }
  }

  if (!open) return null;
  const guide = OS_STEPS[platform];

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
              <p className="mt-3 rounded-md bg-brick-red/10 p-2 text-xs text-brick-red">
                브라우저에서 알림이 차단된 상태예요 — 주소창의 자물쇠(사이트
                설정) &gt; 알림을 [허용]으로 바꾼 뒤 새로고침하면 켤 수 있어요.
              </p>
            )}
            <div className="mt-4 flex gap-2">
              {phase !== "denied" && (
                <button
                  type="button"
                  onClick={enable}
                  className="min-h-11 flex-1 rounded-md bg-brick-green font-bold text-brick-label transition hover:opacity-90"
                >
                  알림 켜기
                </button>
              )}
              <button
                type="button"
                onClick={dismiss}
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white font-bold"
              >
                나중에
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

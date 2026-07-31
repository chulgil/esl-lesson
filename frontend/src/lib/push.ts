/** 웹 푸시 구독 클라이언트 (docs/specs/push-reminder.md) */

/** 구독 상태 변경 브로드캐스트 — 가이드·설정 카드·대화 목록 버튼이 서로의
 *  구독/해제를 즉시 반영하도록 (2026-07-31 재검토: 카드 상태 고착 수정) */
export const PUSH_CHANGED_EVENT = "esl-push-changed";

function broadcastPushChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(PUSH_CHANGED_EVENT));
  }
}

export type PushState =
  | "unsupported" // 브라우저 미지원 (iOS 사파리는 홈 화면 추가 후 가능)
  | "disabled" // 서버 VAPID 미설정
  | "denied" // 사용자가 알림 차단
  | "subscribed"
  | "idle";

function supported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

async function fetchConfig(): Promise<{
  enabled: boolean;
  public_key: string;
}> {
  const res = await fetch("/api/push/config", { credentials: "same-origin" });
  if (!res.ok) return { enabled: false, public_key: "" };
  return res.json();
}

/** base64url → Uint8Array (applicationServerKey 포맷) */
function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const output = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

export async function getPushState(): Promise<PushState> {
  if (!supported()) return "unsupported";
  const config = await fetchConfig();
  if (!config.enabled) return "disabled";
  if (Notification.permission === "denied") return "denied";
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  return sub ? "subscribed" : "idle";
}

export async function subscribePush(): Promise<PushState> {
  if (!supported()) return "unsupported";
  const config = await fetchConfig();
  if (!config.enabled) return "disabled";

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";

  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(config.public_key),
    }));

  const json = sub.toJSON();
  const res = await fetch("/api/push/subscriptions", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
    }),
  });
  if (!res.ok) {
    await sub.unsubscribe().catch(() => undefined);
    throw new Error("subscription save failed");
  }
  broadcastPushChanged();
  return "subscribed";
}

export async function unsubscribePush(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  if (!sub) return;
  await fetch("/api/push/subscriptions", {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: sub.endpoint }),
  }).catch(() => undefined);
  await sub.unsubscribe().catch(() => undefined);
  broadcastPushChanged();
}

export async function sendTestPush(): Promise<{
  sent: number;
  errors: number;
}> {
  const res = await fetch("/api/push/test", {
    method: "POST",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("test push failed");
  const body = await res.json();
  return { sent: body.sent as number, errors: (body.errors as number) ?? 0 };
}

/** 서버를 거치지 않는 로컬 알림 — OS/브라우저 표시 차단 여부를 분리 진단.
 *  이게 안 보이면 서버 문제가 아니라 OS 알림 설정 문제다. */
export async function showLocalTestNotification(): Promise<boolean> {
  if (!supported() || Notification.permission !== "granted") return false;
  const body = "로컬 테스트 — 이 알림이 보이면 브라우저 표시는 정상이에요";
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    if (reg) {
      await reg.showNotification("ESL Lessonaza", { body, tag: "local-test" });
    } else {
      new Notification("ESL Lessonaza", { body, tag: "local-test" });
    }
    return true;
  } catch {
    return false;
  }
}

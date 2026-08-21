"use client";

/** 구매 확인 다이얼로그 — 현재 XP·가격·구매 후 잔액을 보여주고 확정받는다
 *  (2026-08-21 사용자 요청). XP 부족이면 부족분과 모으는 방법을 안내한다.
 *  bg-paper + text-ink 명시 — 오버레이 절연 계약 (ui-design.md). */
export function PurchaseConfirmDialog({
  label,
  priceXp,
  availableXp,
  busy,
  onConfirm,
  onClose,
}: {
  label: string;
  priceXp: number;
  availableXp: number;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const enough = availableXp >= priceXp;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 px-6"
      onClick={busy ? undefined : onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-sm rounded-lg border-2 border-ink/15 bg-paper p-5 text-ink shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="구매 확인"
      >
        {enough ? (
          <>
            <p className="font-bold">{label} — 구매할까요?</p>
            <dl className="mt-3 flex flex-col gap-1.5 rounded-md border-2 border-ink/10 bg-white p-3 text-sm">
              <div className="flex justify-between">
                <dt className="opacity-60">현재 보유</dt>
                <dd className="font-bold">{availableXp.toLocaleString()} XP</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-60">가격</dt>
                <dd className="font-bold text-brick-red">
                  -{priceXp.toLocaleString()} XP
                </dd>
              </div>
              <div className="flex justify-between border-t border-ink/10 pt-1.5">
                <dt className="opacity-60">구매 후 남는 XP</dt>
                <dd className="font-bold text-brick-blue">
                  {(availableXp - priceXp).toLocaleString()} XP
                </dd>
              </div>
            </dl>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={busy}
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white text-sm font-bold opacity-80 transition hover:border-ink/50 disabled:opacity-40"
              >
                취소
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={busy}
                className="min-h-11 flex-1 rounded-md bg-brick-green text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85 disabled:opacity-60"
              >
                {busy ? "구매 중..." : "구매하기"}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="font-bold">XP가 부족해요</p>
            <p className="mt-2 text-sm">
              {label}은(는) <b>{priceXp.toLocaleString()} XP</b>인데 지금{" "}
              <b>{availableXp.toLocaleString()} XP</b>가 있어요 —{" "}
              <b className="text-brick-red">
                {(priceXp - availableXp).toLocaleString()} XP
              </b>{" "}
              더 필요해요.
            </p>
            <p className="mt-1.5 text-xs opacity-60">
              복습·게임·오늘의 미션으로 XP를 모을 수 있어요.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-4 min-h-11 w-full rounded-md border-2 border-ink/20 bg-white text-sm font-bold transition hover:border-ink/50"
            >
              닫기
            </button>
          </>
        )}
      </div>
    </div>
  );
}

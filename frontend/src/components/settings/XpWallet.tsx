/** 보유 XP 지갑 — 상점 구매 시 한눈에 보이는 잔액 카드 (2026-08-11 보고:
 *  "보유 XP 표기가 직관적이지 않아 구매할 때 보기 힘들다").
 *  테마 상점·캐릭터 상점 상단 공용 — 같은 잔액을 두 곳에서 같은 모양으로. */
export function XpWallet({ amount }: { amount: number }) {
  return (
    <div className="mb-3 inline-flex items-center gap-2 rounded-lg border-2 border-brick-yellow/60 bg-highlight/40 px-3 py-1.5">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-brick-yellow text-[10px] font-black text-brick-label">
        XP
      </span>
      <span className="text-xs opacity-70">내 XP</span>
      <b className="text-lg leading-none">{amount.toLocaleString()}</b>
    </div>
  );
}

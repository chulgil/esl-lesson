"use client";

import { useEffect, useState } from "react";
import { PurchaseConfirmDialog } from "@/components/shop/PurchaseConfirmDialog";
import {
  MESSAGE_MAX_WIDTH,
  MascotSvg,
  messageWidthUnits,
} from "@/components/theme/mascots";
import {
  SHOP_EVENT,
  dispatchShopUpdated,
  shopApi,
  type ShopCatalog,
} from "@/lib/shop-api";

/** 캐릭터 상점 — 마스코트·악세사리·책갈피를 XP 로 구매 (docs/specs/mascot-shop.md).
 *
 *  산 캐릭터는 즉시 좌하단에 나타나고(자동 활성), 악세사리는 탭으로
 *  착용/해제한다 (2026-08-21 토글 — 구 all-on 정책 개정). 모든 구매는
 *  확인 다이얼로그를 거친다 — 현재 XP·가격·구매 후 잔액을 보고 확정. */
export function MascotShopSection() {
  const [shop, setShop] = useState<ShopCatalog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // 구매 확인 다이얼로그 — run 이 실제 구매를 실행 (마스코트·악세·책갈피 공용)
  const [confirm, setConfirm] = useState<{
    label: string;
    price: number;
    run: () => Promise<void>;
  } | null>(null);
  // 말풍선 문구 변경 다이얼로그 (변경권 1개 소모 — 신중 안내 포함)
  const [messageDialog, setMessageDialog] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");

  const load = () =>
    shopApi
      .catalog()
      .then(setShop)
      .catch(() => setShop(null));

  useEffect(() => {
    load();
    // 테마 구매로 XP 를 써도 이쪽 잔액·버튼 활성이 즉시 맞아야 한다 (버그 헌트 2026-08-11)
    window.addEventListener(SHOP_EVENT, load);
    return () => window.removeEventListener(SHOP_EVENT, load);
  }, []);

  if (!shop) return null;

  const wornOutfits = shop.outfits
    .filter((o) => o.worn ?? o.owned)
    .map((o) => o.key);

  function fail(e: unknown) {
    const code = e instanceof Error ? e.message : "실패";
    setNotice(
      {
        insufficient_xp: "XP가 부족해요 — 복습·게임으로 더 모을 수 있어요",
        already_owned: "이미 보유한 아이템이에요",
        saver_full: "책갈피는 최대 2개까지 보관돼요",
        item_not_found: "존재하지 않는 아이템이에요",
        event_only_item: "이벤트로만 받을 수 있는 아이템이에요",
        not_owned: "먼저 구매해야 착용할 수 있어요",
        no_ticket: "말풍선 변경권이 필요해요 — 먼저 구매해주세요",
        invalid_message:
          "문구가 너무 길거나 쓸 수 없는 문자가 있어요 — 한글 6자·영문 12자까지, 특수문자 불가",
      }[code] ?? "구매에 실패했어요 — 잠시 후 다시 시도해주세요.",
    );
  }

  async function buy(itemKey: string) {
    setBusy(itemKey);
    setNotice(null);
    try {
      await shopApi.purchase(itemKey);
      await load();
      dispatchShopUpdated(); // 좌하단 마스코트 즉시 갱신
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function activate(key: string | null) {
    setBusy(`activate:${key}`);
    setNotice(null);
    try {
      await shopApi.setMascot(key);
      await load();
      dispatchShopUpdated();
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function toggleOutfit(key: string, worn: boolean) {
    setBusy(`wear:${key}`);
    setNotice(null);
    try {
      await shopApi.setOutfit(key, worn);
      await load();
      dispatchShopUpdated(); // 좌하단·런처의 착용 상태 즉시 갱신
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function buySaver() {
    setBusy("saver");
    setNotice(null);
    try {
      await shopApi.buySaver();
      await load();
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function buyMessageTicket() {
    setBusy("message-ticket");
    setNotice(null);
    try {
      await shopApi.buyMessageTicket();
      await load();
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  async function applyMessage(message: string | null) {
    setBusy("message-apply");
    setNotice(null);
    try {
      await shopApi.setMascotMessage(message);
      await load();
      dispatchShopUpdated(); // 좌하단·런처 말풍선 즉시 갱신
      setMessageDialog(false);
    } catch (e) {
      fail(e);
    }
    setBusy(null);
  }

  return (
    <section className="mt-8">
      <p className="mb-1 text-sm font-bold">캐릭터</p>
      <p className="mb-2 text-xs opacity-60">
        XP로 캐릭터를 데려와요 — 채팅 버튼과 화면 곳곳에서 함께 공부해요.
      </p>
      {notice && <p className="mb-2 text-xs text-brick-red">{notice}</p>}

      {/* 마스코트 — 미리보기 + 구매/활성. 수집 도감식: 보유/미보유가 한눈에 */}
      {shop.mascots.length === 0 ? (
        <p className="rounded-lg border-2 border-ink/10 bg-white p-3 text-xs opacity-60">
          지금은 판매 중인 캐릭터가 없어요
        </p>
      ) : (
        <div className="flex flex-wrap gap-3">
          {shop.mascots.map((m) => {
            const active = shop.active_mascot === m.key;
            return (
              <div
                key={m.key}
                className={`flex w-40 flex-col items-center gap-2 rounded-lg border-2 bg-white p-3 ${
                  active ? "border-brick-blue" : "border-ink/10"
                }`}
              >
                <div
                  className={`origin-bottom scale-90 ${m.owned ? "" : "opacity-40 grayscale"}`}
                >
                  <MascotSvg
                    kind={m.key}
                    outfits={m.owned ? wornOutfits : []}
                    message={
                      m.owned ? shop.message_ticket.current_message : null
                    }
                  />
                </div>
                <p className="text-sm font-bold">{m.label}</p>
                {m.owned ? (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => activate(active ? null : m.key)}
                    className={`min-h-9 w-full rounded-full border-2 text-xs font-bold transition ${
                      active
                        ? "border-ink/20 bg-ink/5"
                        : "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                    }`}
                  >
                    {active ? "쉬게 하기" : "데려오기"}
                  </button>
                ) : m.sale === "event" ? (
                  <span className="grid min-h-9 w-full place-items-center rounded-full border-2 border-brick-yellow/60 bg-highlight/40 text-xs font-bold">
                    이벤트 한정
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() =>
                      setConfirm({
                        label: m.label,
                        price: m.price_xp,
                        run: () => buy(`mascot:${m.key}`),
                      })
                    }
                    className={`min-h-9 w-full rounded-full border-2 text-xs font-bold transition ${
                      shop.available_xp >= m.price_xp
                        ? "border-brick-blue bg-brick-blue/10 text-brick-blue hover:-translate-y-0.5"
                        : "border-ink/15 opacity-50"
                    }`}
                  >
                    {busy === `mascot:${m.key}`
                      ? "구매 중..."
                      : `${m.price_xp.toLocaleString()} XP`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 악세사리 — 보유한 것은 탭으로 착용/해제 (2026-08-21 토글) */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">
        악세사리 — 산 악세사리는 탭해서 착용하거나 벗길 수 있어요
      </p>
      {shop.outfits.length === 0 ? (
        <p className="rounded-lg border-2 border-ink/10 bg-white p-3 text-xs opacity-60">
          악세사리가 없어요
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {shop.outfits.map((o) => {
            const worn = o.worn ?? o.owned;
            return (
              <button
                key={o.key}
                type="button"
                disabled={busy !== null || (!o.owned && o.sale === "event")}
                onClick={() =>
                  o.owned
                    ? toggleOutfit(o.key, !worn)
                    : setConfirm({
                        label: `악세사리 ${o.label}`,
                        price: o.price_xp,
                        run: () => buy(`outfit:${o.key}`),
                      })
                }
                className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
                  o.owned
                    ? worn
                      ? "border-brick-green bg-brick-green/15 text-brick-green"
                      : "border-ink/25 bg-white opacity-70 hover:border-brick-green/60"
                    : o.sale === "event"
                      ? "border-brick-yellow/60 bg-highlight/40"
                      : shop.available_xp >= o.price_xp
                        ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                        : "border-ink/15 opacity-50"
                }`}
              >
                {o.label}{" "}
                {o.owned
                  ? busy === `wear:${o.key}`
                    ? "..."
                    : worn
                      ? "착용 중"
                      : "벗음"
                  : o.sale === "event"
                    ? "이벤트 한정"
                    : busy === `outfit:${o.key}`
                      ? "구매 중..."
                      : `${o.price_xp.toLocaleString()} XP`}
              </button>
            );
          })}
        </div>
      )}

      {/* 책갈피 충전 — 손실 회피 상품 (벤치마크 1순위) */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">책갈피 충전</p>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="opacity-70">
          보유 {shop.streak_saver.count}/{shop.streak_saver.max} — 놓친 날
          자동으로 끼워져 연속 학습을 지켜줘요
        </span>
        <button
          type="button"
          disabled={
            busy !== null || shop.streak_saver.count >= shop.streak_saver.max
          }
          onClick={() =>
            setConfirm({
              label: "책갈피 1개 충전",
              price: shop.streak_saver.price_xp,
              run: buySaver,
            })
          }
          className={`min-h-9 rounded-full border-2 px-3 font-bold transition ${
            shop.streak_saver.count >= shop.streak_saver.max
              ? "border-ink/15 opacity-50"
              : shop.available_xp >= shop.streak_saver.price_xp
                ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                : "border-ink/15 opacity-50"
          }`}
        >
          {busy === "saver"
            ? "구매 중..."
            : `${shop.streak_saver.price_xp} XP로 1개 충전`}
        </button>
      </div>

      {/* 말풍선 문구 변경권 — 소모성 1회권 (2026-08-21 요청) */}
      <p className="mt-4 mb-1 text-xs font-bold opacity-70">말풍선 문구 변경권</p>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="opacity-70">
          보유 {shop.message_ticket.count}개 — 캐릭터 말풍선 문구를 바꿀 수 있어요
          (한글 6자·영문 12자까지)
          {shop.message_ticket.current_message &&
            ` · 현재 "${shop.message_ticket.current_message}"`}
        </span>
        {shop.message_ticket.sale === "event" ? (
          <span className="rounded-full border-2 border-brick-yellow/60 bg-highlight/40 px-3 py-1 font-bold">
            이벤트 한정
          </span>
        ) : (
          <button
            type="button"
            disabled={busy !== null}
            onClick={() =>
              setConfirm({
                label: "말풍선 변경권 1개",
                price: shop.message_ticket.price_xp,
                run: buyMessageTicket,
              })
            }
            className={`min-h-9 rounded-full border-2 px-3 font-bold transition ${
              shop.available_xp >= shop.message_ticket.price_xp
                ? "border-brick-blue/50 bg-white text-brick-blue hover:-translate-y-0.5"
                : "border-ink/15 opacity-50"
            }`}
          >
            {busy === "message-ticket"
              ? "구매 중..."
              : `${shop.message_ticket.price_xp.toLocaleString()} XP로 1개 구매`}
          </button>
        )}
        <button
          type="button"
          disabled={busy !== null || shop.message_ticket.count === 0}
          onClick={() => {
            setDraftMessage("");
            setMessageDialog(true);
          }}
          className={`min-h-9 rounded-full border-2 px-3 font-bold transition ${
            shop.message_ticket.count > 0
              ? "border-brick-green/60 bg-white text-brick-green hover:-translate-y-0.5"
              : "border-ink/15 opacity-50"
          }`}
        >
          문구 바꾸기{shop.message_ticket.count === 0 ? " (변경권 필요)" : ""}
        </button>
        {shop.message_ticket.current_message && (
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => applyMessage(null)}
            className="min-h-9 rounded-full border-2 border-ink/20 bg-white px-3 font-bold opacity-70 transition hover:border-ink/50"
          >
            기본 문구로 (무료)
          </button>
        )}
      </div>

      {/* 문구 변경 다이얼로그 — 변경권 소모 전 신중 안내 (오버레이 절연 계약) */}
      {messageDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 px-6"
          onClick={() => busy === null && setMessageDialog(false)}
          role="presentation"
        >
          <div
            className="w-full max-w-sm rounded-lg border-2 border-ink/15 bg-paper p-5 text-ink shadow-xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="말풍선 문구 바꾸기"
          >
            <p className="font-bold">말풍선 문구 바꾸기</p>
            <p className="mt-2 text-sm">
              캐릭터가 말풍선에 이 문구를 들고 다녀요 — 한글 최대 6자, 영어·숫자 최대 12자 (일본어 가능, 특수문자 불가).
            </p>
            <p className="mt-1.5 rounded-md border-2 border-brick-yellow/60 bg-highlight/30 p-2.5 text-xs">
              변경권 <b>1개가 사용</b>돼요. 다시 바꾸려면 새 변경권이 필요하니
              <b> 신중하게</b> 정해주세요. (기본 문구로 되돌리기는 무료)
            </p>
            <input
              type="text"
              value={draftMessage}
              onChange={(e) => {
                // 허용 문자만(특수문자·이모지 차단) + 폭 한도까지 자름
                let next = e.target.value.replace(
                  /[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9 !?.,~^+\-\u3040-\u30ff\u4e00-\u9fffー]/g,
                  "",
                );
                while (messageWidthUnits(next) > MESSAGE_MAX_WIDTH) {
                  next = next.slice(0, -1);
                }
                setDraftMessage(next);
              }}
              maxLength={MESSAGE_MAX_WIDTH}
              placeholder="예: 화이팅!"
              className="mt-3 w-full rounded-md border-2 border-ink/20 bg-white px-3 py-2.5 text-base focus:border-brick-blue focus:outline-none"
            />
            <p className="mt-1 text-right text-xs opacity-50">
              {messageWidthUnits(draftMessage.trim())}/{MESSAGE_MAX_WIDTH}칸
              (한글 1자=2칸)
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => setMessageDialog(false)}
                disabled={busy !== null}
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white text-sm font-bold opacity-80 transition hover:border-ink/50 disabled:opacity-40"
              >
                취소
              </button>
              <button
                type="button"
                onClick={() => applyMessage(draftMessage.trim())}
                disabled={busy !== null || draftMessage.trim().length === 0}
                className="min-h-11 flex-1 rounded-md bg-brick-green text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85 disabled:opacity-60"
              >
                {busy === "message-apply"
                  ? "바꾸는 중..."
                  : "변경권 1개 사용해 바꾸기"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 구매 확인 — 현재 XP·가격·잔액 확인 후 확정, 부족하면 안내만 (2026-08-21) */}
      {confirm && (
        <PurchaseConfirmDialog
          label={confirm.label}
          priceXp={confirm.price}
          availableXp={shop.available_xp}
          busy={busy !== null}
          onConfirm={async () => {
            await confirm.run();
            setConfirm(null);
          }}
          onClose={() => setConfirm(null)}
        />
      )}
    </section>
  );
}

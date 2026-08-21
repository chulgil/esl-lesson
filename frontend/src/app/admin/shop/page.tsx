"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type AdminShopItem,
  type ItemGrantRow,
  adminShopApi,
} from "@/lib/admin-api";

/** 백오피스 캐릭터 상점 — 가격 오버라이드·이벤트 한정·수동 지급 (mascot-shop.md).
 *  테마 몰과 같은 관리 모델: 기본가는 코드 카탈로그, 오버라이드만 DB. */
export default function AdminShopPage() {
  const [items, setItems] = useState<AdminShopItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [grants, setGrants] = useState<ItemGrantRow[]>([]);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [granting, setGranting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadItems = useCallback(() => {
    adminShopApi
      .items()
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message));
  }, []);

  const loadGrants = useCallback(() => {
    if (!selected) {
      setGrants([]);
      return;
    }
    adminShopApi
      .grants(selected)
      .then((res) => setGrants(res.items))
      .catch((e) => setError(e.message));
  }, [selected]);

  useEffect(loadItems, [loadItems]);
  useEffect(loadGrants, [loadGrants]);

  const selectedItem = items.find((i) => i.key === selected) ?? null;

  // 가격 오버라이드 — 빈 값 = 카탈로그 기본가 복귀
  async function handleSetPrice(item: AdminShopItem) {
    const input = prompt(
      `${item.label} 의 XP 판매 가격 (비우면 기본가 ${item.default_price_xp} XP 복귀)`,
      String(item.price_xp),
    );
    if (input === null) return;
    const price = input.trim() === "" ? null : Number(input.trim());
    if (price !== null && (!Number.isInteger(price) || price < 1)) {
      setError("가격은 1 이상의 정수여야 해요");
      return;
    }
    setError(null);
    try {
      await adminShopApi.patchItem(item.key, { price_xp: price });
      loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "가격 설정 실패");
    }
  }

  // XP 판매 <-> 이벤트 한정 (XP 구매 차단, 지급으로만 보유)
  async function handleToggleSale(item: AdminShopItem) {
    const next = item.sale === "xp" ? "event" : "xp";
    const warning =
      next === "event"
        ? `${item.label} 을(를) 이벤트 한정으로 전환할까요? 사용자는 XP로 살 수 없고 지급으로만 받을 수 있어요.`
        : `${item.label} 을(를) XP 판매로 전환할까요? 사용자가 다시 XP로 살 수 있어요.`;
    if (!confirm(warning)) return;
    setError(null);
    try {
      await adminShopApi.patchItem(item.key, { sale: next });
      loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "판매 방식 전환 실패");
    }
  }

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !email.trim()) return;
    setGranting(true);
    setError(null);
    try {
      await adminShopApi.grant(selected, {
        email: email.trim(),
        note: note.trim() || undefined,
      });
      setEmail("");
      setNote("");
      loadItems();
      loadGrants();
    } catch (err) {
      setError(err instanceof Error ? err.message : "지급 실패");
    } finally {
      setGranting(false);
    }
  }

  async function handleRevoke(grant: ItemGrantRow) {
    if (!confirm(`${grant.email} 의 아이템을 회수할까요?`)) return;
    setError(null);
    try {
      await adminShopApi.revoke(grant.id);
      loadItems();
      loadGrants();
    } catch (err) {
      setError(err instanceof Error ? err.message : "회수 실패");
    }
  }

  return (
    <section>
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">캐릭터 상점</span>
      </h1>
      <p className="mt-2 text-xs opacity-60">
        가격은 카탈로그 기본가를 오버라이드해요. 이벤트 한정 = XP 구매 차단,
        지급으로만 보유 가능. 행을 선택하면 지급/회수를 관리할 수 있어요.
      </p>
      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}

      <div className="overflow-x-auto">
        <table className="mt-4 w-full max-w-2xl border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b-2 border-ink/20 text-left text-xs">
              <th className="p-2 w-32">키</th>
              <th className="p-2">라벨</th>
              <th className="p-2 w-20">종류</th>
              <th className="p-2 w-28">판매가</th>
              <th className="p-2 w-28">판매 방식</th>
              <th className="p-2 w-24">보유자 수</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={item.key}
                onClick={() => setSelected(item.key)}
                className={`cursor-pointer border-b border-ink/10 hover:bg-highlight/30 ${
                  selected === item.key ? "bg-highlight/40" : ""
                }`}
              >
                <td className="p-2 font-mono text-xs">{item.key}</td>
                <td className="p-2">{item.label}</td>
                <td className="p-2 text-xs">
                  {item.kind === "mascot"
                    ? "마스코트"
                    : item.kind === "perk"
                      ? "이용권"
                      : "악세사리"}
                </td>
                <td className="p-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSetPrice(item);
                    }}
                    className="rounded border-2 border-ink/20 px-2 py-0.5 text-xs font-bold hover:border-ink/50"
                  >
                    {item.price_xp.toLocaleString()} XP
                    {item.price_xp !== item.default_price_xp && (
                      <span className="ml-1 opacity-50">
                        (기본 {item.default_price_xp.toLocaleString()})
                      </span>
                    )}
                  </button>
                </td>
                <td className="p-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleSale(item);
                    }}
                    className={`rounded px-2 py-0.5 text-xs font-bold ${
                      item.sale === "event" ? "bg-brick-yellow/40" : "bg-ink/10"
                    }`}
                  >
                    {item.sale === "event" ? "이벤트 한정" : "XP 판매"}
                  </button>
                </td>
                <td className="p-2">{item.grants}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!selectedItem && (
        <p className="mt-8 text-sm opacity-60">
          아이템을 선택하면 보유자 지급/회수를 관리할 수 있어요.
        </p>
      )}

      {selectedItem && (
        <>
          <h2 className="mt-8 text-lg font-bold">
            {selectedItem.label} 보유자
          </h2>

          <form onSubmit={handleGrant} className="mt-3 flex flex-wrap gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="이메일"
              required
              className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-3 text-sm"
            />
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="비고 (이벤트명 등)"
              className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-3 text-sm"
            />
            <button
              type="submit"
              disabled={granting}
              className="min-h-11 rounded-md bg-ink px-4 text-sm font-bold text-white transition hover:opacity-85 disabled:opacity-50"
            >
              {granting ? "지급 중..." : "지급"}
            </button>
          </form>

          <div className="overflow-x-auto">
            <table className="mt-4 w-full max-w-2xl border-collapse bg-white text-sm">
              <thead>
                <tr className="border-b-2 border-ink/20 text-left text-xs">
                  <th className="p-2">이메일</th>
                  <th className="p-2">닉네임</th>
                  <th className="p-2">비고</th>
                  <th className="p-2 w-40">지급일</th>
                  <th className="p-2 w-16">액션</th>
                </tr>
              </thead>
              <tbody>
                {grants.map((g) => (
                  <tr key={g.id} className="border-b border-ink/10">
                    <td className="p-2">{g.email}</td>
                    <td className="p-2">{g.nickname}</td>
                    <td className="p-2 text-xs opacity-60">{g.note ?? "-"}</td>
                    <td className="p-2 text-xs opacity-60">
                      {new Date(g.created_at).toLocaleString("ko-KR")}
                    </td>
                    <td className="p-2">
                      <button
                        type="button"
                        onClick={() => handleRevoke(g)}
                        className="text-xs text-brick-red hover:underline"
                      >
                        회수
                      </button>
                    </td>
                  </tr>
                ))}
                {grants.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="p-4 text-center text-xs opacity-40"
                    >
                      보유자가 없어요
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { APP_THEMES } from "@/lib/theme";
import {
  type AdminThemeItem,
  type ThemeGrantItem,
  themeApi,
} from "@/lib/theme-api";

/** 백오피스 테마 몰 — 제한 테마 수동 지급/회수 (docs/specs/theme-mall.md) */

const THEME_LABELS: Record<string, string> = Object.fromEntries(
  APP_THEMES.map((t) => [t.key, t.label]),
);

export default function AdminThemesPage() {
  const [themes, setThemes] = useState<AdminThemeItem[]>([]);
  // 기본 cat 펼침 — 현재 유일한 제한 테마
  const [selected, setSelected] = useState("cat");
  const [grants, setGrants] = useState<ThemeGrantItem[]>([]);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [granting, setGranting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadThemes = useCallback(() => {
    themeApi
      .adminThemes()
      .then((res) => setThemes(res.items))
      .catch((e) => setError(e.message));
  }, []);

  const loadGrants = useCallback(() => {
    themeApi
      .grants(selected)
      .then((res) => setGrants(res.items))
      .catch((e) => setError(e.message));
  }, [selected]);

  useEffect(loadThemes, [loadThemes]);
  useEffect(loadGrants, [loadGrants]);

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setGranting(true);
    setError(null);
    try {
      await themeApi.grant(selected, {
        email: email.trim(),
        note: note.trim() || undefined,
      });
      setEmail("");
      setNote("");
      loadThemes();
      loadGrants();
    } catch (err) {
      setError(err instanceof Error ? err.message : "지급 실패");
    } finally {
      setGranting(false);
    }
  }

  async function handleRevoke(grant: ThemeGrantItem) {
    if (!confirm(`${grant.email} 의 테마를 회수할까요?`)) return;
    setError(null);
    try {
      await themeApi.revoke(grant.id);
      loadThemes();
      loadGrants();
    } catch (err) {
      setError(err instanceof Error ? err.message : "회수 실패");
    }
  }

  return (
    <section>
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">테마 몰</span>
      </h1>
      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}

      <div className="overflow-x-auto">
        <table className="mt-4 w-full max-w-2xl border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b-2 border-ink/20 text-left text-xs">
              <th className="p-2 w-24">키</th>
              <th className="p-2">라벨</th>
              <th className="p-2 w-20">정책</th>
              <th className="p-2 w-24">보유자 수</th>
            </tr>
          </thead>
          <tbody>
            {themes.map((t) => {
              const restricted = t.access === "restricted";
              return (
                <tr
                  key={t.key}
                  onClick={() => restricted && setSelected(t.key)}
                  className={`border-b border-ink/10 ${
                    restricted ? "cursor-pointer hover:bg-highlight/30" : ""
                  } ${selected === t.key ? "bg-highlight/40" : ""}`}
                >
                  <td className="p-2 font-mono text-xs">{t.key}</td>
                  <td className="p-2">{THEME_LABELS[t.key] ?? t.key}</td>
                  <td className="p-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        restricted ? "bg-brick-yellow/40" : "bg-ink/10"
                      }`}
                    >
                      {restricted ? "제한" : "무료"}
                    </span>
                  </td>
                  {/* 무료 테마는 grant 개념이 없다 — 전원 사용 가능 */}
                  <td className="p-2">{restricted ? t.grants : "전원"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2 className="mt-8 text-lg font-bold">
        {THEME_LABELS[selected] ?? selected} 보유자
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
                <td colSpan={5} className="p-4 text-center text-xs opacity-40">
                  보유자가 없어요
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { APP_THEMES } from "@/lib/theme";
import {
  type AdminThemeItem,
  type ThemeGrantItem,
  type ThemeRewardRule,
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

  // 무료 테마는 grants API 가 422 — 제한 테마 선택 시에만 조회
  const selectedRestricted =
    themes.find((t) => t.key === selected)?.access === "restricted";

  const loadGrants = useCallback(() => {
    if (!selectedRestricted) {
      setGrants([]);
      return;
    }
    themeApi
      .grants(selected)
      .then((res) => setGrants(res.items))
      .catch((e) => setError(e.message));
  }, [selected, selectedRestricted]);

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

  async function handleToggleAccess(t: AdminThemeItem) {
    const next = t.access === "restricted" ? "free" : "restricted";
    const label = THEME_LABELS[t.key] ?? t.key;
    const warning =
      next === "restricted"
        ? `${label} 테마를 제한으로 전환할까요? 지급받지 않은 사용자는 기본 테마로 되돌아가요.`
        : `${label} 테마를 무료로 전환할까요? 모든 사용자가 바로 쓸 수 있어요. (보유자 기록은 보존)`;
    if (!confirm(warning)) return;
    setError(null);
    try {
      await themeApi.setAccess(t.key, next);
      loadThemes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "정책 전환 실패");
    }
  }

  // XP 상점 가격 입력 — 빈 값 = 판매 중단 (업적 보상 규칙과 독립·동시 설정 가능)
  async function handleSetPrice(t: AdminThemeItem) {
    const label = THEME_LABELS[t.key] ?? t.key;
    const input = prompt(
      `${label} 테마의 XP 판매 가격 (비우면 판매 중단)`,
      t.price_xp != null ? String(t.price_xp) : "",
    );
    if (input === null) return; // 취소
    const price = input.trim() === "" ? null : Number(input.trim());
    if (price !== null && (!Number.isInteger(price) || price < 1)) {
      setError("가격은 1 이상의 정수여야 해요");
      return;
    }
    setError(null);
    try {
      await themeApi.setPrice(t.key, price);
      loadThemes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "가격 설정 실패");
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
              <th className="p-2 w-24">전환</th>
              <th className="p-2 w-28">XP 가격</th>
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
                  <td className="p-2">
                    {/* note 는 잠금 복귀(fallback) 테마 — 서버도 제한 전환을 422 로 거부 */}
                    {t.key === "note" ? (
                      <span className="text-xs opacity-40">기본 고정</span>
                    ) : (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleAccess(t);
                        }}
                        className="rounded border-2 border-ink/20 px-2 py-0.5 text-xs font-bold hover:border-ink/50"
                      >
                        {restricted ? "무료로" : "제한으로"}
                      </button>
                    )}
                  </td>
                  <td className="p-2">
                    {/* XP 상점 — 제한 테마만 판매 가능, 빈 값 = 미판매 */}
                    {restricted ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSetPrice(t);
                        }}
                        className="rounded border-2 border-ink/20 px-2 py-0.5 text-xs font-bold hover:border-ink/50"
                      >
                        {t.price_xp != null ? `${t.price_xp} XP` : "미판매"}
                      </button>
                    ) : (
                      <span className="text-xs opacity-40">-</span>
                    )}
                  </td>
                  {/* 무료 테마는 grant 개념이 없다 — 전원 사용 가능 */}
                  <td className="p-2">{restricted ? t.grants : "전원"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!selectedRestricted && (
        <p className="mt-8 text-sm opacity-60">
          제한 테마를 선택하면 보유자 지급/회수를 관리할 수 있어요.
        </p>
      )}

      {selectedRestricted && (
        <>
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

      <RewardRulesSection themes={themes} onError={setError} />
    </section>
  );
}

/** 업적 보상 규칙 — 어떤 업적 달성에 어떤 테마를 줄지 매핑.
 *  규칙 추가 시 과거 달성자도 다음 접속에서 소급 지급된다.
 *  규칙 삭제는 이후 지급만 중단 — 이미 받은 테마는 유지(이력 보존). */
function RewardRulesSection({
  themes,
  onError,
}: {
  themes: AdminThemeItem[];
  onError: (msg: string | null) => void;
}) {
  const [rules, setRules] = useState<ThemeRewardRule[]>([]);
  const [achievements, setAchievements] = useState<
    { key: string; title: string }[]
  >([]);
  const [achievementKey, setAchievementKey] = useState("");
  const [themeKey, setThemeKey] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    themeApi
      .rewardRules()
      .then((res) => {
        setRules(res.items);
        setAchievements(res.achievements);
      })
      .catch((e) => onError(e.message));
  }, [onError]);

  useEffect(load, [load]);

  const restrictedThemes = themes.filter((t) => t.access === "restricted");

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!achievementKey || !themeKey) return;
    setSaving(true);
    onError(null);
    try {
      await themeApi.createRewardRule({
        achievement_key: achievementKey,
        theme_key: themeKey,
      });
      setAchievementKey("");
      setThemeKey("");
      load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "규칙 추가 실패");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(rule: ThemeRewardRule) {
    if (
      !confirm(
        `'${rule.achievement_title}' → ${THEME_LABELS[rule.theme_key] ?? rule.theme_key} 규칙을 삭제할까요?\n이미 지급된 테마는 유지되고, 이후 지급만 중단돼요.`,
      )
    )
      return;
    onError(null);
    try {
      await themeApi.deleteRewardRule(rule.id);
      load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "규칙 삭제 실패");
    }
  }

  return (
    <>
      <h2 className="mt-10 text-lg font-bold">업적 보상 규칙</h2>
      <p className="mt-1 text-xs opacity-60">
        업적 달성 시 테마가 자동 지급돼요. 과거 달성자도 다음 접속에서 소급
        지급되고, 규칙을 삭제해도 이미 받은 테마는 유지돼요.
      </p>

      <form onSubmit={handleAdd} className="mt-3 flex flex-wrap gap-2">
        <select
          value={achievementKey}
          onChange={(e) => setAchievementKey(e.target.value)}
          required
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-2 text-sm"
        >
          <option value="">업적 선택</option>
          {achievements.map((a) => (
            <option key={a.key} value={a.key}>
              {a.title}
            </option>
          ))}
        </select>
        <select
          value={themeKey}
          onChange={(e) => setThemeKey(e.target.value)}
          required
          className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-2 text-sm"
        >
          <option value="">테마 선택 (제한만)</option>
          {restrictedThemes.map((t) => (
            <option key={t.key} value={t.key}>
              {THEME_LABELS[t.key] ?? t.key}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={saving}
          className="min-h-11 rounded-md bg-ink px-4 text-sm font-bold text-white transition hover:opacity-85 disabled:opacity-50"
        >
          {saving ? "추가 중..." : "규칙 추가"}
        </button>
      </form>

      <div className="overflow-x-auto">
        <table className="mt-4 w-full max-w-2xl border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b-2 border-ink/20 text-left text-xs">
              <th className="p-2">업적</th>
              <th className="p-2">지급 테마</th>
              <th className="p-2 w-40">생성일</th>
              <th className="p-2 w-16">액션</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-b border-ink/10">
                <td className="p-2">{r.achievement_title}</td>
                <td className="p-2">
                  {THEME_LABELS[r.theme_key] ?? r.theme_key}
                </td>
                <td className="p-2 text-xs opacity-60">
                  {new Date(r.created_at).toLocaleString("ko-KR")}
                </td>
                <td className="p-2">
                  <button
                    type="button"
                    onClick={() => handleDelete(r)}
                    className="text-xs text-brick-red hover:underline"
                  >
                    삭제
                  </button>
                </td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr>
                <td colSpan={4} className="p-4 text-center text-xs opacity-40">
                  규칙이 없어요 — 업적과 테마를 골라 추가하세요
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

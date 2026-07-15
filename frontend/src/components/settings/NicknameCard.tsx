"use client";

import { useEffect, useState } from "react";
import { fetchMe, updateNickname } from "@/lib/api";

/** 닉네임 설정 — 다른 사용자에게 보이는 유일한 이름 (구글 이름 비공개) */
export function NicknameCard() {
  const [nickname, setNickname] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchMe().then((me) => {
      if (me) {
        setNickname(me.nickname);
        setLoaded(true);
      }
    });
  }, []);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const me = await updateNickname(nickname);
      setNickname(me.nickname);
      setMessage("닉네임을 바꿨어요 — 친구·랭킹·게임에 바로 반영돼요.");
    } catch {
      setMessage("2~16자로 입력해주세요.");
    }
    setBusy(false);
  }

  if (!loaded) return null;

  return (
    <section className="max-w-lg">
      <p className="mb-1 text-sm font-bold">닉네임</p>
      <p className="mb-3 text-xs opacity-60">
        랭킹·친구·게임에서 다른 사용자에게 보이는 이름이에요. 구글 계정 이름은
        누구에게도 공개되지 않아요.
      </p>
      <div className="flex items-center gap-2">
        <input
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && save()}
          maxLength={16}
          className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white px-3 text-sm transition-colors focus:border-brick-blue focus:outline-none"
        />
        <button
          type="button"
          disabled={busy}
          onClick={save}
          className="min-h-11 shrink-0 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold whitespace-nowrap transition hover:border-ink/50 disabled:opacity-50"
        >
          {busy ? "저장 중..." : "저장"}
        </button>
      </div>
      {message && <p className="mt-2 text-xs opacity-70">{message}</p>}
    </section>
  );
}

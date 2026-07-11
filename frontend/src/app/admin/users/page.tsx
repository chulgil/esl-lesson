"use client";

import { useEffect, useState } from "react";
import { adminApi, type AdminUser } from "@/lib/admin-api";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    adminApi
      .listUsers()
      .then((res) => setUsers(res.items))
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function toggleRole(user: AdminUser) {
    const next = user.role === "admin" ? "learner" : "admin";
    if (!confirm(`${user.email} 역할을 ${next} 로 변경할까요?`)) return;
    try {
      await adminApi.patchUser(user.id, next);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "변경 실패");
    }
  }

  return (
    <section>
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">사용자</span>
      </h1>
      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}
      <table className="mt-4 w-full border-collapse bg-white text-sm">
        <thead>
          <tr className="border-b-2 border-ink/20 text-left text-xs">
            <th className="p-2">이메일</th>
            <th className="p-2">이름</th>
            <th className="p-2 w-20">역할</th>
            <th className="p-2 w-24">총 복습</th>
            <th className="p-2 w-40">최근 로그인</th>
            <th className="p-2 w-24">액션</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-ink/10">
              <td className="p-2">{u.email}</td>
              <td className="p-2">{u.name}</td>
              <td className="p-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    u.role === "admin" ? "bg-brick-yellow/40" : "bg-ink/10"
                  }`}
                >
                  {u.role}
                </span>
              </td>
              <td className="p-2">{u.total_reviews}</td>
              <td className="p-2 text-xs opacity-60">
                {u.last_login_at
                  ? new Date(u.last_login_at).toLocaleString("ko-KR")
                  : "-"}
              </td>
              <td className="p-2">
                <button
                  type="button"
                  onClick={() => toggleRole(u)}
                  className="text-xs text-brick-blue hover:underline"
                >
                  역할 전환
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

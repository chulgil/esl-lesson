"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMe, loginUrl, type Me } from "@/lib/api";

const NAV = [
  { href: "/admin", label: "대시보드" },
  { href: "/admin/contents", label: "콘텐츠" },
  { href: "/admin/items", label: "항목 풀" },
  { href: "/admin/users", label: "사용자" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then((user) => {
      setMe(user);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <main className="p-8 text-sm opacity-60">확인 중...</main>;
  }

  if (!me) {
    if (typeof window !== "undefined") {
      window.location.href = loginUrl(window.location.pathname);
    }
    return null;
  }

  if (me.role !== "admin") {
    return (
      <main className="p-8">
        <p>관리자 권한이 필요합니다.</p>
      </main>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b-2 border-ink/10 bg-paper px-4 py-3 sm:px-6">
        <span className="font-hand text-xl font-bold">ESL 백오피스</span>
        <nav className="flex gap-4 text-sm">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="hover:underline">
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto text-xs opacity-60">{me.email}</span>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}

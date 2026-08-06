"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import {
  adminApi,
  type CcSearchItem,
  type ContentPermission,
} from "@/lib/admin-api";

type Tab = "youtube" | "manual";

const EMPTY_PERMISSION: ContentPermission = {
  rights_holder: "",
  rights_holder_contact: "",
  granted_at: "",
  scope_transcript: false,
  scope_translate: false,
  scope_derive: false,
  scope_commercial: false,
  evidence: "",
  note: "",
};

export default function NewContentPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("youtube");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [scriptEn, setScriptEn] = useState("");
  const [scriptKo, setScriptKo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // CC 게이트(cc_required) — 비 CC 는 허락 증빙을 남겨야 등록된다
  const [ccBlocked, setCcBlocked] = useState(false);
  // CC 영상 찾기 — creativeCommon+자막 보유만 검색해 후보에서 바로 등록
  const [ccQuery, setCcQuery] = useState("");
  const [ccItems, setCcItems] = useState<CcSearchItem[] | null>(null);
  const [ccSearching, setCcSearching] = useState(false);
  const [ccError, setCcError] = useState<string | null>(null);
  // 다음 페이지 토큰 — null 이면 더 없음 (2026-08-05 페이징)
  const [ccNextToken, setCcNextToken] = useState<string | null>(null);
  // 사용자 요청 — 수요를 보고 CC 검색으로 채운다 (effectiveness-audit P0-3)
  const [requests, setRequests] = useState<
    { id: number; text: string; nickname: string }[]
  >([]);
  const [permission, setPermission] =
    useState<ContentPermission>(EMPTY_PERMISSION);

  const scopeComplete =
    permission.scope_transcript &&
    permission.scope_translate &&
    permission.scope_derive;
  const permissionComplete =
    permission.rights_holder.trim() !== "" &&
    permission.granted_at !== "" &&
    permission.evidence.trim() !== "" &&
    scopeComplete;

  async function submit(withPermission = false) {
    setError(null);
    setCcBlocked(false);
    setSubmitting(true);
    try {
      if (tab === "youtube") {
        await adminApi.createContent({
          source: "youtube",
          url,
          permission: withPermission ? permission : undefined,
        });
      } else {
        await adminApi.createContent({
          source: "manual",
          title,
          script_en: scriptEn,
          script_ko: scriptKo || undefined,
          url: url || undefined,
        });
      }
      router.push("/admin/contents");
    } catch (e) {
      const message = e instanceof Error ? e.message : "등록 실패";
      if (message === "cc_required") {
        setCcBlocked(true);
      } else if (message === "permission_scope_insufficient") {
        setError("자막·번역·학습항목 세 가지 이용이 모두 허락되어야 등록돼요.");
      } else {
        setError(message);
      }
      setSubmitting(false);
    }
  }

  useEffect(() => {
    adminApi
      .contentRequests()
      .then((res) => setRequests(res.items.slice(0, 5)))
      .catch(() => undefined);
  }, []);

  async function searchCc(more = false) {
    if (!ccQuery.trim()) return;
    setCcSearching(true);
    setCcError(null);
    try {
      const res = await adminApi.ccSearch(
        ccQuery.trim(),
        more ? (ccNextToken ?? undefined) : undefined,
      );
      setCcItems((prev) =>
        more && prev ? [...prev, ...res.items] : res.items,
      );
      setCcNextToken(res.next_page_token ?? null);
    } catch (e) {
      const message = e instanceof Error ? e.message : "검색 실패";
      setCcError(
        {
          youtube_api_key_missing:
            "서버에 YOUTUBE_API_KEY 가 없어요 — .env.api 설정 후 재생성 필요",
          youtube_search_failed:
            "유튜브 검색에 실패했어요 — 쿼터 초과이거나 일시 오류예요",
        }[message] ?? message,
      );
    }
    setCcSearching(false);
  }

  function setPerm<K extends keyof ContentPermission>(
    key: K,
    value: ContentPermission[K],
  ) {
    setPermission((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="max-w-2xl">
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">콘텐츠 등록</span>
      </h1>

      <div className="mt-4 flex gap-2">
        <TabButton
          label="유튜브 URL"
          active={tab === "youtube"}
          onClick={() => setTab("youtube")}
        />
        <TabButton
          label="수기 입력"
          active={tab === "manual"}
          onClick={() => setTab("manual")}
        />
      </div>

      <div className="mt-4 flex flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6">
        {tab === "youtube" ? (
          <>
            <label className="flex flex-col gap-1 text-sm">
              유튜브 URL
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://youtu.be/..."
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
              <span className="text-xs opacity-60">
                제목과 영어/한글 스크립트는 자동으로 추출됩니다.
              </span>
            </label>

            {/* CC 영상 찾기 — 검색 필터는 후보용, 등록 시 서버가 라이선스 재확인 */}
            <div className="mt-2 rounded-md border-2 border-brick-green/30 bg-brick-green/5 p-3">
              <p className="text-sm font-bold">CC(재사용 허용) 영상 찾기</p>
              {requests.length > 0 && (
                <div className="mt-1 rounded bg-highlight/30 px-2 py-1.5 text-xs">
                  <span className="font-bold">사용자 요청:</span>{" "}
                  {requests.map((r) => `"${r.text}"(${r.nickname})`).join(" · ")}
                </div>
              )}
              <p className="mb-2 text-xs opacity-60">
                크리에이티브 커먼즈 + 자막 보유 영상만 검색돼요 — 선택하면 URL이
                채워집니다
              </p>
              <div className="flex gap-2">
                <input
                  value={ccQuery}
                  onChange={(e) => setCcQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      searchCc();
                    }
                  }}
                  placeholder="검색어 (예: english conversation)"
                  className="min-w-0 flex-1 rounded border-2 border-ink/20 px-3 py-2"
                />
                <button
                  type="button"
                  // 클릭 이벤트가 more 인자로 들어가지 않게 명시 호출
                  onClick={() => searchCc()}
                  disabled={ccSearching || !ccQuery.trim()}
                  className="shrink-0 rounded-md border-2 border-brick-green bg-white px-3 text-sm font-bold text-brick-green disabled:opacity-40"
                >
                  {ccSearching ? "검색 중..." : "검색"}
                </button>
              </div>
              {ccError && (
                <p className="mt-2 text-xs text-brick-red">{ccError}</p>
              )}
              {ccItems && ccItems.length === 0 && (
                <p className="mt-2 text-xs opacity-60">검색 결과가 없어요</p>
              )}
              {ccItems && ccItems.length > 0 && (
                <ul className="mt-3 flex max-h-80 flex-col gap-2 overflow-y-auto">
                  {ccItems.map((v) => {
                    const videoUrl = `https://www.youtube.com/watch?v=${v.video_id}`;
                    const selected = url === videoUrl;
                    return (
                      <li key={v.video_id}>
                        <button
                          type="button"
                          onClick={() => setUrl(videoUrl)}
                          className={`flex w-full items-center gap-3 rounded-md border-2 p-2 text-left transition ${
                            selected
                              ? "border-brick-green bg-brick-green/10"
                              : "border-ink/10 bg-white hover:border-brick-green/50"
                          }`}
                        >
                          {v.thumbnail_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={v.thumbnail_url}
                              alt=""
                              className="h-14 w-24 shrink-0 rounded object-cover"
                            />
                          ) : (
                            <span className="h-14 w-24 shrink-0 rounded bg-ink/10" />
                          )}
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-bold">
                              {v.title}
                            </span>
                            <span className="block truncate text-xs opacity-60">
                              {v.channel_title}
                              {v.published_at &&
                                ` · ${v.published_at.slice(0, 10)}`}
                            </span>
                          </span>
                          {selected && (
                            <span className="shrink-0 text-xs font-bold text-brick-green">
                              선택됨
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {/* 페이징 — 결과가 적다는 보고(2026-08-05)로 50개+더 보기 도입 */}
              {ccItems && ccItems.length > 0 && ccNextToken && (
                <button
                  type="button"
                  onClick={() => searchCc(true)}
                  disabled={ccSearching}
                  className="mt-2 w-full rounded-md border-2 border-ink/20 bg-white px-3 py-2 text-sm font-bold disabled:opacity-40"
                >
                  {ccSearching ? "불러오는 중..." : "결과 더 보기"}
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <label className="flex flex-col gap-1 text-sm">
              제목 (필수)
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              영어 스크립트 (필수)
              <textarea
                value={scriptEn}
                onChange={(e) => setScriptEn(e.target.value)}
                rows={8}
                className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              한글 스크립트 (비우면 AI 번역)
              <textarea
                value={scriptKo}
                onChange={(e) => setScriptKo(e.target.value)}
                rows={8}
                className="rounded border-2 border-ink/20 px-3 py-2 font-mono text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              원본 URL (선택)
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
            </label>
          </>
        )}

        {error && <p className="text-sm text-brick-red">{error}</p>}

        {ccBlocked && (
          <div className="flex flex-col gap-3 rounded-md border-2 border-brick-yellow bg-highlight/30 p-4 text-sm">
            <div>
              <p className="font-bold">
                이 영상은 크리에이티브 커먼즈(CC) 라이선스가 아니거나 확인되지
                않았어요.
              </p>
              <p className="mt-1 opacity-70">
                원저작자 허락을 받았다면 아래에 증빙을 남기고 등록하세요. 분쟁이
                생겼을 때 &ldquo;허락받았다&rdquo;를 입증할 유일한 기록이에요.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="권리자 (채널명·법인명) *">
                <input
                  value={permission.rights_holder}
                  onChange={(e) => setPerm("rights_holder", e.target.value)}
                  className="rounded border-2 border-ink/20 px-3 py-2"
                />
              </Field>
              <Field label="연락처 (이메일 등)">
                <input
                  value={permission.rights_holder_contact ?? ""}
                  onChange={(e) =>
                    setPerm("rights_holder_contact", e.target.value)
                  }
                  className="rounded border-2 border-ink/20 px-3 py-2"
                />
              </Field>
              <Field label="허락받은 날짜 *">
                <input
                  type="date"
                  value={permission.granted_at}
                  onChange={(e) => setPerm("granted_at", e.target.value)}
                  className="rounded border-2 border-ink/20 px-3 py-2"
                />
              </Field>
            </div>

            <fieldset className="rounded border-2 border-ink/15 bg-white p-3">
              <legend className="px-1 text-xs font-bold opacity-60">
                허락 범위 — 앞의 세 가지가 모두 있어야 등록돼요
              </legend>
              <div className="flex flex-col gap-1.5">
                <Check
                  checked={permission.scope_transcript}
                  onChange={(v) => setPerm("scope_transcript", v)}
                  label="자막 복제·서버 저장"
                />
                <Check
                  checked={permission.scope_translate}
                  onChange={(v) => setPerm("scope_translate", v)}
                  label="한국어 번역 작성·제공 (2차적저작물)"
                />
                <Check
                  checked={permission.scope_derive}
                  onChange={(v) => setPerm("scope_derive", v)}
                  label="학습 항목 추출·게임 소재 변형"
                />
                <Check
                  checked={permission.scope_commercial}
                  onChange={(v) => setPerm("scope_commercial", v)}
                  label="상업적 이용 (광고·유료) — 선택, 수익화 시 판별용"
                />
              </div>
            </fieldset>

            <Field label="증빙 위치 또는 요지 *">
              <textarea
                value={permission.evidence}
                onChange={(e) => setPerm("evidence", e.target.value)}
                rows={2}
                placeholder="예: 2026-07-20 이메일 승낙 (보관: legal/permissions/채널명.eml)"
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
            </Field>
            <Field label="특약 (기간·해지 조건 등)">
              <input
                value={permission.note ?? ""}
                onChange={(e) => setPerm("note", e.target.value)}
                className="rounded border-2 border-ink/20 px-3 py-2"
              />
            </Field>

            <div>
              <button
                type="button"
                disabled={submitting || !permissionComplete}
                onClick={() => submit(true)}
                className="min-h-11 rounded-md border-2 border-brick-green/60 bg-white px-4 text-sm font-bold text-brick-green transition hover:border-brick-green disabled:opacity-40"
              >
                허락 증빙 남기고 등록
              </button>
              {!permissionComplete && (
                <p className="mt-1.5 text-xs opacity-60">
                  권리자·날짜·증빙과 위 세 가지 범위를 채우면 등록할 수 있어요.
                </p>
              )}
            </div>
          </div>
        )}

        <div>
          <Brick color="green" disabled={submitting} onClick={() => submit()}>
            {submitting ? "등록 중..." : "등록"}
          </Brick>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      {label}
      {children}
    </label>
  );
}

function Check({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-t px-4 py-2 text-sm font-bold ${
        active
          ? "bg-white border-2 border-b-0 border-ink/10"
          : "bg-ink/5 hover:bg-ink/10"
      }`}
    >
      {label}
    </button>
  );
}

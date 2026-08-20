/** 백오피스 API 클라이언트 (docs/specs/backoffice.md) */


import { request } from "@/lib/http";

export interface ContentSummary {
  id: number;
  /** chat = 내가 쓰는 말 덱 (my_phrases 자동 생성 — 목록 응답에 실재) */
  source: "youtube" | "manual" | "chat";
  title: string;
  status: "pending" | "extracting" | "ready" | "failed";
  youtube_video_id: string | null;
  /** "creativeCommon" | "youtube"(표준) | null(미확인) */
  youtube_license: string | null;
  error_message: string | null;
  created_at: string;
}

export interface Segment {
  id: number;
  seq: number;
  start_ms: number | null;
  en_text: string;
  ko_text: string | null;
}

export interface Job {
  step: string;
  status: string;
  attempt: number;
  error: string | null;
}

export interface Item {
  id: number;
  item_type: "word" | "idiom" | "pattern" | "sentence";
  level: number;
  en_text: string;
  ko_text: string;
  hint_thinking: string | null;
  pattern_template: string | null;
  difficulty_hint: string;
  review_status: "pending" | "approved" | "rejected";
  context_en: string | null;
}

/** 항목 풀 검색 응답 — GET /api/admin/items (목록용 축약 필드) */
export interface PoolItem {
  id: number;
  item_type: "word" | "idiom" | "pattern" | "sentence";
  en_text: string;
  ko_text: string;
  review_status: "pending" | "approved" | "rejected";
  difficulty_hint: string;
}

export interface ContentDetail extends ContentSummary {
  url: string | null;
  segments: Segment[];
  jobs: Job[];
  items: Item[];
}

export interface CcSearchItem {
  video_id: string;
  title: string;
  channel_title: string;
  published_at: string;
  thumbnail_url: string;
  /** 이미 등록된 영상 — 연속 등록 시 중복 후보 걸러내기 (2026-08-11) */
  registered: boolean;
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: "admin" | "learner";
  created_at: string;
  last_login_at: string | null;
  total_reviews: number;
}

/** 번역 사용량 — 예산 대비 소진, 엔진별 분담 (i18n 대시보드) */
export interface TranslationUsage {
  month_chars: number;
  budget_chars: number;
  by_engine: { deepl: number; haiku: number };
  today_calls: number;
}


/** 원저작자 이용허락 증빙 — 파이프라인이 수행하는 이용 3종이 모두 허락돼야 등록된다 */
export interface ContentPermission {
  rights_holder: string;
  rights_holder_contact?: string;
  granted_at: string;
  scope_transcript: boolean;
  scope_translate: boolean;
  scope_derive: boolean;
  scope_commercial: boolean;
  evidence: string;
  note?: string;
}

/** 시험지 문항 미리보기 — 검수용이라 정답(answer_index) 포함 */
export interface AdminExamQuestion {
  seq: number;
  quiz_mode: string;
  prompt: string;
  prompt_ko: string | null;
  choices: string[];
  answer_index: number;
  en_text: string;
  ko_text: string;
}

export interface AdminExam {
  exam_id: number;
  round: number;
  status: "active" | "archived";
  question_count: number;
  submitted_count: number;
  created_at: string;
  questions: AdminExamQuestion[];
}

export const adminApi = {
  dashboard: () =>
    request<{
      pending_items: number;
      failed_contents: number;
      in_progress_contents: number;
      total_contents: number;
      /** 공급 리듬 (P0-B) — 이번 주(월요일 KST) 등록 수 / 목표 주 2편 */
      weekly_supply: number;
      supply_goal: number;
      /** ready 공용 콘텐츠의 레벨별 수 (파생 난이도 기준) */
      levels: { beginner: number; intermediate: number; advanced: number };
    }>("/api/admin/dashboard"),

  listContents: (status?: string) =>
    request<{ total: number; items: ContentSummary[] }>(
      `/api/admin/contents${status ? `?status=${status}` : ""}`,
    ),

  getContent: (id: number) =>
    request<ContentDetail>(`/api/admin/contents/${id}`),

  /** 사용자 콘텐츠 요청 — 등록 화면에서 수요 확인 (effectiveness-audit P0-3) */
  contentRequests: () =>
    request<{
      items: {
        id: number;
        text: string;
        nickname: string;
        created_at: string;
      }[];
    }>("/api/admin/contents/requests"),

  /** CC(creativeCommon)·자막 보유·영어 영상만 검색 — 등록 후보
   *  (content-governance.md). pageToken 으로 다음 페이지 (2026-08-05) */
  ccSearch: (q: string, pageToken?: string) =>
    request<{ items: CcSearchItem[]; next_page_token: string | null }>(
      `/api/admin/youtube/cc-search?q=${encodeURIComponent(q)}${
        pageToken ? `&page_token=${encodeURIComponent(pageToken)}` : ""
      }`,
    ),

  createContent: (body: {
    source: "youtube" | "manual";
    url?: string;
    title?: string;
    script_en?: string;
    script_ko?: string;
    /** 콘텐츠 언어 — 생략 시 서버 기본값 "en" (i18n) */
    lang?: "en" | "ja" | "ko";
    /** 비 CC 영상은 원저작자 허락 증빙이 있어야 등록된다 (content-governance.md) */
    permission?: ContentPermission;
  }) =>
    request<{ id: number }>("/api/admin/contents", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  retryContent: (id: number) =>
    request<{ id: number }>(`/api/admin/contents/${id}/retry`, {
      method: "POST",
    }),

  deleteContent: (id: number) =>
    request<void>(`/api/admin/contents/${id}`, { method: "DELETE" }),

  /** 전역 항목 풀 검색 — 타입/상태/키워드 필터 + 페이지네이션 (50/페이지) */
  searchItems: (params: {
    type?: string;
    status?: string;
    q?: string;
    page?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.type) qs.set("type", params.type);
    if (params.status) qs.set("status", params.status);
    if (params.q) qs.set("q", params.q);
    if (params.page) qs.set("page", String(params.page));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ total: number; page: number; items: PoolItem[] }>(
      `/api/admin/items${suffix}`,
    );
  },

  patchItem: (
    id: number,
    body: Partial<
      Pick<Item, "en_text" | "ko_text" | "hint_thinking" | "review_status">
    >,
  ) =>
    request<{ id: number }>(`/api/admin/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  approveAll: (contentId: number) =>
    request<{ approved: number; skipped: number }>(
      `/api/admin/contents/${contentId}/approve-all`,
      { method: "POST" },
    ),

  /** 시험지 생성/재생성 — 기존 active 는 archived, 새 회차 active (library-exam) */
  createExam: (contentId: number) =>
    request<{ exam_id: number; round: number; question_count: number }>(
      `/api/admin/contents/${contentId}/exam`,
      { method: "POST" },
    ),

  listExams: (contentId: number) =>
    request<{ items: AdminExam[] }>(`/api/admin/contents/${contentId}/exams`),

  listUsers: () => request<{ items: AdminUser[] }>("/api/admin/users"),

  patchUser: (id: number, role: "admin" | "learner") =>
    request<{ id: number }>(`/api/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  translationUsage: () =>
    request<TranslationUsage>("/api/admin/translation-usage"),
};

/** 백오피스 캐릭터 상점 — 가격·판매 방식·지급 관리 (docs/specs/mascot-shop.md) */
export interface AdminShopItem {
  key: string;
  kind: "mascot" | "outfit";
  label: string;
  default_price_xp: number;
  price_xp: number;
  sale: "xp" | "event";
  grants: number;
}

export interface ItemGrantRow {
  id: number;
  email: string;
  nickname: string;
  note: string | null;
  created_at: string;
}

export const adminShopApi = {
  items: () => request<{ items: AdminShopItem[] }>("/api/admin/shop"),

  patchItem: (
    key: string,
    body: { price_xp?: number | null; sale?: "xp" | "event" },
  ) =>
    request<{ key: string; price_xp: number; sale: "xp" | "event" }>(
      `/api/admin/shop/${encodeURIComponent(key)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),

  grants: (key: string) =>
    request<{ items: ItemGrantRow[] }>(
      `/api/admin/shop/${encodeURIComponent(key)}/grants`,
    ),

  grant: (key: string, body: { email: string; note?: string }) =>
    request<ItemGrantRow>(`/api/admin/shop/${encodeURIComponent(key)}/grants`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  revoke: (grantId: number) =>
    request<void>(`/api/admin/shop/grants/${grantId}`, { method: "DELETE" }),
};

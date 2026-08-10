import { redirect } from "next/navigation";

/** /my 는 라이브러리 "담은 것" 탭으로 흡수 (ux-redesign #5 — 사용자 화면 20→19).
 *  개별 상세(/my/[id])는 유지 — 처리 중/실패 개인 콘텐츠의 확인 화면. */
export default function MyContentsPage() {
  redirect("/library?tab=mine");
}

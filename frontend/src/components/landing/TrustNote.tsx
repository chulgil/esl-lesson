import Link from "next/link";

/** 개인정보 불안 해소 — 무엇을 받고 무엇을 안 받는지 로그인 순간에 투명하게 */
export function TrustNote() {
  return (
    <p className="max-w-xs text-center text-xs leading-relaxed opacity-60">
      비밀번호를 만들지 않아요 — 인증은 Google이 처리하고, 저장하는 개인정보는
      이메일·이름·프로필 사진뿐입니다. 탈퇴 시 즉시 삭제돼요.{" "}
      <Link href="/privacy" className="underline underline-offset-2">
        개인정보처리방침
      </Link>
    </p>
  );
}

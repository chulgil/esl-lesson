/** 채팅 본문 링크 표현 — 카톡/페북식 (2026-08-12 요청).
 *
 *  긴 URL 은 프로토콜·www 를 떼고 호스트+경로를 36자에서 말줄임해 보여주고,
 *  클릭하면 새 창으로 연다. http/https 만 링크로 인정 (javascript: 등 차단).
 *  색은 테마 토큰(text-brick-blue)이라 위장 테마에서도 그 세계관의 링크색이 된다
 *  (오피스 = 스프레드시트 하이퍼링크처럼 보임 — 위장 유지).
 */

const URL_RE = /(https?:\/\/[^\s<>"')\]]+)/g;
const MAX_LABEL = 36;

function displayUrl(url: string): string {
  let label = url;
  try {
    const u = new URL(url);
    const rest = `${u.pathname}${u.search}${u.hash}`;
    label = u.host.replace(/^www\./, "") + (rest === "/" ? "" : rest);
  } catch {
    // URL 파싱 실패 — 원문 기준으로 말줄임만
  }
  return label.length > MAX_LABEL ? `${label.slice(0, MAX_LABEL - 1)}…` : label;
}

export function LinkifiedText({ text }: { text: string }) {
  if (!text || !text.includes("http")) return <>{text}</>;
  const parts = text.split(URL_RE);
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            title={part}
            // 메시지 행의 탭(답장 선택 등)과 분리 — 링크만 열린다
            onClick={(e) => e.stopPropagation()}
            className="inline-flex max-w-full items-baseline gap-0.5 align-baseline font-bold break-all text-brick-blue underline decoration-brick-blue/40 underline-offset-2 hover:decoration-brick-blue"
          >
            <LinkIcon />
            {displayUrl(part)}
          </a>
        ) : (
          part
        ),
      )}
    </>
  );
}

function LinkIcon() {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="shrink-0 self-center"
    >
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
    </svg>
  );
}

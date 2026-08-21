/** 업데이트 소식 — 버전(배포일)별 사용자 언어 체인지로그 (docs/specs/updates-changelog.md).
 *
 *  유지 규칙: 사용자가 체감할 변경을 배포할 때 맨 위에 항목을 추가한다.
 *  내부 리팩토링·문서 변경은 싣지 않는다 — 이 목록은 신뢰를 위한 화면이다.
 *  최신 항목이 배열의 앞. date 는 KST 배포일. */

export interface ChangelogEntry {
  date: string;
  title: string;
  items: string[];
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    date: "2026-08-21",
    title: "모바일 대개편 + 발음 학습",
    items: [
      "홈이 모바일 한 화면에 쏙 들어와요 — 인사·목표·미션이 스크롤 없이",
      "발음 확인 — 문장을 소리 내어 말하면 인식해서 판정해줘요",
      "학습 채팅 [읽기] — 보낸 외국어 문장의 읽는 법을 한글로 보여줘요",
      "학습 카드 넘김이 차분해졌어요 — 회전·미끄러짐 없이 부드러운 전환",
      "어휘망 색을 기억 순서로 — 모르는 단어는 빨강, 오래 기억한 단어는 회색",
      "악세사리를 탭해서 입히고 벗길 수 있어요 + 구매 전 확인 창",
      "노치 폰에서 하단 메뉴가 가려지던 문제를 고쳤어요",
      "라이브러리 카드에 영상 썸네일이 크게 보여요",
    ],
  },
];

export const CHANGELOG_SEEN_KEY = "esl:changelog:seen";
export const LATEST_CHANGELOG_DATE = CHANGELOG[0]?.date ?? "";

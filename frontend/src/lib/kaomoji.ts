/** 귀여운 카오모지 셋 — 채팅 입력 피커용 (docs/specs/chat.md).
 *  메시지는 일반 텍스트로 저장되므로 서버 변경 불필요. */

export interface KaomojiCategory {
  label: string;
  items: string[];
}

export const KAOMOJI: KaomojiCategory[] = [
  {
    label: "기쁨",
    items: [
      "(´｡• ᵕ •｡`)",
      "(๑˃ᴗ˂)ﻭ",
      "(≧▽≦)",
      "(*´▽`*)",
      "ヽ(´▽`)/",
      "(◕‿◕)",
      "(￣▽￣)ノ",
      "٩(ˊᗜˋ*)و",
    ],
  },
  {
    label: "응원",
    items: [
      "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
      "ᕙ(⇀‸↼‶)ᕗ",
      "(๑•̀ㅂ•́)و✧",
      "ファイト! (o^^)o",
      "\\(^o^)/",
      "(งᐛ )ง",
      "ᕦ(ò_óˇ)ᕤ",
      "(ง •̀_•́)ง",
    ],
  },
  {
    label: "슬픔",
    items: [
      "(´；ω；`)",
      "(ᅲ﹏ᅲ)",
      "(っ˘̩╭╮˘̩)っ",
      "(个_个)",
      "(╥_╥)",
      "( ; ; )",
      "(ノ_<、)",
      "(ᗒᗣᗕ)՞",
    ],
  },
  {
    label: "동물",
    items: [
      "ʕ•ᴥ•ʔ",
      "(=^･ω･^=)",
      "(・⊝・)",
      "ᨐฅ",
      "(=①ω①=)",
      "ʕ￫ᴥ￩ʔ",
      "(°(°ω(°ω°(☆ω☆)°ω°)ω°)°)",
      "〜(꒪꒳꒪)〜",
    ],
  },
  {
    label: "인사",
    items: [
      "(^_^)/",
      "(￣^￣)ゞ",
      "(*ᴗ͈ˬᴗ͈)ꕤ",
      "ヾ(＾-＾)ノ",
      "(o´▽`o)ﾉ",
      "( ´ ▽ ` )ﾉ",
      "(・∀・)ノ",
      "★~(◡﻿‿◕✿)",
    ],
  },
];

const RECENT_KEY = "esl:chat:recent-kaomoji";
const RECENT_MAX = 8;

export function recentKaomoji(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export function pushRecentKaomoji(k: string): void {
  try {
    const next = [k, ...recentKaomoji().filter((x) => x !== k)].slice(
      0,
      RECENT_MAX,
    );
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // localStorage 불가 환경 — 최근 목록만 포기
  }
}

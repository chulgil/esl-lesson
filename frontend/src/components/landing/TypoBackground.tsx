/** 비로그인 랜딩용 타이포그래피 배경 — 학습 소재(단어/숙어/패턴/문장)가 노트 위에 흩어진 연출 */

const WORDS: {
  text: string;
  size: string;
  x: string;
  y: string;
  rotate: string;
  color: string;
}[] = [
  {
    text: "resilient",
    size: "text-7xl",
    x: "left-[4%]",
    y: "top-[8%]",
    rotate: "-rotate-6",
    color: "text-brick-blue/15",
  },
  {
    text: "get it over with",
    size: "text-4xl",
    x: "left-[55%]",
    y: "top-[5%]",
    rotate: "rotate-3",
    color: "text-brick-red/15",
  },
  {
    text: "It takes ___ to ...",
    size: "text-5xl",
    x: "left-[62%]",
    y: "top-[30%]",
    rotate: "-rotate-2",
    color: "text-ink/10",
  },
  {
    text: "spaced repetition",
    size: "text-3xl",
    x: "left-[8%]",
    y: "top-[38%]",
    rotate: "rotate-6",
    color: "text-brick-green/20",
  },
  {
    text: "There is a tree over there",
    size: "text-4xl",
    x: "left-[30%]",
    y: "top-[55%]",
    rotate: "-rotate-3",
    color: "text-brick-yellow/30",
  },
  {
    text: "vocabulary",
    size: "text-6xl",
    x: "left-[70%]",
    y: "top-[62%]",
    rotate: "rotate-6",
    color: "text-brick-blue/10",
  },
  {
    text: "figure out",
    size: "text-5xl",
    x: "left-[12%]",
    y: "top-[72%]",
    rotate: "-rotate-6",
    color: "text-brick-red/10",
  },
  {
    text: "(있다, 나무가, 저기에)",
    size: "text-2xl",
    x: "left-[36%]",
    y: "top-[63%]",
    rotate: "-rotate-3",
    color: "text-ink/15",
  },
  {
    text: "phrasal verb",
    size: "text-3xl",
    x: "left-[45%]",
    y: "top-[18%]",
    rotate: "rotate-2",
    color: "text-ink/10",
  },
  {
    text: "come up with",
    size: "text-4xl",
    x: "left-[20%]",
    y: "top-[22%]",
    rotate: "rotate-1",
    color: "text-brick-green/15",
  },
  {
    text: "forgetting curve",
    size: "text-3xl",
    x: "left-[75%]",
    y: "top-[45%]",
    rotate: "-rotate-6",
    color: "text-margin-red/40",
  },
  {
    text: "keep in mind",
    size: "text-4xl",
    x: "left-[52%]",
    y: "top-[78%]",
    rotate: "rotate-3",
    color: "text-brick-blue/15",
  },
];

export function TypoBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {WORDS.map((word, i) => (
        <span
          key={i}
          className={`absolute select-none whitespace-nowrap font-bold ${word.size} ${word.x} ${word.y} ${word.rotate} ${word.color} animate-typo-float`}
          style={{ animationDelay: `${(i % 6) * 0.8}s` }}
        >
          {word.text}
        </span>
      ))}
    </div>
  );
}

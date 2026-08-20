/** 영어 단어 발음 재생 — 브라우저 내장 TTS (서버 비용 없음, docs/proposal/word-insight.md P1)
 *
 *  음성 선택을 브라우저에 맡기면 안 된다. 시스템 로케일이 한국어인 맥에서는
 *  en 음성 41개 중 default 플래그가 붙은 것이 하나도 없어(2026-07-27 계측),
 *  lang="en-US" 만 준 경우 목록 첫 항목인 Albert(F0 229Hz, 쉰 목소리) 나
 *  시스템이 유일하게 male 로 표기하는 Fred(포먼트 합성, 쇳소리) 가 걸린다.
 *  둘 다 학습용으로 못 쓴다. 아래 우선순위로 성인 남성 음성을 명시 지정한다.
 */

/** 우선순위 — 이름 부분일치(대소문자 무시), 같은 이름이면 en-US 를 먼저 */
const PREFERRED_VOICES = [
  "Alex", // 맥 클래식 성인 남성 (가장 또렷)
  "Aaron", // 맥/iOS 성인 남성
  "Tom", // 맥 성인 남성
  "Reed", // 맥 13+ 성인 남성 (F0 107Hz)
  "Eddy", // 맥 13+ 성인 남성 (F0 120Hz)
  "Microsoft Guy",
  "Microsoft Christopher",
  "Microsoft Eric",
  "Microsoft Andrew",
  "Microsoft David",
  "Microsoft Mark",
  "Google UK English Male",
  "Daniel", // 영국 성인 남성 (F0 111Hz) — 미국 음성이 없을 때 폴백
];

/** 폴백 단계에서도 절대 고르면 안 되는 장난용·기계음 음성 (맥 기본 탑재) */
const AVOID_VOICES = [
  "albert",
  "bad news",
  "bahh",
  "bells",
  "boing",
  "bruce",
  "bubbles",
  "cellos",
  "deranged",
  "fred",
  "good news",
  "grandma",
  "grandpa",
  "hysterical",
  "jester",
  "junior",
  "kathy",
  "organ",
  "princess",
  "ralph",
  "superstar",
  "trinoids",
  "whisper",
  "wobble",
  "zarvox",
];

let cachedVoice: SpeechSynthesisVoice | null = null;

function isEnglish(voice: SpeechSynthesisVoice) {
  return voice.lang.replace("_", "-").toLowerCase().startsWith("en");
}

function isUs(voice: SpeechSynthesisVoice) {
  return voice.lang.replace("_", "-").toLowerCase().startsWith("en-us");
}

function isAvoided(voice: SpeechSynthesisVoice) {
  const name = voice.name.toLowerCase();
  return AVOID_VOICES.some((bad) => name.includes(bad));
}

function pickVoice(
  voices: SpeechSynthesisVoice[],
): SpeechSynthesisVoice | null {
  const english = voices.filter(isEnglish);
  if (english.length === 0) return null;

  for (const wanted of PREFERRED_VOICES) {
    // 맥은 이름이 로케일별로 "Reed (영어(미국))" 처럼 나와 부분일치로 찾는다
    const matches = english.filter((v) =>
      v.name.toLowerCase().includes(wanted.toLowerCase()),
    );
    const hit = matches.find(isUs) ?? matches[0];
    if (hit) return hit;
  }

  // 우선순위에 하나도 없으면 장난용만 걸러 남은 것 중 미국 영어 우선
  const usable = english.filter((v) => !isAvoided(v));
  return usable.find(isUs) ?? usable[0] ?? null;
}

function supported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** 음성 목록은 비동기로 채워진다 — 클릭 전에 미리 로드해 첫 재생부터 제 음성이 나오게 */
export function primeVoices() {
  if (!supported() || cachedVoice) return;
  const resolve = () => {
    cachedVoice = pickVoice(window.speechSynthesis.getVoices());
  };
  resolve();
  if (!cachedVoice) {
    window.speechSynthesis.addEventListener("voiceschanged", resolve, {
      once: true,
    });
  }
}

/** 브라우저 내장 TTS — 서버 신경망 음성 실패 시 폴백 전용 */
function speakWithBrowserTts(word: string) {
  if (!supported()) return;
  if (!cachedVoice) cachedVoice = pickVoice(window.speechSynthesis.getVoices());

  const utter = new SpeechSynthesisUtterance(word);
  if (cachedVoice) {
    utter.voice = cachedVoice;
    utter.lang = cachedVoice.lang;
  } else {
    utter.lang = "en-US";
  }
  utter.rate = 0.9; // 학습용 — 조금 천천히 또렷하게
  utter.pitch = 1;
  utter.volume = 1;
  window.speechSynthesis.cancel();
  // Chrome 은 탭이 백그라운드를 다녀오면 큐가 paused 로 굳는다 — 재개 후 발화
  window.speechSynthesis.resume();
  window.speechSynthesis.speak(utter);
}

let currentAudio: HTMLAudioElement | null = null;
let unlockedAudio: HTMLAudioElement | null = null;

// 무음 WAV — 제스처 컨텍스트에서 한 번 재생해 오디오 채널을 해금한다
const SILENT_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

/** 오디오 자동 재생 해금 — 사용자 제스처(탭/클릭) 안에서 1회 호출.
 *
 *  모바일 브라우저는 제스처 없이 생성된 Audio.play() 를 거부한다 — 빙고처럼
 *  서버 메시지(bg.round)가 재생을 트리거하는 화면에서 "재생됐다 안 됐다"의
 *  원인 (2026-08-20 보고). 제스처 안에서 해금한 요소를 재사용하면 이후
 *  src 교체 재생이 허용된다 (iOS 포함). TTS 큐도 같이 깨운다. */
export function unlockAudio() {
  if (typeof window === "undefined" || unlockedAudio) return;
  try {
    const audio = new Audio(SILENT_WAV);
    audio.play().catch(() => undefined);
    unlockedAudio = audio;
  } catch {
    // Audio 미지원 — TTS 폴백만 사용
  }
  if (supported()) {
    window.speechSynthesis.resume();
  }
  primeVoices();
}

/** 단어 발음 재생 — 서버 신경망 TTS(캐시) 우선, 실패 시 브라우저 TTS 폴백.
 *
 *  브라우저 내장 음성은 기기 의존이라 기계음이 흔했다 (2026-08-05 보고).
 *  제스처에서 해금한 요소(unlockAudio)가 있으면 src 교체로 재사용 — 서버
 *  메시지 트리거 재생도 자동 재생 정책을 통과한다. src 가 곧 인증 요청이라
 *  (same-origin 쿠키) 별도 fetch 가 필요 없다. */
export function speakWord(word: string) {
  if (typeof window === "undefined") return;
  currentAudio?.pause();

  let fellBack = false;
  const fallback = () => {
    if (fellBack) return; // play 거부 + error 이벤트 이중 발화 가드
    fellBack = true;
    speakWithBrowserTts(word);
  };

  const src = `/api/tts?text=${encodeURIComponent(word)}`;
  const audio = unlockedAudio ?? new Audio();
  audio.onerror = fallback;
  audio.src = src;
  currentAudio = audio;
  audio.play().catch(fallback);
}

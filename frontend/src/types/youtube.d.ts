/** YouTube IFrame Player 전역 타입 (SegmentPlayer, 라이브러리 상세 공용) */
interface YTPlayer {
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  playVideo(): void;
  pauseVideo(): void;
  getCurrentTime(): number;
  /** 섀도잉 배속 (0.75/1.0 — ted-routine P1-2) */
  setPlaybackRate(rate: number): void;
  destroy?: () => void;
}

interface Window {
  YT?: { Player: new (el: HTMLElement | string, opts: object) => YTPlayer };
  onYouTubeIframeAPIReady?: () => void;
}

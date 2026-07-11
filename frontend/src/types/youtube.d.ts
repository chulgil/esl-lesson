/** YouTube IFrame Player 전역 타입 (SegmentPlayer, 라이브러리 상세 공용) */
interface YTPlayer {
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  playVideo(): void;
  pauseVideo(): void;
  getCurrentTime(): number;
  destroy?: () => void;
}

interface Window {
  YT?: { Player: new (el: HTMLElement | string, opts: object) => YTPlayer };
  onYouTubeIframeAPIReady?: () => void;
}

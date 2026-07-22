"""단어 정렬 — stable-ts 로 오디오에 자막 텍스트를 정렬 (docs/specs/word-alignment.md).

서버가 아니라 로컬 Mac 에이전트에서 실행된다. stable-ts/torch 는 지연 임포트.
"""

import os
import subprocess
import tempfile


def remap_result_to_segments(result_segments, seg_count: int) -> dict | None:
    """stable-ts align(original_split=True) 결과를 seq→단어시각 으로 변환.

    입력 텍스트를 세그먼트당 한 줄로 주면 결과 세그먼트가 줄 단위로 나뉘어
    인덱스가 seq 와 일치한다. 개수 불일치/빈 세그먼트는 None(폴백)로 안전 처리.
    """
    if len(result_segments) != seg_count:
        return None
    out: dict[int, list[dict]] = {}
    for seq, rseg in enumerate(result_segments):
        words = []
        for w in rseg.words:
            text = (w.word or "").strip()
            if not text:
                continue
            words.append({"w": text, "s": round(w.start * 1000), "e": round(w.end * 1000)})
        if not words:
            return None
        out[seq] = words
    return out


class StableTsAligner:
    """stable-ts 정렬기. 모델은 최초 사용 시 1회 로드 후 캐시."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.environ.get("ESL_ALIGN_MODEL", "base.en")
        self._model = None

    def _load(self):
        if self._model is None:
            import stable_whisper  # 지연 임포트 (torch)

            self._model = stable_whisper.load_model(self._model_name)
        return self._model

    def align(self, audio_path: str, segments: list[tuple[int, str]]) -> dict | None:
        model = self._load()
        text = "\n".join(en for _, en in segments)
        result = model.align(audio_path, text, language="en", original_split=True)
        return remap_result_to_segments(result.segments, len(segments))


def download_audio(video_id: str) -> str:
    """yt-dlp 로 bestaudio 를 임시 디렉토리에 내려받아 경로 반환 (ffmpeg 필요).

    호출측이 os.path.dirname(경로) 를 정리한다.
    """
    tmpdir = tempfile.mkdtemp(prefix="esl-align-")
    subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bestaudio",
            "--extract-audio",
            "--audio-format",
            "m4a",
            "-o",
            os.path.join(tmpdir, "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        check=True,
        capture_output=True,
    )
    return os.path.join(tmpdir, f"{video_id}.m4a")

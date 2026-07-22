"""단어 정렬 적용 — words 저장 + 세그먼트 경계 재계산 (docs/specs/word-alignment.md)."""

from app.models import TranscriptSegment


def apply_alignment(segments: list[TranscriptSegment], alignments: dict[int, list[dict]]) -> int:
    """seq→단어시각 을 세그먼트에 적용. start/end 를 단어 시각에서 파생하고
    인접 세그먼트 겹침을 단조 클램프한다. 갱신된 세그먼트 수 반환."""
    by_seq = {s.seq: s for s in segments}
    updated = 0
    for seq, words in alignments.items():
        seg = by_seq.get(seq)
        if seg is None or not words:
            continue
        seg.words = [{"w": w["w"], "s": int(w["s"]), "e": int(w["e"])} for w in words]
        seg.start_ms = seg.words[0]["s"]
        seg.end_ms = max(seg.start_ms, seg.words[-1]["e"])
        updated += 1

    ordered = sorted(segments, key=lambda s: s.seq)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if prev.words and cur.words and prev.start_ms is not None:
            prev.end_ms = max(prev.start_ms, min(prev.end_ms, cur.start_ms))
    return updated

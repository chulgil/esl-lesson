"""에이전트 정렬 라이브러리 — remap 순수 로직 (docs/specs/word-alignment.md)."""

from types import SimpleNamespace

from scripts.lib.align import remap_result_to_segments


def _word(text, start, end):
    return SimpleNamespace(word=text, start=start, end=end)


def _seg(words):
    return SimpleNamespace(words=words)


def test_remap_index_maps_when_counts_match():
    result_segments = [
        _seg([_word(" Hi", 0.10, 0.70), _word(" there", 0.70, 1.40)]),
        _seg([_word(" Bye", 5.20, 5.90)]),
    ]
    out = remap_result_to_segments(result_segments, [0, 1])
    assert out == {
        0: [{"w": "Hi", "s": 100, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
        1: [{"w": "Bye", "s": 5200, "e": 5900}],
    }


def test_remap_returns_none_on_count_mismatch():
    result_segments = [_seg([_word("a", 0.0, 0.1)])]
    assert remap_result_to_segments(result_segments, [0, 1]) is None


def test_remap_returns_none_when_segment_has_no_words():
    result_segments = [_seg([_word("a", 0.0, 0.1)]), _seg([])]
    assert remap_result_to_segments(result_segments, [0, 1]) is None


def test_remap_keys_by_real_seq_not_position():
    result_segments = [
        _seg([_word(" Hi", 0.10, 0.70)]),
        _seg([_word(" Bye", 5.20, 5.90)]),
    ]
    out = remap_result_to_segments(result_segments, [5, 9])
    assert set(out.keys()) == {5, 9}
    assert out[5] == [{"w": "Hi", "s": 100, "e": 700}]
    assert out[9] == [{"w": "Bye", "s": 5200, "e": 5900}]


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _FakeClient:
    """pending-alignments 1건 반환 후, 이후 호출 기록."""

    def __init__(self, items):
        self._items = items
        self.posts = []

    def get(self, url):
        return _FakeResp(payload={"items": self._items})

    def post(self, url, json=None):
        self.posts.append((url, json))
        return _FakeResp(
            status_code=202, payload={"aligned": len(json["alignments"]) if json else 0}
        )


def test_process_alignments_submits_mapped_words(monkeypatch):
    from scripts import transcript_agent

    items = [
        {
            "content_id": 7,
            "youtube_video_id": "vid00000007",
            "segments": [{"seq": 0, "en_text": "Hi."}],
        }
    ]
    client = _FakeClient(items)

    class FakeAligner:
        def align(self, audio_path, segments):
            return {0: [{"w": "Hi", "s": 10, "e": 90}]}

    processed = transcript_agent.process_alignments_once(
        client, aligner=FakeAligner(), downloader=lambda vid: "/tmp/none.m4a"
    )
    assert processed == 1
    assert client.posts[0][0].endswith("/api/agent/transcripts/7/alignment")
    assert client.posts[0][1] == {"alignments": {0: [{"w": "Hi", "s": 10, "e": 90}]}}


def test_process_alignments_reports_failed_on_none(monkeypatch):
    from scripts import transcript_agent

    items = [
        {
            "content_id": 8,
            "youtube_video_id": "vid00000008",
            "segments": [{"seq": 0, "en_text": "Hi."}],
        }
    ]
    client = _FakeClient(items)

    class FakeAligner:
        def align(self, audio_path, segments):
            return None  # 매핑 실패

    transcript_agent.process_alignments_once(
        client, aligner=FakeAligner(), downloader=lambda vid: "/tmp/none.m4a"
    )
    assert client.posts[0][0].endswith("/api/agent/transcripts/8/alignment/failed")

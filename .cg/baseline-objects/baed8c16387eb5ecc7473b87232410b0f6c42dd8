# pdf-rag-ingest — 상세 레퍼런스

## 의존성

| 도구 | 버전 | 설치 |
|------|------|------|
| ocrmypdf | 17.x | `pipx install --python python3.13 ocrmypdf` |
| tesseract | 5.x | `brew install tesseract tesseract-lang` (kor + kor_vert 포함) |
| pymupdf | 1.24+ | `uv add pymupdf` |
| pymupdf4llm | 0.0.17+ | `uv add pymupdf4llm` |
| qdrant-client | 1.12+ | `uv add qdrant-client` |
| FlagEmbedding | 1.3+ | `uv add FlagEmbedding` (BGE-M3 dense+sparse) |

> macOS 주의: brew Python 3.14 에서 ocrmypdf 가 `_expat` import 에러를 낸다. **pipx + Python 3.13** 으로 격리 설치.

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `ImportError: No module named expat` | brew python 3.14 packaging bug | `pipx install --python python3.13 ocrmypdf` |
| OCR 결과에 한글 0% | tesseract kor 미설치 | `brew install tesseract-lang` |
| 청크 page 메타데이터 누락 | pymupdf4llm OCR 폴백 경로 | OCR 사전처리로 해결 (이 스킬의 목적) |
| Qdrant 컬렉션 vector dim mismatch | BGE-M3 (1024) vs 기존 (예: 384) | 신규 컬렉션 생성 후 alias 교체 |
| `--output-type pdfa` 실패 | Ghostscript 의존성 | `--output-type pdf` 로 변경 (PDF/A 비활성화) |

## 자동화 (선택)

`ebook-qdrant-mcp` 프로젝트에 다음 자산이 추가되면 이 스킬은 더 짧아진다:

- `ebook-qdrant-ocr <dir>` CLI — 진단 + OCR 배치를 한 명령으로
- `ebook-qdrant-ocr <dir> --auto-ingest` — OCR 후 자동 인덱싱
- watch 데몬 — 새 PDF 감지 시 텍스트 레이어 부재면 자동 OCR → 인덱싱

CLI/데몬 부재 시 이 스킬의 절차를 수동 수행.

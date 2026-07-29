---
name: pdf-rag-ingest
description: 한국어 PDF(스캔본 포함)를 깨지지 않게 Qdrant RAG 컬렉션에 인덱싱합니다. 이미지-only PDF는 OCRmyPDF(kor+eng)로 텍스트 레이어 주입 후 pymupdf4llm + BGE-M3 하이브리드 임베딩으로 색인. 트리거: PDF 인덱싱, 한글 OCR, 스캔본, RAG에 책 넣기, ebooks_v2, 한글 깨짐, mojibake
---

# PDF RAG Ingest — 한국어 PDF → Qdrant 인덱싱

## 목적

스캔본 한국어 PDF를 RAG 컬렉션에 넣을 때 **텍스트가 깨져 들어가는 사고**를 막는다. pymupdf4llm은 텍스트 레이어가 없는 PDF에서 Tesseract OCR로 폴백하지만 기본 언어가 `eng` 라 한글이 mojibake로 들어간다. 이 스킬은 인덱싱 전에 OCRmyPDF로 한글 OCR 텍스트 레이어를 주입해 멱등(idempotent)하게 처리한다.

## 적용 대상

- 한국어 PDF 묶음 (전자책, 스캔 자료, 사내 문서)
- 일부는 디지털 텍스트 레이어가 이미 있고, 일부는 이미지-only (혼재)
- 결과를 Qdrant 하이브리드 컬렉션 (dense + sparse, BGE-M3) 에 인덱싱

## 의존성

ocrmypdf 17.x · tesseract 5.x (kor 포함) · pymupdf · pymupdf4llm · qdrant-client · FlagEmbedding (BGE-M3).
버전·설치 명령 전체는 [reference.md](reference.md) §의존성.

> macOS 주의: brew Python 3.14 에서 ocrmypdf 가 `_expat` import 에러를 낸다. **pipx + Python 3.13** 으로 격리 설치.

## 입력

- PDF 디렉토리 (예: `~/Documents/Ebook/`)
- Qdrant 연결 정보 (`QDRANT_URL`, `QDRANT_API_KEY`) — `.env` 에서 로딩
- 컬렉션 이름 (예: `ebooks_v2`)

## 출력

- `<PDF_DIR>/.ocr_out/` — OCR 텍스트 레이어가 주입된 PDF (원본은 보존)
- `/tmp/ocr_logs/*.log` — 파일별 OCR 로그
- Qdrant 컬렉션: 청크 페이로드 `{text, page, section_path, source, source_file, chunk_index, file_hash}`

## 절차

### 1. 진단 (mojibake 위험 식별)

각 PDF의 첫 페이지를 PyMuPDF로 열어 `page.get_text()` 길이를 측정한다.

```python
import fitz
doc = fitz.open(pdf_path)
text_len = len(doc[0].get_text())
needs_ocr = text_len < 50  # threshold
```

- `text_len >= 50` → 디지털 PDF, OCR 불필요 (스킵 리스트)
- `text_len < 50` → 이미지-only, OCR 필수

### 2. OCR (4-way 병렬 배치)

```bash
ocrmypdf -l kor+eng --skip-text --output-type pdf --quiet INPUT.pdf OUTPUT.pdf
```

병렬 실행:

```bash
find "$PDF_DIR" -maxdepth 1 -name '*.pdf' -print0 | \
  xargs -0 -n 1 -P 4 -I {} bash -c 'process_one "$@"' _ {}
```

- `--skip-text`: 텍스트 레이어가 있는 페이지는 보존, 이미지 페이지에만 OCR
- `--output-type pdf`: PDF/A 변환 비활성화 (속도 ↑)
- `-l kor+eng`: 한글 + 영어 혼합 (영어 단어는 영문 OCR 엔진 사용)

**멱등성**: `OUTPUT.pdf` 가 이미 존재하면 스킵.

### 3. 검증 (샘플 텍스트 확인)

OCR 직후 결과 PDF에서 첫 페이지를 추출해 한글 비율을 확인한다.

```python
import fitz, re
doc = fitz.open(ocr_out_path)
text = doc[0].get_text()
hangul = len(re.findall(r'[가-힣]', text))
ratio = hangul / max(len(text), 1)
assert ratio > 0.1, f"한글 비율 너무 낮음 — OCR 실패 의심: {ratio:.2%}"
```

`ratio < 10%` 면 OCR 실패 가능성. 로그(`/tmp/ocr_logs/<name>.log`)에서 tesseract 에러 확인.

### 4. 인덱싱 (pymupdf4llm + BGE-M3 → Qdrant)

```python
import pymupdf4llm
chunks = pymupdf4llm.to_markdown(ocr_out_path, page_chunks=True)
# 각 chunk: {"metadata": {"page": N, ...}, "text": "..."}
```

- 페이지 단위 마크다운 추출 (`page_chunks=True`)
- 2단계 분할: `MarkdownHeaderTextSplitter` (제목 보존) → `RecursiveCharacterTextSplitter` (크기 제한)
- BGE-M3 로 dense (1024-d) + sparse 임베딩 동시 생성
- Qdrant multi-vector 컬렉션에 upsert (`file_hash` 로 중복 방지)

### 5. 재인덱싱 (mojibake 데이터 정리)

기존 컬렉션에 깨진 데이터가 들어 있으면 **새 컬렉션** 으로 갈아탄다 (downtime 회피).

```python
client.create_collection(name="ebooks_v3", ...)
# 인덱싱 완료 후
client.delete_collection(name="ebooks_v2")
client.update_aliases(...)  # alias 사용 시
```

## 검증 (Evidence-Based Completion)

완료 선언 전 다음 증거를 수집한다.

| 단계 | 증거 |
|------|------|
| 진단 | 진단 리포트: 디지털 N개 / OCR 필요 M개 |
| OCR | `ls .ocr_out/ \| wc -l` == 입력 PDF 수 - 스킵 수 |
| 검증 | 한글 비율 평균 ≥ 30% (스캔 품질이 정상일 때) |
| 인덱싱 | `client.count(collection)` == 예상 청크 수 (±5%) |
| 샘플 쿼리 | 책 제목으로 검색 → 해당 책의 chunks 가 top-3 안에 등장 |

## 금지 사항

- **OCR 없이 이미지-only PDF 인덱싱** — mojibake 컬렉션이 만들어진다
- **`-l eng` 단독 사용** — 한국어가 깨진다. 항상 `-l kor+eng`
- **`--force-ocr`** — 이미 텍스트 레이어가 있는 페이지를 덮어쓴다. `--skip-text` 사용
- **원본 덮어쓰기** — 원본은 보존, OCR 결과는 `.ocr_out/` 에 분리
- **brew 의 Python 3.14 로 ocrmypdf 실행** — `_expat` 에러. pipx + python3.13 사용
- **검증 단계 생략** — OCR 실패도 종료 코드 0 인 경우가 있음. 한글 비율 체크 필수

> 상세: [reference.md](reference.md) — 트러블슈팅(증상·원인·해결) · 자동화(`ebook-qdrant-ocr` CLI/watch 데몬) 옵션.

## 상위 규칙과의 관계

- [rules/golden-principles.md §10 Evidence-Based Completion](../../rules/golden-principles.md): 검증 단계의 증거 수집은 필수
- [rules/verification.md](../../rules/verification.md): "OCR 끝났다" 만으로는 완료 선언 금지 — 샘플 한글 비율 확인 후 선언
- [rules/adaptive-quality.md](../../rules/adaptive-quality.md): 데이터 마이그레이션 성격 → **ultra** 모드 적용 (재인덱싱 시 백업 + 신규 컬렉션 우선)

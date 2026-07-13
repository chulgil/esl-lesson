# 스펙: 단어 인사이트 — 단어 정보 카드

> 최종 수정: 2026-07-13 · P1 구현 완료 · 기획 배경: [proposal/word-insight.md](../proposal/word-insight.md)

학습 피드백 화면에서 단어를 눌러 뉘앙스·유사단어·예문을 보는 카드.
말해보카 오답노트 벤치마크 + "내 영상 문맥" 차별화.

## UX (P1)

- 진입점: 학습 채점 피드백의 정답 옆 **[단어 정보]** 버튼 — `level <= 2`
  (단어·숙어)만 노출. 패턴/문장은 문장 단위라 제외
- 바텀시트: 헤더(단어 + TTS 재생 + 닫기) → IPA·품사 → 뉘앙스 →
  예문 2 → 자주 붙는 표현 → 유의어 → 헷갈리기 쉬운 단어
- TTS 는 브라우저 내장 SpeechSynthesis (en-US, 서버 비용 0)
- 최초 조회는 생성 시간 수 초 — 스켈레톤 + "만들고 있어요" 안내
- 실패 시: "불러오지 못했어요 — 다시 열어주세요" (재시도 = 재조회)

## 데이터/생성 규칙

- `word_insights(item_id unique FK, payload JSONB, model, created/updated)`
- **lazy 생성**: 최초 조회 시 1회 생성 후 영구 캐시. learning_items 가 전역
  공유이므로 사용자 무관 1단어 1회 비용으로 수렴
- 모델: `anthropic_insight_model` (기본 haiku). 예문은 occurrence 의
  `context_en` 최대 2개를 프롬프트에 제공 — 첫 예문으로 재사용 유도
- payload 스키마: `ipa, pos, nuance_ko, examples[{en,ko}], collocations[],
  synonyms[{word,ko,diff_ko}], confusables[{word,ko,diff_ko}]`
- 동시 생성 경합: item_id unique 위반 시 롤백 후 승자 레코드 반환

## API

| 메서드/경로 | 동작 |
|---|---|
| GET `/api/study/items/{item_id}/insight` | 캐시 반환 또는 생성. 404 항목 없음, 502 생성 실패(재시도 유도) |

## P2 (구현 완료 — 2026-07-13)

- **임베딩**: Voyage `voyage-3.5-lite` (1024d) → `item_embeddings(halfvec(1024))`
  + HNSW `halfvec_cosine_ops`. 파이프라인 `embed` 단계(신규 콘텐츠 자동) +
  `scripts/backfill_embeddings.py`(기존 항목, PYTHONPATH=/app 로 실행). 키
  미설정/비 postgres 는 전 기능 안전 스킵(랜덤 폴백)
- **오답 선지 개선**: 선다 오답 = 유사단어 2개 우선 + 랜덤 1개 배합
- **"아깝다" 판정**: 오답 텍스트가 정답의 임베딩 top-5 유사단어와 일치하면
  `/study/answer` 응답에 `close_match{en,ko}` → 피드백 화면에 비교 카드
  (내가 고른 답 vs 정답 나란히 + 단어 정보 진입)
- P3 후보: 유사단어 원탭 학습 추가, 어휘망 뷰
- 상세 근거: [proposal/word-insight.md](../proposal/word-insight.md)

# 스펙: 단어 인사이트 — 단어 정보 카드

> 최종 수정: 2026-07-14 · P1-P3 구현 완료 · 기획 배경: [proposal/word-insight.md](../proposal/word-insight.md)

학습 피드백 화면에서 단어를 눌러 뉘앙스·유사단어·예문을 보는 카드.
말해보카 오답노트 벤치마크 + "내 영상 문맥" 차별화.

## UX (P1)

- 진입점: 학습 채점 피드백의 정답 옆 **[단어 정보]** 버튼 — `level <= 2`
  (단어·숙어)만 노출. 패턴/문장은 문장 단위라 제외
- 바텀시트: 헤더(단어 + TTS 재생 + 닫기) → IPA·품사 → 뉘앙스 →
  예문 2 → 자주 붙는 표현 → 유의어 → 헷갈리기 쉬운 단어
- TTS 는 브라우저 내장 SpeechSynthesis (en-US, 서버 비용 0)
- **음성은 반드시 명시 지정** (`frontend/src/lib/speech.ts`). `lang="en-US"` 만 주면 시스템 로케일이 한국어인 맥에서 en 음성 41개 중 default 플래그가 하나도 없어 목록 첫 항목 Albert(F0 229Hz, 쉰 목소리) 나 시스템이 유일하게 male 로 표기하는 Fred(포먼트 합성) 가 걸린다 — 학습용으로 못 씀 (2026-07-27 계측). 성인 남성 우선순위(Alex/Aaron/Tom/Reed/Eddy/Microsoft·Google 남성/Daniel) + 장난용 음성 블랙리스트로 선택하고 `rate 0.9` 로 재생.
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
- **P3 (2026-07-13)**: "아깝다" 카드에서 헷갈린 단어를
  `POST /api/cards` 로 **원탭 학습 추가** (중복은 기존 카드 반환)
- 상세 근거: [proposal/word-insight.md](../proposal/word-insight.md)

## 어휘망 뷰 (P3 완결 — 2026-07-14)

- GET `/api/study/network` — 노드=내 word/idiom 카드(suspend 제외, 최근 300),
  엣지=임베딩 근접(노드당 최대 4, 거리 임계 0.55), 추천=덱 밖 최근접
  (가시성 통과분만, 최대 12). 임베딩 비활성 환경은 노드만 반환(안전 스킵)
- 이웃 검색은 `item_embeddings` LATERAL top-k(행별 HNSW 스캔), 그래프 조립은
  순수 함수 `vocab_network.build_network` (양방향 쌍 dedup + 노드당 상한)
- `/study/network`: 자체 force-directed 캔버스(의존성 없음) — 팬/휠/핀치 줌,
  탭 선택 시 이웃 하이라이트, 레이아웃 안정 후 1회 자동 핏. 상태색
  (새=파랑/학습=노랑/복습=초록/재학습=빨강), 추천은 점선 고스트
- 노드 탭 → 하단 패널: 내 단어=[단어 정보](InsightSheet), 추천=[+ 학습에 추가]
  (`POST /api/cards` 재사용, 추가 즉시 새 단어로 편입 표시)
- 진입점: 홈 대시보드 "내 어휘망 보기", 학습 세션 완료 화면 "어휘망 보기"

# 스펙: 채팅 자동번역·다국어 학습 (Phase 1~3)

> 작성: 2026-08-12 (구현 동시) · 계획: prompt_plan.md
> 목표: 자주 쓰는 채팅이 학습언어로 자동 번역되어 노출량으로 익숙해지게 한다.
> 지원 언어는 ko/en/ja 3개 — `services/langs.py` 가 단일 근거.

## 언어 설정 (user_settings)

| 필드 | 기본 | 의미 |
|---|---|---|
| primary_lang | ko | 주언어(모국어) — 번역 도착지 |
| learning_langs | ["en"] | 학습언어(복수) — 주언어 메시지의 번역 목적지(첫 항목) |
| chat_translate | false | 채팅 자동번역 ON/OFF |

번역 방향: 메시지 언어(휴리스틱 감지 — 한글→ko, 가나→ja, 그 외→en)가
주언어면 → 학습언어[0], 아니면 → 주언어. 같으면 번역 없음.

## 비용 방어 4계층 (2026-08-12 확정)

```
① 전역 문장 캐시 chat_translations (text_key+target_lang 유니크, 사용자 무관)
② DeepL Free (DEEPL_API_KEY, 월 50만 자 무료) — 실패/미설정 시
③ Haiku 폴백 (anthropic_translate_model)
④ 하드캡: 월 TRANSLATE_MONTHLY_BUDGET_CHARS(기본 200만 자) 초과 또는
   사용자 일일 TRANSLATE_USER_DAILY_LIMIT(200건) 초과 → 번역만 조용히 중단
```

- 캐시 히트는 비용 0·usage 미기록. 엔진 호출만 translation_usage 원장에 기록
- 백오피스 `/api/admin/translation-usage` — 월 글자수/예산·엔진별·오늘 호출

## API

| 경로 | 역할 |
|---|---|
| GET /api/chat/with/{id}/messages | 최상위 `translate`(뷰어 설정) + 최신 30개에 `translation:{lang,text}\|null` 동봉 |
| GET /api/chat/messages/{id}/translation | WS 수신 메시지 단건 번역 (대화 참가자만) |
| GET /api/tts?text&lang=en\|ko\|ja | edge-tts (보이스: langs.TTS_VOICES, 캐시 tts_audio) |
| PATCH /api/settings | primary_lang·learning_langs·chat_translate (검증: SUPPORTED 부분집합, 주언어 제외, 비어있지 않음) |

## 프론트

- 설정 "언어·번역" 카드(LanguageCard): 주언어 1개 + 학습언어 복수 칩 + 자동번역 토글
- 채팅 3뷰(NoteSkin/ExcelSkin/위젯) 공통 `TranslationLine`: 본문 아래 회색
  번역 줄 + 스피커(해당 언어 TTS). 위장 테마에선 각주처럼 보인다
- WS 수신 메시지는 클라이언트가 단건 번역 엔드포인트로 지연 로드

## 콘텐츠 다국어 (Phase 3)

- `contents.lang` en/ja/ko (기존 en 백필) — 자막 fetch·번역 프롬프트·추출
  프롬프트가 이 언어를 따른다. 번역 대상(ko_text)은 ko 고정 — 시청자별
  번역은 Phase 4
- 세그먼트·학습 항목의 `en_text` 필드에는 콘텐츠 언어의 원문이 담긴다
  (필드명은 역사적 유산 — Phase 4 에서 text/native 로 일반화 예정)
- 등록: 언어 선택(기본 영어) + 유튜브 defaultAudioLanguage 자동 감지.
  라이브러리: ja/ko 배지 + 언어 필터 칩

## Phase 4 (미착수 — 별도 승인)

en_text/ko_text 데이터 모델 일반화, 게임 6종 다국어(타자 자판·어순 분절 등
게임별 재설계). 위험이 커서 1~3 배포 후 사용 데이터 보고 진행 판단.

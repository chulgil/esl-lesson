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
| translate_mine | true | 내가 쓴 글 번역 (2026-08-12 — 기본, 1차 목표) |
| translate_theirs | false | 상대가 쓴 글 번역 — 둘 다 체크하면 전체 번역 |

번역 방향: 메시지 언어(휴리스틱 감지 — 한글→ko, 가나→ja, 그 외→en)가
주언어면 → 학습언어[0], 아니면 → 주언어. 같으면 번역 없음.

## 비용 방어 4계층 (2026-08-12 확정)

```
① 전역 문장 캐시 chat_translations (text_key+target_lang 유니크, 사용자 무관)
② Haiku (원어민 캐주얼 채팅체 프롬프트) — 2026-08-12 실측 감사로 1순위 교체:
   DeepL 이 문맥 없는 단문에서 의미 반전 오역·의성어 음차·직역을 냄.
   이 번역은 '내가 쓰는 말' 학습 재료라 품질 우선
③ DeepL Free 폴백 (DEEPL_API_KEY, 월 50만 자 무료)
④ 하드캡: 월 TRANSLATE_MONTHLY_BUDGET_CHARS(기본 200만 자) 초과 또는
   사용자 일일 TRANSLATE_USER_DAILY_LIMIT(200건) 초과 → 번역만 조용히 중단
```

이모티콘·초성(ㅋㅋ)·기호 전용 메시지는 번역 대상이 아니다
(`langs.has_translatable_text` — 2026-08-12 실측: 음차·캐시 오염 방지).

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

## Phase 4 — 언어 학습 방으로 개편 (2026-08-14 착수)

- **방 기준 번역**: 채팅이 언어쌍 단위 학습 방으로 확장 —
  [chat-language-rooms.md](chat-language-rooms.md) 가 정본. 방에서는
  개인 설정(translate_mine/theirs)이 아니라 **방의 target_lang** 이 번역
  방향을 결정하고, **번역문이 본문·원문이 힌트**로 반전 표시된다.
  `translate_to(db, user_id, text, target)` 추출 — 캐시·예산·엔진 체인 공유.
- **게임 풀 언어 분리**: 풀 쿼리에 콘텐츠 lang 필터 + 게임 언어 선택
  (chat-language-rooms.md §게임 언어 분리). 게임별 입력 재설계(자판 등)는
  여전히 후속.
- en_text/ko_text 데이터 모델 일반화(text/native 개명)는 여전히 미착수.

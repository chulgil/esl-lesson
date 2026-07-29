---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Lore Commit — 의사결정 지식을 git trailer에 기록

> 목적: 커밋 메시지의 본문/제목이 아닌 **trailer 영역**에 구조화된 의사결정 정보를 남겨, 코드는 무엇(what)을, lore는 왜·무엇을 배제했는가(why / rejected)를 보관한다.

## 원칙

- **결정(directive)**, **제약(constraint)**, **거절된 대안(rejected)** 세 가지만 trailer로 기록한다.
- 커밋 본문은 그대로 유지. trailer는 별도 블록(마지막 빈 줄 뒤)에 추가.
- lore는 **반복 검색용**이므로 모든 커밋에 남기지 말고, 의사결정이 있는 커밋에만.

## 트레일러 포맷

```
<제목>

<본문 설명>

Lore-directive: <결정 한 줄>
Lore-constraint: <제약 한 줄>
Lore-rejected: <거절된 대안> — 이유
```

각 줄은 **한 줄 내 완결**. 다중 항목이 필요하면 같은 키를 여러 번.

## 적용 시점

| 상황 | 기록 의무 | trailer |
|---|---|---|
| 아키텍처 선택 (ex: SSE vs WebSocket) | 필수 | directive + rejected |
| 라이브러리 채택 (ex: Riverpod vs Bloc) | 필수 | directive + rejected |
| 범위 제한 결정 (ex: "이번 분기는 iOS만") | 필수 | constraint |
| 단순 버그 수정, docs 변경, 의존성 업데이트 | 불필요 | — |

## 조회

```bash
# 특정 키의 모든 결정
git log --grep="^Lore-directive:" --all --format="%h %s%n%b"

# 전체 제약 목록
git log --grep="^Lore-constraint:" --all

# 거절된 대안 히스토리
git log --grep="^Lore-rejected:" --all

# 특정 파일이 포함된 커밋의 결정
git log --follow --grep="^Lore-" -- path/to/file
```

## 작성 규칙

- **한 trailer = 한 문장**: 개행 금지. 다중 항목은 trailer를 여러 줄로.
- **과거시제**: "선택함", "거절함" — 결정은 이미 내려진 사실.
- **이유 포함 (rejected)**: "— " 구분자 뒤에 거절 이유 필수. 이유 없는 rejected는 기록하지 않는다.
- **코드 상세 금지**: 파일 경로, 변수명, 라인 번호는 trailer에 넣지 않는다 (코드/본문에 속함).

## 예시

```
feat(auth): OAuth 2.0 PKCE 흐름 추가

Flutter 앱 → 백엔드 → IdP 인증을 PKCE (RFC 7636)로 구현.
code_verifier는 SecureStorage에 저장하고 로그인 후 즉시 폐기.

Lore-directive: OAuth 2.0 Authorization Code + PKCE 채택 (RFC 7636)
Lore-constraint: 모바일 앱은 client_secret 보유 금지 — PKCE로 대체
Lore-rejected: Implicit Flow — deprecated, access token URL 노출 위험
Lore-rejected: ROPC — 앱이 사용자 비밀번호를 직접 취급하는 안티패턴
```

## 금지

- Lore trailer에 PR 링크, 이슈 번호 넣기 → 기존 trailer(`Refs`, `Closes`) 사용
- Lore-why / Lore-because / Lore-note 같은 임의 키 → 3개 공식 키만 사용
- 같은 결정을 여러 커밋에 반복 기록 → 최초 결정 커밋에만

## 책임

- 결정권자가 커밋 작성자와 다르면 `Co-Authored-By:` 와 함께 남긴다.
- 90일 이상 된 directive는 재검토 대상. 유효하면 새 커밋으로 re-affirm.

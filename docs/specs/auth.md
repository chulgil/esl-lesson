# 스펙: 인증 (Google SSO)

> 최종 수정: 2026-07-11

Google OAuth 2.0 Authorization Code 흐름을 백엔드(FastAPI)가 직접 처리하고, 자체 JWT를 httpOnly 쿠키로 발급한다. 서비스(esl)와 백오피스(esladmin) 두 도메인이 세션을 공유한다.

## 역할 모델

| 역할 | 권한 |
|------|------|
| `learner` | 서비스 페이지(학습/게임), 본인 데이터 조회 |
| `admin` | learner 전체 + 백오피스(콘텐츠 등록/검수, 사용자 관리) |

- 신규 가입자는 기본 `learner`.
- `ADMIN_EMAILS` 환경변수에 포함된 이메일은 로그인 시 자동으로 `admin` 승격.
- 백오피스에서 admin이 다른 사용자의 역할 변경 가능 (본인 강등은 금지 — 관리자 0명 방지).

## 로그인 흐름

```
1. 사용자: [Google로 시작하기] 클릭
2. GET /api/auth/login?next=<복귀경로>
     backend: state(CSRF 토큰) 생성 → 서명 쿠키 저장 → Google 인가 URL로 302
3. Google 동의 화면 → redirect_uri = https://<현재도메인>/api/auth/callback
4. GET /api/auth/callback?code=...&state=...
     backend: state 검증 → code를 토큰으로 교환 → id_token 검증(iss/aud/exp)
     → users upsert (google_sub 기준, last_login_at 갱신, ADMIN_EMAILS 체크)
     → 세션 JWT 발급 → Set-Cookie → next 경로로 302
5. 이후 모든 /api 요청: 쿠키의 JWT 검증 (미들웨어)
```

- 요청 scope: `openid email profile` (최소 권한).
- redirect URI는 두 도메인 모두 Google Console에 등록 — 콜백은 요청이 들어온 도메인 기준으로 구성.

## 세션 토큰 (JWT)

| 항목 | 값 |
|------|-----|
| 저장 | httpOnly + Secure + SameSite=Lax 쿠키 `els_session` |
| Domain | `.lessonaza.com` (두 서브도메인 공유) |
| 서명 | HS256, `JWT_SECRET` |
| 수명 | access 24h. 만료 시 재로그인 (개인 서비스 규모 — refresh 토큰 생략) |
| 클레임 | `sub`(user id), `email`, `role`, `exp`, `iat` |

- role은 편의상 클레임에 넣되, **admin 전용 API는 매 요청 DB에서 role 재확인** (강등 즉시 반영).
- 로그아웃: `POST /api/auth/logout` → 쿠키 삭제.
- WebSocket(페이즈 2): 핸드셰이크 시 같은 쿠키로 인증.

## 인가 규칙

| 경로 | 요구 |
|------|------|
| `/api/auth/*`, `/api/health` | 공개 |
| `/api/study/*`, `/api/contents/*`(읽기), `/api/game/*` | 로그인 |
| `/api/admin/*` | admin (DB 재확인) |
| 프론트 `/admin/*` 라우트 | middleware에서 role 확인, 미달 시 서비스 홈으로 |

프론트 가드는 UX용이고, **보안 경계는 항상 백엔드 API**다.

## API

| 메서드/경로 | 설명 |
|-------------|------|
| GET `/api/auth/login` | Google 인가 URL 302 |
| GET `/api/auth/callback` | 코드 교환 + 세션 발급 |
| POST `/api/auth/logout` | 세션 쿠키 삭제 |
| GET `/api/me` | 현재 사용자 (id, name, email, avatar, role, settings) |

## 보안 고려사항

- CSRF: OAuth `state` 검증 + SameSite=Lax + 상태 변경 API는 JSON 본문만 수용(폼 전송 차단).
- 오픈 리다이렉트 방지: `next` 파라미터는 자체 도메인 상대경로만 허용.
- 시크릿: GOOGLE_CLIENT_SECRET / JWT_SECRET은 서버 .env로만 주입, 코드/저장소 금지.
- 세션 무효화: JWT 특성상 즉시 폐기 불가 → 수명 24h로 제한 + admin API는 DB 확인으로 보완.
- 실패 처리: 콜백 오류 시 `/login?error=oauth`로 복귀, 상세 원인은 서버 로그에만 남김(정보 노출 방지).

## 에러/엣지 케이스

| 케이스 | 처리 |
|--------|------|
| Google 이메일 미검증 계정 | `email_verified=false`면 가입 거부 |
| 동일 이메일, 다른 google_sub | google_sub 기준 신규 계정 (이메일 변경 대응은 범위 외) |
| 관리자 0명 상태 | ADMIN_EMAILS로 항상 복구 가능 |
| 쿠키 차단 브라우저 | 로그인 페이지에서 안내 문구 표시 |

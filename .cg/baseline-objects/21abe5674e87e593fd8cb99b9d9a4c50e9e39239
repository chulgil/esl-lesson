# security-pipeline — 상세 레퍼런스

## CWE Scanning Rules

### Critical (커밋 차단)

| CWE ID | Rule | Grep Pattern |
|--------|------|--------------|
| CWE-89 | SQL Injection | `query\(.*\$\{`, `query\(.*\+` |
| CWE-79 | XSS | `innerHTML`, `dangerouslySetInnerHTML`, `v-html` |
| CWE-78 | OS Command Injection | `exec\(.*\$\{`, `spawn\(.*req\.` |
| CWE-77 | Command Injection | Template string in shell command |
| CWE-798 | Hardcoded Credentials | `apiKey\s*=\s*['"]`, `secret\s*=\s*['"]` |

### High (경고, 커밋 허용)

| CWE ID | Rule | Grep Pattern |
|--------|------|--------------|
| CWE-22 | Path Traversal | `\.\.\/` with user input |
| CWE-352 | CSRF | POST handler without csrf check |
| CWE-287 | Improper Auth | Route without auth middleware |
| CWE-862 | Missing Authz | Handler without role/permission check |
| CWE-502 | Unsafe Deserialization | `eval\(`, `new Function\(` |
| CWE-918 | SSRF | `fetch\(.*req\.`, `axios.*req\.` |
| CWE-434 | Unrestricted Upload | Upload without validation |
| CWE-269 | Privilege Escalation | Role change without verification |

### Medium (정보 제공)

| CWE ID | Rule | Grep Pattern |
|--------|------|--------------|
| CWE-200 | Info Disclosure | `console\.log.*password\|token\|secret` |
| CWE-20 | Input Validation | Endpoint without schema validation |
| CWE-327 | Broken Crypto | `md5\(`, `sha1\(`, `Math\.random\(\)` |
| CWE-276 | Incorrect Perms | `origin:\s*['"]?\*`, `0o?777` |

---

## Auto-Fix Rules

자동 수정은 사용자 승인 후 적용한다. 신뢰도가 High인 항목만 자동 수정 대상이다.

### Parameterized Queries (CWE-89)

```
Before: db.query(`SELECT * FROM users WHERE id = '${id}'`)
After:  db.query('SELECT * FROM users WHERE id = $1', [id])
```

### Environment Variables (CWE-798)

```
Before: const apiKey = 'sk-proj-abc123'
After:  const apiKey = process.env.API_KEY
+ .env.example에 API_KEY= 추가
```

### Safe DOM Manipulation (CWE-79)

```
Before: element.innerHTML = userInput
After:  element.textContent = userInput
```

### Remove Sensitive Logs (CWE-200)

```
Before: console.log('Token:', token)
After:  // (line removed)
```

### Secure Hash (CWE-327)

```
Before: const hash = md5(data)
After:  const hash = crypto.createHash('sha256').update(data).digest('hex')
```

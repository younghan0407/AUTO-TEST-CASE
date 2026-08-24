# 세팅 가이드 (팀원용)

이 하네스는 **기획서(PDF·이미지·Figma) → 테스트 케이스 → 구글 시트 작성·리뷰**를 자동으로 수행합니다.
아래 순서대로 진행하면 15분 내에 첫 실행이 가능합니다. 마지막 5단계에서 **실제로 되는지 검증**합니다.

---

## 0. 사전 준비물

| 항목 | 필요 여부 | 비고 |
|------|----------|------|
| Claude Code | 필수 | CLI 또는 IDE 확장 |
| Python 3.9+ | 필수 | `python3 --version` |
| Google 서비스 계정 키 | 필수 | 구글 시트 읽기·쓰기용 (3단계) |
| Figma Personal Access Token | 선택 | **Figma 기획서를 쓸 때만.** PDF·이미지만 쓰면 불필요 |

---

## 1. 저장소 clone

```bash
git clone https://github.com/sihan-qa/OKE-AUTO-TEST-CASE.git
cd OKE-AUTO-TEST-CASE
```

> **zip 다운로드는 권장하지 않습니다.** `scripts/` 의 6개 파일이 심볼릭 링크라서 zip으로 받으면 깨질 수 있습니다. git clone은 링크를 보존합니다.

## 2. 파이썬 패키지 설치

```bash
python3 -m pip install -r requirements.txt
```

## 3. Google 서비스 계정 키 배치

키 파일을 **`.credentials/google-service-account.json`** 이름으로 저장합니다.

```bash
mkdir -p .credentials
cp ~/Downloads/<받은_키파일>.json .credentials/google-service-account.json
```

- 이 위치에 두면 **환경변수를 설정하지 않아도** 스크립트가 자동으로 찾습니다.
- `.credentials/` 는 `.gitignore` 에 있어 **절대 커밋되지 않습니다.**
- 키를 받는 방법은 팀 리더에게 문의하세요. 두 가지 정책 중 하나입니다:
  - **공용 키**: 팀 리더가 보안 채널(1Password 등)로 전달. 받아서 위 경로에 저장하면 끝
  - **개인 키**: GCP 콘솔 → IAM → 서비스 계정 → 키 추가(JSON). 이 경우 4단계의 공유 대상 이메일이 본인 계정 이메일이 됩니다

> ⚠️ 키 파일을 Slack·메일·카톡으로 주고받지 마세요. 서비스 계정 키는 비밀번호와 동급입니다.

## 4. 대상 구글 시트 공유

작업할 구글 시트(참고 시트 + 작성 대상 시트) **양쪽 모두**에 서비스 계정 이메일을 **편집자**로 공유합니다.

```
testcase-auto-agent@testcase-auto.iam.gserviceaccount.com
```

- 개인 키를 발급받은 경우, 위 이메일 대신 **본인 키의 `client_email` 값**을 공유하세요. 5단계 점검 결과에 그 이메일이 출력됩니다.
- 공유하지 않으면 `403` 오류가 납니다. 가장 흔한 실패 원인입니다.

## 5. (선택) Figma 토큰 — Figma 기획서를 쓸 때만

```bash
cp .claude/settings.json.example .claude/settings.json
```

`.claude/settings.json` 을 열어 `FIGMA_ACCESS_TOKEN` 값을 본인 토큰으로 바꿉니다.
발급: Figma → Settings → Security → Personal access tokens.

- **본인 토큰을 쓰세요.** 남의 토큰을 공유받으면 그 사람의 Figma 접근 권한 전체를 쓰게 됩니다.
- PDF·이미지 기획서만 다룰 예정이면 이 단계를 건너뛰어도 됩니다. 6단계에서 `주의`로만 표시됩니다.

## 6. 세팅 검증 (스모크 테스트) — 반드시 실행

```bash
# 로컬 환경만 점검
python3 verify_setup.py

# 시트 접근 권한까지 실제로 확인 (권장)
python3 verify_setup.py "https://docs.google.com/spreadsheets/d/<시트ID>/edit"
```

기대 출력:

```
결과: 정상 11 · 주의 0 · 실패 0

필수 항목 모두 통과. 이제 Claude Code에서 기획서와 시트 URL을 주고
"테스트 케이스 만들어줘" 라고 요청하면 됩니다.
```

**`실패` 가 하나라도 있으면 그 항목의 `→` 조치를 먼저 해결하세요.** 실패를 남긴 채 실제 기획서로 실행하면, 결과가 이상해도 원인이 환경인지 기획서인지 구분되지 않습니다.

### 실패 항목별 원인

| 항목 | 원인 | 조치 |
|------|------|------|
| 패키지 미설치 | 2단계 누락 또는 다른 파이썬 환경 | `python3 -m pip install -r requirements.txt`. venv를 쓰면 활성화 후 재설치 |
| `scripts/` 링크 | zip으로 받음 | git clone으로 다시 받기 |
| 서비스 계정 키 | 3단계 경로·파일명 불일치 | 파일명이 정확히 `google-service-account.json` 인지 확인 |
| 서비스 계정 키 형식 아님 | OAuth 클라이언트 파일을 잘못 넣음 | 키 안의 `"type"` 이 `service_account` 인지 확인 |
| 시트 접근 403 | 4단계 공유 누락 | 시트에 서비스 계정 이메일을 편집자로 추가 |
| Figma 토큰 인증 실패 | 토큰 만료·오타 | 재발급. Figma를 안 쓰면 `.claude/settings.json` 에서 토큰 값을 비워도 됨 |

---

## 7. 첫 실행

프로젝트 폴더에서 Claude Code를 실행합니다. **이 폴더 안에서 실행해야** 스킬·에이전트가 인식됩니다.

```bash
cd OKE-AUTO-TEST-CASE
claude
```

요청 예시:

```
테스트 케이스 자동 생성해줘.

기획서: ./PRD/화면정의서_v1.pdf
대상 시트: https://docs.google.com/spreadsheets/d/<작성할_시트>/edit
대상 탭: 새 탭으로 만들어줘 (탭 이름: 테스트_초안_260824)

범위: 첫 번째 챕터만 먼저 해줘. 결과 보고 나머지 진행 여부 정할게
```

**참고 시트 URL은 필요하지 않습니다.** 팀 양식은 `.claude/formats/team-viola.md` 에 사양으로
커밋되어 있고, 대상 시트에서는 헤더와 마지막 TC ID만 확인합니다.

첫 실행은 **범위를 좁히고 되돌릴 수 있는 곳에 쓰는 것**이 좋습니다. 전체를 돌리면 케이스가
수백 건 나오는데, 방향이 틀렸으면 전부 다시 해야 합니다. 마지막 줄이 그 안전장치입니다.

진행 중 **확인 게이트 2곳**(챕터 목록 확인 / 첫 챕터 케이스 검토)에서 멈춥니다.
각 게이트에서 무엇을 봐야 하는지, 품질을 올리는 프롬프트와 상황별 변형(변경분만 / 이미지 /
사양 갱신 / 부분 재실행)은 **[docs/PROMPTS.md](docs/PROMPTS.md)** 에 정리되어 있습니다.

> 첫 실행 전에 `docs/PROMPTS.md` 의 "확인 게이트 2곳"을 한 번 읽어두면 좋습니다.
> 게이트에서 무엇을 지시하느냐가 나머지 챕터 전체의 품질을 결정합니다.

- 기획서가 **이미지(PNG 등)** 면 파일·디렉터리 경로를 그대로 주면 됩니다. PDF로 변환할 필요 없습니다.
- **"변경된 내용만 테스트 케이스 만들어줘"** 라고 하면 개정판 기획서의 빨간색 표기(변경분)만 케이스화합니다.
- 진행 중 **챕터 목록 확인**과 **첫 챕터 케이스 검토** 두 지점에서 확인을 요청합니다. 여기서 방향을 잡으면 이후는 자동 진행됩니다.

산출물은 `_workspace/` 에 생성됩니다 (커밋되지 않습니다).

| 파일 | 내용 |
|------|------|
| `00_chapters.md` | 감지된 챕터 목록 |
| `01_prd_analysis_ch{N}.md` | 챕터별 기획서 분석 |
| `02_sheet_format.md` | 참고 시트 양식 분석 |
| `03_testcases_ch{N}.md` | 생성된 케이스 (시트 작성 전 검토용) |
| `04_review_report_ch{N}.md` | 리뷰 보고서 |

---

## 8. 커밋하면 안 되는 것

`.gitignore` 가 아래를 자동으로 막습니다. 확인만 하고 **강제로 추가하지 마세요**(`git add -f` 금지).

- `.credentials/`, `*.json`, `.claude/settings.json` — 자격증명·개인 토큰
- `PDF/`, `*.pdf`, `img/` — 사내 기획서 원본
- `_workspace*/` — 분석·케이스 산출물 (사내 정보 포함)

커밋 전 확인:

```bash
git status --short          # 위 항목이 목록에 없어야 정상
```

---

## 9. 하네스 개선 반영

케이스 품질 문제나 누락 패턴을 발견하면 브랜치를 만들어 PR을 올려주세요.
규칙을 바꿀 때는 **`CLAUDE.md` 하단의 변경 이력 테이블에 날짜·대상·사유를 함께 기록**해야 합니다.
어떤 파일을 고쳐야 하는지는 `HARNESS_OVERVIEW.md` 의 구성도를 참고하세요.

하네스 구조 자체(에이전트 추가, 워크플로우 변경)를 손볼 때는 `harness` 메타 스킬이 도움이 됩니다.
외부 프로젝트(Apache-2.0)라 이 저장소에는 포함하지 않았으니 필요할 때 설치하세요.

```
/plugin marketplace add revfactory/harness
```

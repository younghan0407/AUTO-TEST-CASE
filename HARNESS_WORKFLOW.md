# testcase-auto 하네스 동작 방식

> 작성일: 2026-08-07 · 기준 경로: `/Users/hanflex/Git/testcase-auto`
> 실제 구성 파일(`.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `scripts/*.py`, `settings.json`)을 읽어 검증한 내용

기획서(PDF/Figma) 한 건을 넣으면 → 팀 시트 양식을 역공학하고 → 챕터 단위로 잘라 → 테스트 케이스를 만들어 구글 시트에 쓰고 → 스스로 QA 리뷰까지 하는 파이프라인이다.

---

## 1. 실행 계층 — 무엇이 무엇을 부르는가

하네스는 **스킬(규칙 문서) / 에이전트(실행 주체) / 스크립트(외부 I/O)** 세 층으로 나뉜다.

```
사용자 요청
   │  "기획서로 TC 뽑아줘" 등 트리거 키워드
   ▼
┌──────────────────────────────────────────────────────────┐
│ testcase-auto (오케스트레이터 스킬)                           │
│ Phase 0~6의 순서·게이트·에러 정책을 규정. 직접 일하지 않는다         │
└──────────────────────────────────────────────────────────┘
   │ 서브에이전트 4명에게 작업 할당 (모두 model: opus)
   ├── prd-analyst ──────── 스킬: prd-analyzer ──── 스크립트: pdf_to_images.py / figma_api.py
   ├── sheet-analyst ────── 스킬: sheet-operator ── 스크립트: sheets_api.py
   ├── testcase-writer ──── 스킬: testcase-generator + sheet-operator
   └── testcase-reviewer ── 스킬: testcase-reviewer + sheet-operator
```

**층별 책임 분리가 이 하네스의 핵심 설계다.**

| 층 | 파일 | 역할 | 성격 |
|----|------|------|------|
| 오케스트레이터 스킬 | `.claude/skills/testcase-auto/SKILL.md` | 순서, 사용자 게이트, 에러 정책 | 흐름 제어 |
| 도구 스킬 | `prd-analyzer`, `sheet-operator` | 외부 시스템(PDF·Figma·Sheets) 접근 방법 | How-to |
| 판단 스킬 | `testcase-generator`, `testcase-reviewer` | 케이스를 어떻게 뽑고 어떻게 검증할지 | 품질 규칙 |
| 메타 스킬 | `.claude/skills/harness/harness/` | 하네스 자체를 수정·진화시키는 방법 | 자기 수정 |
| 에이전트 | `.claude/agents/*.md` | 스킬을 실제로 실행하는 주체, 출력 프로토콜 정의 | 실행 |
| 스크립트 | `scripts/*.py` (심볼릭 링크) | Python 레벨 I/O | 결정적 실행 |

에이전트 정의는 "무엇을 만들어야 하는가(출력 형식)"를, 스킬은 "어떻게 만드는가(절차·규칙)"를 담당한다. 같은 이름의 스킬과 에이전트가 있는 경우(`testcase-reviewer`)에도 이 분리가 유지된다.

---

## 2. 전체 실행 흐름 (Phase 0 → 6)

```
Phase 0  컨텍스트 확인 ─────────── 환경변수 · 입력 수집 · 실행 모드 결정 · 시트 공유 안내
Phase 1  사전 준비
         ├ 1-A  PDF → 이미지 변환  ┐
         │                        ├ 병렬 실행
         ├ 1-D  sheet-analyst     ┘  → 02_sheet_format.md
         ├ 1-B  간지 감지 → 챕터 목록 생성
         └ 1-C ★ 사용자 확인 게이트 (OK까지 반복) → 00_chapters.md
Phase 2~4  챕터 루프 (ch01 → ch02 → … 순차, 챕터당 완결)
         ├ P2  prd-analyst      → 01_prd_analysis_ch{N}.md
         ├ P3  testcase-writer  → 03_testcases_ch{N}.md → 시트 batch append
         │       ★ 첫 챕터만 사용자 검토 게이트, 이후 자동
         └ P4  testcase-reviewer → 04_review_report_ch{N}.md
                 Critical 발견 시 → writer 재작성 → 재리뷰 (최대 1회 루프)
Phase 5  합본 생성 + 종합 보고
Phase 6  피드백 수집 → 하네스 진화 (harness 스킬)
```

### Phase 0 — 컨텍스트 확인

1. **환경변수 검증** — `FIGMA_ACCESS_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`. 누락 시 안내 후 중단.
2. **입력 수집** — 기획서(PDF 경로 또는 Figma URL), 참고 시트 URL(양식 파악용), 대상 시트 URL(작성처), 대상 탭, 분석 범위, 생성 모드.
3. **실행 모드 결정** — `_workspace/` 존재 여부와 사용자 요청을 조합해 4가지로 분기한다.

| 상황 | 모드 | 동작 |
|------|------|------|
| `_workspace/` 없음 | 초기 실행 | Phase 1부터 전체 |
| 있음 + "다시/재실행" | 새 실행 | 기존을 `_workspace_prev/`로 이동 후 처음부터 |
| 있음 + "챕터 N만 보완" | 부분 재실행 | 해당 챕터 에이전트만 호출, 나머지 산출물 재사용 |
| 있음 + 변경 없음 | 이어 실행 | 미완료 단계부터 |

4. **시트 공유 안내** — 참고/대상 시트 두 곳 모두 서비스 계정에 편집자 공유가 필요함을 알린다.

### Phase 1 — 사전 준비

**1-A. 이미지 변환 (PDF 입력 시)** — 페이지를 두 벌로 만든다.

```bash
# ① 전체 페이지 150 DPI — UI 화면 파악용
python scripts/pdf_to_images.py <pdf> --dpi=150 --output-dir=_workspace/pdf_images/<name>

# ② Description 패널 크롭 200 DPI — 텍스트 정밀 판독용 (최우선 소스)
python scripts/pdf_to_images.py <pdf> --crop-desc --dpi=200 --output-dir=_workspace/pdf_images/<name>_desc
```

크롭은 각 페이지의 **우측 47% 영역**(`_DESC_X_RATIO`)을 잘라낸다. 기획서 스펙 페이지가 "좌측 UI 화면 + 우측 Description 패널" 구조라는 전제에 맞춘 값이다. 출력은 `page_001.png` / `page_001_desc.png` 형식.

**1-B. 간지 감지** — 경량 스캔 에이전트가 전체 이미지를 훑어 챕터 구분 슬라이드를 찾는다. 판별 기준은 ⓐ 어두운 단색 배경이 페이지 전체를 채움, ⓑ UI·Description 패널 없음, ⓒ 대분류 제목 텍스트, ⓓ 우측 하단 챕터 번호+소제목. 애매하면 후보로 표시하고 판단을 미룬다.

**1-C. 사용자 확인 게이트 (필수)** — 챕터 목록(`p3~p15 "빌드배포 > 01. 파이프라인 관리"` 형태)을 보여주고 OK를 받을 때까지 수정·재확인을 반복한다. 확정본만 `_workspace/00_chapters.md`에 저장된다. **하네스에서 우회 불가능한 게이트 두 곳 중 첫 번째.**

**1-D. sheet-analyst (1-A와 병렬)** — 참고 시트를 역공학해 `02_sheet_format.md`를 만든다. 세 가지가 핵심:
- enum은 **시트 전체에서 distinct로** 수집한다 (앞 50행만 보면 P4를 놓친다 — 실제 발생했던 누락)
- 솔루션 컬럼 실측 = 사양 선택 판정 기준 (VIOLA는 `VIOLA` 단일값 — `VIOLA_CICD` 접미사 분리는 실측 0건이므로 발견 시 사양 외 enum(Major)으로 보고). 관리대상 구분(`K8s`/`CI·CD`)은 `1 Depth`·사전조건·비고에 나타난다
- **검증 단위 판정** (atomic / scenario) — Phase 0에서 모드가 명시되지 않았으면 이 판정을 사용자에게 보고하고 확인받는다

### Phase 2~4 — 챕터 루프

확정된 챕터를 **한 번에 하나씩, 분석→생성→리뷰가 끝나야 다음으로** 넘어간다.

**Phase 2 (prd-analyst)** — 단일 에이전트가 담당 챕터 페이지를 순서대로 읽는다. 에이전트당 안전 이미지 한도는 12~13페이지(전체+크롭 합산 ~26장)이며, 챕터가 이를 넘으면 **여러 에이전트로 쪼개지 않고** 한 에이전트가 13페이지씩 나눠 읽으며 앞 구간 맥락을 유지한다. 페이지별 판독 순서는 고정이다:

1. 크롭 이미지에서 Description 전수 추출 — 번호 계층(❶, 1, 1.a) 보존, 빨간 강조는 `[강조]` 태그, 우측 상단 **Page ID**(`ADM-TCK-0100-02` 형식) 필수 추출
2. 전체 이미지에서 Description에 없는 UI 요소 보완
3. UI ↔ Description 비교 → 다르면 `[UI↔DESC 불일치] UI: … / DESC: …` 로 기록. **어느 쪽이 맞는지 판단하지 않는다.**

챕터 전 페이지를 읽은 뒤 페이지 간 Description을 비교해, 2개 이상 페이지에 반복되는 항목에 `[공통 DESC: 페이지목록]` 태그를 단다. 공통이어도 각 페이지 결과에 모두 남긴다.

**Phase 3 (testcase-writer)** — `01_prd_analysis_ch{N}.md` + `02_sheet_format.md` + 대상 시트 URL + 생성 모드를 받아 케이스를 도출하고 `03_testcases_ch{N}.md`를 쓴다. 분포 표는 실제 작성분을 세서 채운다(추정 금지). **첫 챕터만** 사용자 검토 게이트를 거치고, 이후 챕터는 자동 진행한다. OK 후 `sheet-operator`로 한 번에 batch append 하고 기록된 행 범위를 보고한다.

**Phase 4 (testcase-reviewer)** — 세 경계면을 교차 비교한다(§4). Critical이 나오면 writer에게 재작성을 요청하고 재리뷰하되 **루프는 최대 1회**. 두 번째에도 남으면 사용자에게 결정을 위임하고 다음 챕터로 간다. 첫 챕터에서 Critical이 특정 패턴(예: 표시 형식 케이스 전멸)으로 반복되면, 남은 챕터를 돌리기 전에 사용자에게 방향 조정을 확인받는다.

### Phase 5~6 — 합본과 진화

챕터별 파일을 순서대로 이어 붙여 `01_prd_analysis.md` / `03_testcases.md`(ID 순 정렬) / `04_review_report.md`를 만들고, 챕터별 케이스 수·리뷰 결과 표와 함께 종합 보고한다. 이후 결과·워크플로우에 대한 피드백을 받아 `harness` 메타 스킬로 하네스를 수정하고, 변경은 `CLAUDE.md` 이력 테이블에 기록한다.

---

## 3. 데이터 전달 — 파일 기반 프로토콜

에이전트끼리 결과를 대화로 넘기지 않는다. **모든 산출물은 `_workspace/` 아래 파일**이고, 다음 에이전트는 파일을 읽는다.

| 파일 | 생성자 | 소비자 |
|------|--------|--------|
| `00_chapters.md` | 오케스트레이터 (1-B~1-C) | prd-analyst, 사용자 확인 |
| `01_prd_analysis_ch{N}.md` | prd-analyst | testcase-writer, testcase-reviewer |
| `02_sheet_format.md` | sheet-analyst | writer·reviewer (**모든 챕터가 공유**, 1회만 생성) |
| `03_testcases_ch{N}.md` | testcase-writer | testcase-reviewer |
| `04_review_report_ch{N}.md` | testcase-reviewer | 오케스트레이터, 사용자 |
| `01/03/04_*.md` (합본) | 오케스트레이터 (Phase 5) | 사용자 |
| 구글 시트 행 | testcase-writer | testcase-reviewer (역방향 검증) |

직접 메시지(SendMessage)는 **예외 상황 두 가지에만** 쓴다 — writer ↔ analyst의 모호함 재질문, reviewer → writer의 Critical 재작성 요청.

이 구조 덕분에 부분 재실행이 성립한다. ch02만 다시 만들 때 prd-analyst·sheet-analyst를 호출하지 않고 기존 `01_ch02` / `02` 파일을 그대로 읽어 writer만 재실행할 수 있다.

---

## 4. 품질 규칙 — 케이스를 어떻게 뽑는가

### 생성 모드

| 모드 | 한 케이스 단위 | 케이스 수(4화면 기준) |
|------|--------------|------------------|
| **atomic** (기본값) | 단일 검증 1건 — 컬럼 1개, 클릭 1회, 표시 1건 | 80~120개 |
| scenario | 사용자 행동 시나리오(다단계·다중 검증) | 30~50개 |

팀이 정착시킨 양식이 atomic이므로 명시적 요청이 없으면 atomic이다. atomic에서는 절차 1~2단계, 예상 결과 1~3줄을 넘으면 케이스를 쪼갠다.

### 필수 준수 규칙 (0-A ~ 0-G)

| 규칙 | 내용 |
|------|------|
| 0-A Description 100% 커버리지 | 분석 파일의 Description 항목은 **전부** 케이스화. 비고에 `[DESC ❶-1-a]` 출처 표시. UI에 안 보인다는 이유로 생략 금지 |
| 0-B 화면 ID = Page ID | 화면 ID 컬럼에 기획서 우측 상단 Page ID 기입. 없는 화면은 상위 기능 Page ID 사용 |
| 0-C 사전조건 명시 | 같은 화면에서 상황별 UI가 다르면 사전조건으로 구분 (버튼 클릭 후 상태, 데이터 유무, 권한별 화면) |
| 0-D 공통 DESC 독립 TC | `[공통 DESC]` 항목은 **페이지마다 독립 TC 작성**. "다른 페이지에 이미 있음"으로 생략 금지 |
| 0-E UI↔DESC 불일치 기재 | 비고에 `[기획 확인] UI: … / DESC: … — 어느 쪽이 맞는지 확인 필요`, 별도 섹션에도 기재 |
| 0-G 오탈자 검수 | 작성 후 필수 — 기획서 용어 일치, 상태 enum 정확성, 숫자·단위, 메시지 코드(`CMN001` 등) |

### 자동 도출 (atomic 필수)

기획서에 아래가 등장하면 케이스를 자동으로 추가한다.

| 표시 항목 | 자동 생성 케이스 |
|----------|--------------|
| 테이블 컬럼 | 컬럼 순서·이름 / 정렬 동작 / 빈 값 `-` 표시 |
| 상태 enum | 각 상태 노출 형식 / 호버 툴팁(열거된 모든 값) |
| 일시 | `yyyy-mm-dd hh:mm:ss` 형식 / 값 없을 때 `No data (-)` |
| 액션 버튼 | 클릭→이동 / 모달 표출 / 모달 취소(P4) / 모달 진행 |

**화면당 권장 개수(atomic)** — 표시 형식 8~15, 인터랙션 5~10, 정상 2~4, 비정상 3~6, 엣지 2~4, 부수(취소·비활성) 3~5.

### 우선순위 정책

`02_sheet_format.md`에서 발견된 enum에 따라 자동 분기한다.

- **P4가 있으면 A 정책** — P1: 라우팅·핵심 트리거(**매우 보수적**, 기준은 "깨지면 다음 화면으로 못 가는가") / P2: 다이얼로그 진행·임팩트 큰 비정상 / P3: UI 표시 검증 / P4: 취소·비활성·권한 없음
- **없으면 B 정책** — P1~P3 일반 분류

---

## 5. 리뷰 — 세 경계면 교차 비교

"N개 작성됨" 같은 존재 확인은 QA가 아니라는 것이 이 스킬의 전제다.

| 경계면 | 비교 | 검증 질문 |
|--------|------|----------|
| 기획 ↔ 케이스 | `01_*.md` ↔ `03_*.md` | 모든 기능 단위가 커버됐는가? 추측 케이스가 표시됐는가? |
| 양식 ↔ 케이스 | `02_*.md` ↔ `03_*.md` | 컬럼 순서·enum·ID 체계가 일치하는가? |
| 로컬 ↔ 시트 | `03_*.md` ↔ 실제 시트 | 행 수와 셀 내용이 같은가? 빠진 행은? |

여기에 태그 전용 점검 두 가지가 추가된다 — `[공통 DESC]` 대상 페이지에 TC가 모두 있는지(**누락 시 Critical**), `[UI↔DESC 불일치]`가 비고에 기재됐는지(**누락 시 Major**).

**권고 3단계** — Critical(즉시 수정, writer 재호출) / Major(사용자 결정 위임) / Minor(정보 제공).

**리뷰어는 케이스를 직접 고치지 않는다.** 고치면 작성자 의도가 묻히므로, TC-ID·컬럼명·발견값·기준값을 명시해 지적만 하고 수정은 writer가 한다.

---

## 6. 환경·인증

`.claude/settings.json`의 `env`로 주입된다.

| 변수 | 값·용도 |
|------|--------|
| `FIGMA_ACCESS_TOKEN` | Figma REST API 토큰 |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.credentials/google-service-account.json` |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com` |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` — 에이전트 팀 기능 활성화 |

**하이브리드 인증이 필요한 이유** — 서비스 계정은 자체 Drive storage가 없어 새 스프레드시트를 만들 수 없다(`storageQuotaExceeded`). 그래서 **생성만 OAuth2**로 하고, 이후 읽기·쓰기는 전부 서비스 계정으로 한다.

```bash
# 새 시트가 필요할 때만 (1회성)
python scripts/oauth_sheet.py create "TEST_VIOLA_AUTO" testcase-auto-agent@testcase-auto.iam.gserviceaccount.com
# → 사용자 권한으로 생성 + 서비스 계정에 편집자 권한 자동 부여
```

OAuth 토큰은 `.credentials/oauth_token.json`에 저장·자동 갱신된다.

**기존 시트는 사용자가 직접 서비스 계정 이메일에 편집자 공유해야 한다.** 안 하면 403이다.

### 스크립트 4종

원본은 `.claude/skills/*/scripts/`에 있고 루트 `scripts/`에 **심볼릭 링크**가 걸려 있다. 모든 명령은 프로젝트 루트에서 `scripts/...` 경로로 실행한다.

| 스크립트 | 서브커맨드 |
|---------|----------|
| `sheets_api.py` | `metadata` / `read` / `write` / `append` / `add_tab` (서비스 계정) |
| `oauth_sheet.py` | `create` (OAuth2 시트 생성 + 공유) |
| `pdf_to_images.py` | `--dpi=` `--crop-desc` `--output-dir=` `--pages=START-END` |
| `figma_api.py` | `file <URL> <depth>` / `images <FILE_KEY> <NODE_IDS>` |

의존성: `pymupdf`, `google-api-python-client`, `google-auth-oauthlib`.

---

## 7. 사용자 개입 지점과 에러 정책

**필수 게이트 2곳** — 자동으로 넘어가지 않는다.

1. **Phase 1-C 챕터 목록 확정** — OK할 때까지 반복
2. **Phase 3 첫 챕터 TC 검토** — 첫 챕터만, 이후 자동

**조건부 개입** — 생성 모드 미지정 시 sheet-analyst 판정 확인, 첫 챕터 패턴성 Critical 시 방향 조정, 2회 리뷰 후에도 남은 Critical 처리.

**에러 원칙: 1회 재시도 → 재실패 시 해당 챕터를 건너뛰고 보고서에 누락을 명시한다.** 전체를 멈추지 않는다.

| 에러 | 대응 |
|------|------|
| Figma 토큰 누락/만료 | 즉시 중단 + 재발급 안내 |
| 시트 403 | 서비스 계정 편집자 공유 안내 후 재시도 |
| 시트 404 | URL 재확인 요청 |
| API 429 | 60초 대기 후 1회 재시도, 실패 시 부분 결과 보고 |
| 시트 쓰기 부분 실패 | 어디까지 썼는지 + 미작성 TC-ID 목록 보고 |
| 간지 감지 불가 | 사용자에게 페이지 범위 직접 입력 요청 |
| 챕터 분석 0건 | 범위 재확인 후 재시도 또는 스킵 |

---

## 8. 왜 이런 규칙이 생겼는가

현재 규칙 대부분은 설계로 미리 만든 것이 아니라 **실행 후 발견된 누락에서 역산된 것**이다. `CLAUDE.md` 변경 이력이 그 궤적을 보여준다.

| 발견된 문제 | 도입된 규칙 | 시점 |
|------------|-----------|------|
| 팀원 시트 대비 Critical 누락 7건 | 표시 형식 자동 도출, P4 enum 인식, 솔루션 분리 인식 | 2026-05-13 |
| 시나리오 단위가 팀 협업에 부적합 | atomic 기본 모드 | 2026-05-13 |
| 샘플링 리뷰에서 Description 누락 다수 | Description 100% 커버리지, Page ID 매핑, 오탈자 검수, 사전조건 명시 | 2026-06-09 |
| 단일 에이전트 멀티이미지 컨텍스트 초과 | `--pages` 분할 (트리 합성 전략은 도입 다음 날 폐기) | 2026-06-10 |
| 공통 항목을 한 번만 쓰고 넘어가는 패턴 | `[공통 DESC]` 독립 TC 의무화 | 2026-06-11 |
| 일괄 처리 시 누락 다수 + 처리 시간 과다 | **챕터 단위 순차 처리 전면 전환** (병렬 청크 에이전트 제거) | 2026-06-11 |
| 스킬 문서의 스크립트 경로에 파일 부재 | 루트 `scripts/` 심볼릭 링크, `oauth_sheet.py` 경로 탐색 수정 | 2026-08-06 |

여기에 `.claude/memory/feedback_tc_completeness.md`가 별도로 축적돼 있다 — 팝업·모달·처리 결과·에러 화면 등 **보조 화면을 메인과 동등하게 다루고, 여러 케이스가 나올 항목을 1개로 요약하지 말 것**. 지적된 누락 1건은 대표 예시일 뿐이라는 전제로 항상 전수 분석한다.

**설계 사상 4가지로 요약하면:**

1. **챕터 단위 순차 처리** — 넓게 한 번보다 좁게 여러 번. 한 챕터를 완결한 뒤 다음으로
2. **Description 최우선** — 우측 패널이 1순위 소스, UI는 보완용. 항목은 100% 케이스화
3. **atomic 단위** — 한 케이스 = 한 검증. 실패 시 원인이 바로 특정돼야 한다
4. **판단하지 않고 기록** — 불명확·불일치는 추측 대신 `[UI↔DESC 불일치]` / `확인 불가`로 남기고 사람에게 넘긴다

---

## 9. 현재 상태

- `_workspace/` — 12개 챕터 전체 세트(`01`/`03`/`04` × ch01~ch12) + 합본 3종 + `00_chapters.md` + `02_sheet_format.md` 완비
- 과거 실행본 11개 디렉토리 보관 (`_workspace_prev*`, `_workspace_공통`, `_workspace_일반_v1` 등)
- 관련 문서 — `HARNESS_OVERVIEW.md`(상세 구성), `HARNESS_SUMMARY.md`(1페이지 요약), `HARNESS_SETUP_PROMPT.md`(구축 프롬프트), 본 문서(동작 방식)
- 하네스 변경 시 `CLAUDE.md` 이력 테이블 갱신이 규칙이며, 하네스 자체 수정은 `harness` 메타 스킬이 담당한다

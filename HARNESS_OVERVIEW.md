# testcase-auto 하네스 구성 및 동작 정리

> 작성일: 2026-08-06
> 대상: 프로젝트 루트 (이 저장소를 clone 한 디렉터리)
> 목적: 기획서(PRD) → 팀 양식 테스트 케이스 자동 생성 → 구글 시트 작성·리뷰

---

## 1. 한눈에 보기

```
 [사용자] PDF/Figma 기획서 + 참고 시트 URL + 대상 시트 URL
     │
     ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 오케스트레이터 스킬: testcase-auto                            │
 │  Phase 0 컨텍스트 확인 → Phase 1 사전준비 → 챕터 루프 → 합본   │
 └─────────────────────────────────────────────────────────────┘
     │                              │
     │ (병렬)                        │ (병렬)
     ▼                              ▼
 PDF→이미지 변환                sheet-analyst 에이전트
 (pdf_to_images.py)            └ sheet-operator 스킬 → 참고 시트 읽기
     │                              │
     ▼                              ▼
 간지 감지 → 챕터 목록          02_sheet_format.md (양식 사양서)
     │
     ▼ [사용자 확인 게이트]
 ┌──── 챕터 루프 (ch01 → ch02 → ... 순차) ────────────────────┐
 │                                                            │
 │  ① prd-analyst        → 01_prd_analysis_ch{N}.md           │
 │      └ prd-analyzer 스킬 (Description 우선 판독)            │
 │                ▼                                           │
 │  ② testcase-writer    → 03_testcases_ch{N}.md + 시트 append │
 │      └ testcase-generator 스킬 (케이스 도출)                │
 │      └ sheet-operator 스킬 (batch 쓰기)                     │
 │                ▼                                           │
 │  ③ testcase-reviewer  → 04_review_report_ch{N}.md          │
 │      └ testcase-reviewer 스킬 (3개 경계면 교차 검증)         │
 │      └ Critical 발견 시 ②에 재작성 요청 (최대 1회 루프)      │
 └────────────────────────────────────────────────────────────┘
     │
     ▼
 Phase 5: 챕터별 산출물 합본 + 종합 보고 → Phase 6: 피드백/진화
```

**핵심 설계 사상 4가지**

| 사상 | 내용 |
|------|------|
| 챕터 단위 순차 처리 | 전체 일괄 처리 시 누락이 많아, 간지(챕터 구분 슬라이드) 기준으로 잘라 한 챕터씩 완결 처리 |
| Description 최우선 | 기획서 우측 Description 패널이 1순위 소스, UI 화면은 보완용. Description 항목은 100% 케이스화 의무 |
| atomic 단위 생성 | 팀이 정착시킨 양식이 atomic(단일 검증 1케이스)이므로 시나리오 묶음 금지 |
| 판단하지 않고 기록 | 불명확·불일치는 추측 대신 `[UI↔DESC 불일치]`, `확인 불가`로 명시하고 사용자에게 위임 |

---

## 2. 디렉토리 구조

```
testcase-auto/
├── CLAUDE.md                     # 하네스 포인터 (트리거 규칙 + 변경 이력 테이블)
├── HARNESS_SETUP_PROMPT.md       # 하네스 구축 시 사용한 원본 프롬프트 (61KB)
├── .claude/
│   ├── settings.json             # 환경변수 (Figma 토큰, GCP 자격증명 경로)
│   ├── settings.local.json       # Bash 권한 allowlist
│   ├── agents/                   # 에이전트 정의 4개
│   │   ├── prd-analyst.md
│   │   ├── sheet-analyst.md
│   │   ├── testcase-writer.md
│   │   └── testcase-reviewer.md
│   ├── skills/                   # 스킬 5개(+메타스킬)
│   │   ├── testcase-auto/        # 오케스트레이터
│   │   ├── prd-analyzer/         # + scripts/figma_api.py, pdf_to_images.py, detect_red_regions.py, check_image_quality.py
│   │   ├── sheet-operator/       # + scripts/sheets_api.py, oauth_sheet.py
│   │   ├── testcase-generator/
│   │   ├── testcase-reviewer/
│   │   └── harness/harness/      # 메타 스킬 (하네스 자체를 구성·진화)
│   └── memory/
│       └── feedback_tc_completeness.md   # 누락·요약 금지 피드백
├── .credentials/                 # 서비스 계정 키, OAuth 토큰 (gitignore)
├── scripts/                      # 루트 실행용 심볼릭 링크 5개 (원본은 각 스킬 하위)
├── PDF/                          # 입력 기획서 PDF
├── _workspace/                   # 현재 실행 산출물 (gitignore)
└── _workspace_*/                 # 과거 실행 보관 (prev, prev2, 공통, 일반_v1 등 11개)
```

---

## 3. 구성 요소

### 3-1. 에이전트 4개 (`.claude/agents/`)

모두 `type: general-purpose`, `model: opus`.

| 에이전트 | 역할 | 사용 스킬 | 산출물 |
|---------|------|----------|--------|
| **prd-analyst** | 기획서(PDF/Figma) 판독 → 화면·Description·UI 요소·플로우·Page ID 추출 | `prd-analyzer` | `01_prd_analysis_ch{N}.md` |
| **sheet-analyst** | 기존 팀 시트 양식·컨벤션 역공학 (컬럼, ID 체계, enum, 검증 단위) | `sheet-operator` | `02_sheet_format.md` |
| **testcase-writer** | 분석 결과 + 양식 → 실제 TC 도출 및 시트 batch 작성 | `testcase-generator`, `sheet-operator` | `03_testcases_ch{N}.md` + 시트 행 |
| **testcase-reviewer** | 3개 경계면 교차 검증 QA | `testcase-reviewer`, `sheet-operator` | `04_review_report_ch{N}.md` |

각 에이전트 정의는 동일한 6개 섹션 구조를 가진다: 핵심 역할 / 작업 원칙 / 입력 프로토콜 / 출력 프로토콜 / 팀 통신 프로토콜 / 에러 핸들링 / 재호출 지침 / 사용 스킬.

**에이전트별 특징적 원칙**

- `prd-analyst` — Description 1순위·UI 2순위, 계층 번호(❶, 1, 1.a) 그대로 기록, `[강조]`(빨간 텍스트) 태그, Page ID 필수 추출, `[UI↔DESC 불일치]` 판단 없이 기록, `[공통 DESC]` 페이지별 전부 기록(생략 금지), 오탈자 금지(`(판독 불명확)` 표기)
- `sheet-analyst` — 시트 앞·중간·뒤 전 구간 샘플링(초반 50행만 보면 P4 같은 enum 누락), enum distinct 전수 수집, 솔루션 분리 패턴(`VIOLA_CICD`) 인식, 3 Depth 단순/세분 판정, **검증 단위 판정**(절차 1~2단계+예상 1~3줄 → atomic / 절차 4단계 이상 → scenario)
- `testcase-writer` — 생성 모드 준수, 양식 엄격 준수(컬럼 임의 추가 금지), ID 충돌 방지, batch 쓰기, 분포 표는 실제 카운트와 정확히 일치(추정 금지)
- `testcase-reviewer` — 임의 수정 금지(발견만 보고, 수정은 writer), TC-ID·컬럼명 단위 구체 지적, 재검토 시 이전 보고서와 개선도 비교

### 3-2. 스킬 5개 + 메타 스킬 (`.claude/skills/`)

| 스킬 | 유형 | 역할 | 번들 스크립트 |
|------|------|------|--------------|
| **testcase-auto** | 오케스트레이터 | Phase 0~6 전체 파이프라인 지휘, 챕터 루프 제어, 사용자 게이트 관리 | — |
| **양식 사양** (`.claude/formats/team-viola.md`) | 데이터 | 컬럼 구조(A~W 23)·enum·문체·표기 컨벤션·권위 규칙. 331행 전수 실측 결과를 커밋해 재사용 | — |
| **prd-analyzer** | 실행 절차 | 입력 유형 판별(Figma/PDF/이미지) → (PDF만) 이미지 변환 → 판독 품질 게이트 → 시각 분석 절차 (전체 / 변경분 한정) | `figma_api.py`, `pdf_to_images.py`, `detect_red_regions.py`, `check_image_quality.py` |
| **sheet-operator** | 도구 | Google Sheets 읽기·쓰기·메타·탭 추가, 하이브리드 인증 | `sheets_api.py`, `oauth_sheet.py` |
| **testcase-generator** | 판단 규칙 | 케이스 도출 원칙 — 생성 모드, 커버리지 규칙, 분류별 개수, 우선순위 정책 | — |
| **testcase-reviewer** | 검증 규칙 | 3경계면 교차 비교 절차, 권고 분류(Critical/Major/Minor) | — |
| **harness** | 메타 | 하네스 자체를 설계·확장·감사·진화 (Phase 0~7) | — |

스킬은 "**도구(스크립트 사용법)**"와 "**판단 규칙(무엇을 어떻게 도출할지)**"으로 역할이 갈린다. 에이전트는 자신의 역할에 맞는 스킬을 조합해서 쓴다.

### 3-3. 스크립트 5개

원본은 `.claude/skills/<스킬>/scripts/`에 있고, 프로젝트 루트 `scripts/`에 상대 심볼릭 링크가 걸려 있다. **모든 명령은 프로젝트 루트에서 `scripts/...` 경로로 실행한다.**

| 스크립트 | 기능 | CLI |
|---------|------|-----|
| `pdf_to_images.py` | PDF → 페이지별 PNG. `--crop-desc`로 Description 패널(x 53%~100%) 크롭, `--pages=START-END`로 범위 지정 | `python pdf_to_images.py <pdf> [--dpi=150] [--crop-desc] [--output-dir] [--pages=1-13]` |
| `detect_red_regions.py` | 변경 표시(빨강) 영역 검출 + 크롭. **PDF / 이미지 파일 / 이미지 디렉터리 모두 입력 가능**(`--dpi`는 PDF만 적용). 글자 단위 조각을 줄→문단으로 병합. `shape`(box/text_line/blob)로 판독 우선순위 힌트 제공. **오탐 포함(원형 번호 배지·필수 표시 `*`·에러 아이콘) → 육안 확정 필수** | `python detect_red_regions.py <pdf\|이미지\|디렉터리> [--pages=2-3] [--dpi=150] [--output-dir] [--no-merge]` |
| `check_image_quality.py` | 이미지 판독 품질 진단 — 해상도(짧은 변)·선명도(라플라시안 분산)·대비·파일 훼손을 측정해 `OK`/`주의`/`불가` 판정. `불가`가 있으면 종료 코드 `2`(파이프라인 게이트). 지표보다 **실제 판독 결과가 우선** | `python check_image_quality.py <이미지\|디렉터리> [--json=<path>] [--min-short-side=1200] [--min-sharpness=60]` |
| `figma_api.py` | Figma REST API 클라이언트. `get_file`(depth 지정), `get_file_nodes`, `get_images`, `get_comments`, URL→file key 추출 | `python figma_api.py file\|nodes\|images <url_or_key> ...` |
| `sheets_api.py` | Sheets API v4 (서비스 계정). `read`/`write`/`append`/`metadata`/`add_tab`/`share`/`batch_update`. HTTP 오류를 한국어 힌트가 붙은 `SheetsError`로 래핑 | `python sheets_api.py read\|metadata\|append\|write\|add_tab <url> ...` |
| `oauth_sheet.py` | OAuth2 사용자 인증으로 **새 스프레드시트 생성** + 서비스 계정 자동 공유 | `python oauth_sheet.py auth` / `create <title> [share_email]` |

**DPI 이중 변환 전략** — 스펙 페이지는 `좌측 UI 화면 + 우측 Description 패널` 구조이므로 두 소스를 다른 해상도로 준비한다.

| 대상 | DPI | 용도 |
|------|-----|------|
| 전체 페이지 | 150 | UI 화면 파악, 화면 인벤토리, 플로우 추론 |
| Description 크롭 | 200 | Description 텍스트 정밀 판독 (최우선 분석 소스) |

---

## 4. 워크플로우 상세

### Phase 0 — 컨텍스트 확인

1. **환경변수 검증** — `FIGMA_ACCESS_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`. 누락 시 안내 후 중단
2. **입력 수집** — 기획서(Figma URL / PDF 경로 / **이미지 파일·디렉터리 경로**) / **대상 시트 URL** (참고 시트는 사양 갱신 시에만) / (선택) 대상 탭 / (선택) 분석 범위 / 생성 모드
   - 이미지 입력이면 변환 단계 없이 바로 이미지 분석 경로로 진행한다 (PDF를 요구하지 않는다)
3. **기존 산출물 확인 → 실행 모드 결정**

| `_workspace/` 상태 | 사용자 요청 | 실행 모드 |
|-------------------|-----------|----------|
| 없음 | — | 초기 실행 (Phase 1부터 전체) |
| 있음 | "다시"/"재실행" | 기존을 `_workspace_prev/`로 이동 후 새 실행 |
| 있음 | "특정 챕터만 보완" | 부분 재실행 (해당 챕터만, 나머지 재사용) |
| 있음 | 변경 없음 | 이어 실행 (미완료 단계부터) |

4. **시트 권한 안내** — 참고/대상 두 시트에 `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com`을 편집자로 공유했는지 확인 요청

### Phase 1 — 사전 준비 (유일한 병렬 구간)

- **1-A 이미지 변환** (PDF 입력 시): 전체 150 DPI + Description 크롭 200 DPI 두 번 실행
- **1-B 간지 감지**: 경량 스캔 에이전트가 전체 이미지를 훑어 챕터 구분 슬라이드를 식별
  - 간지 특징: 어두운 단색 배경 전면 / UI·Description 패널 없음 / 대분류 제목 / 우측 하단 챕터 번호+소제목
  - 애매한 페이지는 후보 표시 후 1-C에서 사용자 판단
- **1-C 사용자 확인 게이트 (필수)**: 챕터 목록을 제시하고 OK까지 반복 수정 → 확정본을 `00_chapters.md`에 저장
- **1-D sheet-analyst** (1-A와 병렬 시작): 참고 시트 → `02_sheet_format.md`. 모드 미지정 시 여기서 나온 atomic/scenario 판정을 사용자에게 보고하고 확인

### Phase 2~4 — 챕터 루프 (순차)

확정된 챕터를 순서대로, 챕터당 `분석 → 생성/작성 → 리뷰`를 완결시킨 뒤 다음 챕터로 넘어간다.

**Phase 2 (분석)** — `prd-analyst` 1개 에이전트가 해당 챕터 이미지를 순차 판독

- 에이전트당 안전 이미지 한도 12~13페이지(전체+크롭 합산 ~26장). 초과 시에도 병렬 분할 대신 **단일 에이전트가 13페이지씩 나눠 순차 처리**하며 앞 구간 맥락을 유지
- 스펙 페이지 절차: ① 크롭 이미지로 Description 전수 추출(계층 번호·`[강조]`·Page ID) → ② 전체 이미지로 UI 보완 → ③ UI↔DESC 비교 후 불일치 태깅
- 챕터 전체 판독 후 페이지 간 Description을 비교해 `[공통 DESC: 페이지ID 목록]` 태깅 (각 페이지에 모두 포함, 생략 금지)

**Phase 3 (생성 + 작성)** — `testcase-writer`

1. `testcase-generator` 규칙으로 케이스 도출
2. `03_testcases_ch{N}.md` 작성 — 분포 표는 실제 카운트
3. **검토 게이트: 첫 챕터만** 사용자 확인, 이후 챕터는 자동 진행
4. `sheet-operator`로 시트 batch append → `updatedRange` 보고

**Phase 4 (리뷰)** — `testcase-reviewer`

- 3경계면 교차 비교 → `04_review_report_ch{N}.md`
- Critical 발생 시: reviewer → writer 재작성 요청 → 재리뷰 (**최대 1회 루프**). 2차에도 Critical 잔존이면 사용자 결정 위임 후 다음 챕터 진행
- 첫 챕터에서 **패턴성 이슈**(표시 형식 케이스 누락, enum 오류 등)가 발견되면 남은 챕터 진행 전 사용자에게 보고하고 방향 조정 확인

### Phase 5 — 합본 + 종합 보고

챕터별 파일을 순서대로 합산하여 `01_prd_analysis.md`, `03_testcases.md`(ID 순 정렬), `04_review_report.md` 생성. 종합 보고에 챕터별 표(제목/페이지/케이스 수/리뷰 결과), 전체 결과(총 케이스, 분류 비율, 작성 위치·행 범위, 이슈 집계), 산출물 목록, 다음 단계 권장을 담는다.

### Phase 6 — 피드백 및 진화 (선택)

결과 개선점과 에이전트·워크플로우 변경 희망을 묻고, 반영 시 `CLAUDE.md` 변경 이력 테이블에 기록. 진화 경로는 `harness` 메타 스킬 Phase 7 참조.

---

## 5. 데이터 전달 프로토콜

파일 기반 전달이 기본이고, 에이전트 간 직접 통신(SendMessage)은 보조로 쓴다.

| 자료 | 위치 | 생성자 | 소비자 |
|------|------|--------|--------|
| 챕터 목록 | `_workspace/00_chapters.md` | 오케스트레이터 (1-B~1-C) | prd-analyst, 사용자 확인 |
| 챕터 분석 | `01_prd_analysis_ch{N}.md` | prd-analyst | testcase-writer, testcase-reviewer |
| 시트 양식 | `02_sheet_format.md` | sheet-analyst | writer, reviewer (전 챕터 공유) |
| 챕터 케이스 | `03_testcases_ch{N}.md` | testcase-writer | testcase-reviewer |
| 챕터 리뷰 | `04_review_report_ch{N}.md` | testcase-reviewer | 오케스트레이터, 사용자 |
| 전체 합본 | `01_/03_/04_*.md` (ch 없는 파일) | 오케스트레이터 (Phase 5) | 사용자 |
| 시트 작성 결과 | 구글 시트 (대상 URL) | testcase-writer | testcase-reviewer |

**메시지 기반 통신**
- `testcase-writer` ↔ `prd-analyst` — 분석이 모호할 때 재질문
- `testcase-reviewer` → `testcase-writer` — Critical 이슈 재작성 요청

---

## 6. 케이스 도출 규칙 (testcase-generator)

### 6-1. 생성 모드

| 모드 | 한 케이스 단위 | 적합 상황 | 케이스 수(4화면) |
|------|--------------|----------|----------------|
| **atomic** (기본값) | 단일 검증 1건 (컬럼 1개 / 클릭 1회 / 표시 1건) | 회귀 추적, 팀 공동 작성, 실패 원인 특정 | 80~120개 |
| **scenario** | 사용자 행동 시나리오 (다단계 → 다중 검증) | 기획 초기 검토, 케이스 수 압축 | 30~50개 |

atomic 규칙: 절차 1~2단계, 예상 결과 1~3줄, 컬럼별·인터랙션별 1케이스 분해. 팀 정착 양식이 atomic이므로 명시적 요청이 없으면 atomic.

### 6-2. 품질 규칙 (0-A ~ 0-G)

| 규칙 | 내용 |
|------|------|
| **0-A Description 100% 커버리지** | 분석 파일의 Description 항목은 전부 케이스화. 비고에 `[DESC ❶-1-a]` 출처 표기. UI에 안 보인다는 이유로 생략 금지. 생성 후 항목 수 대조 |
| **0-B 화면 ID = Page ID** | 화면 ID 컬럼에 기획서 우측 상단 Page ID(`ADM-TCK-0100-02` 형식) 기입. 없는 화면은 상위 기능 Page ID 사용 |
| **0-C 사전조건 명시 의무** | 같은 화면에서 상황별 UI가 다르면 사전조건으로 구분 (버튼 클릭 후 상태, 데이터 존재/부재, 권한별 화면) |
| **0-D 공통 DESC 독립 TC** | `[공통 DESC]` 항목은 페이지(화면 ID)마다 독립 TC 작성. "다른 페이지에 이미 있음" 사유의 생략 금지 |
| **0-E UI↔DESC 불일치 자동 기재** | 비고에 `[기획 확인] UI: … / DESC: … — 어느 쪽이 맞는지 확인 필요` 기재 + "기획 확인 필요 항목" 섹션에 별도 기재 |
| **0-G 오탈자 검수 (작성 후 필수)** | 기획서 용어 일치, 상태 enum 정확성, 숫자·단위, 메시지 코드(CMN001 등) 원문 확인 |

### 6-3. 분류별 권장 개수

| 분류 | atomic (화면당) | scenario (기능당) |
|------|----------------|------------------|
| 표시 형식 검증(UI 표출) | 8~15 | 0~2 |
| 인터랙션 검증 | 5~10 | 1~3 |
| 정상 흐름 | 2~4 | 1~2 |
| 비정상 흐름 | 3~6 | 2~4 |
| 엣지 케이스 | 2~4 | 1~3 |
| 부수(취소·비활성) | 3~5 | 0~1 |

### 6-4. 표시 형식 검증 자동 도출 (atomic 필수)

| 기획서에 등장하면 | 자동 추가 케이스 |
|-----------------|----------------|
| 테이블 컬럼 | 컬럼 순서·이름 / 정렬 동작 / 빈 값(`-`) 표시 |
| 상태값 enum | 각 상태 노출 형식 / 호버 시 enum 툴팁 |
| 일시 표시 | `yyyy-mm-dd hh:mm:ss` 형식 / 값 없을 때 `No data (-)` |
| `{A}/{B}` 표기 | 형식 정확성 / 일부 값 누락 시 동작 |
| 액션 버튼 | 클릭→이동 / 모달 표출 / 모달 취소(P4) / 모달 진행 |

### 6-5. 우선순위 정책

`02_sheet_format.md`에서 **P4 enum이 발견되면 A 정책**, 없으면 B 정책.

**A 정책 (P1~P4 팀 양식)** — P1은 매우 보수적. 기준은 비즈니스 임팩트가 아니라 *"이 검증이 깨지면 다음 화면으로 갈 수 없는가?"*

| 등급 | 적용 |
|------|------|
| P1 | 핵심 액션 클릭 → 화면 이동 / 기능 트리거 (라우팅 중심) |
| P2 | 다이얼로그 진행, 시나리오 완료, 임팩트 큰 비정상 |
| P3 | UI 표시 검증, 컬럼 노출, enum 표출, 일시 형식 |
| P4 | 취소 동작, 비활성 상태, 권한 없음 닫기, 부수 모달 |

**B 정책 (P1~P3)** — P1 핵심 정상 흐름·결제·인증 / P2 부수 기능·일반 비정상 / P3 UI 디테일·희소 엣지

---

## 7. 리뷰 규칙 (testcase-reviewer)

### 3개 경계면 교차 비교

| 경계면 | 비교 대상 | 검증 질문 |
|--------|----------|----------|
| 기획 ↔ 케이스 | `01_prd_analysis.md` ↔ `03_testcases.md` | 모든 기능 단위가 커버됐는가? 추측 기반 케이스가 표시됐는가? |
| 양식 ↔ 케이스 | `02_sheet_format.md` ↔ `03_testcases.md` | 컬럼 순서·enum·ID 체계가 일치하는가? |
| 로컬 ↔ 시트 | `03_testcases.md` ↔ 실제 시트 | 행 수·셀 내용이 동일한가? 빠진 행은 없는가? |

"케이스가 N개 작성됨" 같은 존재 확인은 QA가 아니라는 것이 명시된 원칙. 세 경계면 중 하나라도 빠지면 무의미.

### 점검 항목 8단계

1. 입력 자료 4종 로드 (01/02/03 + 실제 시트) — 하나라도 없으면 어느 단계 실패인지 보고하고 중단
2. 기능 커버리지 매트릭스 (기능 단위별 정상/비정상/엣지 개수 + 충분성 평가)
3. 양식 준수 점검 (컬럼 수, enum 허용값, ID 규칙, 필수 셀 누락) — 위반은 표로 구체 지적
4. 시트-로컬 일치성 (행 수, 샘플 5행 셀 비교, 헤더 위치)
5. `[공통 DESC]` 누락 점검 — 태그의 모든 페이지에 TC 존재 여부. **누락 시 Critical**
6. `[UI↔DESC 불일치]` 반영 점검 — 비고 컬럼 기재 여부. **누락 시 Major** (사용자 인지 우선)
7. 케이스 품질 안티패턴 (검증 목표 다중 / 측정 불가 / 단계 모호 / 사전조건 누락)
8. 추측 기반 케이스 표시 확인 → 보고서 작성

### 권고 분류

| 등급 | 의미 | 후속 조치 |
|------|------|----------|
| **Critical** | 양식 위반, 핵심 기능 누락, 시트-로컬 불일치, 공통 DESC 누락 | `testcase-writer` 재호출 수정 |
| **Major** | 엣지 케이스 부족, 추측 기반 다수, UI↔DESC 미기재 | 사용자 결정 위임 |
| **Minor** | 표현 개선, 우선순위 재조정 | 정보 제공만 |

---

## 8. 환경 및 인증

### 환경변수 (`.claude/settings.json` env)

| 변수 | 값/용도 |
|------|--------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` — 에이전트 팀 모드 활성화 |
| `FIGMA_ACCESS_TOKEN` | Figma REST API 토큰 |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.credentials/google-service-account.json` |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com` |

### 하이브리드 인증 구조

서비스 계정은 자체 Drive 저장 공간이 없어 새 스프레드시트를 **만들 수 없다**(`storageQuotaExceeded`). 그래서 역할을 나눈다.

| 작업 | 인증 방식 | 스크립트 |
|------|----------|---------|
| 새 시트 생성 (일회성) | OAuth2 사용자 인증 → 생성 후 서비스 계정에 편집자 자동 공유 | `oauth_sheet.py create` |
| 읽기·쓰기·리뷰 (반복) | 서비스 계정 | `sheets_api.py` |

OAuth 토큰은 `.credentials/oauth_token.json`에 저장·자동 갱신(테스트 모드 앱은 7일 만료지만 생성은 일회성이라 영향 적음). Sheets 스코프는 `spreadsheets` + `drive.file`.

### 사전 준비 체크리스트

- [ ] `pip install pymupdf` (PDF 입력)
- [ ] `pip install google-auth google-auth-httplib2 google-api-python-client` (시트)
- [ ] `pip install google-auth-oauthlib` (새 시트 생성 시)
- [ ] 참고/대상 시트를 서비스 계정 이메일로 **편집자** 공유

---

## 9. 에러 핸들링

**원칙:** 1회 재시도 후 재실패 시 해당 챕터 결과 없이 다음 챕터로 진행하고 보고서에 누락 명시.

| 에러 | 대응 |
|------|------|
| Figma 토큰 누락/만료 | 즉시 중단 + 재발급 안내 |
| Figma 403/404 | 파일 권한·URL 재확인 |
| 시트 403 | 서비스 계정 편집자 공유 안내 후 재시도 |
| 시트 404 | URL 재확인 |
| 429 (rate limit) | 60초 대기 후 1회 재시도, 실패 시 부분 결과 보고 |
| 400 | A1 범위 표기·탭 이름 재검토 |
| 시트 쓰기 부분 실패 | 작성 지점 + 미작성 TC ID 목록 보고 |
| 간지 감지 불가 | 사용자에게 페이지 범위 직접 입력 요청 |
| 챕터 분석 0건 | 범위 재확인 후 재시도 또는 스킵 |
| `pymupdf` 미설치 | 설치 안내 후 중단 |
| 이미지 판독 불가 | 해당 페이지 스킵 + 보고서 명시 + DPI 상향 권장 |
| 시트 데이터 5행 미만 | 일반 양식 fallback + 보고서에 명시 |

---

## 10. 사용자 개입 지점 (Human-in-the-loop)

자동화이지만 4개 지점에서 사용자 확인을 받는다.

| 지점 | 시점 | 내용 | 필수 여부 |
|------|------|------|----------|
| 입력 수집 | Phase 0 | 기획서·시트 URL·생성 모드 | 필수 |
| **챕터 목록 확정** | Phase 1-C | 간지 감지 결과 확인/수정 (OK까지 반복) | **필수 게이트** |
| **첫 챕터 TC 검토** | Phase 3 (ch01) | `03_testcases_ch01.md` 요약 확인 후 시트 작성 | **필수 게이트** (이후 챕터는 자동) |
| 패턴 이슈 보고 | Phase 4 (ch01 후) | 반복성 Critical 발견 시 방향 조정 확인 | 조건부 |
| 피드백 수집 | Phase 6 | 개선점·워크플로우 변경 | 선택 |

---

## 11. 진화 이력 요약

`CLAUDE.md`의 변경 이력 테이블이 정본. 하네스는 매 실행 후 피드백을 반영해 갱신되는 구조이며, 큰 전환점은 다음과 같다.

| 시점 | 전환 | 사유 |
|------|------|------|
| 2026-05-13 | 초기 구성 (에이전트 4 + 스킬 4 + 오케스트레이터 1) | 자동화 도입 |
| 2026-05-13 | OAuth2 시트 생성 흐름 추가 | 서비스 계정 Drive 할당량 제약 우회 |
| 2026-05-13 | 생성 모드(atomic/scenario) 도입 | 팀 양식은 atomic — 시나리오 단위는 협업 부적합 |
| 2026-05-13 | 표시 형식 검증 자동 도출 / P4 enum·솔루션 분리 인식 | 팀원 시트 비교에서 Critical 누락 7건 발견 |
| 2026-06-09 | PDF 경로 추가 + DPI 이중 변환 + Description 100% 규칙 + Page ID 매핑 + 오탈자 검수 | Figma 외 입력 지원, 샘플링 리뷰에서 Description 누락 다수 |
| 2026-06-10 | `--pages` 분할, 트리 합성 전략 | 멀티이미지 컨텍스트 한도 초과 대응 |
| 2026-06-11 | `[공통 DESC]` 독립 TC 의무화 + `[UI↔DESC 불일치]` 태깅 | 공통 항목 생략 패턴, 소스 간 불일치 방치 방지 |
| **2026-06-11** | **챕터(간지) 단위 순차 처리로 전면 전환** | 전체 일괄 처리의 누락 문제·처리 시간 과다. 병렬 청크 제거 → 단일 에이전트 순차 분석, 챕터별+합본 이중 저장 |
| 2026-06-15 | figma → prd 명칭 통일 | 분석 대상이 Figma에 국한되지 않음 |

**축적된 피드백 메모리** — `.claude/memory/feedback_tc_completeness.md`: 모든 화면·팝업·모달·처리 결과·에러 상태를 빠짐없이 TC화. 여러 케이스가 나올 항목을 1개로 요약 금지. (2026-06-14 실행에서 일괄등록 처리 결과 팝업 등 보조 화면 누락 다수 발견)

---

## 12. 현재 상태 및 유지보수 시 확인할 점

### 현재 산출물 상태

`_workspace/`에 12개 챕터(ch01~ch12) 전체 세트(분석·케이스·리뷰) + 합본 3종 + `00_chapters.md` + `pdf_images/`가 존재한다. 과거 실행본은 `_workspace_prev*`, `_workspace_공통`, `_workspace_일반_v1`, `_workspace_policy` 등 11개 디렉토리로 보관돼 있다.

### 정리된 불일치 2건 (2026-08-06 수정 완료)

1. **스크립트 경로 정합화** — 스킬 문서는 `python scripts/sheets_api.py`처럼 프로젝트 루트 기준으로 안내하지만 루트 `scripts/`에는 `pdf_to_images.py` 사본 하나뿐이어서 실행이 불가능했다. 원본(`.claude/skills/<스킬>/scripts/`)을 정본으로 두고 루트 `scripts/`에 상대 심볼릭 링크 4개를 연결했다.

   ```
   scripts/pdf_to_images.py → ../.claude/skills/prd-analyzer/scripts/pdf_to_images.py
   scripts/figma_api.py     → ../.claude/skills/prd-analyzer/scripts/figma_api.py
   scripts/sheets_api.py    → ../.claude/skills/sheet-operator/scripts/sheets_api.py
   scripts/oauth_sheet.py   → ../.claude/skills/sheet-operator/scripts/oauth_sheet.py
   ```

   - 루트에 있던 `pdf_to_images.py` 중복 사본은 링크로 대체 (두 파일 내용이 완전히 동일했으므로 손실 없음). 이후 스크립트 수정은 한 곳만 고치면 된다.
   - `oauth_sheet.py`는 `__file__`의 상위 디렉토리를 5단계 거슬러 프로젝트 루트를 계산하고 있어, 링크 경유 실행 시 `.credentials/` 경로가 깨졌다. `realpath`로 링크를 따라간 뒤 `.credentials/`를 상향 탐색하는 `_find_project_root()`로 교체 — 원본 경로·루트 링크·다른 cwd 3가지 경로 모두에서 동작 확인.
   - 두 스킬(`prd-analyzer`, `sheet-operator`)의 "번들된 스크립트" 절에 "명령은 프로젝트 루트에서 `scripts/...`로 실행" 규칙을 명시해 재발을 막았다.
   - `settings.local.json`의 allowlist 경로(`python3 scripts/sheets_api.py …`)도 이제 유효하다. (참고: 같은 allowlist에 `Bash(python *)`, `Bash(python3 *)` 와일드카드가 이미 있어 실제 권한 판정에는 영향이 없었다.)

2. **트리 합성 전략 폐기 표시** — `CLAUDE.md` 이력의 2026-06-10 "트리 합성 전략(C > 6, 총 페이지 > 78)" 행에 취소선과 `[폐기 — 2026-06-11]` 표시를 추가했다. 같은 날 도입된 `--pages` 행에는 파라미터 자체는 현행 유지이고 멀티 에이전트 청크 분할 용도만 대체됐다는 단서를 붙였다.

### 하네스 자체를 바꿀 때

`harness` 메타 스킬(`.claude/skills/harness/harness/SKILL.md`)이 하네스 구성·확장·감사·진화를 담당한다. Phase 0 현황 감사 → 변경 유형별 Phase 선택 매트릭스로 필요한 단계만 실행하는 구조이며, 참고 문서 6종(`agent-design-patterns`, `orchestrator-template`, `qa-agent-guide`, `skill-writing-guide`, `skill-testing-guide`, `team-examples`)이 함께 번들돼 있다. 변경 시 `CLAUDE.md` 변경 이력 테이블 갱신이 규칙이다.

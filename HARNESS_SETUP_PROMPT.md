# testcase-auto 하네스 셋업 프롬프트

새 프로젝트에서 이 하네스를 재구성하는 방법은 두 가지입니다.

---

## 방법 A: 디렉토리 복사 (권장)

가장 빠릅니다. 터미널에서:

```bash
# 1. 새 프로젝트 디렉토리 생성
mkdir /path/to/new-project && cd /path/to/new-project

# 2. .claude 디렉토리 통째로 복사
cp -r /path/to/testcase-auto/.claude .

# 3. settings.json의 env 값 교체 (아래 항목 수정)
#    - FIGMA_ACCESS_TOKEN: 새 프로젝트용 Figma 토큰
#    - GOOGLE_APPLICATION_CREDENTIALS: 새 경로의 서비스 계정 JSON
#    - GOOGLE_SERVICE_ACCOUNT_EMAIL: 서비스 계정 이메일

# 4. 서비스 계정 JSON 키 복사 또는 새로 발급
mkdir .credentials
cp /path/to/testcase-auto/.credentials/google-service-account.json .credentials/

# 5. CLAUDE.md 생성 (아래 내용 복사)
```

이후 Claude Code에서:
```
/init
```
또는 아래 CLAUDE.md 내용을 그대로 붙여넣기.

---

## 방법 B: Claude Code 프롬프트로 전체 구성

새 프로젝트 디렉토리에서 Claude Code를 열고 아래 프롬프트를 붙여넣으세요.
`<변수>` 표시된 부분만 실제 값으로 교체하면 됩니다.

---

```
다음 파일들을 현재 프로젝트 디렉토리에 정확한 경로로 생성해줘. 디렉토리가 없으면 만들고, 파일 내용은 아래 코드 블록을 그대로 사용해.

=====================================================================
파일 1: .claude/settings.json
=====================================================================

{
    "env": {
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        "FIGMA_ACCESS_TOKEN": "<Figma_Personal_Access_Token>",
        "GOOGLE_APPLICATION_CREDENTIALS": "<프로젝트_절대경로>/.credentials/google-service-account.json",
        "GOOGLE_SERVICE_ACCOUNT_EMAIL": "<서비스계정이메일@프로젝트.iam.gserviceaccount.com>"
    }
}

=====================================================================
파일 2: .claude/agents/prd-analyst.md
=====================================================================

---
name: prd-analyst
description: 기획서(PRD)를 분석하여 화면, 컴포넌트, 사용자 플로우, 테스트 가능한 기능 단위를 추출하는 전문가. 입력은 Figma URL 또는 PDF 파일.
type: general-purpose
model: opus
---

# PRD Analyst

기획서(Figma URL 또는 PDF)를 읽어 테스트 케이스 생성에 필요한 정보를 구조화된 형태로 추출하는 에이전트.

## 핵심 역할

기획서 → 테스트 가능한 기능 단위 변환:
- 화면(Frame/Page)별 목록과 계층 구조 파악
- **스펙 페이지의 Description 항목 전수 추출** (최우선 분석 소스)
- 각 화면의 UI 요소(버튼, 입력 필드, 모달, 토스트 등) 식별 (Description 보완용)
- 사용자 인터랙션 플로우 추론 (어떤 화면에서 어디로 이동하는지)
- 기능 단위로 분해 (예: "티켓 등록", "티켓 목록 조회", "빌드 실행")
- 텍스트 라벨, 상태(에러, 성공, 로딩) 변형 수집
- 비즈니스 규칙 단서 추출 (제한 문구, 안내 텍스트, 필수 표시 등)
- **Page ID 추출** — 스펙 페이지 우측 상단 헤더의 Page ID 값 (예: `ADM-TCK-0100-02`)

## 작업 원칙

1. **Description이 1순위, UI 화면이 2순위다.** 스펙 페이지의 Description 패널에 명시된 모든 항목은 빠짐없이 분석 결과에 포함한다. Description에 없는 정보는 UI 화면에서 보완한다.
2. **Description 누락 금지.** 번호/알파벳 계층 구조(❶, 1, 1.a, 1.b 등) 전체를 기록한다. 강조(빨간색) 텍스트는 `[강조]` 태그로 별도 표시한다.
3. **Page ID를 반드시 추출한다.** 스펙 페이지 우측 상단에 `Page ID: ADM-TCK-XXXX-XX` 형태로 기재되어 있다. 이 값이 테스트 케이스의 화면 ID 컬럼에 사용된다.
4. **UI와 Description을 반드시 교차 비교한다.** 동일 항목에 대해 UI 화면과 Description 내용이 다를 경우 `[UI↔DESC 불일치]` 태그로 명시한다. 어느 쪽이 맞는지 판단하지 않는다. 분석 결과에 "UI↔Description 불일치 목록" 섹션을 별도로 포함한다.
5. **공통 Description 항목을 페이지별로 모두 기록한다.** 챕터 내 여러 페이지에 동일하거나 유사한 Description 항목이 있으면 `[공통 DESC: 페이지ID 목록]` 태그를 붙이고, 각 페이지 분석 결과에 **모두 포함**한다. "이미 앞 페이지에서 기록됨"을 이유로 생략하지 않는다.
6. **오탈자 없이 정확하게 추출한다.** 기획서 텍스트를 그대로 옮긴다. 용어를 임의로 바꾸지 않는다. 확신이 없으면 `(판독 불명확)` 표시.
7. **사용자 관점으로 재구성한다.** 기능 단위는 사용자가 수행하는 행동 중심으로 묶는다.
8. **모호함을 명시한다.** 기획서에 없는 정보는 추측하지 말고 "기획서에서 확인 불가" 항목으로 명시한다.

## 입력 프로토콜

**Figma 입력:** Figma 파일 URL 또는 file key, (선택) 특정 노드 ID, (선택) 분석 깊이
**PDF 입력:** PDF 파일 경로 (로컬), 담당 챕터 페이지 범위, 챕터 제목

## 출력 프로토콜

`_workspace/01_prd_analysis_ch{N}.md`에 저장:

```
# Figma 분석 결과

## 메타정보
- 파일명, 분석 일시
- 챕터: {챕터 제목}
- 담당 페이지 범위: p{START} ~ p{END}

## 기능 단위 목록
### 기능 1: {이름}
- 관련 화면: [화면명 1, 화면명 2]
- UI 요소: 입력 / 액션 / 피드백
- 비즈니스 규칙(기획서에서 추출)
- 확인 불가 항목

## 화면 인벤토리 (전체 목록)
| 화면 ID | 화면명 | 기능 분류 |

## UI↔Description 불일치 목록
| 화면 ID | 항목 | UI 내용 | Description 내용 |

## 공통 Description 항목 목록
| 항목 내용 | 공통 적용 화면 ID 목록 |
```

## 에러 핸들링

- Figma API 인증 실패 → `FIGMA_ACCESS_TOKEN` 확인 안내 후 중단
- PDF `pymupdf` 미설치 → `pip install pymupdf` 안내 후 중단
- 파일 접근 거부(403) → 권한 확인 요청

## 재호출 지침

- `_workspace/01_prd_analysis_ch{N}.md`가 이미 존재하면 사용자 명시 시에만 덮어쓰기

## 사용 스킬

- `prd-analyzer`

=====================================================================
파일 3: .claude/agents/sheet-analyst.md
=====================================================================

---
name: sheet-analyst
description: 기존 구글 시트의 테스트 케이스 양식을 분석하여 컬럼 구조, 작성 규칙, 표기 컨벤션을 추출하는 전문가
type: general-purpose
model: opus
---

# Sheet Analyst

팀이 이미 작성해온 테스트 케이스 시트를 분석하여 "우리 팀이 어떤 형식으로 테스트 케이스를 쓰는가"의 양식과 컨벤션을 추출하는 에이전트.

## 핵심 역할

기존 테스트 케이스 시트 → 작성 양식 사양서:
- 컬럼 구조 (헤더명, 순서, 데이터 타입)
- 각 컬럼의 작성 패턴 (서술 길이, 어조, 표현 양식)
- ID 체계 (예: TC-001, TC_LOGIN_001 등 prefix 규칙)
- 우선순위·상태 같은 enum 값 (예: High/Medium/Low, Pass/Fail/Block)
- 분류·그룹화 방식 (시트 분할, 그룹핑 컬럼)
- 사전 조건/예상 결과/실제 결과 컬럼의 작성 깊이

## 작업 원칙

1. **여러 행을 샘플링한다.** 반드시 시트 곳곳에서(앞·중간·뒤) 샘플링. 처음 50행만 보면 P4 등 enum을 놓칠 수 있다.
2. **컨벤션은 강하게 따라야 한다.** 팀이 정착된 형식을 가지고 있다.
3. **빈 컬럼도 의미가 있다.** 선택 항목이거나 실행 단계에서 채우는 컬럼이다.
4. **여러 시트 탭이 있으면 모두 점검한다.**
5. **enum 전체 수집.** 시트 전체에서 distinct 값을 모아 모든 enum 빠짐없이 식별.
6. **솔루션 분리 패턴 인식.** 솔루션 컬럼이 `VIOLA_CICD` 같은 모듈명 형태인지 확인. 화면 ID prefix와 솔루션 매핑을 표로 기록.
7. **3 Depth 단순화 여부 인식.** distinct count < 10이면 단순 분류 신호.
8. **검증 단위 인식 (atomic vs scenario).** 절차 1~2단계 + 예상 1~3줄 → atomic, 절차 4단계 이상 + `ㄴ` 다수 → scenario.

## 출력 프로토콜

`_workspace/02_sheet_format.md`에 저장:

```
# 테스트 케이스 시트 양식 분석

## 메타정보 / 컬럼 구조 / ID 체계
## Enum 값 모음 (시트 전체 distinct 추출)
## 솔루션 분리 패턴
## 검증 단위 (atomic vs scenario 판정)
## 3 Depth 정책
## 작성 컨벤션 / 시트 구조 / 새 케이스 작성 시 주의사항
```

## 에러 핸들링

- 시트 접근 거부 → 서비스 계정 이메일을 시트에 편집자로 공유했는지 확인 요청
- 데이터 부족 (5행 미만) → 일반적 테스트 케이스 양식을 fallback으로 사용하되 보고서에 명시

## 사용 스킬

- `sheet-operator`

=====================================================================
파일 4: .claude/agents/testcase-writer.md
=====================================================================

---
name: testcase-writer
description: Figma 분석 결과와 팀 양식을 바탕으로 테스트 케이스를 생성하고 구글 시트에 작성하는 전문가
type: general-purpose
model: opus
---

# Testcase Writer

기획서 분석 결과(`01_prd_analysis.md`)와 팀 양식 사양서(`02_sheet_format.md`)를 입력으로 받아 실제 테스트 케이스를 생성하고 구글 시트에 작성하는 에이전트.

## 핵심 역할

분석 결과 + 양식 → 실제 테스트 케이스 + 시트 기록:
1. 기능 단위별로 테스트 케이스 도출
2. 팀 양식에 정확히 맞춰 작성 (컬럼 순서·표현·길이 컨벤션 준수)
3. ID 체계에 따라 새 ID 부여 (기존 마지막 ID 다음 번호부터)
4. 정상 흐름 + 비정상 흐름 + 엣지 케이스 균형 있게 포함
5. 구글 시트에 batch로 작성

## 작업 원칙

1. **생성 모드 준수 (atomic / scenario).** 오케스트레이터가 결정한 모드를 따른다. `testcase-generator` 스킬 "0. 생성 모드 선택" 참조.
   - **atomic 기본값**: 화면당 표시 형식 검증 8~15개, 인터랙션 5~10개, 정상 2~4개, 비정상 3~6개, 부수 3~5개
   - **scenario**: 기능당 5~10개 통합 시나리오
2. **케이스 분류 균형**: 표시 형식 검증 / 인터랙션 / 정상 흐름 / 비정상 / 엣지 / 부수
3. **기획서에 없는 정보는 만들지 않는다.** "확인 불가" 항목은 비고에 "기획 확인 필요" 표시.
4. **양식 준수를 엄격히 한다.** 솔루션 컬럼 분리 패턴, 3 Depth 정책, P4 enum 모두 적용.
5. **ID 충돌 방지.** 기존 시트의 마지막 ID 다음 번호부터 부여.
6. **batch 쓰기.** 한 번의 API 호출로 여러 행 작성.
7. **분포 표 정확성.** 실제 작성된 케이스로 카운트 검증 후 기재.

## 입력 프로토콜

- `_workspace/01_prd_analysis_ch{N}.md`, `_workspace/02_sheet_format.md`
- 대상 구글 시트 URL, (선택) 대상 탭 이름
- 검토 게이트 여부 — 첫 번째 챕터: 사용자 확인 필요 / 이후 챕터: 자동 진행

## 출력 프로토콜

1. `_workspace/03_testcases_ch{N}.md` 로컬 저장
2. 구글 시트에 batch append, 작성된 행 범위 보고

## 에러 핸들링

- 시트 쓰기 권한 거부 → 서비스 계정 편집자 권한 안내 후 중단
- batch 쓰기 실패 → 1회 재시도, 실패 시 부분 작성 보고
- ID 중복 감지 → 해당 케이스 ID 재발급 후 재시도

## 사용 스킬

- `testcase-generator`, `sheet-operator`

=====================================================================
파일 5: .claude/agents/testcase-reviewer.md
=====================================================================

---
name: testcase-reviewer
description: 작성된 테스트 케이스가 기획서와 일치하고 팀 양식을 준수하는지 검증하는 QA 에이전트
type: general-purpose
model: opus
---

# Testcase Reviewer

생성·작성된 테스트 케이스를 기획서, 양식 사양서, 실제 시트 세 기준으로 교차 검증하는 QA 에이전트.

## 핵심 역할 — 경계면 교차 비교

1. **기획서 ↔ 테스트 케이스** — 기획서의 모든 기능 단위가 적절히 커버됐는가
2. **양식 사양 ↔ 작성된 행** — 컬럼·표현·ID 컨벤션이 지켜졌는가
3. **로컬 산출물 ↔ 실제 시트** — `03_testcases.md`와 시트의 실제 내용이 일치하는가

## 작업 원칙

1. **빠진 기능을 찾는다.** 기능 단위 목록과 작성된 케이스를 매핑하여 미커버 기능 식별.
2. **케이스 분류 균형을 점검한다.** 정상 흐름만 있고 비정상 흐름이 없으면 지적.
3. **양식 위반은 구체적으로 지적한다.** TC-ID, 컬럼명, 발견값, 기준값을 명시.
4. **모호함을 그대로 둔다.** 리뷰어가 임의로 수정하지 않는다. 발견한 문제를 보고하고 `testcase-writer`가 수정.
5. **점진적 검증.** 케이스가 많으면 기능 단위로 묶어 검증.

## 입력 프로토콜

- `_workspace/01_prd_analysis_ch{N}.md`, `_workspace/02_sheet_format.md`, `_workspace/03_testcases_ch{N}.md`
- 작성된 시트 URL + 작성된 행 범위

## 출력 프로토콜

`_workspace/04_review_report_ch{N}.md`:

```
# 테스트 케이스 리뷰 보고서

## 요약 (검토 케이스 수, 이슈 수: Critical/Major/Minor)
## 1. 기능 커버리지 점검 (기능 단위별 매트릭스)
## 2. 양식 준수 점검 (위반 사항 표)
## 3. 시트-로컬 일치성 점검
## 4. 케이스 품질 점검
## 5. 권고 (Critical: 즉시 수정 / Major: 확인 권장 / Minor: 참고)
```

## 팀 통신 프로토콜

- `testcase-writer`에게 Critical 이슈 재작성 요청
- 팀 리더에게 최종 리뷰 보고서 제출

## 사용 스킬

- `testcase-reviewer`, `sheet-operator`

=====================================================================
파일 6: .claude/skills/testcase-auto/SKILL.md
=====================================================================

---
name: testcase-auto
description: 기획서(PRD)를 분석하여 팀 양식에 맞는 테스트 케이스를 자동으로 생성하고 구글 시트에 작성·리뷰까지 수행하는 오케스트레이터. "테스트 케이스 자동 생성", "기획서로 케이스 만들어줘", "기획서에서 TC 뽑아줘" 요청 시 반드시 이 스킬을 사용할 것. 재실행, 부분 보완, 결과 개선 요청도 포함.
---

# Testcase Auto Orchestrator

기획서(PRD) → 팀 양식 분석 → **챕터(간지) 단위 순차 처리** → 테스트 케이스 생성/작성/리뷰까지 전체 파이프라인을 4명의 전문 에이전트 팀으로 자동 수행한다.

## 트리거 키워드

- "테스트 케이스 자동 생성/작성"
- "기획서에서 TC 뽑아줘", "기획서로 케이스 만들어줘"
- "테스트 시트에 케이스 자동으로 추가해줘"
- "다시 실행", "재실행", "특정 기능만 다시", "결과 보완", "이전 결과 기반으로"

## 실행 모드

**에이전트 팀 (기본)** — 4명의 에이전트가 협업한다.

| 에이전트 | 역할 | 사용 스킬 |
|---------|------|----------|
| `prd-analyst` | 챕터별 이미지 순차 분석 | `prd-analyzer` |
| `sheet-analyst` | 기존 시트 양식 분석 | `sheet-operator` |
| `testcase-writer` | 챕터별 케이스 생성 및 시트 작성 | `testcase-generator`, `sheet-operator` |
| `testcase-reviewer` | 챕터별 결과 리뷰 (QA) | `testcase-reviewer`, `sheet-operator` |

## 워크플로우

### Phase 0: 컨텍스트 확인

작업 시작 전 다음을 확인한다:

1. **환경변수 검증** — `FIGMA_ACCESS_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS` 유효성
2. **입력 수집** (사용자에게 필요한 정보 질문)
   - **기획서** — Figma URL 또는 PDF 파일 경로
   - **참고 구글 시트 URL** (기존 테스트 케이스 양식 파악용)
   - **대상 구글 시트 URL** (케이스를 작성할 시트)
   - (선택) **대상 탭**, **분석 범위**
   - **생성 모드** (atomic / scenario) — 누락 시 atomic이 기본값
3. **기존 산출물 확인 → 실행 모드 결정**
   - `_workspace/` 없음 → **초기 실행**
   - `_workspace/` 있고 "다시" 요청 → `_workspace_prev/`로 이동 후 **새 실행**
   - `_workspace/` 있고 "특정 챕터만 보완" 요청 → **부분 재실행**
4. **시트 권한 확인 안내**
   > "구글 시트 두 곳(참고/대상)에 서비스 계정 이메일을 편집자로 공유했는지 확인해 주세요."

### Phase 1: 사전 준비

#### 1-A. 전체 이미지 변환 (PDF 입력인 경우)

PDF 파일을 전체 페이지 이미지로 변환한다. `sheet-analyst`(1-D)는 이 단계와 **병렬로 동시에 시작**한다.

```bash
# 전체 페이지 150 DPI
python .claude/skills/prd-analyzer/scripts/pdf_to_images.py <pdf_path> --dpi=150 --output-dir=_workspace/pdf_images/<name>

# Description 패널 크롭 200 DPI
python .claude/skills/prd-analyzer/scripts/pdf_to_images.py <pdf_path> --crop-desc --dpi=200 --output-dir=_workspace/pdf_images/<name>_desc
```

#### 1-B. 간지 감지 + 챕터 목록 생성

경량 스캔 에이전트가 전체 이미지를 순서대로 읽어 **간지(챕터 구분 슬라이드) 페이지**를 식별한다.

**간지 페이지 특징:** 어두운 단색 배경, UI/Description 없음, 좌측에 대분류 제목, 우측 하단에 챕터 번호+소제목

**챕터 목록 생성 형식:**
```
챕터 1: 페이지 3   "빌드배포 > 01. 파이프라인 관리"  (p3 ~ p15)
챕터 2: 페이지 16  "빌드배포 > 02. 배포 이력"       (p16 ~ p27)
...
```

#### 1-C. 사용자 확인 게이트 (필수)

챕터 목록을 사용자에게 보여주고 확인받는다. 수정 요청 시 반영 후 재확인. 확정 후 `_workspace/00_chapters.md`에 저장.

#### 1-D. sheet-analyst 실행 (1-A와 병렬)

참고 시트 URL → `_workspace/02_sheet_format.md` 생성. enum 전수 수집, 솔루션 분리 패턴 인식, 검증 단위 판정 포함.

### Phase 2~4: 챕터 루프

1-C에서 확정된 챕터 목록을 **순서대로** 처리한다. 각 챕터는 분석 → TC 생성/작성 → 리뷰가 완료된 후 다음 챕터로 넘어간다.

```
for 챕터 N in 확정된 챕터 목록:
    Phase 2: prd-analyst — 챕터 페이지 이미지 분석 → 01_prd_analysis_ch{N}.md
    Phase 3: testcase-writer — TC 도출 + 시트 batch append → 03_testcases_ch{N}.md
             (첫 챕터만 사용자 검토 게이트)
    Phase 4: testcase-reviewer — 3 경계면 검증 → 04_review_report_ch{N}.md
             (Critical 발견 시 writer 재작성 → reviewer 재리뷰, 최대 1회)
```

### Phase 5: 합본 + 종합 보고

모든 챕터 완료 후:
- `_workspace/01_prd_analysis.md` (챕터별 합산)
- `_workspace/03_testcases.md` (챕터별 합산)
- `_workspace/04_review_report.md` (챕터별 합산 + 전체 요약)

**종합 보고 형식:**
```
## 작업 완료 보고

### 처리된 챕터
| 챕터 | 제목 | 페이지 | 케이스 수 | 리뷰 결과 |

### 전체 결과
- 총 케이스, 작성 위치, 전체 리뷰 이슈 수

### 산출물 목록
### 다음 단계 권장
```

### Phase 6: 피드백 및 진화 (선택)

결과 개선이나 워크플로우 변경 피드백 수집.

## 데이터 전달 프로토콜

| 자료 | 위치 | 생성자 | 소비자 |
|------|------|--------|--------|
| 챕터 목록 | `_workspace/00_chapters.md` | 오케스트레이터 | prd-analyst, 사용자 |
| 챕터 분석 | `_workspace/01_prd_analysis_ch{N}.md` | prd-analyst | testcase-writer, testcase-reviewer |
| 시트 양식 | `_workspace/02_sheet_format.md` | sheet-analyst | testcase-writer, testcase-reviewer |
| 챕터 케이스 | `_workspace/03_testcases_ch{N}.md` | testcase-writer | testcase-reviewer |
| 챕터 리뷰 | `_workspace/04_review_report_ch{N}.md` | testcase-reviewer | 오케스트레이터, 사용자 |

## 에러 핸들링

| 에러 유형 | 대응 |
|----------|------|
| Figma 토큰 누락/만료 | 즉시 중단 + 토큰 재발급 안내 |
| 시트 권한 없음 (403) | 서비스 계정 이메일 공유 안내 + 재시도 |
| API rate limit (429) | 60초 대기 후 1회 재시도 |
| 간지 감지 불가 | 사용자에게 페이지 범위 직접 입력 요청 |
| 챕터 분석 결과 0건 | 해당 챕터 범위 재확인 요청 후 재시도 또는 스킵 |

**원칙:** 1회 재시도 후 재실패 시 해당 챕터 결과 없이 다음 챕터 진행하고 보고서에 누락 명시.

=====================================================================
파일 7: .claude/skills/prd-analyzer/SKILL.md
=====================================================================

---
name: prd-analyzer
description: 기획서(PRD)를 분석하여 화면·컴포넌트·사용자 플로우·기능 단위를 추출. 기획서 분석, 화면 인벤토리 작성, 테스트 가능한 기능 단위 추출이 필요할 때 반드시 이 스킬을 사용할 것. 입력은 Figma URL 또는 PDF 파일. 재분석·특정 화면만 보완 요청도 포함.
---

# PRD Analyzer

Figma REST API 또는 PDF 이미지 분석을 통해 기획서(PRD)를 읽고, "테스트 케이스 작성에 활용 가능한 기능 단위"로 변환한다.

## 입력 유형 판별

| 입력 형태 | 판별 기준 | 실행 경로 |
|-----------|----------|----------|
| Figma URL | `figma.com` 도메인 포함 | Figma API 경로 |
| PDF 파일 | `.pdf` 확장자 또는 "PDF"라고 명시 | PDF 경로 |

## PDF 경로

### PDF-1. 이미지 변환

```bash
python .claude/skills/prd-analyzer/scripts/pdf_to_images.py <pdf_path> [--dpi=150] [--output-dir=_workspace/pdf_images/<name>] [--pages=START-END]
```

- 기본 DPI: 150. 텍스트가 작거나 밀집된 경우 200으로 올린다.
- `--pages=START-END`: 페이지 범위 지정 (1-indexed, 양 끝 포함).

### PDF-1.5. 챕터 단위 순차 분석 전략

PDF 분석은 **챕터(간지) 단위로 순차 처리**한다. 1개의 prd-analyst 에이전트가 담당 챕터의 페이지 이미지를 처음부터 끝까지 순서대로 읽어 분석한다.

에이전트당 안전 이미지 한도: 12~13페이지 (전체 + 크롭 이미지 합산 ~26장). 초과 시 13페이지씩 나누어 순차 분석 후 하나의 파일로 통합.

### PDF-2. 이미지 변환 전략 (DPI 선택)

| 변환 대상 | DPI | 명령 옵션 | 용도 |
|----------|-----|---------|------|
| 전체 페이지 | 150 | (기본) | UI 화면 파악, 화면 인벤토리, 플로우 추론 |
| Description 패널 크롭 | 200 | `--crop-desc` | Description 텍스트 정밀 판독 (최우선 분석 소스) |

스펙 페이지는 반드시 크롭 이미지를 먼저 읽어 Description을 추출한 뒤, 전체 이미지로 UI를 보완한다.

### PDF-3. 이미지 시각 분석

**분석 우선순위: Description 패널 > UI 화면**

Description 패널(`page_NNN_desc.png`)을 먼저 읽어 모든 항목을 추출한다. Description에 명시된 내용은 100% 케이스화 대상이다.

**스펙 페이지 분석 절차:**
1. 크롭 이미지(`page_NNN_desc.png`) → Description 항목 전수 추출 (계층 구조, 강조 태그 포함)
2. 전체 이미지(`page_NNN.png`) → UI 요소 중 Description 미포함 항목 보완
3. **UI ↔ Description 비교** — 불일치 시 `[UI↔DESC 불일치]` 태그로 명시

**챕터 내 공통 Description 감지:**
2개 이상 페이지에서 동일하거나 유사한 항목 발견 시 `[공통 DESC: 페이지ID 목록]` 태그. **공통 항목이라도 각 페이지 분석 결과에 모두 포함. 생략 금지.**

### PDF-4. 결과 저장

`_workspace/01_prd_analysis_ch{N}.md`에 저장. 메타정보에 챕터 제목, 담당 페이지 범위 포함.

## Figma API 경로

### 1. 파일 키 추출 및 메타정보 확인

```bash
python .claude/skills/prd-analyzer/scripts/figma_api.py file <FIGMA_URL> 1
```

### 2. 분석 범위 결정

- **소규모 파일** (페이지 ≤ 3, 프레임 ≤ 20): `get_file` 전체 가져오기
- **중대형 파일**: 페이지별 `depth=3~4` 또는 주요 프레임 ID만 `get_file_nodes`로 추출
- URL에 `?node-id=...`가 있으면 해당 노드 중심으로 분석

### 3. 기능 단위 추출

노드 트리를 추상화하여 사용자 행동 중심 기능 단위로 묶는다.

### 4. 비주얼 확인이 필요할 때만 이미지 export

```bash
python .claude/skills/prd-analyzer/scripts/figma_api.py images <FILE_KEY> <NODE_IDS> --format=png --scale=1
```

## 번들된 스크립트

- `.claude/skills/prd-analyzer/scripts/figma_api.py` — Figma REST API 클라이언트
- `.claude/skills/prd-analyzer/scripts/pdf_to_images.py` — PDF → PNG 변환

=====================================================================
파일 8: .claude/skills/sheet-operator/SKILL.md
=====================================================================

---
name: sheet-operator
description: Google Sheets 읽기·쓰기·메타데이터 조회·탭 추가 등 모든 구글 시트 조작을 수행. Google Sheets URL을 언급하거나 시트에서 데이터 읽기, 시트에 행 추가, 시트 양식 분석, 새 탭 생성이 필요할 때 반드시 이 스킬을 사용할 것. 서비스 계정 인증 기반.
---

# Sheet Operator

Google Sheets API v4를 서비스 계정 인증으로 호출하여 시트 읽기·쓰기·메타데이터 조회를 수행한다.

## 사전 조건

1. `GOOGLE_APPLICATION_CREDENTIALS` 환경변수가 서비스 계정 JSON 키 경로를 가리킴
2. 대상 시트를 서비스 계정 이메일과 **편집자 권한**으로 공유

권한 누락 시 API는 403을 반환한다.

## 작업 흐름

### 읽기

```bash
# 메타데이터 조회 (먼저 실행)
python .claude/skills/sheet-operator/scripts/sheets_api.py metadata <SHEET_URL>

# 범위 읽기
python .claude/skills/sheet-operator/scripts/sheets_api.py read <SHEET_URL> 'Sheet1!A1:Z20'
```

### 쓰기

```bash
# batch append (권장 — 여러 행을 한 번에)
python .claude/skills/sheet-operator/scripts/sheets_api.py append <SHEET_URL> 'Sheet1!A:Z' '[["TC-001","로그인","..."]]'

# 새 탭 추가
python .claude/skills/sheet-operator/scripts/sheets_api.py add_tab <SHEET_URL> '<탭이름>'
```

## 에러 핸들링

| HTTP | 원인 | 대응 |
|------|------|------|
| 403 | 서비스 계정 권한 없음 | 시트에 서비스 계정 이메일 편집자 추가 안내 |
| 404 | 시트 ID 잘못됨 | URL 재확인 요청 |
| 429 | API 호출 한도 초과 | 60초 대기 후 1회 재시도 |

## 하이브리드 인증 (새 시트 생성 시)

서비스 계정은 자체 Drive 저장 공간이 없어 새 파일을 만들 수 없다(`storageQuotaExceeded`). 새 시트 생성이 필요하면 `oauth_sheet.py`로 OAuth2 사용자 인증을 사용한다.

```bash
# 최초 인증 (브라우저 로그인)
python .claude/skills/sheet-operator/scripts/oauth_sheet.py auth

# 시트 생성 + 서비스 계정에 자동 공유
python .claude/skills/sheet-operator/scripts/oauth_sheet.py create "시트제목" <서비스계정이메일>
```

## 번들된 스크립트

- `.claude/skills/sheet-operator/scripts/sheets_api.py` — 서비스 계정 기반 읽기·쓰기
- `.claude/skills/sheet-operator/scripts/oauth_sheet.py` — OAuth2 기반 새 시트 생성

=====================================================================
파일 9: .claude/skills/testcase-generator/SKILL.md
=====================================================================

---
name: testcase-generator
description: Figma 기획서 분석 결과와 팀 시트 양식을 입력으로 받아 실제 테스트 케이스 항목을 도출. "테스트 케이스 만들어줘", "케이스 생성", "기획서 기반 TC 작성" 요청 시 반드시 이 스킬을 사용할 것. 정상·비정상·엣지 케이스의 균형, 양식 컨벤션 준수, ID 충돌 방지가 핵심.
---

# Testcase Generator

기획서 분석(`01_prd_analysis.md`)과 팀 양식 사양(`02_sheet_format.md`)을 입력으로, 팀이 그대로 사용할 수 있는 테스트 케이스 행 집합을 생성한다.

## 0. 생성 모드 선택 (atomic vs scenario)

| 모드 | 한 케이스 단위 | 적합한 상황 | 케이스 수 (4화면 기준) |
|------|--------------|----------|---------------------|
| **atomic** (팀 협업 권장) | 화면 내 단일 검증 (컬럼 1개, 클릭 1회, 표시 1건) | 회귀 추적, 팀 공동 작성 | 80~120개 |
| **scenario** (초안 작성 권장) | 사용자 행동 시나리오 (다단계) | 기획 초기 검토, 케이스 수 압축 | 30~50개 |

**모드 선택이 누락된 경우 기본값은 `atomic`**

### atomic 모드 핵심 규칙

1. 한 케이스 = 하나의 단일 검증. 절차 1~2 단계 이내.
2. 예상 결과 1~3 줄. 다항목 검증이면 케이스 분리.
3. 화면 진입 후 컬럼별 표시는 각 컬럼당 1개 케이스로 분해.
4. 호버·툴팁·정렬·페이지네이션도 각 동작당 별도 케이스.

## 케이스 도출 원칙

### 0-A. Description 100% 커버리지 (최우선)

`01_prd_analysis.md`에 기록된 Description 항목은 **전부** 케이스화한다. 누락 금지.
- Description 항목 번호(❶-1-a 등) → 케이스 비고에 `[DESC ❶-1-a]` 출처 표시
- `[강조]` 태그 항목 → 특히 빠짐없이 케이스화

### 0-B. 화면 ID 컬럼 = Page ID

화면 ID 컬럼에는 기획서 스펙 페이지 우측 상단의 **Page ID** 값을 기입 (예: `ADM-TCK-0100-02`).

### 0-C. 사전조건 명시 의무

동일 화면에서 상황별로 다른 UI/동작이 있을 때 케이스마다 사전조건 명확히 구분.
- 특정 버튼 클릭 후 나타나는 UI 상태
- 특정 데이터 존재/부재 상태
- 권한·역할에 따른 화면 분기

### 0-D. 공통 Description 항목 독립 TC 의무화

`[공통 DESC]` 태그 항목은 **해당 페이지(화면 ID)마다 독립적으로 TC를 작성**한다. 생략 금지.

### 0-E. UI ↔ Description 불일치 항목 확인사항 자동 추가

`[UI↔DESC 불일치]` 항목 → TC 비고에 반드시 기재:
`[기획 확인] UI: {UI 내용} / DESC: {Description 내용} — 어느 쪽이 맞는지 확인 필요`

### 0-G. 오탈자 검수 (케이스 작성 후 필수)

1. 기획서 용어와 케이스 용어 일치 여부
2. 상태 enum 값 정확성 (기획서에 없는 상태값 사용 금지)
3. 숫자·단위 정확성 (Description 기준 우선)
4. 메시지 코드 정확성

## 1. 기능 단위마다 분류별 케이스 작성

| 분류 | 목적 | atomic 모드 (화면당) |
|------|------|------------------|
| **표시 형식 검증** | 컬럼별 노출, enum, 빈 값 표시, 일시 형식 | 8~15개 |
| **인터랙션 검증** | 버튼 클릭→이동, 호버, 정렬, 페이지네이션 | 5~10개 |
| **정상 흐름** | 정상 입력으로 의도한 결과 | 2~4개 |
| **비정상 흐름** | 잘못된 입력, 오류 처리, 권한 문제 | 3~6개 |
| **엣지 케이스** | 경계값, 조건부 분기, 자동 처리 | 2~4개 |
| **부수적 (취소/비활성)** | 취소 동작, 비활성화 상태, 권한 없음 | 3~5개 |

### 1-A. 표시 형식 검증 자동 도출 (atomic 모드 필수)

| 표시 항목 | 자동 도출 케이스 |
|----------|--------------|
| 테이블 컬럼 | 컬럼 순서·이름 확인 / 정렬 동작 / 빈 값(`-`) 표시 |
| 상태값 enum | 각 상태 노출 형식 / 호버 시 enum 툴팁 |
| 일시 표시 | `yyyy-mm-dd hh:mm:ss` 형식 확인 / 값 없을 때 `No data (-)` |
| 액션 버튼 | 클릭 → 이동/동작 / 모달 표출 / 모달 취소(P4) / 모달 진행 |

## 우선순위 결정 기준

### P1/P2/P3/P4 enum이 정의된 양식 (atomic 모드 권장)

| 우선순위 | 적용 케이스 |
|---------|-----------|
| **P1** | 핵심 액션 버튼 클릭 → 다음 화면 이동 / 기능 동작 트리거 |
| **P2** | 다이얼로그 진행, 비즈니스 임팩트 큰 비정상 |
| **P3** | UI 표시 검증, 컬럼별 노출, enum 표출, 일시 형식 |
| **P4** | 취소 동작, 비활성화 상태, 권한 없음 닫기, 부수 모달 |

> **중요**: P1은 매우 보수적. "이 검증이 깨지면 다음 화면으로 갈 수 없는가?" 기준.

## 출력 형식

`_workspace/03_testcases_ch{N}.md`:

```
# 생성된 테스트 케이스

## 메타정보 (대상 시트, 탭, 케이스 수, ID 범위, 생성 일시)
## 케이스 요약 (분류별)
## 기능별 매핑
## 케이스 전문 (양식 컬럼 순서대로)
## 기획 확인 필요 항목
```

=====================================================================
파일 10: .claude/skills/testcase-reviewer/SKILL.md
=====================================================================

---
name: testcase-reviewer
description: 작성된 테스트 케이스를 기획서·양식·시트 세 기준으로 교차 검증하는 QA 스킬. "테스트 케이스 리뷰", "케이스 검토", "TC 품질 점검" 요청 시 반드시 이 스킬을 사용할 것. 단순 존재 확인이 아닌 경계면 교차 비교가 핵심.
---

# Testcase Reviewer

`testcase-writer`가 작성한 케이스를 세 가지 경계면에서 교차 검증한다.

## 핵심 원칙 — 경계면 교차 비교

| 경계면 | 비교 대상 | 검증 질문 |
|--------|----------|----------|
| **기획 ↔ 케이스** | `01_prd_analysis.md` ↔ `03_testcases.md` | 모든 기능 단위가 커버됐는가? |
| **양식 ↔ 케이스** | `02_sheet_format.md` ↔ `03_testcases.md` | 컬럼 순서·enum 값·ID 체계가 일치하는가? |
| **로컬 ↔ 시트** | `03_testcases.md` ↔ 실제 시트 내용 | 작성된 행과 로컬 산출물이 동일한가? |

## 작업 흐름

### 1. 입력 자료 로드

`01_prd_analysis_ch{N}.md`, `02_sheet_format.md`, `03_testcases_ch{N}.md`, 실제 시트 내용 모두 읽기.

### 2. 기능 커버리지 매트릭스 생성

| 기능 단위 | 작성 케이스 수 | 정상 | 비정상 | 엣지 | 충분성 평가 |

평가 기준:
- **Critical**: 정상 흐름이 0개거나 핵심 기능에 비정상 없음
- **Major**: 엣지 케이스가 전혀 없는 핵심 기능
- **OK**: 정상·비정상이 균형 있게 존재

### 3. 양식 준수 점검

각 케이스 행에 대해: 컬럼 수, enum 값, ID 규칙, 필수 컬럼 누락 확인.

### 4. 시트-로컬 일치성 점검

작성된 행 범위를 읽어 `03_testcases.md`와 비교: 행 수, 샘플 5개 행 셀 내용.

### 5. 공통 Description 항목 누락 점검

`[공통 DESC]` 태그 항목이 태그에 명시된 **모든 페이지**에 TC가 작성됐는지 확인. 누락 시 Critical.

### 5-1. UI ↔ Description 불일치 반영 점검

`[UI↔DESC 불일치]` 항목이 TC 비고 컬럼에 기재됐는지 확인. 누락 시 Major.

### 6. 케이스 품질 점검

검증 목표 다중, 측정 불가, 단계 모호, 사전조건 누락 등 안티 패턴 식별.

## 권고 분류

| 권고 | 의미 | 후속 조치 |
|------|------|----------|
| **Critical** | 양식 위반, 핵심 기능 누락, 시트-로컬 불일치 | `testcase-writer` 재호출 |
| **Major** | 엣지 케이스 부족, 추측 기반 케이스 다수 | 사용자에게 결정 위임 |
| **Minor** | 표현 개선, 우선순위 재조정 제안 | 정보 제공만 |

## 작업 원칙

1. **임의로 수정하지 않는다.** 발견한 문제를 보고하고 `testcase-writer`가 수정.
2. **구체적으로 지적한다.** TC-ID, 컬럼명, 발견값, 기준값 명시.
3. **재검토 시 개선 평가.** 이전 보고서와 비교하여 해결/잔존 이슈 명시.

=====================================================================
파일 11: .claude/skills/prd-analyzer/scripts/pdf_to_images.py
=====================================================================

"""PDF를 페이지별 PNG 이미지로 변환.

의존성: pymupdf (pip install pymupdf)

CLI 사용:
  python pdf_to_images.py <pdf_path> [--dpi=150] [--output-dir=<dir>] [--pages=START-END]
  python pdf_to_images.py <pdf_path> --crop-desc [--dpi=200] [--output-dir=<dir>] [--pages=START-END]

  --crop-desc: Description 패널 영역(x 53%~100%)만 크롭하여 저장.
  --pages=START-END: 변환할 페이지 범위 (1-indexed, 양 끝 포함).
"""

from __future__ import annotations

import os
import sys

_DESC_X_RATIO = 0.53


def convert_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    pages: tuple[int, int] | None = None,
) -> list[str]:
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. 다음 명령 실행 후 재시도하세요:\n"
            "  pip install pymupdf"
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    for i in range(start_idx, end_idx):
        pix = doc[i].get_pixmap(matrix=matrix)
        out_path = os.path.join(output_dir, f"page_{i + 1:03d}.png")
        pix.save(out_path)
        paths.append(out_path)

    doc.close()
    return paths


def crop_description_panels(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    pages: tuple[int, int] | None = None,
) -> list[str]:
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. pip install pymupdf 실행 후 재시도하세요."
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    for i in range(start_idx, end_idx):
        page = doc[i]
        rect = page.rect
        x_start = rect.width * _DESC_X_RATIO
        clip = fitz.Rect(x_start, 0, rect.width, rect.height)
        pix = page.get_pixmap(matrix=matrix, clip=clip)
        out_path = os.path.join(output_dir, f"page_{i + 1:03d}_desc.png")
        pix.save(out_path)
        paths.append(out_path)

    doc.close()
    return paths


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    pdf_path = argv[1]
    dpi = None
    output_dir: str | None = None
    crop_desc = False
    pages: tuple[int, int] | None = None

    for arg in argv[2:]:
        if arg.startswith("--dpi="):
            dpi = int(arg.split("=", 1)[1])
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg == "--crop-desc":
            crop_desc = True
        elif arg.startswith("--pages="):
            raw = arg.split("=", 1)[1]
            parts = raw.split("-")
            if len(parts) != 2:
                print(f"오류: --pages 형식은 START-END여야 합니다. 예: --pages=1-13", file=sys.stderr)
                return 1
            pages = (int(parts[0]), int(parts[1]))

    base = os.path.splitext(os.path.basename(pdf_path))[0]

    try:
        if crop_desc:
            if dpi is None:
                dpi = 200
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", f"{base}_desc")
            paths = crop_description_panels(pdf_path, output_dir, dpi, pages=pages)
        else:
            if dpi is None:
                dpi = 150
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", base)
            paths = convert_pdf(pdf_path, output_dir, dpi, pages=pages)

        for p in paths:
            print(p)
        page_range = f" (p{pages[0]}~{pages[1]})" if pages else ""
        mode = "Description 크롭" if crop_desc else "전체 페이지"
        print(f"\n총 {len(paths)}페이지{page_range} {mode} 변환 완료 → {output_dir}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

=====================================================================
파일 12: .claude/skills/prd-analyzer/scripts/figma_api.py
=====================================================================

"""Figma REST API 헬퍼.

환경변수 FIGMA_ACCESS_TOKEN 필요.

CLI 사용:
  python figma_api.py file <file_key_or_url>
  python figma_api.py nodes <file_key_or_url> <node_id1,node_id2>
  python figma_api.py images <file_key_or_url> <node_id1,node_id2> [--format=png|svg|jpg|pdf] [--scale=1]
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.figma.com/v1"


class FigmaError(Exception):
    pass


class FigmaClient:
    def __init__(self, token: str | None = None):
        token = token or os.environ.get("FIGMA_ACCESS_TOKEN")
        if not token:
            raise FigmaError(
                "FIGMA_ACCESS_TOKEN 환경변수가 설정되지 않았습니다. "
                ".claude/settings.json의 env에 토큰을 추가하세요."
            )
        self.token = token

    @staticmethod
    def extract_file_key(url_or_key: str) -> str:
        m = re.search(r"figma\.com/(?:file|design|proto)/([A-Za-z0-9]+)", url_or_key)
        if m:
            return m.group(1)
        if re.fullmatch(r"[A-Za-z0-9]+", url_or_key):
            return url_or_key
        raise FigmaError(f"Figma URL이나 file key 형식이 아닙니다: {url_or_key}")

    @staticmethod
    def extract_node_ids_from_url(url: str) -> list[str]:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        node_ids = qs.get("node-id", [])
        return [nid.replace("-", ":") for nid in node_ids]

    def _request(self, path: str, params: dict | None = None) -> dict:
        url = f"{API_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-Figma-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise FigmaError(f"Figma API HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise FigmaError(f"Figma API 네트워크 오류: {e}") from e

    def get_me(self) -> dict:
        return self._request("/me")

    def get_file(self, file_key: str, depth: int | None = None) -> dict:
        params = {}
        if depth is not None:
            params["depth"] = depth
        return self._request(f"/files/{file_key}", params=params or None)

    def get_file_nodes(self, file_key: str, node_ids: list[str]) -> dict:
        params = {"ids": ",".join(node_ids)}
        return self._request(f"/files/{file_key}/nodes", params=params)

    def get_images(
        self,
        file_key: str,
        node_ids: list[str],
        format: str = "png",
        scale: float = 1.0,
    ) -> dict:
        params = {
            "ids": ",".join(node_ids),
            "format": format,
            "scale": scale,
        }
        return self._request(f"/images/{file_key}", params=params)

    def get_comments(self, file_key: str) -> dict:
        return self._request(f"/files/{file_key}/comments")


def summarize_node(node: dict, max_depth: int = 3, _depth: int = 0) -> dict:
    out = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
    }
    if node.get("type") == "TEXT" and "characters" in node:
        out["text"] = node["characters"]
    if node.get("componentId"):
        out["componentId"] = node["componentId"]
    children = node.get("children", [])
    if children and _depth < max_depth:
        out["children"] = [summarize_node(c, max_depth, _depth + 1) for c in children]
    elif children:
        out["children_count"] = len(children)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    client = FigmaClient()
    if cmd == "me":
        print(json.dumps(client.get_me(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "file":
        key = client.extract_file_key(argv[2])
        depth = int(argv[3]) if len(argv) > 3 else None
        data = client.get_file(key, depth=depth)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if cmd == "nodes":
        key = client.extract_file_key(argv[2])
        ids = argv[3].split(",")
        data = client.get_file_nodes(key, ids)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if cmd == "images":
        key = client.extract_file_key(argv[2])
        ids = argv[3].split(",")
        fmt = "png"
        scale = 1.0
        for arg in argv[4:]:
            if arg.startswith("--format="):
                fmt = arg.split("=", 1)[1]
            elif arg.startswith("--scale="):
                scale = float(arg.split("=", 1)[1])
        data = client.get_images(key, ids, format=fmt, scale=scale)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

=====================================================================
파일 13: .claude/skills/sheet-operator/scripts/sheets_api.py
=====================================================================

"""Google Sheets API 헬퍼 (서비스 계정 인증).

환경변수 GOOGLE_APPLICATION_CREDENTIALS 필요 (서비스 계정 JSON 키 경로).

CLI 사용:
  python sheets_api.py read <url_or_id> <range>
  python sheets_api.py metadata <url_or_id>
  python sheets_api.py append <url_or_id> <range> <json>
  python sheets_api.py write <url_or_id> <range> <json>
  python sheets_api.py add_tab <url_or_id> <tab_title>
"""

from __future__ import annotations

import json
import os
import re
import sys

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "필수 라이브러리가 없습니다. 설치:\n"
        "  pip install google-auth google-auth-httplib2 google-api-python-client",
        file=sys.stderr,
    )
    raise


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class SheetsError(Exception):
    pass


class SheetsClient:
    def __init__(self, key_path: str | None = None):
        key_path = key_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not key_path or not os.path.exists(key_path):
            raise SheetsError(
                "GOOGLE_APPLICATION_CREDENTIALS 환경변수가 유효한 JSON 키 경로를 가리키지 않습니다."
            )
        self.creds = service_account.Credentials.from_service_account_file(
            key_path, scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=self.creds, cache_discovery=False)
        self.drive = build("drive", "v3", credentials=self.creds, cache_discovery=False)

    @staticmethod
    def extract_id(url_or_id: str) -> str:
        m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url_or_id)
        if m:
            return m.group(1)
        if re.fullmatch(r"[A-Za-z0-9_-]+", url_or_id):
            return url_or_id
        raise SheetsError(f"Google Sheets URL 또는 ID 형식이 아닙니다: {url_or_id}")

    def get_metadata(self, sheet_id: str) -> dict:
        try:
            data = self.service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        sheets = []
        for s in data.get("sheets", []):
            prop = s["properties"]
            sheets.append(
                {
                    "title": prop.get("title"),
                    "sheetId": prop.get("sheetId"),
                    "rows": prop.get("gridProperties", {}).get("rowCount"),
                    "cols": prop.get("gridProperties", {}).get("columnCount"),
                }
            )
        return {
            "title": data.get("properties", {}).get("title"),
            "sheets": sheets,
        }

    def read(self, sheet_id: str, range_a1: str) -> list[list]:
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range_a1)
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res.get("values", [])

    def write(self, sheet_id: str, range_a1: str, values: list[list]) -> dict:
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=sheet_id,
                    range=range_a1,
                    valueInputOption="USER_ENTERED",
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def append(self, sheet_id: str, range_a1: str, values: list[list]) -> dict:
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=sheet_id,
                    range=range_a1,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def add_tab(self, sheet_id: str, title: str) -> dict:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        try:
            res = (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=sheet_id, body=body)
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    @staticmethod
    def _format_http_error(e: HttpError) -> str:
        status = e.resp.status if hasattr(e, "resp") else "?"
        try:
            content = json.loads(e.content.decode("utf-8"))
            msg = content.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        hints = {
            403: " (서비스 계정에 시트 편집자 권한이 부여됐는지 확인)",
            404: " (시트 ID/URL이 올바른지 확인)",
            429: " (API 호출 한도 초과 — 잠시 후 재시도)",
        }
        return f"Sheets API HTTP {status}: {msg}{hints.get(status, '')}"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    c = SheetsClient()
    if cmd == "metadata":
        sid = c.extract_id(argv[2])
        print(json.dumps(c.get_metadata(sid), ensure_ascii=False, indent=2))
        return 0
    if cmd == "read":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        rows = c.read(sid, rng)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if cmd == "write":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        values = json.loads(argv[4])
        print(json.dumps(c.write(sid, rng, values), ensure_ascii=False, indent=2))
        return 0
    if cmd == "append":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        values = json.loads(argv[4])
        print(json.dumps(c.append(sid, rng, values), ensure_ascii=False, indent=2))
        return 0
    if cmd == "add_tab":
        sid = c.extract_id(argv[2])
        title = argv[3]
        print(json.dumps(c.add_tab(sid, title), ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

=====================================================================
파일 14: .claude/skills/sheet-operator/scripts/oauth_sheet.py
=====================================================================

"""OAuth2 기반 스프레드시트 생성 헬퍼.

서비스 계정은 자체 Drive 저장 공간이 없어 새 파일을 만들 수 없다.
이 스크립트는 사용자 OAuth2 인증으로 시트를 생성한 뒤,
반복 작업을 담당할 서비스 계정에 자동으로 공유한다.

전제 조건:
- .credentials/oauth_client.json (Google Cloud에서 다운로드)
- 최초 1회 인증 후 .credentials/oauth_token.json 자동 생성

CLI 사용:
  python oauth_sheet.py auth                    # 최초 인증 (브라우저 로그인)
  python oauth_sheet.py create <title> [<share_with_email>]
"""

from __future__ import annotations

import json
import os
import sys

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "필수 라이브러리가 없습니다. 설치:\n"
        "  pip install google-auth-oauthlib google-api-python-client",
        file=sys.stderr,
    )
    raise

# 이 스크립트는 .claude/skills/sheet-operator/scripts/ 에 위치
# 5단계 위로 올라가면 프로젝트 루트
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))))

CLIENT_SECRET_PATH = os.path.join(PROJECT_ROOT, ".credentials", "oauth_client.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, ".credentials", "oauth_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _load_or_authenticate() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise FileNotFoundError(
            f"OAuth 클라이언트 시크릿 파일이 없습니다: {CLIENT_SECRET_PATH}\n"
            "Google Cloud Console에서 OAuth 클라이언트 ID(데스크톱 앱)를 만들고 "
            "JSON을 다운받아 위 경로에 저장하세요."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def authenticate() -> str:
    creds = _load_or_authenticate()
    service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    info = service.userinfo().get().execute()
    return info.get("email", "(unknown)")


def create_spreadsheet(title: str, share_with: str | None = None) -> dict:
    creds = _load_or_authenticate()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    try:
        res = sheets.spreadsheets().create(body={"properties": {"title": title}}).execute()
    except HttpError as e:
        raise RuntimeError(f"스프레드시트 생성 실패: {e}") from e

    sid = res["spreadsheetId"]
    url = res["spreadsheetUrl"]
    shared = []

    if share_with:
        try:
            drive.permissions().create(
                fileId=sid,
                body={"type": "user", "role": "writer", "emailAddress": share_with},
                sendNotificationEmail=False,
                fields="id,role,emailAddress",
            ).execute()
            shared.append({"email": share_with, "role": "writer"})
        except HttpError as e:
            print(f"공유 실패({share_with}): {e}", file=sys.stderr)

    return {
        "spreadsheetId": sid,
        "spreadsheetUrl": url,
        "shared_with": shared,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "auth":
        email = authenticate()
        print(f"인증 완료: {email}")
        print(f"토큰 저장: {TOKEN_PATH}")
        return 0
    if cmd == "create":
        if len(argv) < 3:
            print("사용: oauth_sheet.py create <title> [<share_with_email>]")
            return 1
        title = argv[2]
        share_with = argv[3] if len(argv) > 3 else None
        result = create_spreadsheet(title, share_with=share_with)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

=====================================================================
파일 15: CLAUDE.md
=====================================================================

# testcase-auto

## 하네스: 테스트 케이스 자동 생성

**목표:** 기획서(PRD)를 분석하여 팀 양식에 맞는 테스트 케이스를 자동 생성하고 구글 시트에 작성·리뷰한다.

**트리거:** 테스트 케이스 자동 생성·기획서 분석·시트 작성 관련 요청 시 `testcase-auto` 스킬을 사용하라. 기획서(Figma URL 또는 PDF)와 구글 시트 URL이 등장하는 케이스 생성 요청도 동일. 단순 질문(스킬 의미, 환경 설정 방법 등)은 직접 응답 가능.

**환경:**
- `FIGMA_ACCESS_TOKEN` — Figma 토큰 (`.claude/settings.json`의 env)
- `GOOGLE_APPLICATION_CREDENTIALS` — 서비스 계정 JSON 키 경로
- 서비스 계정 이메일: `.claude/settings.json`의 `GOOGLE_SERVICE_ACCOUNT_EMAIL` 참조
- 대상 구글 시트는 사전에 위 이메일로 편집자 공유 필요

**변경 이력:**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| (최초 구성일) | 초기 구성 | 에이전트 4개, 스킬 5개, 오케스트레이터 1개 | 기획서(PRD)→테스트 케이스 자동화 도입 |

=====================================================================
[생성 완료 후 확인 사항]
=====================================================================

모든 파일 생성이 완료되면 다음을 확인해줘:

1. .claude/settings.json — env 값 3개(FIGMA_ACCESS_TOKEN, GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_SERVICE_ACCOUNT_EMAIL) 채워져 있는가
2. .claude/agents/ — prd-analyst.md, sheet-analyst.md, testcase-writer.md, testcase-reviewer.md 4개 존재하는가
3. .claude/skills/ — testcase-auto, prd-analyzer, sheet-operator, testcase-generator, testcase-reviewer 디렉토리 5개 각각에 SKILL.md 존재하는가
4. .claude/skills/prd-analyzer/scripts/ — pdf_to_images.py, figma_api.py 존재하는가
5. .claude/skills/sheet-operator/scripts/ — sheets_api.py, oauth_sheet.py 존재하는가
6. CLAUDE.md — 프로젝트 루트에 존재하는가

확인 후 트리 구조(tree .claude)로 출력해줘.
```

---

## 셋업 후 사전 준비 체크리스트

| 항목 | 방법 |
|------|------|
| Python 패키지 설치 | `pip install pymupdf google-auth google-auth-httplib2 google-api-python-client google-auth-oauthlib` |
| Figma 토큰 발급 | Figma → Settings → Personal access tokens |
| GCP 서비스 계정 생성 | Google Cloud Console → IAM → 서비스 계정 → JSON 키 발급 |
| GCP API 활성화 | Google Sheets API, Google Drive API 활성화 |
| settings.json 값 교체 | FIGMA_ACCESS_TOKEN, GOOGLE_APPLICATION_CREDENTIALS (절대경로), GOOGLE_SERVICE_ACCOUNT_EMAIL |
| OAuth 클라이언트 설정 (새 시트 생성 시 필요) | GCP → OAuth 2.0 클라이언트 ID (데스크톱 앱) → JSON 다운로드 → `.credentials/oauth_client.json` 저장 |
| OAuth 최초 인증 (새 시트 생성 시 필요) | `python .claude/skills/sheet-operator/scripts/oauth_sheet.py auth` |

새 시트 생성이 필요한 경우:
```bash
python .claude/skills/sheet-operator/scripts/oauth_sheet.py create "시트제목" <서비스계정이메일>
```

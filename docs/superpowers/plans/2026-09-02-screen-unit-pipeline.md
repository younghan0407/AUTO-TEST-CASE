# 처리 단위 재편 (챕터 → 화면 ID 1개) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하네스의 분석·생성·작성·리뷰 단위를 챕터(간지)에서 화면 ID(`Screen ID` / `Page ID`) 1개로 바꾸고, 화면 하나를 시트 작성까지 끝낸 뒤 다음 화면으로 넘어가게 한다.

**Architecture:** 이 저장소에는 실행 코드가 거의 없다. 하네스는 **스킬 문서(`.claude/skills/*/SKILL.md`) · 에이전트 정의(`.claude/agents/*.md`) · 양식 사양(`.claude/formats/*.md`)** 으로 이루어진 프롬프트 시스템이고, 파이프라인은 오케스트레이터 스킬이 서술한 절차를 Claude가 따라 실행한다. 따라서 이 계획의 "구현"은 문서 편집이며, "테스트"는 **금지 패턴 부재 / 필수 패턴 존재를 검사하는 grep 검사기**다. 검사기(`scripts/verify_unit_migration.sh`)를 Task 1에서 먼저 만들어 전면 FAIL을 확인하고, 이후 각 태스크가 자기 구역의 검사를 통과시킨다.

**Tech Stack:** Markdown, bash + grep (검사기), git

**Spec:** `docs/superpowers/specs/2026-09-02-screen-unit-pipeline-design.md`

## Global Constraints

스펙 §8 「유지되는 것」이 전 태스크의 요구사항에 암묵적으로 포함된다. 아래를 훼손하는 편집은 회귀다.

- Phase 0 기본 정보 5개 수집 게이트 · 추정 금지 · 확정값 표 되보여주기 — 그대로 유지
- **변경 표시색은 묻지 않는다** (스크립트 실측 우선). 이 규칙 문장을 삭제하지 않는다
- 양식 로드 = `common.md` + 제품 프로파일 **두 파일 함께**. "한쪽만 읽으면 규칙의 절반이 없다" 문장 유지
- 전 제품 **23컬럼 A~W** / `관리대상` 컬럼 폐지 상태 유지
- 스킬·에이전트에서는 **열 문자를 쓰지 않고 컬럼명(`비고`·`피드백`)으로 지칭**한다. 새로 쓰는 문장도 이 규칙을 따른다
- **취소선 = 삭제** 독립 정의 + **삭제 내용의 정상 동작 케이스 금지**(Critical) 유지
- 취소선 검출 **0건 페이지도 DESC 전문 육안 재판독** 의무 유지
- **색 박스 = 범위 후보(확정력 없음)** / DESC 색 텍스트·취소선·스티커·`ChangeLog` = 항목 확정. `[변경 범위 불명]` 처리와 신규 화면 전수의 역방향 오판 금지 유지
- **C-ID 정의 일치 판정 근거는 기획서의 상호 참조뿐** (사양 v1.8). 일자·회차·내용이 같아도 상호 참조가 없으면 연결하지 않는다
- 정책 예외 양방향 점검 · `[정책 예외]` 피드백 기재 유지
- 이미지 판독 품질 게이트 · 사용자 통보 의무 · 판독 불가 페이지 추측 금지 유지
- 탭명은 `metadata` 의 `title` 원문 사용 (NFD/NFC 함정) 유지
- `sheets_api.py` CLI 하위 명령은 **`metadata`·`read`·`write`·`append`·`add_tab` 5개뿐**이다. 새 예시를 쓸 때 `get_metadata` 를 셸 명령으로 쓰지 않는다
- **`챕터` 라는 단어 자체를 일괄 치환하지 않는다.** 아래 세 용법은 정당하게 남는다 — ⓐ `CLAUDE.md` 변경 이력 테이블의 과거 기록 ⓑ `common.md` 「탭 분할 기준 = 기능 챕터 / 모듈 / 변경분 단위」 ⓒ 새 인덱스의 「소속 간지」 라벨 설명. 금지 대상은 **처리 단위로서의 챕터**다

---

## File Structure

| 파일 | 책임 | 태스크 |
|------|------|-------|
| `scripts/verify_unit_migration.sh` | **신규.** 처리 단위 재편의 금지/필수 패턴 검사기. 영구 회귀 가드 | 1 |
| `.claude/formats/common.md` | 권위 사양 — CH-ID 네임스페이스, C-ID 배정 절차 | 1 |
| `.claude/skills/testcase-auto/SKILL.md` | 오케스트레이터 — Phase 1 사전 스캔, 화면 루프, Phase 5 집계 | 2·3·4 |
| `.claude/skills/prd-analyzer/SKILL.md` | 분석 절차 — 화면 단위 전략, C-ID 발급 요청 | 5 |
| `.claude/agents/prd-analyst.md` | 분석 담당 입·출력 프로토콜 | 5 |
| `.claude/skills/testcase-generator/SKILL.md` | 생성 절차 — CH-ID, 산출물 경로, 분포 대조 시점 | 6 |
| `.claude/agents/testcase-writer.md` | 작성 담당 — 첫 화면 게이트, 비고 태그 | 6 |
| `.claude/skills/testcase-reviewer/SKILL.md` | 리뷰 절차 — 화면 리뷰 / 전체 집계 리뷰 분리 | 7 |
| `.claude/agents/testcase-reviewer.md` | 리뷰 담당 프로토콜 | 7 |
| `.claude/agents/sheet-analyst.md` | 모드 A 꼬리 읽기에 **기존 CH-ID 최대 `NN` 실측** 추가 | 8 |
| `.claude/skills/sheet-operator/SKILL.md` | 예시 문자열 | 8 |
| `README.md` · `HARNESS_OVERVIEW.md` · `HARNESS_WORKFLOW.md` · `docs/PROMPTS.md` | 사용자 문서 | 9 |
| `CLAUDE.md` | 변경 이력 기록 | 9 |

**계획 중 발견한 스펙 보완 1건** — 스펙의 화면 인덱스 템플릿에는 CH-ID 접두를 담는 칸이 없다. 기존 탭 충돌 회피로 CH-ID 번호가 인덱스 순번과 오프셋만큼 어긋날 수 있으므로(기존 최대가 `CH04` 면 첫 화면이 `CH05`), 인덱스에 **`CH-ID 접두` 컬럼을 추가**한다. 오프셋 산술이 여러 문서에 흩어지는 것을 막는다. Task 1 Step 7에서 스펙도 함께 고친다.

---

### Task 1: 검사기 + 양식 사양 (`common.md`)

권위 사양을 먼저 고친다. 다른 모든 파일이 이 파일의 CH-ID·C-ID 규칙을 참조하므로, 순서를 뒤집으면 참조가 존재하지 않는 규칙을 가리킨다.

**Files:**
- Create: `scripts/verify_unit_migration.sh`
- Modify: `.claude/formats/common.md` (「CH-ID 네임스페이스」 절 = 317-320행, C-ID 「규칙」 목록 = 298-306행)
- Modify: `docs/superpowers/specs/2026-09-02-screen-unit-pipeline-design.md` (§5 인덱스 템플릿)

**Interfaces:**
- Produces: `scripts/verify_unit_migration.sh` — 인자 없이 실행, 통과 시 exit 0 / 위반 시 exit 1. 이후 모든 태스크의 검증 명령이 이 스크립트다
- Produces: 사양 용어 `CH{NN}-N` (`NN` = 화면 인덱스 순번), `_workspace/00_cid_register.md`, `_workspace/00_screen_index.md`, 산출물 접미사 `_s{NN}`. 후속 태스크는 이 표기를 그대로 쓴다

- [ ] **Step 1: 검사기를 작성한다**

`scripts/verify_unit_migration.sh`:

```bash
#!/usr/bin/env bash
# 처리 단위 재편(챕터 → 화면 ID 1개, 2026-09-02) 이후 잔존 참조 검사기.
#
# 금지 대상은 "처리 단위로서의 챕터"다. 아래 용법은 정당하므로 검사 대상에서 뺀다.
#   - CLAUDE.md 변경 이력 테이블의 과거 기록
#   - common.md 「탭 분할 기준 = 기능 챕터 / 모듈 / 변경분 단위」
#   - 화면 인덱스의 「소속 간지」 라벨
set -u
cd "$(dirname "$0")/.." || exit 1

SKILLS=(.claude/skills/testcase-auto/SKILL.md
        .claude/skills/prd-analyzer/SKILL.md
        .claude/skills/testcase-generator/SKILL.md
        .claude/skills/testcase-reviewer/SKILL.md
        .claude/skills/sheet-operator/SKILL.md)
AGENTS=(.claude/agents/prd-analyst.md
        .claude/agents/testcase-writer.md
        .claude/agents/testcase-reviewer.md
        .claude/agents/sheet-analyst.md)
FORMATS=(.claude/formats/common.md)
DOCS=(README.md HARNESS_OVERVIEW.md HARNESS_WORKFLOW.md docs/PROMPTS.md)
CORE=("${SKILLS[@]}" "${AGENTS[@]}" "${FORMATS[@]}")

fail=0

absent() { # $1=라벨 $2=ERE 패턴 $3..=파일
  local label="$1" pat="$2"; shift 2
  local hits
  hits=$(grep -nE "$pat" "$@" 2>/dev/null)
  if [ -n "$hits" ]; then
    printf 'FAIL  %s\n' "$label"
    printf '%s\n' "$hits" | sed 's/^/        /'
    fail=1
  else
    printf 'ok    %s\n' "$label"
  fi
}

present() { # $1=라벨 $2=ERE 패턴 $3..=파일
  local label="$1" pat="$2"; shift 2
  local f missing=""
  for f in "$@"; do
    grep -qE "$pat" "$f" 2>/dev/null || missing="$missing $f"
  done
  if [ -n "$missing" ]; then
    printf 'FAIL  %s — 패턴 없음:%s\n' "$label" "$missing"
    fail=1
  else
    printf 'ok    %s\n' "$label"
  fi
}

echo "── 금지: 챕터 처리 단위 잔존 ──────────────────────────────"
absent "산출물 접미사 _ch{N}"        '_ch\{N\}'                "${CORE[@]}" "${DOCS[@]}"
absent "00_chapters.md 참조"          '00_chapters'             "${CORE[@]}" "${DOCS[@]}"
absent "red_regions/ch{N} 경로"       'red_regions/ch'          "${CORE[@]}" "${DOCS[@]}"
absent "CH{챕터2자리} 표기"           'CH\{챕터2자리\}'          "${CORE[@]}" "${DOCS[@]}"
absent "챕터 루프"                    '챕터 루프'                "${CORE[@]}" "${DOCS[@]}"
absent "간지 감지"                    '간지 감지'                "${CORE[@]}" "${DOCS[@]}"
absent "챕터 단위 순차"               '챕터.{0,2}단위.{0,2}순차'  "${CORE[@]}" "${DOCS[@]}"
absent "챕터 분석/챕터별 산출물"      '챕터 분석|챕터별'          "${CORE[@]}"
absent "첫 챕터 게이트"               '첫 (번째 )?챕터'          "${CORE[@]}" "${DOCS[@]}"

echo "── 필수: 화면 단위 구조 ───────────────────────────────────"
present "화면 인덱스 파일"  '00_screen_index'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/agents/prd-analyst.md
present "C-ID 레지스터"     '00_cid_register'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/agents/prd-analyst.md \
                                               .claude/formats/common.md
present "산출물 접미사 _s{NN}" '_s\{NN\}'      .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/skills/testcase-generator/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "CH-ID = CH{NN}-N, NN=화면 순번" 'CH\{NN\}-N' .claude/formats/common.md \
                                               .claude/skills/testcase-generator/SKILL.md
present "CH-ID 충돌 방지 절"  'CH-ID 충돌 방지' .claude/formats/common.md \
                                               .claude/agents/sheet-analyst.md
present "전체 집계 리뷰"      '전체 집계 리뷰'   .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "첫 화면 검토 게이트" '첫 화면'          .claude/skills/testcase-auto/SKILL.md \
                                               .claude/agents/testcase-writer.md

echo "── 회귀 가드: 유지돼야 하는 규칙 (스펙 §8) ────────────────"
present "변경 표시색 묻지 않음"  '변경 표시색'   .claude/skills/testcase-auto/SKILL.md
present "취소선=삭제 정상케이스 금지" '정상 동작|정상 케이스' .claude/formats/common.md \
                                               .claude/skills/testcase-generator/SKILL.md
present "취소선 0건도 육안 재판독" '육안 재판독'  .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "색 박스 확정력 없음"    '범위를 확정하지 않는다|범위 후보' .claude/formats/common.md \
                                               .claude/skills/prd-analyzer/SKILL.md
present "[변경 범위 불명] 태그"  '변경 범위 불명' .claude/formats/common.md
present "C-ID 상호 참조 판정"    '상호 참조'      .claude/formats/common.md \
                                               .claude/agents/prd-analyst.md
present "23컬럼 A~W"             '23.{0,2}컬럼'   .claude/formats/common.md \
                                               .claude/skills/testcase-auto/SKILL.md
present "양식 두 파일 함께 로드" '함께 읽는다|함께 로드' .claude/skills/testcase-auto/SKILL.md
present "정책 예외 태그"         '\[정책 예외\]'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/testcase-generator/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md

echo "── CLI 명령 오표기 가드 ───────────────────────────────────"
absent "get_metadata 셸 명령 표기" 'sheets_api\.py get_metadata' "${CORE[@]}" "${DOCS[@]}"

echo
if [ "$fail" -eq 0 ]; then
  echo "PASS — 처리 단위 재편 검사 통과"
else
  echo "FAIL — 위 항목을 고칠 것"
fi
exit "$fail"
```

- [ ] **Step 2: 실행 권한을 주고 돌려서 전면 FAIL을 확인한다**

```bash
chmod +x scripts/verify_unit_migration.sh
./scripts/verify_unit_migration.sh
```

기대: `FAIL` 다수 + 종료 코드 1. 특히 `산출물 접미사 _ch{N}` · `00_chapters.md 참조` · `간지 감지` · `CH{챕터2자리} 표기` 가 FAIL이고, 필수 패턴 전부가 FAIL이어야 한다. **모두 ok로 나오면 검사기가 잘못 쓰인 것이다** — 패턴이 파일을 못 찾고 있는지 확인한다.

- [ ] **Step 3: `common.md` 의 「CH-ID 네임스페이스」 절을 교체한다**

317-320행의 다음 내용을

```markdown
### CH-ID 네임스페이스

챕터별 분석서가 CH-ID를 제각기 매기면 한 탭에서 충돌한다. **`CH{챕터2자리}-N`** 형식으로 통일한다
(`CH01-1`, `CH02-1`). 챕터가 하나뿐이어도 규칙을 지킨다.
```

아래로 바꾼다.

```markdown
### CH-ID 네임스페이스

화면별 분석서가 CH-ID를 제각기 매기면 한 탭에서 충돌한다. **`CH{NN}-N`** 형식으로 통일하며
`NN` 은 **화면 인덱스(`_workspace/00_screen_index.md`)가 그 화면에 배정한 CH-ID 접두**다
(`CH01-1`, `CH02-1`). 화면이 하나뿐이어도 규칙을 지킨다.

> **`NN` 의 의미가 2026-09-02에 바뀌었다.** 그 전까지 `NN` 은 챕터 2자리였다. **표기 형식이
> 같아서 기존 시트의 태그와 형태로는 구별되지 않는다** — 아래 충돌 방지 규칙이 그 때문에 있다.

### CH-ID 충돌 방지 — 기존 탭에 이어 쓸 때

챕터 의미의 `CH01-1` 이 이미 있는 탭에 화면 의미의 `CH01-1` 을 추가하면 **한 탭에 두 체계가
섞여 역추적이 어느 정의를 가리키는지 판별할 수 없다.** 2026-08-25 `C5` 충돌 12행과 같은 종류의
사고이며, 형태가 같으므로 나중에 눈으로 갈라낼 수도 없다.

1. **모드 A 드리프트 검증의 꼬리 읽기에서 기존 CH-ID 의 최대 `NN` 을 실측한다**
2. 화면의 CH-ID 접두는 **그 다음 번호부터** 배정한다 (기존 최대가 `CH04` 면 첫 화면은 `CH05`)
3. 배정 결과는 **화면 인덱스의 `CH-ID 접두` 컬럼에 적는다.** 인덱스 순번과 어긋날 수 있으므로
   (순번 `01` 인 화면이 `CH05`) 오프셋을 문서마다 다시 계산하지 않고 인덱스를 단일 출처로 쓴다
4. 꼬리 표본에 CH-ID 가 없어 최대값을 실측할 수 없으면 **사용자에게 확인한다.** `CH01` 부터
   시작한다고 단정하지 않는다 — 탭 중간에만 CH-ID 가 있을 수 있다
```

- [ ] **Step 4: `common.md` C-ID 「규칙」 2·3·5번을 교체한다**

298-306행의 규칙 목록에서 2·3·5번을 아래로 바꾼다. 1·4번은 그대로 둔다.

```markdown
2. **하나의 정의가 여러 화면에 걸치면 그 전부가 같은 번호를 단다.** 이것이 태그의 본래 용도다
3. **새 번호는 새 정의가 나올 때만 부여한다.** 화면이 넘어간다고 번호를 올리지 않는다
```

```markdown
5. **배정은 오케스트레이터가 레지스터로 선발급한다.** Phase 1-B 사전 스캔이 전체 페이지를 훑어
   공통 DESC 후보에 `C1`~`Cn` 을 미리 배정하고 `_workspace/00_cid_register.md` 에 정의표를 만든다.
   **분석 담당은 로컬 번호를 매기지 않는다** — 레지스터를 읽어 쓰고, 레지스터에 없는 정의를
   발견하면 오케스트레이터에게 발급을 요청한다.
   화면 단위 순차 작성은 정의상 순차 배정이다(앞 화면 행이 뒤 화면을 보기 전에 시트에 박힌다).
   그래서 **배정 시점을 루프 이전으로 옮기는 것이 유일한 해법이다.** 루프 안에서 번호를 나눠
   매기면 2026-08-25 충돌이 그대로 재발한다
```

- [ ] **Step 5: `common.md` 「탭 분할 기준」이 그대로인지 확인한다**

```bash
grep -n '탭 분할 기준' .claude/formats/common.md
```

기대: `탭 분할 기준 = **기능 챕터 / 모듈 / 변경분 단위**` 가 그대로 있다. **이 줄은 고치지 않는다** — 탭은 여전히 여러 화면을 담는다.

- [ ] **Step 6: 검사기를 돌려 사양 항목이 통과하는지 본다**

```bash
./scripts/verify_unit_migration.sh
```

기대: `CH-ID 충돌 방지 절` 이 `common.md` 쪽은 통과하고 `sheet-analyst.md` 쪽은 아직 FAIL(Task 8). `CH{챕터2자리} 표기` 가 ok로 바뀐다. `C-ID 레지스터` 는 `common.md` 만 통과. 나머지 파일 항목은 여전히 FAIL — 정상이다.

- [ ] **Step 7: 스펙의 화면 인덱스 템플릿에 `CH-ID 접두` 컬럼을 추가한다**

`docs/superpowers/specs/2026-09-02-screen-unit-pipeline-design.md` §5 의 표 머리와 예시를 아래로 바꾼다.

```markdown
| 순번 | 화면 ID(원문) | CH-ID 접두 | 페이지 | 소속 간지 | 정책 | 상태 | 시트 행 |
|------|--------------|-----------|--------|----------|------|------|--------|
| 01 | VIOE-02_01_01-11 | CH01 | p5~p7 | 통합 모니터링 | 변경 | 완료 | 2~19 |
| 02 | VIOE-02_01_02 | CH02 | p8 | 통합 모니터링 | 변경 | 완료 | 20~31 |
| 03 | VIOE-03_01_04_13 | CH03 | p9 | 파드 | **신규(예외)** | 분석중 | - |
| 04 | NOID-01 | CH04 | p10 | 파드 | 변경 | 대기 | - |
```

바로 아래에 한 줄 덧붙인다.

```markdown
- `CH-ID 접두` 는 기존 탭의 CH-ID 최대값 다음부터 배정되므로 **인덱스 순번과 어긋날 수 있다** (`common.md` 「CH-ID 충돌 방지」). 오프셋을 다시 계산하지 않고 이 컬럼을 단일 출처로 쓴다
```

- [ ] **Step 8: 커밋**

```bash
git add scripts/verify_unit_migration.sh .claude/formats/common.md \
        docs/superpowers/specs/2026-09-02-screen-unit-pipeline-design.md
git commit -m "사양: CH-ID를 화면 순번으로 재정의 + C-ID 레지스터 선발급 + 재편 검사기 신설"
```

---

### Task 2: 오케스트레이터 Phase 1 — 화면 인덱스 사전 스캔

**Files:**
- Modify: `.claude/skills/testcase-auto/SKILL.md` (1-A-3 = 231-256행, 1-B = 258-280행, 1-C = 282-300행)

**Interfaces:**
- Consumes: Task 1의 `CH{NN}-N` 표기, `00_cid_register.md` 이름
- Produces: `_workspace/00_screen_index.md` 와 `_workspace/00_cid_register.md` 의 **템플릿과 작성 규칙**. Task 3·5가 이 스키마를 읽어 쓴다. 인덱스 컬럼은 `순번 / 화면 ID(원문) / CH-ID 접두 / 페이지 / 소속 간지 / 정책 / 상태 / 시트 행`, 상태 enum 은 `대기 / 분석중 / 작성중 / 완료 / 실패`

- [ ] **Step 1: 1-A-3 의 검출 실행을 전역 1회로 바꾼다**

243-249행의 세 명령에서 출력 경로 `_workspace/red_regions/ch{N}` 을 `_workspace/red_regions` 로 바꾸고, `--pages=START-END` 를 붙이지 않는다(전 페이지 1회 실행).

```bash
# PDF 입력 — 전 페이지 1회 실행
python scripts/detect_red_regions.py <pdf_path> --output-dir=_workspace/red_regions

# 이미지 입력 (디렉터리·단일 파일 모두 가능. DPI 옵션 무시, 원본 해상도 사용)
python scripts/detect_red_regions.py <이미지 디렉터리|파일> --output-dir=_workspace/red_regions

# 빨강 + 파랑을 함께 쓰는 기획서
python scripts/detect_red_regions.py <입력> --color=both --output-dir=_workspace/red_regions
```

252-253행의 "각 챕터의 `prd-analyst`" · "챕터 에이전트 프롬프트" 를 아래로 바꾼다.

```markdown
- 출력은 **후보**다. 오탐(필수 `*`, 원형 번호 배지, 에러 아이콘, 실패 badge, 삭제 버튼, 차트 색, **페이지 외곽 아트보드 프레임**, 파랑의 경우 링크·기본 버튼·선택 탭·간지 배경)이 섞여 있으므로 각 화면의 `prd-analyst`가 육안으로 확정한다.
- **검출은 전 페이지에 1회만 실행한다.** 오케스트레이터가 화면 인덱스의 페이지 범위로 결과를 잘라 각 화면 에이전트에게 넘긴다 — 화면마다 스크립트를 다시 돌리지 않는다.
- 검출 결과 경로(해당 화면 페이지 분) **+ 실측한 표시색 + 확정된 오탐 목록**을 화면 에이전트 프롬프트에 함께 전달한다.
```

`--color=both --no-crops` 로 색을 먼저 실측하는 0단계와 "색으로 변경 종류·회차를 단정하지 않는다" 문장은 **그대로 둔다**.

- [ ] **Step 2: 1-B 를 「화면 인덱스 사전 스캔」으로 전면 교체한다**

258-280행(`#### 1-B. 간지 감지 + 챕터 목록 생성` 절 전체)을 아래로 바꾼다.

```markdown
#### 1-B. 화면 인덱스 사전 스캔

경량 스캔 에이전트 1개가 전체 이미지를 순서대로 **얕게** 훑어 처리 단위 목록을 만든다.

**판독 깊이를 얕게 유지한다** — 화면 식별자 / 페이지 경계 / Description 항목 **제목** / 상호 참조
원문(`… 참고`) 까지만 본다. **본 판독은 Phase 2가 한다.** 여기서 깊이 읽으면 분석을 두 번 하는 것이다.

**산출물 3개:**

| 산출물 | 내용 |
|--------|------|
| `_workspace/00_screen_index.md` | 처리 단위 목록 + 진행 상태 |
| `_workspace/00_cid_register.md` | 공통 DESC 후보 + C-ID 선배정 |
| (보고) 화면 식별자 출처 필드명 | `Screen ID` / `Page ID` / 기타 — **제품 프로파일의 화면 ID 체계와 대조**하고 어긋나면 보고 |

**화면 식별자 추출은 `prd-analyzer` 의 「화면 식별자 추출 규칙」을 따른다** (프로파일의 우선순위대로
탐색하고 **원문 표기를 그대로** 쓴다. 형식 정규화 금지).

**인덱스 형식:**

```
# 화면 인덱스

- 기획서: PDF/VIOLA_V4.0/03_파드.pdf
- 화면 식별자 출처: Screen ID
- 문서 기본 정책: 변경
- 예외 항목: VIOE-03_01_04_13 (신규 정책)
- 기존 탭 CH-ID 최대: CH04 (sheet-analyst 실측) → 화면 CH-ID는 CH05부터

| 순번 | 화면 ID(원문) | CH-ID 접두 | 페이지 | 소속 간지 | 정책 | 상태 | 시트 행 |
|------|--------------|-----------|--------|----------|------|------|--------|
| 01 | VIOE-02_01_01-11 | CH05 | p5~p7 | 통합 모니터링 | 변경 | 대기 | - |
| 02 | VIOE-02_01_02 | CH06 | p8 | 통합 모니터링 | 변경 | 대기 | - |
| 03 | VIOE-03_01_04_13 | CH07 | p9 | 파드 | 신규(예외) | 대기 | - |
| 04 | NOID-01 | CH08 | p10 | 파드 | 변경 | 대기 | - |
```

- 상태 enum: `대기` / `분석중` / `작성중` / `완료` / `실패`
- `시트 행` 은 append 직후 오케스트레이터가 기록한다. 미작성은 `-`
- `CH-ID 접두` 는 **1-D `sheet-analyst` 가 실측한 기존 최대값 다음부터** 배정한다
  (`common.md` 「CH-ID 충돌 방지」). 인덱스 순번과 어긋날 수 있으며 이 컬럼이 단일 출처다
- **소속 간지**는 처리 단위가 아니라 **그룹 라벨**이다. 분석 컨텍스트로 화면 에이전트에게 넘긴다

**단위 확정 규칙 (경계 케이스):**

| 상황 | 처리 |
|------|------|
| 한 화면 ID가 여러 페이지에 걸침 | 묶어서 **한 단위** |
| 한 페이지에 여러 화면 ID (팝업 등) | 페이지 중복 등재 허용 — 단위 기준은 화면 |
| 같은 화면 ID가 문서 앞뒤로 떨어져 등장 | 한 단위로 병합하고 페이지 목록에 둘 다 기재 |
| 화면 ID 판독 불가 | `[판독 불가]` 로 등재 + 1-C에서 사용자 확인. **추정 금지** |
| 간지 · 목차 | **인덱스 제외** — UI·Description이 없어 케이스 원천이 없다 |
| 공통 정책 · 플로우 페이지 | `NOID-{일련번호}` 로 **독립 단위** 등재 |

**`NOID` 단위의 표기:**

- 일련번호는 인덱스 순번과 **별개인 자체 연번**이다 (`NOID-01`, `NOID-02`)
- 시트의 `화면 ID` 컬럼에 **`NOID-01` 을 쓰지 않는다.** 기획서에 없는 문자열이므로 사양의
  No-data 규칙대로 표기한다. `NOID` 는 하네스 내부 단위 식별자다
- 그 케이스의 `비고` 에 근거 페이지를 남긴다 (예: `[DESC p10-2항]`)
- **직전 화면에 병합하지 않는다** — 여러 화면에 걸치는 공통 정책을 한 화면에만 귀속시키면
  나머지 화면에서 근거가 사라진다

**C-ID 레지스터 형식** (`_workspace/00_cid_register.md`):

```
# 공통 DESC C-ID 레지스터

※ 배정 권한은 오케스트레이터에 있다. 분석 담당은 로컬 번호를 매기지 않는다.

| C-ID | 정의 내용 | 근거 화면 ID·DESC 항목 | 적용 화면 순번 | 연결 근거(상호 참조 원문) |
|------|----------|---------------------|--------------|------------------------|
| C1 | '터미널 실행' 버튼 동작 | VIOE-03_01_01-01 > 2항 | 01, 04 | `상세 동작은 목록 > '작업' 버튼 정의와 동일하게 제공 (VIOE-03_01_01-01 > 2항 참고)` |
```

- **「연결 근거」가 빈 항목은 레지스터에 올리지 않는다.** 연결 판정 근거는 **기획서의 상호 참조**
  뿐이다 — 일자·회차·내용이 같아도 상호 참조가 없으면 병렬 변경으로 두고 연결하지 않는다
  (`common.md` 「하나의 정의 판단 기준」)
- 사전 스캔이 놓친 정의는 루프 중 분석 담당의 **발급 요청**으로 추가한다 (Phase 2)

**이미지 입력 특이사항:** 페이지 번호는 파일명 기준으로 부여하고 인덱스의 `페이지` 칸에 파일명을
함께 표기한다 (예: `page_005.png ~ page_007.png`).

**화면 식별자를 어느 페이지에서도 찾지 못하면** 인덱스를 만들 수 없다. 사용자에게 식별자
필드명·위치를 확인한다. **간지 단위로 임의 폴백하지 않는다.**
```

- [ ] **Step 3: 1-C 게이트를 화면 인덱스 확인으로 바꾼다**

282-300행(`#### 1-C. 사용자 확인 게이트 (필수)` 절 전체)을 아래로 바꾼다.

```markdown
#### 1-C. 사용자 확인 게이트 (필수)

화면 인덱스를 사용자에게 보여주고 확인받는다. **화면 수와 예상 에이전트 사이클을 함께 알린다** —
화면 N개면 `3N + 1` 회다(화면마다 분석·생성·리뷰 3회 + 마지막 Phase 5 집계 리뷰 1회).
챕터 단위 시절 챕터 1개가 3회였으므로 사용자가 규모를 알고 시작해야 한다.

```
다음 화면 단위로 처리합니다. 맞는지 확인해 주세요. (화면 8개 → 에이전트 사이클 25회)

| 순번 | 화면 ID | 페이지 | 소속 간지 | 정책 |
|------|---------|--------|----------|------|
| 01 | VIOE-02_01_01-11 | p5~p7 | 통합 모니터링 | 변경 |
| 02 | VIOE-02_01_02 | p8 | 통합 모니터링 | 변경 |
| 03 | VIOE-03_01_04_13 | p9 | 파드 | 신규(예외) |
| 04 | NOID-01 (공통 정책 페이지) | p10 | 파드 | 변경 |
...

제외한 페이지: p1~p4 (간지·목차)
판독 불가: 없음

수정이 필요하면 알려주세요. (예: "p8도 01번 화면에 포함시켜줘", "04번은 제외해줘")
OK면 그대로 진행합니다.
```

- 사용자 OK → 확정된 인덱스로 루프 진입
- 사용자 수정 → 인덱스 수정 후 다시 보여주고 재확인 (OK까지 반복)
- 확정된 인덱스는 `_workspace/00_screen_index.md` 에 저장
- **제외한 페이지와 판독 불가 항목을 반드시 함께 보여준다** — 조용히 빠진 페이지가 누락의 원천이다
- 화면 수가 많으면(예: 50개 초과) 사이클 수를 알리고 **범위 축소 여부를 확인한다**
```

- [ ] **Step 4: 1-A-2 판독 품질 게이트의 "챕터 에이전트" 표현을 고친다**

215행의 `각 챕터 에이전트 프롬프트에` 를 `각 화면 에이전트 프롬프트에` 로 바꾼다.

- [ ] **Step 5: 검사기를 돌린다**

```bash
./scripts/verify_unit_migration.sh
```

기대: `간지 감지` · `red_regions/ch{N} 경로` 가 ok로 바뀐다. `화면 인덱스 파일` 은 `testcase-auto` 만 통과(나머지는 Task 5). `00_chapters.md 참조` · `챕터 루프` 는 여전히 FAIL — Phase 2~5가 Task 3이다.

- [ ] **Step 6: 커밋**

```bash
git add .claude/skills/testcase-auto/SKILL.md
git commit -m "오케스트레이터 Phase 1: 간지 감지 → 화면 인덱스 사전 스캔 + 색 검출 전역 1회"
```

---

### Task 3: 오케스트레이터 Phase 2~5 — 화면 루프와 집계 리뷰

**Files:**
- Modify: `.claude/skills/testcase-auto/SKILL.md` (Phase 2~4 = 333-408행, Phase 5 = 409-460행)

**Interfaces:**
- Consumes: Task 2의 인덱스 스키마와 C-ID 레지스터
- Produces: 산출물 경로 계약 `_workspace/01_prd_analysis_s{NN}.md` · `03_testcases_s{NN}.md` · `04_review_report_s{NN}.md` (`{NN}` = 인덱스 **순번**, CH-ID 접두가 아니다). Task 5·6·7이 이 경로를 쓴다

- [ ] **Step 1: 루프 머리(333-343행)를 화면 루프로 바꾼다**

```markdown
### Phase 2~4: 화면 루프

1-C에서 확정된 화면 인덱스를 **순번대로** 처리한다. 각 화면은 분석 → TC 생성/작성 → 리뷰가
완료된 후 다음 화면으로 넘어간다. **화면 하나가 시트에 쓰이고 나서 다음 화면이 시작된다** —
진행 중에도 사용자가 시트에서 지금까지 작성된 분량을 확인할 수 있다.

```
for 화면 in 화면 인덱스 (순번 순):
    인덱스 상태 → 분석중
    Phase 2: 화면 분석      → 01_prd_analysis_s{NN}.md
    인덱스 상태 → 작성중
    Phase 3: TC 생성 + 시트 작성 → 03_testcases_s{NN}.md → 시트 append
             인덱스에 시트 행 범위 기록
    Phase 4: 화면 리뷰      → 04_review_report_s{NN}.md
    인덱스 상태 → 완료 (실패 시 실패)
```

**`{NN}` 은 인덱스 순번이다** (CH-ID 접두가 아니다 — 둘은 어긋날 수 있다).
**인덱스 상태는 매 단계 후 갱신한다.** 이 파일이 진행 상태의 단일 출처이므로, 갱신하지 않으면
중단 후 이어 실행이 어디서 끊겼는지 알 수 없다.
```

- [ ] **Step 2: Phase 2(344-368행)를 화면 분석으로 바꾼다**

머리 3줄과 입출력을 아래로 교체하고, 그 아래 「에이전트 프롬프트에 반드시 포함할 것」 표는 **행을 추가만** 한다(기존 4행은 유지).

```markdown
#### Phase 2: 화면 분석

`prd-analyst` 1개 에이전트가 그 화면의 페이지 이미지를 **순차적**으로 읽어 분석한다.

- 입력: **화면 ID 원문 · 페이지 범위 · CH-ID 접두 · 소속 간지 · 그 화면의 정책**, 전체 이미지
  (+ PDF 입력 시 Description 크롭 이미지), 판독 이슈 페이지 목록(1-A-2),
  (변경 정책인 경우) **그 화면 페이지 분의** 변경 표시 검출 결과·실측 표시색·확정 오탐 목록(1-A-3),
  `_workspace/00_cid_register.md` 경로, `_workspace/00_screen_index.md` 전문
- 상세 분석 절차: `prd-analyzer` 스킬 참조
- 출력: `_workspace/01_prd_analysis_s{NN}.md`

분석 중 모호한 항목은 "확인 불가"로 명시하고 진행 (추측 금지).

**인덱스 전문을 넘기는 이유** — 목록↔상세처럼 화면 간 연결이 있는 기획서에서 자기 화면만 보면
맥락이 끊긴다. 다른 화면의 존재와 ID를 알아야 상호 참조를 판독할 수 있다.
```

「반드시 포함할 것」 표에 두 행을 덧붙인다.

```markdown
| **CH-ID 접두** (`CH05` 등) | 변경분 CH-ID를 `CH{접두}-N` 으로 매긴다. 인덱스 순번과 다를 수 있으므로 인덱스 값을 그대로 넘긴다 |
| **C-ID 레지스터 경로** | 공통 DESC 번호는 레지스터에서 **읽어 쓴다.** 로컬 번호를 매기지 않는다 — 없는 정의를 발견하면 발급을 요청한다 |
```

- [ ] **Step 3: Phase 3(369-385행)의 경로와 게이트를 바꾼다**

```markdown
#### Phase 3: TC 생성 + 시트 작성

`testcase-writer`에게 작업 할당:

- 입력: `_workspace/01_prd_analysis_s{NN}.md` + `_workspace/02_sheet_format.md` + 대상 시트 URL·탭명
  + **Phase 0 확정값 전부**(제품 유형 / 기획서 유형 / 예외 항목 / 생성 모드) + **CH-ID 접두**
  + `_workspace/00_cid_register.md`
- **양식은 `.claude/formats/common.md` + 해당 프로파일 두 개를 함께 읽도록 지시한다.** 한쪽만 읽으면 규칙의 절반이 없다
- **예외 화면 케이스의 피드백에 `[정책 예외] 문서 기본=… / 이 화면=…` 을 남기도록 지시한다**
- 작업:
  1. 케이스 도출 (`testcase-generator` 스킬) — 판독 이슈 페이지 처리 규칙 적용 (0-J)
  2. `_workspace/03_testcases_s{NN}.md` 작성
     - 케이스 수는 **실제 작성분을 센 정확한 값** 사용 (추정 금지)
     - **프로파일 분포 대조는 여기서 하지 않는다.** 화면 1개 표본으로는 편차가 의미를 갖지
       못한다 — Phase 5 전체 집계에서 1회 측정한다
  3. **검토 게이트** (**첫 화면만**):
     - `03_testcases_s01.md` 요약을 사용자에게 보여주고 진행 확인
     - 이후 화면은 자동 진행
     - **첫 화면에서 문체·태그·enum을 잡아야 나머지 전 행에 번지지 않는다**
  4. 사용자 OK (또는 자동 진행) → `sheet-operator`로 시트에 작성
     - 대상 탭이 없으면 `add_tab` → **생성 직후 `metadata` 의 `title` 을 복사** → `common.md` 의 **헤더 원문**을 `A1:W1` (23컬럼)에 기입 → 2행부터 batch append
     - 기존 탭이면 batch append (헤더 대조는 1-D에서 이미 완료)
  5. 작성된 행 범위 보고 → **오케스트레이터가 인덱스의 `시트 행` 칸에 기록**
```

- [ ] **Step 4: Phase 4(386-408행)를 화면 리뷰로 바꾸고 전역 지표를 뺀다**

```markdown
#### Phase 4: 화면 리뷰

`testcase-reviewer`에게 작업 할당:

- 입력: 그 화면의 01·03 파일 + `02_sheet_format.md` + 실제 시트의 작성된 행 범위
  + **Phase 0 확정값 3개**(제품 유형 / 기획서 유형 / 예외 항목)
- 작업: 세 경계면 교차 비교 (기획 ↔ 케이스, 양식 ↔ 케이스, 로컬 ↔ 시트)
- 출력: `_workspace/04_review_report_s{NN}.md`

**화면 리뷰에서 제외하는 점검 — 전역 지표이므로 Phase 5로 이관됐다:**

| 제외 항목 | 이유 |
|----------|------|
| **분포 편차 점검 (`testcase-reviewer` 3-1)** | 화면 1개 표본은 5~20건이다. 이 표본으로 프로파일 실측 분포와 대조하면 **지배 구분 역전이 상시 Critical로 뜬다** |
| **TC ID 연속성** | 시작 번호·중복·결번은 탭 전역 지표다 |

**리뷰어 프롬프트에 반드시 넣을 오판 방지 항목:**

- **제품 유형 → 프로파일**을 명시한다. 프로파일마다 **정반대인 규칙**이 있다 (UI 라벨 백틱 ↔ 대괄호, 지배 구분 `표시` ↔ `정상`, `정상`의 우선순위 P1·P2만 ↔ P1~P4 전부). 한쪽 기준으로 다른 쪽을 지적하는 것이 대표적 오판이다
- **기획서 유형이 `변경` 이면 비변경분 미작성은 정상**이다 — 누락으로 지적하지 않는다
- **예외 화면이 문서 기본 정책과 다르게 작성된 것은 정상**이다 — 그게 예외의 정의다. 대신 ① 예외 화면이 실제로 반대 정책으로 작성됐는가 ② `[정책 예외]` 표시가 있는가 ③ 예외 목록에 없는 화면이 반대 정책으로 작성되지 않았는가(범위 초과)를 점검한다
- **관리대상 컬럼은 폐지됐다** — 부재를 결함으로 지적하지 않는다
- **분포 편차와 TC ID 연속성은 이 단계에서 지적하지 않는다** — 표본이 한 화면뿐이다
- **작성자 자기 점검표를 인용하지 말고 독립 실측하라**

**Critical 이슈 발생 시:**
- 리뷰어가 `testcase-writer`에게 재작성 요청
- writer가 수정 → reviewer가 재리뷰 (최대 1회 루프)
- 두 번째 리뷰에도 Critical이 남으면 사용자에게 결정 위임 후 다음 화면 진행

> **첫 화면 리뷰 후 패턴 이슈 발견 시:** Critical이 특정 패턴(예: 표시 형식 케이스 누락, enum 오류)에서 나왔다면 남은 화면 진행 전 사용자에게 보고하고 방향 조정 여부를 확인받는다. **화면 단위는 반복 횟수가 많아 패턴 오류의 번짐이 더 크다.**
```

- [ ] **Step 5: Phase 5 에 전체 집계 리뷰를 넣고 보고 형식을 바꾼다**

409-416행의 합본 절을 아래로 교체한다.

```markdown
### Phase 5: 합본 + 전체 집계 리뷰 + 종합 보고

모든 화면 루프 완료 후 오케스트레이터가 합본을 만들고, **전체 집계 리뷰를 1회 실행**한 뒤 종합
보고를 작성한다.

**합본 생성:**
- `_workspace/01_prd_analysis.md` — 화면별 분석 파일 순번대로 합산
- `_workspace/03_testcases.md` — 화면별 TC 파일 순번대로 합산 (ID 순 정렬)
- `_workspace/04_review_report.md` — 화면별 리뷰 보고서 합산 + 전체 요약

**전체 집계 리뷰 (신설)** — `testcase-reviewer` 에게 탭 전체를 대상으로 1회 할당한다.
화면 단위에서 측정할 수 없었던 전역 지표만 본다.

| 항목 | 판정 |
|------|------|
| 분포 편차 (프로파일 실측 대비) — **시트에서 직접 카운트** | ±15%p 이상 + 사유 없음은 Major. **지배 구분 역전은 Critical** |
| TC ID · `No` 연속성 (시작 번호 = 실측 마지막 + 1, 중복·결번) | Major |
| C-ID 레지스터 ↔ 시트 태그 대조 | 정의표 없는 C-ID 사용은 Major |
| CH-ID 충돌 0건 (한 탭에 두 체계가 섞이지 않았는가) | **Critical** |
| 화면 인덱스 전 항목 상태 = `완료` | 미완료·`실패` 항목은 누락으로 보고 |

- 출력: `_workspace/04_review_report.md` 의 「전체 집계 리뷰」 절
- **분포 편차가 크게 나오면 케이스가 아니라 프로파일이 틀렸을 수 있다** — `profile-bootfactory`
  처럼 실측 근거가 없는 프로파일이면 그 가능성을 함께 보고한다
```

- [ ] **Step 6: 종합 보고 형식(417-460행)의 표와 산출물 목록을 바꾼다**

`### 처리된 챕터` 표를 아래로 바꾼다.

```markdown
### 처리된 화면
| 순번 | 화면 ID | 소속 간지 | 페이지 | 정책 | 케이스 수 | 시트 행 | 리뷰 결과 |
|------|---------|----------|--------|------|----------|--------|----------|
| 01 | VIOE-02_01_01-11 | 통합 모니터링 | p5~p7 | 변경 | 18개 | 2~19 | Critical 0 |
| 02 | VIOE-02_01_02 | 통합 모니터링 | p8 | 변경 | 12개 | 20~31 | Critical 1→해결 |
| ... | ... | ... | ... | ... | ... | ... | ... |
```

`### 전체 결과` 에 한 줄 덧붙인다.

```markdown
- 전체 집계 리뷰: 분포 편차 {값} / TC ID 연속성 {판정} / CH-ID 충돌 {건수}
```

`### 산출물` 목록을 아래로 바꾼다.

```markdown
- `_workspace/00_screen_index.md` (화면 인덱스 — 진행 상태·시트 행 포함)
- `_workspace/00_cid_register.md` (공통 DESC C-ID 레지스터)
- `_workspace/01_prd_analysis_s{NN}.md` (화면별)
- `_workspace/01_prd_analysis.md` (전체 합본)
- `_workspace/02_sheet_format.md`
- `_workspace/03_testcases_s{NN}.md` (화면별)
- `_workspace/03_testcases.md` (전체 합본)
- `_workspace/04_review_report_s{NN}.md` (화면별)
- `_workspace/04_review_report.md` (전체 합본 + 전체 집계 리뷰)
- `_workspace/00_image_quality.json` (이미지 판독 품질 진단 결과 — 이미지 입력 시)
```

- [ ] **Step 7: 검사기를 돌린다**

```bash
./scripts/verify_unit_migration.sh
```

기대: `챕터 루프` · `00_chapters.md 참조` 가 ok로 바뀐다. `전체 집계 리뷰` 는 `testcase-auto` 만 통과(나머지는 Task 7). `산출물 접미사 _ch{N}` 은 다른 파일이 남아 여전히 FAIL.

- [ ] **Step 8: 커밋**

```bash
git add .claude/skills/testcase-auto/SKILL.md
git commit -m "오케스트레이터 Phase 2~5: 화면 루프 + 첫 화면 게이트 + 전체 집계 리뷰 신설"
```

---

### Task 4: 오케스트레이터 잔여 참조 정리

Phase 절차가 바뀌었으니 그 절차를 요약·색인하는 표들을 맞춘다. 이 태스크를 건너뛰면 스킬 안에서 절차와 색인이 서로 다른 파이프라인을 가리킨다.

**Files:**
- Modify: `.claude/skills/testcase-auto/SKILL.md` (8행, 23-26행, 133행, 163행, 461-480행 프로토콜 표, 490-514행 에러 표, 516-521행 팀 조율, 522-560행 테스트 시나리오, 561-574행 체크리스트)

**Interfaces:**
- Consumes: Task 2·3이 확정한 경로·용어 전부

- [ ] **Step 1: 머리 문장과 역할 표를 고친다**

8행:

```markdown
기획서(PRD) → 팀 양식 분석 → **화면 ID(`Screen ID` / `Page ID`) 단위 순차 처리** → 테스트 케이스 생성/작성/리뷰까지 전체 파이프라인을 4명의 전문 에이전트 팀으로 자동 수행한다.
```

23-26행의 역할 칸:

```markdown
| `prd-analyst` | 화면별 이미지 순차 분석 | `prd-analyzer` |
| `sheet-analyst` | 기존 시트 양식 분석 | `sheet-operator` |
| `testcase-writer` | 화면별 케이스 생성 및 시트 작성 | `testcase-generator`, `sheet-operator` |
| `testcase-reviewer` | 화면별 리뷰 + 전체 집계 리뷰 (QA) | `testcase-reviewer`, `sheet-operator` |
```

- [ ] **Step 2: Phase 0 의 범위·재실행 항목을 고친다**

133행:

```markdown
| **분석 범위** (특정 화면만) | 전체 | 사용자가 부분 처리를 요청할 때 |
```

163행:

```markdown
- `_workspace/` 가 있고 사용자가 "특정 화면만 보완" 요청 → **부분 재실행** (인덱스에서 그 순번을 찾아 해당 화면만 재처리. 인덱스의 상태·시트 행이 남아 있어 범위가 정확히 특정된다)
```

- [ ] **Step 3: 데이터 전달 프로토콜 표(461-480행)를 고친다**

`챕터 목록` 행을 두 행으로 바꾸고, `_ch{N}` 경로를 `_s{NN}` 으로 바꾼다.

```markdown
| **화면 인덱스** | `_workspace/00_screen_index.md` | 오케스트레이터 (1-B~1-C, 루프 중 상태 갱신) | prd-analyst · testcase-writer · testcase-reviewer, 사용자 확인 |
| **C-ID 레지스터** | `_workspace/00_cid_register.md` | 오케스트레이터 (1-B 선발급 / 루프 중 추가 발급) | prd-analyst (읽기·발급 요청), testcase-writer |
| 화면 분석 | `_workspace/01_prd_analysis_s{NN}.md` | prd-analyst | testcase-writer, testcase-reviewer |
| 전체 분석 합본 | `_workspace/01_prd_analysis.md` | 오케스트레이터 (Phase 5) | 사용자 참조 |
```

`| 시트 양식 …` 행의 `(모든 챕터 공유)` 를 `(모든 화면 공유)` 로, `| 챕터 케이스 …` 를 `| 화면 케이스 | _workspace/03_testcases_s{NN}.md | …`, `| 챕터 리뷰 …` 를 `| 화면 리뷰 | _workspace/04_review_report_s{NN}.md | …` 로 바꾼다.

**메시지 기반 통신** 목록에 한 줄 덧붙인다.

```markdown
- `prd-analyst` → 오케스트레이터: 레지스터에 없는 공통 DESC 정의 발견 시 **C-ID 발급 요청**
```

- [ ] **Step 4: 에러 핸들링 표(490-514행)를 고친다**

498-499행 두 행을 삭제하고 그 자리에 아래를 넣는다.

```markdown
| 화면 식별자를 어느 페이지에서도 찾지 못함 | 인덱스 생성 불가 → 사용자에게 식별자 필드명·위치 확인 요청. **간지 단위로 임의 폴백하지 않는다** |
| 특정 페이지의 화면 ID 판독 불가 | 인덱스에 `[판독 불가]` 로 등재 + 1-C에서 사용자 확인. 추정 금지 |
| 인덱스에 없는 화면 ID가 분석 중 발견 | 보고 후 인덱스에 추가. **임의로 진행하지 않는다** — 인덱스가 진행 상태의 단일 출처이므로 우회하면 상태가 깨진다 |
| 기존 탭에 챕터 의미의 CH-ID가 존재 | `sheet-analyst` 실측 최대 `NN` 다음부터 배정. 실측 불가 시 사용자 확인 (`common.md` 「CH-ID 충돌 방지」) |
| 화면 분석 결과 0건 | 사용자에게 그 화면의 페이지 범위 재확인 요청 후 재시도 또는 스킵 |
| 화면 하나 처리 실패 | 인덱스 상태 `실패` 기록 후 다음 화면 진행. Phase 5 보고서에 누락 명시 |
| 화면 수 과다 (예: 50개 초과) | 1-C 게이트에서 사이클 수(`3N+1`)를 알리고 범위 축소 여부 확인 |
```

514행 원칙 문장:

```markdown
**원칙:** 1회 재시도 후 재실패 시 해당 화면 결과 없이 다음 화면으로 진행하고, 인덱스 상태를 `실패` 로 남기고 보고서에 누락을 명시한다.
```

- [ ] **Step 5: 팀 조율(516-521행)을 고친다**

```markdown
- 팀 크기: 4명 (소규모 ~ 중규모)
- Phase 1만 일부 병렬 (1-A + 1-D), 화면 루프는 순차
- 조율 오버헤드 최소화: 화면 루프 내에서는 분석→생성→리뷰 순차 처리
- **에이전트 사이클은 화면 수에 비례한다** (`3N + 1`). 화면 단위는 페이지 1~3장이라 사이클당
  비용은 챕터보다 작지만 횟수가 늘어난다 — 1-C에서 사용자에게 규모를 알린다
```

- [ ] **Step 6: 테스트 시나리오(522-560행)를 고친다**

「정상 흐름」 4~6번, 「챕터 목록 수정 흐름」, 「특정 챕터 재실행 흐름」, 「첫 챕터 패턴 이슈 발견 흐름」을 아래로 교체한다.

```markdown
4. Phase 1-B: 화면 인덱스 사전 스캔 (+ C-ID 선발급)
5. Phase 1-C: 사용자에게 화면 인덱스 + 사이클 수 확인 → OK
6. 화면 루프 시작:
   - s01: prd-analyst 분석 → testcase-writer 케이스 생성 → **첫 화면 사용자 검토** → 시트 작성 → reviewer 리뷰
   - s02: 자동 진행 → ... → 리뷰
   - ... (반복)
7. Phase 5: 합본 + 전체 집계 리뷰 + 종합 보고
8. Phase 6: 피드백 수집

### 화면 인덱스 수정 흐름

1. Phase 1-C에서 "p8도 01번 화면에 포함시켜줘" 요청
2. 오케스트레이터: 인덱스 수정 후 재표시 (사이클 수도 다시 계산)
3. 사용자 OK → 확정

### 특정 화면 재실행 흐름

1. 사용자: "VIOE-02_01_02 케이스 다시 만들어줘"
2. `_workspace/00_screen_index.md` 에서 그 화면 ID의 순번·페이지·CH-ID 접두·기존 시트 행 확인
3. prd-analyst·sheet-analyst 호출 없음 (기존 산출물 재사용)
4. testcase-writer만 호출, 그 화면 케이스 재생성
5. reviewer가 새 케이스만 검토
6. **인덱스의 시트 행 칸을 갱신한다** — 기존 행을 남기고 신규만 append하면 두 범위가 생기므로 둘 다 적는다

### 첫 화면 패턴 이슈 발견 흐름

1. s01 리뷰: "표시 형식 검증 케이스가 전혀 없음" Critical 발견
2. writer 재작성 → reviewer 재리뷰 → Critical 해결
3. 오케스트레이터: "s01에서 표시 형식 자동 도출 누락 패턴 발견. 남은 화면 진행 전 확인합니다."
4. 사용자 확인 → 이후 화면 진행
```

- [ ] **Step 7: 산출물 체크리스트(561-574행)를 고친다**

```markdown
- [ ] `_workspace/00_screen_index.md` 존재 (사용자 확인 완료 + 전 항목 상태 기록)
- [ ] `_workspace/00_cid_register.md` 존재 (정의표 없는 C-ID 사용 0건)
- [ ] 화면별 `01_prd_analysis_s{NN}.md` 모두 존재
- [ ] `_workspace/01_prd_analysis.md` (전체 합본) 존재
- [ ] `_workspace/02_sheet_format.md` 존재 (최상단에 모드 A/B 명시, 헤더 대조 결과·다음 TC ID·**기존 CH-ID 최대값** 포함)
- [ ] 화면별 `03_testcases_s{NN}.md` 모두 존재 (**첫 화면** 사용자 검토 완료)
- [ ] `_workspace/03_testcases.md` (전체 합본) 존재
- [ ] 화면별 `04_review_report_s{NN}.md` 모두 존재
- [ ] `_workspace/04_review_report.md` (전체 합본 + **전체 집계 리뷰**) 존재
- [ ] 구글 시트의 작성된 행 범위가 화면별로 인덱스에 기록됨
- [ ] 이미지 입력인 경우 `_workspace/00_image_quality.json` 존재 + 판독 이슈가 사용자에게 보고됨
- [ ] 판독 `불가` 페이지가 추측 케이스 없이 판독 불가 케이스로 남음
- [ ] 사용자가 결과를 확인하고 피드백 기회를 제공받음
```

- [ ] **Step 8: 오케스트레이터 파일 단독으로 검사한다**

```bash
grep -nE '_ch\{N\}|00_chapters|red_regions/ch|챕터 루프|간지 감지|첫 (번째 )?챕터|챕터별|챕터 분석' \
  .claude/skills/testcase-auto/SKILL.md
```

기대: **출력 없음.**

- [ ] **Step 9: 커밋**

```bash
git add .claude/skills/testcase-auto/SKILL.md
git commit -m "오케스트레이터 잔여 참조 정리: 프로토콜 표·에러 표·시나리오·체크리스트"
```

---

### Task 5: `prd-analyzer` 스킬 + `prd-analyst` 에이전트

**Files:**
- Modify: `.claude/skills/prd-analyzer/SKILL.md` (PDF-1.5 = 158-177행, 공통 DESC 감지·C-ID 배정 = 207-256행, 출력 메타 = 499-506행, IMG 표 = 537행·554행, 체크리스트 = 637-649행)
- Modify: `.claude/agents/prd-analyst.md` (공통 DESC·C-ID = 48-56행, 입력 = 149-156행, 출력 = 163-170행·222-224행, 재실행 = 262-263행)

**Interfaces:**
- Consumes: `_workspace/00_screen_index.md` · `_workspace/00_cid_register.md` 스키마 (Task 2), 산출물 경로 `01_prd_analysis_s{NN}.md` (Task 3)
- Produces: 분석서 메타정보 필드 — `화면 ID`, `CH-ID 접두`, `페이지 범위`, `소속 간지`, `적용 정책`, `화면 식별자 출처`

- [ ] **Step 1: PDF-1.5 를 화면 단위 전략으로 교체한다**

158-177행 전체를 아래로 바꾼다.

```markdown
### PDF-1.5. 화면 단위 순차 분석 전략

PDF 분석은 **화면 ID(`Screen ID` / `Page ID`) 단위로 순차 처리**한다. 1개의 prd-analyst 에이전트가
담당 화면의 페이지 이미지를 처음부터 끝까지 순서대로 읽어 분석한다.

**화면 하나는 대개 페이지 1~3장**이므로 이미지 컨텍스트 한도는 사실상 문제가 되지 않는다.

**한도 폴백 (드물게 한 화면이 여러 페이지에 걸칠 때):** 에이전트당 안전 이미지 한도는
12~13페이지(전체 + 크롭 합산 ~26장)다. 한 화면이 이를 넘으면 **여러 에이전트로 쪼개지 않고**
한 에이전트가 13페이지씩 나눠 읽으며 앞 구간 맥락을 유지하고, 모든 구간 완료 후 하나의 분석
파일로 통합한다.

**파일 명명 규칙:**

| 단계 | 파일명 패턴 | 생성자 |
|------|-----------|--------|
| 화면 분석 결과 | `_workspace/01_prd_analysis_s{NN}.md` | prd-analyst |
| 전체 합본 | `_workspace/01_prd_analysis.md` | 오케스트레이터 (Phase 5) |

`{NN}` 은 `_workspace/00_screen_index.md` 의 **순번**이다 (예: s01, s02, ...).
**CH-ID 접두와 혼동하지 않는다** — 기존 탭에 이어 쓰는 경우 둘은 어긋난다.
```

- [ ] **Step 2: 공통 DESC 감지 범위를 레지스터 조회로 바꾼다**

207-212행을 아래로 바꾼다.

```markdown
**공통 Description 감지 (담당 화면 분석 후):**

담당 화면의 페이지 분석이 끝난 뒤, Description 항목을 **C-ID 레지스터
(`_workspace/00_cid_register.md`)와 대조**한다.

- 레지스터에 이미 있는 정의와 일치하면 **그 C-ID를 그대로 쓴다** — 다른 화면이 먼저 썼더라도
  같은 정의면 같은 번호다. 그것이 이 태그의 본래 용도다
- 레지스터에 없는데 **다른 화면과 공통으로 보이는 정의**를 발견하면 오케스트레이터에게
  **C-ID 발급을 요청**한다. 임의로 다음 번호를 매기지 않는다
- 형식: `[공통 DESC C1] {항목 내용}` — 근거 화면 ID 목록은 레지스터의 정의표가 갖는다
- **공통 항목이라도 담당 화면의 분석 결과에 모두 포함한다. 생략 금지.**
- 담당 화면 안에서 여러 페이지에 반복되는 항목도 각 페이지 결과에 모두 남긴다
```

- [ ] **Step 3: C-ID 배정 절차를 발급 요청 절차로 교체한다**

214-238행(「공통 DESC C-ID 배정 절차」 절)의 역할 표와 1·2번을 아래로 바꾼다. **「하나의 정의 판단 기준」(240행 이하 상호 참조 규칙)은 그대로 둔다.**

```markdown
**공통 DESC C-ID 배정 절차 (분석 담당이 할 일 / 하지 말 일):**

시트 비고에 들어가는 `[공통 DESC CN]` 의 번호는 **탭 전역에서 정의 단위로 유일**해야 한다.
화면 단위 순차 작성은 앞 화면 행이 뒤 화면을 보기 전에 시트에 박히므로, **번호는 루프 이전에
확정돼 있어야 한다.** 그래서 배정 권한을 오케스트레이터가 갖는다.

| 단계 | 담당 | 하는 일 |
|------|------|--------|
| 1 | **오케스트레이터** | Phase 1-B 사전 스캔에서 공통 DESC 후보에 `C1`~`Cn` **선발급** → 레지스터 |
| 2 | **분석 담당(나)** | 레지스터를 **읽어 쓴다.** 없는 정의를 발견하면 **발급을 요청**한다 |

1. **로컬 번호를 매기지 않는다.** `C1` 부터 새로 세지 않고, 앞 화면이 어디까지 썼는지
   추측하지도 않는다. 번호의 출처는 레지스터 하나다
2. **발급 요청 형식** — 분석서에 다음 절을 남기고 오케스트레이터에게 알린다:

   ```
   ## C-ID 발급 요청
   | 정의 내용 | 근거 화면 ID·DESC 항목 | 연결 근거(상호 참조 원문) |
   |----------|---------------------|------------------------|
   ```

   **「연결 근거」가 비어 있으면 요청하지 않는다** — 연결하면 안 되는 항목이다
3. **정의표 없는 C-ID를 쓰지 않는다.** 정의가 없으면 시트 행에서 기획서 근거로 역추적이 끊겨
   태그 자체가 무의미해진다
```

- [ ] **Step 4: 출력 메타정보와 IMG 절을 고친다**

499행 `분석 정책: 기본=변경 / 예외={화면 ID 목록 또는 없음}` 아래, 505행 메타정보 문장을 아래로 바꾼다.

```markdown
메타정보에 입력 유형(`PDF`), 원본 파일명, **화면 ID 원문 · CH-ID 접두 · 담당 페이지 범위 · 소속 간지**, 전체 이미지 경로, Description 크롭 이미지 경로와 함께 **Phase 0에서 받은 제품 유형·기획서 유형·분석 정책(기본 + 예외 화면 목록) + 이 화면에 적용한 정책** 을 추가한다.
```

537행 IMG 표의 `| 챕터(간지) 구분 | …` 행을 아래로 바꾼다.

```markdown
| 화면 단위 구분 | 이미지 순서대로 스캔해 화면 식별자를 추출한다. 간지는 처리 단위가 아니라 **소속 간지 라벨**로만 쓴다. 이미지가 이미 화면 단위 디렉터리로 나뉘어 전달됐다면 그 구분을 인덱스 후보로 쓰고 사용자에게 확인받는다 |
```

554행:

```markdown
메타정보에 입력 유형(`이미지`), 이미지 디렉터리 경로, 파일 수, 페이지↔파일명 매핑, 화면 ID 원문, 담당 범위, 소속 간지를 기재한다.
```

- [ ] **Step 5: 체크리스트를 고친다**

637-649행의 해당 항목들을 아래로 바꾼다.

```markdown
- [ ] `_workspace/01_prd_analysis_s{NN}.md` 생성됨 (인덱스 순번 사용)
- [ ] 메타정보에 화면 ID 원문 · CH-ID 접두 · 담당 페이지 범위 · 소속 간지 · 적용 정책 기록됨
```

```markdown
- [ ] 담당 화면의 공통 Description 항목 `[공통 DESC CN]` 태그로 기록됨 (페이지별 생략 없음)
- [ ] **C-ID는 레지스터에서 읽어 썼음** — 로컬 번호를 매기지 않았고, 없는 정의는 「C-ID 발급 요청」 절로 올렸음
- [ ] C-ID 연결은 **기획서 상호 참조**에 근거함 (내용·일자·회차만 같고 독립 근거인 항목을 임의로 묶지 않음)
```

- [ ] **Step 6: `prd-analyst` 에이전트의 공통 DESC·C-ID 절(48-56행)을 교체한다**

```markdown
5. **공통 Description 항목을 페이지별로 모두 기록한다.** 담당 화면의 여러 페이지에 동일하거나 유사한 Description 항목이 있으면 `[공통 DESC CN]` 태그를 붙이고 각 페이지 분석 결과에 **모두 포함**한다. "이미 앞 페이지에서 기록됨"을 이유로 생략하지 않는다.

   **C-ID 배정 — 나는 번호를 매기지 않는다.** 시트의 `[공통 DESC CN]` 은 탭 전역에서 정의 단위로 유일해야 하고, 화면 단위 순차 작성에서는 **앞 화면 행이 이미 시트에 박힌 뒤** 내가 시작한다. 그래서 번호의 출처는 오케스트레이터가 관리하는 `_workspace/00_cid_register.md` 하나다:

   - **레지스터를 읽어 쓴다.** 내 정의가 레지스터의 항목과 일치하면 **그 번호를 그대로 쓴다** — 다른 화면이 먼저 썼더라도 같은 정의면 같은 번호다
   - **로컬 `C1` 부터 세지 않는다.** 앞 화면이 `C1`~`C4` 를 썼을 것 같다고 `C5` 부터 시작하지도 않는다
   - 레지스터에 없는 공통 정의를 발견하면 분석서에 **「C-ID 발급 요청」 절**로 올린다 (정의 내용 / 근거 화면 ID·DESC 항목 / 연결 근거 원문). **연결 근거가 비면 요청하지 않는다**
   - 최종 배정은 **오케스트레이터**가 한다 (2026-08-25 `C5` 충돌 12행이 루프 안 배정의 결과였다)
```

- [ ] **Step 7: `prd-analyst` 입출력 프로토콜을 고친다**

149-156행 입력 목록:

```markdown
- 담당 화면 ID 원문 (예: `VIOE-02_01_01-11`) — 오케스트레이터가 `00_screen_index.md` 기준으로 지정
- 담당 페이지 범위 (예: `p5~p7` 또는 `page_005.png ~ page_007.png`)
- CH-ID 접두 (예: `CH05`) — 변경분 CH-ID는 `CH{접두}-N` 으로 매긴다
- 소속 간지 (예: `통합 모니터링`) — 처리 단위가 아니라 분석 컨텍스트
- 이 화면에 적용할 정책 (`변경` / `신규`, 예외 화면이면 그 사실)
- `_workspace/00_cid_register.md` 경로
- `_workspace/00_screen_index.md` 전문 (다른 화면의 존재·ID를 알아야 상호 참조를 판독할 수 있다)
```

163-170행 출력 경로·메타:

```markdown
`_workspace/01_prd_analysis_s{NN}.md`에 다음 구조로 저장 (`{NN}` = 인덱스 순번, 오케스트레이터가 지정):
```

메타 블록의 `- 챕터: {챕터 제목}` 을 아래로 바꾼다.

```markdown
- 화면 ID: {원문}
- CH-ID 접두: {예: CH05}
- 소속 간지: {라벨}
- 적용 정책: {변경|신규} {예외 화면이면 「정책 예외」 표시}
```

222-224행의 정의표 머리 문구(`※ 이 C-ID는 본 분석서 내 로컬 번호다…`)와 `**C1 부터 시작.**` 항목을 삭제하고 아래로 바꾼다.

```markdown
※ C-ID는 `_workspace/00_cid_register.md` 에서 읽어 썼다. 새 정의는 「C-ID 발급 요청」 절에 있다.
```

262-263행 재실행 절:

```markdown
`_workspace/01_prd_analysis_s{NN}.md`가 이미 존재하면:
- 사용자가 "해당 화면 다시 분석"을 명시하면 덮어쓰기
```

- [ ] **Step 8: 두 파일을 검사한다**

```bash
grep -nE '_ch\{N\}|00_chapters|챕터' .claude/skills/prd-analyzer/SKILL.md .claude/agents/prd-analyst.md
./scripts/verify_unit_migration.sh
```

기대: 첫 명령의 출력은 **없다**(prd-analyzer·prd-analyst 에는 정당한 `챕터` 용법이 없다). 검사기에서 `화면 인덱스 파일` · `C-ID 레지스터` 의 이 두 파일 몫이 ok로 바뀐다.

- [ ] **Step 9: 커밋**

```bash
git add .claude/skills/prd-analyzer/SKILL.md .claude/agents/prd-analyst.md
git commit -m "분석 단계: 화면 단위 전략 + C-ID 레지스터 조회·발급 요청으로 전환"
```

---

### Task 6: `testcase-generator` 스킬 + `testcase-writer` 에이전트

**Files:**
- Modify: `.claude/skills/testcase-generator/SKILL.md` (265행 CH-ID, 283행, 295행, 321·324행, 328·347행, 369행, 385행, 623행)
- Modify: `.claude/agents/testcase-writer.md` (95행 태그, 106행·111행·115행 입출력, 159-160행 재실행)

**Interfaces:**
- Consumes: `CH{NN}-N` 정의와 CH-ID 접두 (Task 1·2), 경로 `03_testcases_s{NN}.md` (Task 3)
- Produces: 케이스 산출물 메타에 `화면 ID` / `CH-ID 접두` / `적용 정책` 기재. Task 7 리뷰어가 이 메타를 읽는다

- [ ] **Step 1: CH-ID 네임스페이스 지시를 고친다 (265행)**

```markdown
- **CH-ID는 `CH{NN}-N` 네임스페이스를 지킨다.** `NN` 은 **오케스트레이터가 넘긴 CH-ID 접두**이며 화면 인덱스의 값이다 (`CH05-1`, `CH06-3`). **인덱스 순번과 다를 수 있으므로 직접 계산하지 않고 넘겨받은 값을 쓴다** — 기존 탭에 챕터 의미의 CH-ID가 있으면 그 최대값 다음부터 배정된다 (`common.md` 「CH-ID 충돌 방지」). 화면이 하나뿐이어도 지킨다 — 제각기 매기면 한 탭에서 충돌한다 (2026-08-25 실제 사고).
```

- [ ] **Step 2: 산출물 경로 참조를 모두 `_s{NN}` 으로 바꾼다**

283·295·321·324·328·347·369·385행의 `03_testcases_ch{N}.md` → `03_testcases_s{NN}.md`, `01_prd_analysis_ch{N}.md` → `01_prd_analysis_s{NN}.md`.

283행의 `참고 시트의 다른 챕터에서 쓰인 값` 은 `참고 시트의 다른 탭·화면에서 쓰인 값` 으로 바꾼다.

- [ ] **Step 3: 분포 대조 시점을 Phase 5로 이관한다 (369행 부근)**

369행을 아래로 바꾼다.

```markdown
- **화면 단위에서는 프로파일 분포와 대조하지 않는다.** 화면 1개 표본은 5~20건이라 편차가 의미를 갖지 못하고, 억지로 맞추면 그 화면에 없는 케이스를 만들게 된다. 분포 대조는 **오케스트레이터 Phase 5 전체 집계 리뷰**에서 탭 전체를 대상으로 1회 한다
- `03_testcases_s{NN}.md` 에는 **그 화면의 실제 분류별 케이스 수만** 센 값으로 적는다 (추정 금지)
```

1-0 절(353행 부근)의 분포 기준 설명은 유지하되, 적용 시점만 위 문장이 규정한다. 385행의 폴백 명시 문장은 경로만 바꾼다.

- [ ] **Step 4: 체크리스트(623행)를 고친다**

```markdown
- [ ] CH-ID가 `CH{NN}-N` 네임스페이스를 지킴 — **오케스트레이터가 넘긴 CH-ID 접두를 그대로 사용**했고 직접 계산하지 않았음 (충돌 0건)
```

- [ ] **Step 5: `testcase-writer` 의 비고 태그 지시(95행)를 고친다**

```markdown
   - 비고 태그는 `[변경 CH{NN}-N {종류 원문} {회차}-{일자}]`. **CH-ID 필수**이고 `NN` 은 **오케스트레이터가 넘긴 CH-ID 접두**를 그대로 쓴다(인덱스 순번과 다를 수 있으므로 직접 계산하지 않는다). **종류 원문이 다어절이면 회차와 붙지 않게 띄운다** (`[변경 CH05-1 명칭 변경 v1-26.07.31]`)
```

- [ ] **Step 6: `testcase-writer` 입출력과 게이트(106·111·115행)를 고친다**

```markdown
- `_workspace/01_prd_analysis_s{NN}.md` 경로 (오케스트레이터가 인덱스 순번 지정)
- 화면 ID 원문 · CH-ID 접두 · 적용 정책
- `_workspace/00_cid_register.md` 경로 — 공통 DESC 번호는 여기서 읽어 쓴다
```

```markdown
- 검토 게이트 여부 — **첫 화면(s01)**: 사용자 확인 필요 / 이후 화면: 자동 진행
```

```markdown
1. **로컬 산출물:** `_workspace/03_testcases_s{NN}.md`에 작성한 케이스 목록 (시트 작성 전 검토용, 인덱스 순번은 오케스트레이터가 지정). 메타에 화면 ID · CH-ID 접두 · 적용 정책을 적는다
```

- [ ] **Step 7: `testcase-writer` 재실행 절(159-160행)을 고친다**

```markdown
`_workspace/03_testcases_s{NN}.md`가 이미 존재하면:
- 사용자가 "해당 화면 다시 작성"을 요청하면 새로 생성 (시트에는 기존 케이스 유지하고 신규만 append). **행 범위가 두 곳으로 나뉘므로 인덱스의 `시트 행` 칸에 둘 다 적는다**
```

- [ ] **Step 8: 두 파일을 검사한다**

```bash
grep -nE '_ch\{N\}|CH\{챕터2자리\}|첫 (번째 )?챕터|챕터' \
  .claude/skills/testcase-generator/SKILL.md .claude/agents/testcase-writer.md
./scripts/verify_unit_migration.sh
```

기대: 첫 명령 출력 없음. 검사기에서 `CH-ID = CH{NN}-N` 이 ok로 바뀐다.

- [ ] **Step 9: 커밋**

```bash
git add .claude/skills/testcase-generator/SKILL.md .claude/agents/testcase-writer.md
git commit -m "생성 단계: CH-ID 접두 전달 방식 + 첫 화면 게이트 + 분포 대조 Phase 5 이관"
```

---

### Task 7: `testcase-reviewer` 스킬 + 에이전트

리뷰를 **화면 리뷰**와 **전체 집계 리뷰** 두 모드로 갈라 쓴다. 분포 편차와 TC ID 연속성을 화면 모드에서 빼는 것이 이 태스크의 핵심이며, 빼지 않으면 화면마다 오탐 Critical이 뜬다.

**Files:**
- Modify: `.claude/skills/testcase-reviewer/SKILL.md` (0절 리뷰 전제 = 30-43행, 3-1 = 123-138행, 8절 보고서 = 381-383행, 체크리스트 = 410-448행)
- Modify: `.claude/agents/testcase-reviewer.md` (42행, 산출물 경로)

**Interfaces:**
- Consumes: `03_testcases_s{NN}.md` 메타 (Task 6), 인덱스·레지스터 (Task 2)
- Produces: `04_review_report_s{NN}.md` (화면 모드) / `04_review_report.md` 의 「전체 집계 리뷰」 절 (집계 모드)

- [ ] **Step 1: 0절에 리뷰 모드 구분을 신설한다**

30행 `### 0. 리뷰 전제 확인 — 프롬프트로 받는 3개` 바로 앞에 아래 절을 넣는다.

```markdown
### 0-0. 리뷰 모드 — 화면 리뷰 / 전체 집계 리뷰

프롬프트가 어느 모드인지 먼저 확인한다. **모드를 혼동하면 점검 항목이 어긋난다.**

| 모드 | 대상 | 산출물 | 점검 |
|------|------|--------|------|
| **화면 리뷰** (기본) | 화면 1개 + 그 시트 행 범위 | `_workspace/04_review_report_s{NN}.md` | 2 · 3 · 3-2 · 3-3 · 4 · 5 · 5-1 · 5-2 · 5-2-1 · 5-2-2 · 5-3 · 6 · 7 |
| **전체 집계 리뷰** | 탭 전체 (Phase 5) | `_workspace/04_review_report.md` 의 「전체 집계 리뷰」 절 | **3-1 분포 편차** · TC ID·`No` 연속성 · C-ID 레지스터 대조 · CH-ID 충돌 · 인덱스 상태 |

**화면 리뷰에서 절대 하지 않을 것:**

- **분포 편차 점검(3-1)** — 화면 1개 표본은 5~20건이다. 프로파일 실측 분포와 대조하면
  **지배 구분 역전이 상시 Critical로 뜬다.** 그 화면에 없는 케이스를 만들라는 지적이 된다
- **TC ID 시작 번호·중복·결번** — 탭 전역 지표다

**전체 집계 리뷰에서 절대 하지 않을 것:**

- 개별 케이스의 기획 대조·문체 지적 — 화면 리뷰가 이미 했다. 중복 지적은 보고서를 흐린다
```

- [ ] **Step 2: 3-1 절을 전체 집계 리뷰 전용으로 표시한다**

123행 제목과 그 아래 첫 문장을 아래로 바꾼다. **표·판정 기준·오판 주의·실측 근거는 그대로 둔다.**

```markdown
### 3-1. 분포 편차 점검 (프로파일 실측 대비) — **전체 집계 리뷰 전용**

> **화면 리뷰에서는 이 절을 실행하지 않는다.** 화면 1개 표본(5~20건)으로는 편차가 의미를
> 갖지 못하고 지배 구분 역전이 상시 뜬다. Phase 5에서 탭 전체를 대상으로 1회 측정한다.

**해당 프로파일의** "구분 분포" 실측값과 작성된 케이스 분포를 대조한다. `common.md` 에는 분포가 없다.
```

132행의 편차 사유 참조 경로를 바꾼다.

```markdown
- 편차 사유가 화면별 `03_testcases_s{NN}.md` 에 기재돼 있으면 그 타당성만 평가하고 위반으로 세지 않는다
```

절 끝에 한 줄 덧붙인다.

```markdown
- **편차가 크면 케이스가 아니라 프로파일이 틀렸을 수 있다.** `profile-bootfactory` 처럼 팀 시트
  실측 근거가 없는 프로파일이면 그 가능성을 함께 보고한다
```

- [ ] **Step 3: 전체 집계 리뷰의 나머지 점검 항목 절을 신설한다**

3-1 절 바로 뒤에 아래를 넣는다.

```markdown
### 3-1-1. 전역 정합성 점검 — **전체 집계 리뷰 전용**

| # | 점검 내용 | 위반 시 |
|---|----------|--------|
| 1 | TC ID 시작 번호가 실측 마지막 ID + 1 인가 / 중복·결번 0건인가 | Major |
| 2 | `No` 컬럼이 연속인가 | Minor |
| 3 | 시트에 쓰인 모든 `[공통 DESC CN]` 이 `_workspace/00_cid_register.md` 정의표에 있는가 | Major (정의표 없는 C-ID는 역추적이 끊긴다) |
| 4 | **같은 C-ID가 서로 다른 정의에 쓰이지 않았는가** | **Critical** (2026-08-25 충돌 12행의 재발) |
| 5 | **같은 정의가 서로 다른 C-ID로 쪼개지지 않았는가** | Major (2026-08-27 사고 유형) |
| 6 | **CH-ID가 한 탭에서 두 체계로 섞이지 않았는가** — 챕터 의미와 화면 의미 | **Critical** (형태가 같아 눈으로 갈라낼 수 없다) |
| 7 | `00_screen_index.md` 전 항목 상태가 `완료` 인가 | `실패`·미완료는 누락으로 보고 |
| 8 | 인덱스의 `시트 행` 합이 실제 작성 행 수와 일치하는가 | Major |
```

- [ ] **Step 4: 8절 보고서 경로(381-383행)를 고친다**

```markdown
화면 리뷰는 `_workspace/04_review_report_s{NN}.md` 에, 전체 집계 리뷰는
`_workspace/04_review_report.md` 의 「전체 집계 리뷰」 절에 결과를 저장한다.
형식은 `testcase-reviewer` 에이전트 정의의 출력 프로토콜 참조.
```

- [ ] **Step 5: 체크리스트를 모드별로 가른다**

410-448행 체크리스트에서 아래 3개 항목을 옮기고 고친다.

- `- [ ] **분포 편차 표 작성** …` 항목 → 문구를 `- [ ] (**전체 집계 리뷰만**) 분포 편차 표 작성 (프로파일 실측 vs 작성 — **직접 카운트**). 지배 구분 역전은 Critical` 로 바꾼다
- `- [ ] TC ID 시작 번호가 실측 마지막 ID + 1 인지 확인` → `- [ ] (**전체 집계 리뷰만**) TC ID 시작 번호·중복·결번 / `No` 연속성 확인` 로 바꾼다
- `- [ ] _workspace/04_review_report_ch{N}.md 생성` → `- [ ] `_workspace/04_review_report_s{NN}.md` (화면 리뷰) 또는 `04_review_report.md` 의 「전체 집계 리뷰」 절 생성` 로 바꾼다

체크리스트 머리에 두 항목을 덧붙인다.

```markdown
- [ ] **리뷰 모드(화면 / 전체 집계)를 확인**했고 그 모드의 점검 항목만 실행했음
- [ ] (**화면 리뷰**) 분포 편차·TC ID 연속성을 지적하지 않았음 — 전역 지표이며 표본이 한 화면뿐이다
```

전체 집계 전용 항목을 체크리스트 끝에 덧붙인다.

```markdown
전체 집계 리뷰인 경우 추가:
- [ ] C-ID 레지스터 ↔ 시트 태그 대조 (같은 번호 다른 정의 = Critical / 같은 정의 다른 번호 = Major)
- [ ] **CH-ID 두 체계 혼재 0건** (챕터 의미 ↔ 화면 의미, Critical)
- [ ] `00_screen_index.md` 전 항목 상태 `완료` 확인 — `실패`·미완료는 누락으로 보고
- [ ] 인덱스의 시트 행 합 ↔ 실제 작성 행 수 일치
```

- [ ] **Step 6: `testcase-reviewer` 에이전트를 고친다**

42행:

```markdown
11. **작성자 자기 점검표를 인용하지 말고 독립 실측한다.** `03_testcases_s{NN}.md` 의 커버리지 표는 작성자의 주장이지 측정 결과가 아니다. 행 수·태그 기재율은 **시트에서 직접 센다.** 작성자 표와 실측이 어긋나면 그 불일치 자체를 이슈로 보고한다. **분포는 전체 집계 리뷰에서만 센다.**
```

에이전트 정의의 출력 프로토콜에 있는 `04_review_report_ch{N}.md` 를 `04_review_report_s{NN}.md` 로 바꾸고, 「리뷰 모드」 항목을 입력 프로토콜에 추가한다.

```markdown
- 리뷰 모드 (`화면 리뷰` / `전체 집계 리뷰`) — 오케스트레이터가 지정
```

- [ ] **Step 7: 두 파일을 검사한다**

```bash
grep -nE '_ch\{N\}|챕터' .claude/skills/testcase-reviewer/SKILL.md .claude/agents/testcase-reviewer.md
./scripts/verify_unit_migration.sh
```

기대: 첫 명령 출력 없음. 검사기의 `전체 집계 리뷰` · `산출물 접미사 _s{NN}` 이 ok로 바뀐다.

- [ ] **Step 8: 커밋**

```bash
git add .claude/skills/testcase-reviewer/SKILL.md .claude/agents/testcase-reviewer.md
git commit -m "리뷰 단계: 화면 리뷰 / 전체 집계 리뷰 분리 + 분포·TC ID 연속성 이관"
```

---

### Task 8: `sheet-analyst` 기존 CH-ID 실측 + `sheet-operator` 예시

**Files:**
- Modify: `.claude/agents/sheet-analyst.md` (A-2 꼬리 읽기 판정 표 = 145행 부근, 산출물 형식 = 176행 부근, 읽기 범위 한계 = 129-130행, 데이터 부족 = 349행)
- Modify: `.claude/skills/sheet-operator/SKILL.md` (120·127·130행 예시)

**Interfaces:**
- Produces: `02_sheet_format.md` 에 **`기존 CH-ID 최대: {값}`** 줄. Task 2의 1-B가 이 값을 읽어 CH-ID 접두를 배정한다

- [ ] **Step 1: `sheet-analyst` 모드 A 판정 표에 CH-ID 실측을 추가한다**

145행 `| 마지막 TC ID 추출 성공 | OK | 다음 시작 번호 = 실측값 + 1 |` 아래에 두 행을 넣는다.

```markdown
| 기존 CH-ID 최대값 추출 성공 | OK | 화면 CH-ID 접두 = 실측값 + 1 (`CH04` → 첫 화면 `CH05`) |
| 꼬리 표본에 CH-ID 없음 | **보고** | `CH01` 부터라고 단정하지 않는다 — 탭 중간에만 있을 수 있다. 오케스트레이터가 사용자에게 확인 |
```

- [ ] **Step 2: 「CH-ID 충돌 방지」 절을 신설한다**

판정 표 아래에 넣는다.

```markdown
#### CH-ID 충돌 방지 — 실측이 필요한 이유

`CH{NN}-N` 의 `NN` 은 **2026-09-02에 챕터 2자리에서 화면 순번으로 의미가 바뀌었다.** 표기 형식이
같으므로 **기존 시트의 태그와 형태로는 구별되지 않는다.** 챕터 의미의 `CH01-1` 이 있는 탭에
화면 의미의 `CH01-1` 을 추가하면 역추적이 어느 정의를 가리키는지 판별할 수 없고, 나중에 눈으로
갈라낼 수도 없다.

꼬리 읽기에서 `비고` 컬럼의 `[변경 CH…]` 태그를 훑어 **최대 `NN` 을 실측**하고 산출물에 적는다.
```

- [ ] **Step 3: 산출물 형식(176행 부근)에 한 줄을 추가한다**

```markdown
- 마지막 TC ID: {값} → 다음 시작: {값+1}
- 기존 CH-ID 최대: {값 또는 `없음` / `실측 불가`} → 화면 CH-ID 접두 시작: {값+1 또는 `사용자 확인 필요`}
```

- [ ] **Step 4: 읽기 범위 한계 문장(129-130행)에 CH-ID를 추가한다**

`판정 항목은 헤더·마지막 TC ID·꼬리 표본 enum 세 가지뿐이며` 를 아래로 바꾼다.

```markdown
> 판정 항목은 헤더·마지막 TC ID·**기존 CH-ID 최대값**·꼬리 표본 enum 네 가지뿐이며,
```

349행 데이터 부족 항목에 한 문장을 덧붙인다.

```markdown
- 데이터 부족 (5행 미만) → **모드 A라면 정상 상황이다.** 사양 파일이 양식의 원천이므로 그대로 진행한다. 마지막 TC ID만 실측되지 않으므로 프로파일의 시작 정책을 적용하고 보고한다. **기존 CH-ID도 없으므로 화면 CH-ID 접두는 `CH01` 부터 시작한다** (빈 탭에는 충돌 대상이 없다)
```

- [ ] **Step 5: `sheet-operator` 예시 문자열(120·127·130행)을 고친다**

`"01_챕터명"` 을 `"01_파드"` 로 바꾼다 (탭명은 여전히 기능/모듈 단위이므로 구조는 그대로 두고, 챕터라는 단어만 실제 모듈명 예시로 교체한다).

```bash
python scripts/sheets_api.py add_tab <SHEET_URL> "01_파드"
```

```bash
python scripts/sheets_api.py write <SHEET_URL> "'01_파드'!A1:W1" '[["No","솔루션","기능테스트 ID","요구사항 ID", ...]]'
```

```bash
python scripts/sheets_api.py append <SHEET_URL> "'01_파드'!A:W" '[[...],[...]]'
```

- [ ] **Step 6: 검사한다**

```bash
grep -nE '챕터' .claude/agents/sheet-analyst.md .claude/skills/sheet-operator/SKILL.md
./scripts/verify_unit_migration.sh
```

기대: 첫 명령 출력 없음. 검사기의 `CH-ID 충돌 방지 절` 이 완전히 ok로 바뀐다. **이 시점에서 `.claude/` 아래 검사는 전부 통과해야 한다** — 남은 FAIL은 `DOCS` 몫뿐이다.

- [ ] **Step 7: 커밋**

```bash
git add .claude/agents/sheet-analyst.md .claude/skills/sheet-operator/SKILL.md
git commit -m "시트 단계: 기존 CH-ID 최대값 실측 추가 (두 체계 혼재 방지)"
```

---

### Task 9: 사용자 문서 + 변경 이력

**Files:**
- Modify: `README.md` (10행 다이어그램)
- Modify: `HARNESS_OVERVIEW.md` (24·33·36·51·59·129·208·221·229-233·236-240행 및 이후 챕터 참조 전체)
- Modify: `HARNESS_WORKFLOW.md` (6·52·54·57·74·93·95·102-120·132행)
- Modify: `docs/PROMPTS.md` (73·105·123·130·155·162·184-198·215·253행)
- Modify: `CLAUDE.md` (하네스 요약부 + 변경 이력 테이블)

- [ ] **Step 1: `README.md` 다이어그램을 고친다**

10행:

```
                              ├─→ 화면 ID 단위 순차 처리 ─→ 구글 시트 작성 ─→ QA 리뷰
```

- [ ] **Step 2: `HARNESS_OVERVIEW.md` 를 고친다**

24·33·36·51행 다이어그램의 `챕터 루프` → `화면 루프`, `간지 감지 → 챕터 목록` → `화면 인덱스 사전 스캔`, `(ch01 → ch02 → ... 순차)` → `(s01 → s02 → ... 순차)`, `Phase 5: 챕터별 산출물 합본` → `Phase 5: 화면별 산출물 합본 + 전체 집계 리뷰`.

59행 설계 근거 행을 아래로 바꾼다.

```markdown
| 화면 ID 단위 순차 처리 | 전체 일괄 처리는 누락이 많았고(2026-06-11 챕터 순차로 전환), 챕터 단위는 시트의 식별 축(`화면 ID`)과 어긋났다. 2026-09-02에 화면 ID 1개 단위로 재편 — 화면 하나를 시트 작성까지 끝낸 뒤 다음으로 넘어간다 |
```

129행 오케스트레이터 행의 `챕터 루프 제어` → `화면 루프 제어`.

208·221행의 `특정 챕터만` → `특정 화면만`.

229-233행 Phase 1 설명을 아래로 바꾼다.

```markdown
- **1-B 화면 인덱스 사전 스캔**: 경량 스캔 에이전트가 전체 이미지를 얕게 훑어 화면 식별자를 추출하고 처리 단위 목록을 만든다. 공통 DESC 후보에 C-ID를 선발급한다
  - 판독 깊이: 화면 식별자 / 페이지 경계 / DESC 항목 제목 / 상호 참조 원문까지. 본 판독은 Phase 2
  - 경계 규칙: 한 화면이 여러 페이지면 묶고, 한 페이지에 여러 화면 ID면 중복 등재. 간지·목차는 제외, 공통 정책 페이지는 `NOID-{일련번호}` 독립 단위
  - 간지는 처리 단위가 아니라 **소속 간지 라벨**로 남아 분석 컨텍스트가 된다
- **1-C 사용자 확인 게이트 (필수)**: 화면 인덱스 + 화면 수 + 예상 사이클(`3N+1`)을 제시하고 OK까지 반복 수정 → 확정본을 `00_screen_index.md`에 저장
- **1-A-3 변경 표시 검출** (기획서 유형이 `변경` 일 때): `--color=both --no-crops` 로 쓰인 색을 먼저 실측한 뒤 **전 페이지 1회** 검출. 출력은 **후보**이므로 오탐(원형 번호 배지, 필수 `*`, 페이지 외곽 아트보드 프레임, 파랑의 링크·기본 버튼·선택 탭 등)은 화면 에이전트가 육안 확정
```

236-240행 이후 Phase 2~4 절을 화면 루프로 바꾸고, Phase 5에 전체 집계 리뷰를 추가한다. 도구 표의 `detect_red_regions.py` 출력 경로 설명에서 `ch{N}` 을 지운다.

- [ ] **Step 3: `HARNESS_WORKFLOW.md` 를 고친다**

6행:

```markdown
기획서(PDF/Figma) 한 건을 넣으면 → 팀 시트 양식을 역공학하고 → **화면 ID 단위로 잘라** → 테스트 케이스를 만들어 구글 시트에 쓰고 → 스스로 QA 리뷰까지 하는 파이프라인이다.
```

52·54·57행 다이어그램:

```
         ├ 1-B  화면 인덱스 사전 스캔 (+ C-ID 선발급)
Phase 2~4  화면 루프 (s01 → s02 → … 순차, 화면당 완결)
         │       ★ 첫 화면만 사용자 검토 게이트, 이후 자동
```

74행: `| 있음 + "화면 N만 보완" | 부분 재실행 | 인덱스에서 순번 특정, 해당 화면 에이전트만 호출, 나머지 산출물 재사용 |`

93·95행을 1-B·1-C 새 설명으로 교체한다(Step 2의 문구를 그대로 쓴다).

102-120행 Phase 2~5 절을 화면 루프로 다시 쓴다. 106행의 이미지 한도 설명은 **폴백으로 격하**한다.

```markdown
**Phase 2 (prd-analyst)** — 단일 에이전트가 담당 화면 페이지를 순서대로 읽는다. 화면 하나는 대개 페이지 1~3장이라 컨텍스트 한도가 문제되지 않는다. 드물게 한 화면이 12~13페이지를 넘으면 **여러 에이전트로 쪼개지 않고** 한 에이전트가 13페이지씩 나눠 읽으며 앞 구간 맥락을 유지한다. 페이지별 판독 순서는 고정이다:
```

112행 공통 DESC 문장:

```markdown
담당 화면의 Description을 C-ID 레지스터와 대조해 이미 있는 정의는 그 번호를 쓰고, 없는 공통 정의는 오케스트레이터에게 발급을 요청한다. 공통이어도 각 페이지 결과에 모두 남긴다.
```

114행 Phase 3, 116행 Phase 4, 120행 Phase 5를 새 경로·게이트·집계 리뷰로 바꾼다. 132행 `(**모든 챕터가 공유**, 1회만 생성)` → `(**모든 화면이 공유**, 1회만 생성)`.

- [ ] **Step 4: `docs/PROMPTS.md` 를 고친다**

73행: `기본값: 생성 모드 atomic, 범위 전체 화면.`

105·130행 예시: `- 범위: 첫 번째 화면만 먼저 해줘. 결과 보고 나머지 진행 여부 정할게` / `화면 1개만 먼저. 결과 확인하고 나머지 진행 여부 정할게.`

123·253행 탭 예시: `- 탭: 신규 — "01_파드"` / `- 탭: 신규 — "<모듈명> 변경분"`

155행 표 행을 아래로 바꾼다.

```markdown
| 화면 1개로 범위 축소 | 방향 틀린 케이스를 수백 건 쓴 뒤 발견 | `2026-06-11` 챕터 순차 전환 → `2026-09-02` 화면 ID 단위로 재편 |
```

162행: `진행 중 세 지점에서 멈춘다. **여기서 무엇을 지시하느냐가 나머지 화면 전체 품질을 결정한다.**`

184-198행 「① 챕터 목록 확인」 절을 아래로 바꾼다.

```markdown
### ① 화면 인덱스 확인

```
다음 화면 단위로 처리합니다. (화면 8개 → 에이전트 사이클 25회)

| 순번 | 화면 ID | 페이지 | 소속 간지 | 정책 |
|------|---------|--------|----------|------|
| 01 | VIOE-02_01_01-11 | p5~p7 | 통합 모니터링 | 변경 |
| 02 | VIOE-02_01_02 | p8 | 통합 모니터링 | 변경 |

제외한 페이지: p1~p4 (간지·목차)
```

볼 것 셋:
- **제외한 페이지.** 간지·목차 외의 페이지가 빠졌으면 그 화면이 통째로 누락된다
- **한 화면이 여러 페이지에 걸친 경우의 묶음.** 페이지가 갈라지면 케이스도 갈라진다
- **화면 수와 사이클 수.** 화면이 많으면 범위를 좁힐지 지금 정한다

지시 예:
```
p8도 01번 화면에 포함시켜줘
04번은 제외해줘
01~03번만 먼저 해줘
```
```

198행 「② 첫 챕터 케이스 검토」 제목을 `### ② 첫 화면 케이스 검토 (시트 쓰기 **전**)` 로, 215행을 `케이스 검토했어. 아래대로 고치고 나머지 화면도 같은 기준으로 진행해줘.` 로 바꾼다.

- [ ] **Step 5: `CLAUDE.md` 요약부를 고친다**

「하네스: 테스트 케이스 자동 생성」 절과 「환경」 절에서 챕터 단위를 전제한 문장을 찾아 화면 단위로 바꾼다. 최소한 아래를 반영한다.

```bash
grep -n '챕터' CLAUDE.md | grep -v '^[0-9]*:| 2026-'
```

찾은 줄 중 **변경 이력 테이블 행이 아닌 것만** 고친다. 이력 테이블의 과거 기록은 손대지 않는다.

- [ ] **Step 6: `CLAUDE.md` 변경 이력에 행을 추가한다**

테이블 맨 아래에 넣는다.

```markdown
| 2026-09-02 | **처리 단위 재편 — 챕터(간지) → 화면 ID(`Screen ID`/`Page ID`) 1개** | `scripts/verify_unit_migration.sh` 신설, `.claude/formats/common.md`, 스킬 5개, 에이전트 4개, `HARNESS_OVERVIEW`·`HARNESS_WORKFLOW`·`README`·`docs/PROMPTS` | 사용자 지시. 챕터 단위는 **시트의 식별 축(`화면 ID` 컬럼)과 어긋나** 있었고, 2026-09-02에 도입한 **정책 예외가 이미 화면 ID 단위**여서 한 챕터 안에 기본 정책 화면과 예외 화면이 섞인 채 한 에이전트에게 넘어갔다. 간지에 의존하는 단위는 기획서 편집 관행에도 종속됐다(간지 없는 문서, 간지 하나에 화면 20개). → **화면 1개를 분석 → 생성 → 시트 append 까지 끝낸 뒤 다음 화면으로** 넘어간다. **가장 어려운 문제는 공통 DESC C-ID의 순서 역전이었다** — 기존 규칙은 *"모든 챕터 분석을 받은 뒤 한 번에 배정"*(2026-08-25 `C5` 충돌 12행의 대책, **순차 배정이 그 사고의 원인**)인데 화면 단위 즉시 작성은 정의상 순차 배정이다. 배정 시점을 **루프 이전**으로 옮겨 해결했다: Phase 1-B 사전 스캔이 전체를 얕게 훑어 `00_cid_register.md` 에 `C1`~`Cn` 을 선발급하고, **분석 담당은 로컬 번호를 매기지 않고 레지스터를 읽어 쓴다**(없는 정의는 발급 요청). 함께 정한 것 넷 — ⓐ **CH-ID는 `CH{NN}-N` 표기를 유지하고 `NN` 의 의미만 화면 순번으로 재정의**. 새 접두어(`SC-`)는 기존 탭에서 두 체계가 섞인다. 다만 **표기가 같아 형태로 구별되지 않으므로** `sheet-analyst` 꼬리 읽기에 **기존 CH-ID 최대값 실측**을 신설하고 그 다음부터 배정한다(인덱스의 `CH-ID 접두` 컬럼이 단일 출처) ⓑ **리뷰는 화면마다 돌리되 분포 편차·TC ID 연속성은 Phase 5 「전체 집계 리뷰」로 이관** — 화면 1개 표본은 5~20건이라 **지배 구분 역전이 상시 Critical로 뜬다**(그 화면에 없는 케이스를 만들라는 지적이 된다) ⓒ **화면 ID 없는 페이지는 종류별 분기** — 간지·목차는 제외(케이스 원천 없음), 공통 정책·플로우는 `NOID-{일련번호}` 독립 단위(직전 화면에 병합하면 나머지 화면에서 근거가 사라진다) ⓓ **첫 화면 검토 게이트 유지** — 문체·태그·enum 오류를 첫 화면에서 잡아야 전 행에 번지지 않는다. 부수 이득 둘 — **색 검출이 챕터별 반복 실행에서 전역 1회로** 줄었고, **`00_screen_index.md` 의 상태·시트 행 컬럼으로 부분 재실행이 화면 단위까지 정밀**해졌다. 재발 방지로 **`verify_unit_migration.sh`** 를 영구 회귀 가드로 남겼다 — 금지 패턴(`_ch{N}`·`00_chapters`·`CH{챕터2자리}`)과 스펙 §8 「유지되는 것」의 필수 패턴을 함께 검사한다. 설계·계획: `docs/superpowers/specs/2026-09-02-screen-unit-pipeline-design.md`, `docs/superpowers/plans/2026-09-02-screen-unit-pipeline.md` |
```

- [ ] **Step 7: 검사기를 돌려 전면 통과를 확인한다**

```bash
./scripts/verify_unit_migration.sh
```

기대: 모든 항목 `ok` + 마지막 줄 `PASS — 처리 단위 재편 검사 통과` + 종료 코드 0.

- [ ] **Step 8: 커밋**

```bash
git add README.md HARNESS_OVERVIEW.md HARNESS_WORKFLOW.md docs/PROMPTS.md CLAUDE.md
git commit -m "문서: 화면 ID 단위 파이프라인 반영 + 변경 이력 기록"
```

---

### Task 10: 최종 정합성 검증

검사기는 패턴만 본다. 사람이 읽어야 잡히는 모순을 여기서 훑는다.

**Files:** 없음 (검증 전용. 발견된 문제는 해당 파일을 고친다)

- [ ] **Step 1: 검사기 전면 통과를 재확인한다**

```bash
./scripts/verify_unit_migration.sh; echo "exit=$?"
```

기대: `exit=0`.

- [ ] **Step 2: 경로 계약이 파일 간에 일치하는지 확인한다**

```bash
grep -rhoE '_workspace/[0-9]{2}_[a-z_]+(_s\{NN\})?\.(md|json)' \
  .claude/skills .claude/agents .claude/formats | sort -u
```

기대 목록 — 이 외의 경로가 나오면 오타다.

```
_workspace/00_cid_register.md
_workspace/00_image_quality.json
_workspace/00_screen_index.md
_workspace/01_prd_analysis.md
_workspace/01_prd_analysis_s{NN}.md
_workspace/02_sheet_format.md
_workspace/03_testcases.md
_workspace/03_testcases_s{NN}.md
_workspace/04_review_report.md
_workspace/04_review_report_s{NN}.md
```

- [ ] **Step 3: `{NN}` 의 두 의미가 섞이지 않았는지 확인한다**

```bash
grep -nE 'CH\{NN\}|CH-ID 접두|인덱스 순번' .claude/skills/*/SKILL.md .claude/agents/*.md .claude/formats/common.md
```

읽고 확인할 것: **산출물 파일명의 `{NN}` 은 인덱스 순번**, **CH-ID의 `NN` 은 CH-ID 접두**다. 두 값이 같다고 서술한 문장이 있으면 고친다 — 기존 탭에 이어 쓸 때 어긋난다.

- [ ] **Step 4: 스펙 §8 회귀 방지 목록을 육안 대조한다**

스펙의 「유지되는 것」 항목을 하나씩 읽으며 해당 문장이 살아 있는지 확인한다. 검사기가 잡지 못하는 것 위주로 본다.

```bash
grep -n '열 문자' .claude/skills/*/SKILL.md .claude/agents/*.md
grep -n '판독 불가' .claude/skills/testcase-auto/SKILL.md
grep -n 'title' .claude/skills/sheet-operator/SKILL.md | head -5
```

- [ ] **Step 5: 새로 쓴 문장이 열 문자를 쓰지 않았는지 확인한다**

```bash
git diff main --unified=0 -- .claude/skills .claude/agents | grep '^+' | grep -nE '\b[A-X]열|A1:W1'
```

`A1:W1`(헤더 기입 범위)은 허용된다. 그 외 `V열`·`W열` 같은 표기가 새로 들어왔으면 컬럼명으로 바꾼다.

- [ ] **Step 6: 검사기 자체를 반증한다 — 가짜 위반을 넣어 FAIL이 나는지 본다**

```bash
printf '\n<!-- 검사기 반증용: _ch{N} -->\n' >> .claude/skills/testcase-auto/SKILL.md
./scripts/verify_unit_migration.sh; echo "exit=$?"
git checkout .claude/skills/testcase-auto/SKILL.md
./scripts/verify_unit_migration.sh; echo "exit=$?"
```

기대: 첫 실행 `exit=1` (`산출물 접미사 _ch{N}` FAIL), 되돌린 뒤 `exit=0`. **첫 실행이 통과하면 검사기가 무의미하다** — 패턴이나 파일 목록을 고친다.

- [ ] **Step 7: 커밋 (수정이 있었을 때만)**

```bash
git add -A
git commit -m "정합성 검증에서 발견된 경로·표기 불일치 수정"
```

---

## 실행 후 검증 (실제 기획서 1건으로)

이 계획의 태스크는 문서 정합성까지만 보증한다. 스펙 §11의 실행 검증은 **하네스를 실제로 한 번 돌려야** 확인된다. 구현 완료 후 사용자에게 아래를 제안한다.

1. `_workspace_prev_021_monitoring_20260827` 의 기획서(VIOLA `02-1`, 챕터 4개)로 **1-C 게이트까지만** 실행 → 생성된 화면 인덱스를 기존 챕터별 분석서의 화면 ID 목록과 대조해 누락·중복 0건 확인
2. 같은 기획서로 화면 2~3개까지 루프 → C-ID가 화면 간에 공유되는지, CH-ID 접두가 인덱스대로 붙는지 확인
3. Boot Factory 기획서로 **취소선·색 박스 규칙 회귀** 확인 (삭제 항목 정상 케이스 0건 / 전면 박스 전수화 0건)
4. 화면 리뷰 보고서에 분포 편차 Critical이 없고 Phase 5에서만 측정되는지 확인

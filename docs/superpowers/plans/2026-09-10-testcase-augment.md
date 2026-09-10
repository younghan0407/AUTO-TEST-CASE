# 테스트케이스 추가 작업 (예외 사항 / 권한) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이미 작성된 테스트 케이스를 원천으로 예외 사항 케이스와 권한 케이스를 파생 생성해 구글 시트에 작성하는 별도 절차(`testcase-augment`)를 하네스에 추가한다.

**Architecture:** 기존 `testcase-auto` 와 나란한 두 번째 오케스트레이터를 신설한다. 원본 탭 읽기·집계는 신규 스크립트 `read_tc_inventory.py` 가 전담하고(에이전트에게 시트를 읽히지 않는다), 케이스 생성·시트 작성은 신규 에이전트 `tc-augmenter` 가, 리뷰는 기존 `testcase-reviewer` 가 추가 작업 모드로 수행한다. 양식 사양·`verify_sheet_rows.py`·프로파일은 그대로 공유한다.

**Tech Stack:** Python 3 표준 라이브러리 + `google-auth` / `google-api-python-client` (기존 `sheets_api.py` 경유). 테스트는 이 저장소 관행대로 스크립트 내장 `--selftest` (pytest 미사용 — `requirements.txt` 에 테스트 의존성이 없고 기존 `verify_sheet_rows.py` 가 같은 방식이다).

**Spec:** `docs/superpowers/specs/2026-09-10-testcase-augment-design.md`

## Global Constraints

- **구글 시트 전용.** 엑셀(.xlsx) 경로가 들어오면 미지원을 안내하고 중단한다. openpyxl 등 엑셀 의존성을 추가하지 않는다.
- **전 제품 23컬럼 A~W.** 열 문자(`V`·`W` 등)는 `.claude/formats/` 파일에만 둔다. 스킬·에이전트 문서에서는 **컬럼명**(`비고`·`피드백`)으로만 지칭한다.
- **규칙은 사양 파일에서 파싱한다.** 헤더 원문·`솔루션` 고정값·파생 태그 접두·프로파일 분포·결합 규칙을 스크립트나 스킬 본문에 박지 않는다. **파싱 실패 시 하드코딩 폴백 없이 종료 코드 `3`** 으로 실패한다.
- **서브에이전트가 오케스트레이터에게 돌려주는 리턴은 20줄 이내.** 파일 경로·건수·시트 행 범위·다음 단계 필요값·사용자 결정 항목만.
- **케이스 본문의 단일 출처는 시트.** `.md` 에 케이스 전문을 중복 저장하지 않고 `.tsv` 가 복구 경로다.
- **산출물은 `_workspace/augment/` 에 둔다.** 진행 중인 `testcase-auto` 산출물(`_workspace/00_*` ~ `04_*`)과 충돌하지 않게 격리한다.
- **파생 케이스는 프로파일 분포 편차 점검의 대상이 아니다** (스펙 결정 3).
- 모든 신규 문서는 **한국어**로 쓴다. 기존 파일들의 문체(단정형 서술, 실측 근거 병기)를 따른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` 를 붙인다.
- 작업 브랜치는 이미 `harness/testcase-augment` 다 (스펙 커밋이 올라가 있다).
- **명령을 실행할 때는 `python3` 을 쓴다.** 이 환경에는 `python` 이 없다 (`python3` 3.9.6만 있다).
  이 계획 본문의 `Run:` 명령에 `python` 으로 적힌 것이 있으면 `python3` 으로 바꿔 실행한다.
  **다만 문서·스킬 본문에 *쓰는* 예시 명령은 `python scripts/…` 그대로 둔다** — 저장소 기존
  문서 28곳이 그 표기이며, 표기 통일은 이 작업의 범위가 아니다.
- **Python 3.9 호환.** 새 스크립트는 `from __future__ import annotations` 를 반드시 넣는다
  (`dict[str, str]`·`str | None` 주석이 3.9에서 그 없이는 죽는다). 기존 스크립트와 같은 방식이다.
- **`verify_sheet_rows.py` 는 이 작업의 수정 대상이 아니다.** `common.md` 를 고쳐 그 스크립트의
  `--selftest` 가 깨지면 **`common.md` 쪽 표기를 기존 표 형식에 맞춘다.**
- 검증 기준선 (변경 전 실측): `verify_unit_migration.sh` → `PASS` /
  `build_brief.py --coverage-check` → 절 74종 전부 배정 /
  `verify_sheet_rows.py --selftest` → 위반 17종 검출 + 오탐 0건.
  **어느 태스크도 이 셋을 깨뜨린 채 완료하지 않는다.**

---

### Task 1: 양식 사양 확장 — 파생 태그 2종 + 「파생 케이스의 원천」 절

**Files:**
- Modify: `.claude/formats/common.md` (「비고 = 근거 태그」 표에 행 추가, 「변경 표기 경로의 위계」 절 앞에 새 `##` 절 삽입, 「메타」 절의 사양 버전)
- Modify: `.claude/skills/testcase-auto/scripts/build_brief.py` (`ROLES`·`ROLE_SECTIONS`·`--doc-type` 허용값·브리핑 머리말 1줄)

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `common.md` 에 `**파생 태그 접두 (스크립트 파싱 대상):**` 다음에 오는 펜스 코드블록. 각 줄이 태그 접두 문자열 하나다. Task 2의 `derived_prefixes()` 가 이 블록을 파싱한다.
  - `build_brief.py` 의 `--role=augmenter` 와 `--doc-type=추가`. Task 9의 SKILL이 호출한다.

- [ ] **Step 1: `common.md` 「비고 = 근거 태그」 표에 파생 태그 2행을 추가**

`.claude/formats/common.md` 의 `### 비고 = 근거 태그` 표에서 `| \`[확인 불가 기반]\` | 확인 불가 항목에서 파생된 케이스 |` 행 **다음에** 아래 두 행을 삽입한다.

```markdown
| `[예외 파생 {원본 기능테스트 ID}]` | **기존 테스트 케이스**의 정상 흐름을 뒤집어 도출한 예외 케이스. 뒤에 예외 유형명을 덧붙인다 — `[예외 파생 TC_VIO_014] 필수값 누락` |
| `[권한 매트릭스 {역할}×{기능}]` | **권한 매핑 자료**의 셀 하나가 근거. 뒤에 권한값을 덧붙인다 — `[권한 매트릭스 일반 사용자×파드 생성] 불가` |
```

- [ ] **Step 2: `common.md` 에 「파생 케이스의 원천」 절을 신설**

`## 변경 표기 경로의 위계 — 박스는 범위를 확정하지 않는다` 바로 **앞에** 아래 절을 삽입한다. 앞뒤에 `---` 구분선을 둔다 (이 파일의 절 구분 관행).

```markdown
## 파생 케이스의 원천 — 기획서가 아닌 근거

이 사양의 근거 태그는 오래도록 **기획서 하나**를 전제했다 (`[DESC …]`·`[UI]`·`[스티커]`·`[ChangeLog]`).
2026-09-10에 **기존 테스트 케이스를 원천으로 삼는 절차**(`testcase-augment`)가 생겨 원천이 둘이 됐다.

| 원천 | 근거 태그 | 만드는 절차 |
|------|----------|------------|
| **기획서** | `[DESC …]` · `[UI]` · `[스티커]` · `[강조]` · `[ChangeLog]` · `[전 화면 공통]` | `testcase-auto` |
| **기존 테스트 케이스** | `[예외 파생 {원본 기능테스트 ID}]` | `testcase-augment` (예외 사항) |
| **권한 매핑 자료** | `[권한 매트릭스 {역할}×{기능}]` | `testcase-augment` (권한) |

**파생 태그 접두 (스크립트 파싱 대상):**

```
[예외 파생
[권한 매트릭스
```

> 위 코드블록은 `read_tc_inventory.py` 가 파싱한다. **접두 문자열을 스크립트에 박지 않기 위해** 사양이
> 단일 출처다. 태그를 늘리거나 이름을 바꾸면 이 블록도 함께 고친다 — 고치지 않으면 그 태그가 붙은 행이
> 원본으로 다시 읽혀 **파생의 파생**이 생긴다.

### 규칙

1. **한 케이스에 두 원천의 태그를 섞지 않는다.** 역추적 대상이 갈린다
2. **파생 태그가 붙은 행은 다음 실행에서 원본이 되지 않는다.** 원본 탭과 작성 대상 탭이 같을 수 있으므로
   (같은 시트의 같은 탭에 이어 쓰는 것이 허용된다) 이 규칙이 없으면 재실행 때 파생분에서 또 파생이 나온다.
   그 행은 **중복 제거용 커버리지 맵에만** 쓰인다
3. **파생 케이스는 프로파일의 구분 분포 대조 대상이 아니다 — 분포 편차 점검을 적용하지 않는다.**
   예외 파생은 정의상 `비정상`·`엣지` 만,
   권한 파생은 `정상`·`부수` 만 만든다 — 어느 프로파일로 채점해도 **지배 구분 역전이 반드시 뜬다.**
   그것을 결함으로 지적하면 *"그 작업이 만들라고 한 것을 만들지 말라"* 는 리뷰가 된다.
   완전성은 **예외 유형 카탈로그 커버리지**와 **권한 매트릭스 셀 커버리지**로 측정한다
4. **기획 근거가 없는 예상 결과는 동작 수준까지만 쓴다.** 문구·코드·지연 시간 같은 확정값을 단정하지 않고
   `피드백` 에 `[기획 확인] … — 확정값 확인 필요` 를 남긴다. 자기모순 금지 규칙(예상 결과를 단정해 놓고
   확인 불가를 적는 것)이 그대로 적용된다
5. **`화면 ID`·`1~3 Depth`·`2 Depth` 는 원본 케이스에서 승계한다.** 유추로 만들지 않는다
```

- [ ] **Step 3: `common.md` 「메타」 절의 사양 버전을 올린다**

`| 사양 버전 |` 행의 값 맨 앞에 아래를 덧붙인다 (기존 이력은 뒤에 그대로 남긴다).

```
**2.2** (2026-09-10 파생 케이스 원천 2종 추가 — `[예외 파생 …]`·`[권한 매트릭스 …]` 태그 등재 + 파생분은 분포 대조 대상 아님) /
```

- [ ] **Step 4: `build_brief.py` 에 `augmenter` 역할과 `추가` 원천 유형을 추가**

`.claude/skills/testcase-auto/scripts/build_brief.py` 를 아래 4곳 수정한다.

```python
# (1) ROLES 확장
ROLES = ("analyst", "writer", "reviewer", "sheet-analyst", "augmenter")
```

```python
# (2) 독스트링의 --role / --doc-type 설명 교체
#   --role: analyst | writer | reviewer | sheet-analyst | augmenter
#   --doc-type: 신규 | 변경 | 추가
#               `신규` + 예외 없음 / `추가` 는 변경분 모드 절을 제외한다.
#               `추가` 는 기획서가 아니라 기존 테스트 케이스를 원천으로 삼는
#               `testcase-augment` 절차용이다.
```

```python
# (3) build() 안의 브리핑 머리말 — "기획서 유형" 이라는 표현이 `추가` 에서 어긋난다
    parts.append(f"""# 브리핑 — `{role}` (이 실행 전용, 자동 생성)

**이 파일은 사양의 발췌가 아니라 원문이다.** 역할에 필요한 절만 골라 옮겼을 뿐,
문장을 요약·의역하지 않았다. 그래서 이 파일만 읽고 작업해도 규칙이 빠지지 않는다.

- 원천: `{common}` + `{prof}`
- 이 역할에 배정되지 않은 절은 들어 있지 않다. **필요하다고 판단되면 원천 파일을 직접 열어라**
- 변경분 모드 절 포함 여부: **{'포함' if include_change else '제외'}**
  (원천 유형 `{doc_type}` / 변경 정책 예외 {'있음' if has_change_exc else '없음'})
""")
```

```python
# (4) ROLE_SECTIONS — 신설 절 배정 + augmenter 를 필요한 절에 추가.
#     "파생 케이스의 원천 — 기획서가 아닌 근거" 를
#     "변경 표기 경로의 위계 — 박스는 범위를 확정하지 않는다" 항목 **앞에** 넣는다.
    "파생 케이스의 원천 — 기획서가 아닌 근거": ("writer", "reviewer", "augmenter"),
```

이어서 `augmenter` 를 **`writer` 가 배정된 절 전부**에 추가한다 (파생 케이스도 같은 양식으로 쓴다). 단 아래 **2개만 제외**한다 — 이 절차에 해당 개념이 없다.

| 제외할 절 | 이유 |
|----------|------|
| `"공통 DESC C-ID는 **공유 키**다 — 소진되는 번호가 아니다"` | 기획서 Description이 원천이 아니다 |
| `"DESC 번호 두 체계 — 섞지 말고 분석서를 따른다"` | 동상 |

> `"헤더 원문 (탭 문자 구분 — 빈 시트에 헤더 생성 시 그대로 사용)"` 은 **반드시 포함한다** —
> 신규 탭 생성 시 헤더를 기입해야 한다. 제외하지 마라.

`CHANGE_ONLY` 집합은 **수정하지 않는다.** `--doc-type=추가` 는 `include_change` 가 `False` 가 되어 자동으로 제외된다 (`include_change = (doc_type == "변경") or has_change_exc`).

- [ ] **Step 5: 절 배정 검사를 돌려 통과를 확인**

Run: `python3 scripts/build_brief.py --coverage-check`
Expected: `✅ 전 절 배정 완료 · 유령 배정 0건` + 종료 코드 `0`

미배정이 나오면 새 절 제목이 `ROLE_SECTIONS` 키와 **글자 단위로** 일치하지 않는다는 뜻이다. `sections()` 가 `#{2,3} ` 만 떼므로 제목 원문(강조 기호·`—` 포함)을 그대로 키로 써야 한다.

- [ ] **Step 6: `augmenter` 브리핑이 실제로 생성되는지 확인**

Run:
```bash
python3 scripts/build_brief.py --role=augmenter --profile=viola --doc-type=추가 --out=- | head -40
python3 scripts/build_brief.py --role=augmenter --profile=viola --doc-type=추가 --out=- | grep -c '^## '
python3 scripts/build_brief.py --role=augmenter --profile=viola --doc-type=추가 --out=- | grep -c '변경분 모드'
```
Expected: 머리말에 `원천 유형 \`추가\`` / `변경분 모드 절 포함 여부: **제외**` 가 보이고, 절 수가 20개 이상, `변경분 모드` 등장 0회.

세 프로파일 모두 도는지도 확인한다.

Run: `for p in viola trombone bootfactory; do python3 scripts/build_brief.py --role=augmenter --profile=$p --doc-type=추가 --out=- >/dev/null && echo "$p ok"; done`
Expected: `viola ok` / `trombone ok` / `bootfactory ok`

- [ ] **Step 7: 기존 역할의 브리핑이 깨지지 않았는지 회귀 확인**

Run: `for r in analyst writer reviewer sheet-analyst; do for d in 신규 변경; do python3 scripts/build_brief.py --role=$r --profile=viola --doc-type=$d --out=- >/dev/null || echo "FAIL $r $d"; done; done; echo done`
Expected: `FAIL` 출력 없이 `done`

- [ ] **Step 7-1: `verify_sheet_rows.py` 의 사양 파서가 깨지지 않았는지 확인 (필수)**

`common.md` 를 고쳤으므로 그 파일을 파싱하는 다른 스크립트가 깨졌을 수 있다. **이 확인을
Task 10까지 미루면 9개 태스크 뒤에 원인을 찾게 된다.**

Run: `python3 scripts/verify_sheet_rows.py --selftest | tail -3`
Expected: `✅ 전 항목 통과 — 심어 둔 위반 17종 검출 + 오탐 0건` (변경 전 기준선과 동일)

실패하면 태그표에 추가한 행이나 새 절이 그 스크립트의 정규식과 충돌한다는 뜻이다.
**`verify_sheet_rows.py` 를 고치지 말고 `common.md` 쪽 표기를 기존 표의 형식에 맞춘다** —
그 스크립트는 이 작업의 수정 대상이 아니다.

Run: `bash scripts/verify_unit_migration.sh | tail -2`
Expected: `PASS — 처리 단위 재편 검사 통과`

- [ ] **Step 8: 커밋**

```bash
git add .claude/formats/common.md .claude/skills/testcase-auto/scripts/build_brief.py
git commit -m "$(cat <<'EOF'
사양: 파생 케이스 원천 2종 등재 + build_brief augmenter 역할

기존 근거 태그가 전부 기획서를 가리킨다는 전제를 명시적으로 확장했다.
`[예외 파생 …]`·`[권한 매트릭스 …]` 를 태그표에 올린 이유는 2026-08-25·
08-26과 같은 왕복을 막기 위한 것이다 — 스킬이 요구하는 태그가 사양에
없으면 리뷰가 매번 "사양 미등재"로 지적한다.

파생 태그 접두를 사양의 코드블록에 두어 스크립트가 파싱하게 했다.
접두를 스크립트에 박으면 태그 이름이 바뀔 때 그 행이 원본으로 다시
읽혀 파생의 파생이 생긴다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `read_tc_inventory.py` — 사양 파싱 + `--selftest` 골격

**Files:**
- Create: `.claude/skills/testcase-augment/scripts/read_tc_inventory.py`
- Test: 같은 파일의 `--selftest` (이 저장소는 pytest를 쓰지 않는다 — `verify_sheet_rows.py` 와 같은 관행)

**Interfaces:**
- Consumes: Task 1이 만든 `common.md` 의 `**파생 태그 접두 (스크립트 파싱 대상):**` 코드블록
- Produces:
  - `SpecParseError(RuntimeError)`
  - `spec_header(formats_dir: str) -> list[str]` — 23개 컬럼명
  - `derived_prefixes(formats_dir: str) -> list[str]` — 파생 태그 접두 목록
  - `profile_solutions(formats_dir: str) -> dict[str, str]` — `{"VIOLA": "viola", …}`
  - `_cells(line) -> list[str]` / `_plain(t) -> str` / `_ticks(t) -> list[str]` — Task 3이 재사용
  - `selftest() -> int` — Task 3이 케이스를 추가
  - `main(argv: list[str]) -> int`

- [ ] **Step 1: 실패하는 selftest부터 쓴다 (파일 신규 생성)**

`.claude/skills/testcase-augment/scripts/read_tc_inventory.py` 를 아래 내용으로 만든다. 이 단계에서는 **구현 없이 selftest만** 넣는다 — 함수가 없어 실패하는 것을 먼저 본다.

```python
#!/usr/bin/env python3
"""원본 테스트 케이스 인벤토리 — `testcase-augment` Phase 1.

기존 테스트 케이스를 원천으로 파생 케이스(예외 사항·권한)를 만들기 전에,
**원본 탭을 스크립트가 읽어** 기능 단위 인벤토리와 기존 커버리지 맵을 만든다.

에이전트에게 시트를 읽히지 않는 이유: 원본 탭은 수백~수천 행이고 그 텍스트가
오케스트레이터 컨텍스트에 쌓이면 이후 모든 턴에서 다시 읽힌다 (2026-09-08 실측:
오케스트레이터 평균 40만 토큰 · 전체 비용의 25.5%). 인벤토리 집계에는 판단할
값이 없으므로 `verify_sheet_rows.py` 와 같은 논리로 스크립트가 맡는다.

의존성: google-auth, google-api-python-client (시트 입력일 때만)

CLI 사용:
  python read_tc_inventory.py --source-sheet=<ID|URL> --source-tab='03_파드' \\
      --target-sheet=<ID|URL> --target-tab='03_파드_예외' \\
      --out-dir=_workspace/augment
  python read_tc_inventory.py --source-tsv=rows.tsv --out-dir=_workspace/augment
  python read_tc_inventory.py --selftest

  --source-tab: 여러 번 지정 가능 (탭마다 읽고 합산한다)
  --source-tsv: 로컬 TSV(헤더 포함) 입력 — 시트 접근 없이 검증할 때
  --target-sheet / --target-tab: 생략 가능 (생략 시 대상 탭 실측을 건너뛴다)
  --formats-dir: 사양 디렉터리 (기본 `.claude/formats`)
  --out-dir: 산출물 디렉터리 (기본 `_workspace/augment`)
  --selftest: 심어 둔 상황이 전부 잡히는지 자기검증 (사양을 고친 뒤 실행)

종료 코드: 0 정상 / 2 Critical 있음 / 3 실행 오류

⚠️ 규칙은 **사양 파일에서 파싱**한다. 헤더 원문·`솔루션` 고정값·파생 태그 접두를
   스크립트에 박지 않는다. 파싱 실패 시 하드코딩으로 넘어가지 않고 즉시 실패한다
   (종료 코드 3) — 낡은 값으로 조용히 집계하는 것이 집계를 안 하는 것보다 해롭다.

⚠️ 이 스크립트가 **판정하지 않는 것** (에이전트·리뷰어가 봐야 한다):
   어떤 예외 유형이 이 기능에 적용되는가 · 중복 여부의 의미 판정 ·
   권한 자료의 기능 ↔ 원본 기능 단위 매핑 · 케이스 문안
"""

from __future__ import annotations

import json
import os
import re
import sys

CRITICAL, MAJOR = "Critical", "Major"


class SpecParseError(RuntimeError):
    """사양에서 규칙을 읽지 못했다. 하드코딩 폴백 금지 — 그대로 실패시킨다."""


# ─────────────────────────────────────────────── selftest

def _fixture(tmp: str) -> str:
    """사양 파서 검증용 최소 사양 디렉터리를 만든다.

    **실제 사양값(23컬럼·`VIOLA` 등)을 테스트에 박지 않는다.** 파서가 사양을
    읽는지만 확인해야 하므로, 픽스처는 실제와 다른 5컬럼·다른 솔루션명을 쓴다.
    실제값을 박으면 사양이 바뀔 때 테스트가 사양을 거스르게 된다.
    """
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "common.md"), "w", encoding="utf-8") as f:
        f.write(
            "## 컬럼 구조\n\n"
            "### 헤더 원문 (탭 문자 구분)\n\n"
            "```\nNo\t솔루션\t기능테스트 ID\t비고\t피드백\n```\n\n"
            "## 파생 케이스의 원천\n\n"
            "**파생 태그 접두 (스크립트 파싱 대상):**\n\n"
            "```\n[테스트 파생\n[테스트 매트릭스\n```\n"
        )
    with open(os.path.join(tmp, "profile-fixt.md"), "w", encoding="utf-8") as f:
        f.write(
            "## 제품 고유 값\n\n"
            "| 항목 | 값 |\n|---|---|\n"
            "| `솔루션`(B) | **`FIXTURE`** | 강조만 있는 행 — 잡히면 안 된다 |\n"
            "| **`솔루션`(B)** | **`FIXTPROD` 단일값 고정.** 접미사 금지 |\n"
        )
    return tmp


def selftest() -> int:
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="tcinv_")
    fails: list[str] = []

    def check(name: str, cond: bool, got=None) -> None:
        if cond:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name}" + (f" — got {got!r}" if got is not None else ""))
            fails.append(name)

    try:
        fdir = _fixture(os.path.join(tmp, "formats"))

        print("── 사양 파싱 ─────────────────────────────────")
        h = spec_header(fdir)
        check("S1 헤더 원문을 사양에서 읽는다",
              h == ["No", "솔루션", "기능테스트 ID", "비고", "피드백"], h)

        p = derived_prefixes(fdir)
        check("S2 파생 태그 접두를 사양에서 읽는다",
              p == ["[테스트 파생", "[테스트 매트릭스"], p)

        s = profile_solutions(fdir)
        check("S3 솔루션 고정값 → 프로파일 이름", s == {"FIXTPROD": "fixt"}, s)

        print("── 파싱 실패 시 즉시 실패 (하드코딩 폴백 금지) ──")
        bad = os.path.join(tmp, "bad")
        os.makedirs(bad, exist_ok=True)
        open(os.path.join(bad, "common.md"), "w", encoding="utf-8").write("## 빈 사양\n")
        open(os.path.join(bad, "profile-x.md"), "w", encoding="utf-8").write("## 빈 프로파일\n")
        for name, fn in (
            ("S4 헤더 원문 없음 → SpecParseError", lambda: spec_header(bad)),
            ("S5 파생 태그 접두 없음 → SpecParseError", lambda: derived_prefixes(bad)),
            ("S6 솔루션 고정값 없음 → SpecParseError", lambda: profile_solutions(bad)),
        ):
            try:
                fn()
                check(name, False, "예외가 나지 않았다")
            except SpecParseError:
                check(name, True)

        print("── 실제 사양으로도 파싱된다 ─────────────────")
        real = os.path.join(".claude", "formats")
        if os.path.isdir(real):
            rh = spec_header(real)
            check("S7 실제 사양 헤더 파싱 (컬럼 수 > 20)", len(rh) > 20, len(rh))
            rp = derived_prefixes(real)
            check("S8 실제 사양 파생 태그 접두 2종 이상", len(rp) >= 2, rp)
            rs = profile_solutions(real)
            check("S9 실제 프로파일 전부에서 솔루션값 파싱",
                  len(rs) >= 3 and all(v for v in rs.values()), rs)
        else:
            print("  skip  실제 사양 디렉터리 없음 (프로젝트 루트에서 실행하라)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print(f"FAIL — {len(fails)}건: " + ", ".join(fails))
        return 1
    print("PASS — selftest 통과")
    return 0


def main(argv: list[str]) -> int:
    opts: dict = {}
    tabs: list[str] = []
    for a in argv[1:]:
        if not a.startswith("--"):
            print(f"오류: 위치 인자를 받지 않는다: {a}", file=sys.stderr)
            return 3
        k, _, v = a.partition("=")
        if k == "--source-tab":
            tabs.append(v)
        else:
            opts[k] = v or True
    opts["--source-tab"] = tabs

    if opts.get("--selftest"):
        return selftest()

    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 2: selftest를 돌려 실패를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `NameError: name 'spec_header' is not defined` 로 죽는다 (아직 구현이 없다).

- [ ] **Step 3: 사양 파서 3개를 구현**

`class SpecParseError` 정의 **다음**, `# ─── selftest` 주석 **앞에** 아래를 삽입한다.

```python
# ─────────────────────────────────────────────── 사양 파싱

def _cells(line: str) -> list[str]:
    """마크다운 표 한 줄을 셀 목록으로."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(text: str) -> str:
    """마크다운 강조(`**`)를 벗긴다. 사양 표는 셀에 강조를 섞어 쓴다."""
    return text.replace("**", "").strip()


def _ticks(text: str) -> list[str]:
    """백틱으로 감싼 토큰 목록."""
    return re.findall(r"`([^`]+)`", text)


def spec_header(formats_dir: str) -> list[str]:
    """`common.md` 의 「헤더 원문」 코드블록에서 컬럼명 목록을 읽는다."""
    path = os.path.join(formats_dir, "common.md")
    md = open(path, encoding="utf-8").read()
    m = re.search(r"### 헤더 원문[^\n]*\n+```\n(.+?)\n```", md, re.S)
    if not m:
        raise SpecParseError(f"{path}: 「헤더 원문」 코드블록을 찾지 못했다")
    cols = [c.strip() for c in m.group(1).split("\t")]
    if len(cols) < 2 or not all(cols):
        raise SpecParseError(f"{path}: 「헤더 원문」을 컬럼으로 나누지 못했다: {cols!r}")
    return cols


def derived_prefixes(formats_dir: str) -> list[str]:
    """`common.md` 「파생 케이스의 원천」 절의 파생 태그 접두 목록.

    접두를 스크립트에 박지 않는 이유: 태그 이름이 바뀌었는데 스크립트가 모르면
    그 태그가 붙은 행이 원본으로 다시 읽혀 **파생의 파생**이 생긴다.
    """
    path = os.path.join(formats_dir, "common.md")
    md = open(path, encoding="utf-8").read()
    m = re.search(
        r"\*\*파생 태그 접두 \(스크립트 파싱 대상\):\*\*\s*\n+```\n(.+?)\n```", md, re.S
    )
    if not m:
        raise SpecParseError(f"{path}: 「파생 태그 접두」 코드블록을 찾지 못했다")
    pref = [ln.strip() for ln in m.group(1).split("\n") if ln.strip()]
    if not pref:
        raise SpecParseError(f"{path}: 「파생 태그 접두」 코드블록이 비어 있다")
    return pref


def profile_solutions(formats_dir: str) -> dict[str, str]:
    """{`솔루션` 고정값: 프로파일 이름}.

    「제품 고유 값」 표에서 `솔루션` 행의 **「단일값 고정」 문구가 있는 행**만 읽는다.
    `profile-bootfactory.md` 처럼 같은 컬럼을 두 번 언급하는 파일이 있어,
    문구로 가려내지 않으면 근거 서술 행이 먼저 잡힌다.
    """
    out: dict[str, str] = {}
    for fn in sorted(os.listdir(formats_dir)):
        if not (fn.startswith("profile-") and fn.endswith(".md")):
            continue
        name = fn[len("profile-"):-len(".md")]
        md = open(os.path.join(formats_dir, fn), encoding="utf-8").read()
        val = ""
        for line in md.splitlines():
            c = _cells(line)
            if len(c) < 2 or "솔루션" not in c[0]:
                continue
            if "단일값 고정" not in _plain(c[1]):
                continue
            t = _ticks(c[1])
            if t:
                val = t[0]
                break
        if not val:
            raise SpecParseError(f"{fn}: `솔루션` 단일값 고정값을 읽지 못했다")
        out[val] = name
    if not out:
        raise SpecParseError(f"{formats_dir}: profile-*.md 를 찾지 못했다")
    return out
```

- [ ] **Step 4: selftest를 돌려 통과를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `S1`~`S9` 전부 `ok` + `PASS — selftest 통과` + 종료 코드 `0`

`S9` 가 실패하면 프로파일 중 하나의 `솔루션` 행 문구가 「단일값 고정」과 다르다는 뜻이다. 그 파일을 직접 열어 표기를 확인하고 **파서를 실제 표기에 맞춘다** (사양을 파서에 맞춰 고치지 않는다).

- [ ] **Step 5: 커밋**

```bash
git add .claude/skills/testcase-augment/scripts/read_tc_inventory.py
git commit -m "$(cat <<'EOF'
스크립트: read_tc_inventory 사양 파서 + selftest 골격

헤더 원문·파생 태그 접두·솔루션 고정값을 사양에서 파싱하고, 실패하면
하드코딩 폴백 없이 종료한다. selftest 픽스처에는 실제 사양값을 쓰지
않았다 — 실제값을 박으면 사양이 바뀔 때 테스트가 사양을 거스른다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `read_tc_inventory.py` — 인벤토리 집계

**Files:**
- Modify: `.claude/skills/testcase-augment/scripts/read_tc_inventory.py`
- Test: 같은 파일의 `--selftest` (케이스 `S10`~`S17` 추가)

**Interfaces:**
- Consumes: Task 2의 `spec_header` · `derived_prefixes` · `profile_solutions` · `_cells` · `_plain` · `_ticks` · `selftest`
- Produces:
  - `header_mismatch(actual: list, spec: list[str]) -> str | None`
  - `tcid_max_by_prefix(tcids: list[str]) -> dict[str, dict]` — `{접두: {"max": int, "digits": int, "next": str}}`
  - `build_inventory(header, tabs, prefixes, solutions) -> dict` — `tabs` 는 `[(탭명, [행,…]), …]`
  - `findings(inv, src_header_issue, tgt_header_issue) -> list[dict]`
  - `exit_code(finds) -> int`

- [ ] **Step 1: 실패하는 selftest 케이스를 먼저 추가**

`selftest()` 의 `print("── 실제 사양으로도 파싱된다 …")` 블록 **앞에** 아래를 삽입한다.

```python
        print("── 헤더 대조 ─────────────────────────────────")
        check("S10 헤더 일치 → None",
              header_mismatch(["No", "솔루션", "기능테스트 ID", "비고", "피드백"], h) is None)
        check("S11 꼬리 빈칸은 무시한다",
              header_mismatch(
                  ["No", "솔루션", "기능테스트 ID", "비고", "피드백", "", ""], h) is None)
        mm = header_mismatch(["No", "솔루션", "기능테스트 ID", "비고"], h)
        check("S12 컬럼 수 불일치를 잡는다", mm is not None and "컬럼 수" in mm, mm)
        mm = header_mismatch(["No", "솔루션", "기능테스트ID", "비고", "피드백"], h)
        check("S13 컬럼명 불일치를 위치와 함께 잡는다",
              mm is not None and "3번째" in mm, mm)

        print("── TC ID 최대값 ──────────────────────────────")
        t = tcid_max_by_prefix(["TC_VIO_007", "TC_VIO_010", "TC_VIO_009"])
        check("S14 자릿수가 아니라 수치로 비교한다",
              t["TC_VIO_"]["next"] == "TC_VIO_011", t)
        t = tcid_max_by_prefix(["TC_AAA_003", "TC_BBB_012"])
        check("S15 접두별로 따로 센다 (TROMBONE 모듈별 연속)",
              t["TC_AAA_"]["next"] == "TC_AAA_004"
              and t["TC_BBB_"]["next"] == "TC_BBB_013", t)

        print("── 인벤토리 집계 ─────────────────────────────")
        hdr = ["기능테스트 ID", "솔루션", "화면 ID", "우선순위", "구분",
               "1 Depth", "2 Depth", "3 Depth", "절차", "예상 결과", "비고"]

        def r(tc, sol, scr, pri, cat, d2, d3, note):
            return [tc, sol, scr, pri, cat, "메뉴", d2, d3,
                    f"1. {tc} 절차", f"{tc} 예상 결과", note]

        rows = [
            r("TC_F_001", "FIXTPROD", "SC-01", "P3", "표시", "목록 화면", "목록", "[DESC 1항]"),
            r("TC_F_002", "FIXTPROD", "SC-01", "P3", "표시", "목록 화면", "목록", "[DESC 2항]"),
            r("TC_F_003", "FIXTPROD", "SC-01", "P2", "비정상", "목록 화면", "목록", "[DESC 3항]"),
            r("TC_F_004", "FIXTPROD", "SC-02", "P1", "정상", "생성 화면", "생성", "[DESC 1항]"),
            # 파생 태그 행 — 원본에서 제외되고 커버리지에만 남아야 한다
            r("TC_F_005", "FIXTPROD", "SC-01", "P2", "비정상", "목록 화면", "목록",
              "[테스트 파생 TC_F_003] 서버 오류"),
            [""] * len(hdr),                      # 빈 행은 세지 않는다
        ]
        inv = build_inventory(hdr, [("탭A", rows)], p, s)

        check("S16 빈 행을 세지 않는다", inv["total_rows"] == 5, inv["total_rows"])
        check("S17 파생 태그 행을 원본에서 제외한다",
              (inv["derived_rows"], inv["source_rows"]) == (1, 4),
              (inv["derived_rows"], inv["source_rows"]))
        u = {(x["screen_id"], x["d3"]): x for x in inv["units"]}
        check("S18 화면 ID + 2/3 Depth 로 기능 단위를 묶는다", len(inv["units"]) == 2,
              len(inv["units"]))
        check("S19 커버리지 맵은 파생분까지 센다 (중복 제거의 근거)",
              u[("SC-01", "목록")]["coverage"] == {"표시": 2, "비정상": 2},
              u[("SC-01", "목록")]["coverage"])
        check("S20 원본 케이스 수는 파생분을 뺀 값이다",
              u[("SC-01", "목록")]["source_count"] == 3,
              u[("SC-01", "목록")]["source_count"])
        check("S21 케이스 요약에 절차·예상이 한 줄로 들어간다",
              u[("SC-02", "생성")]["cases"][0]["step"] == "1. TC_F_004 절차",
              u[("SC-02", "생성")]["cases"][0])
        check("S22 솔루션 실측으로 프로파일을 판정한다", inv["profile"] == "fixt",
              inv["profile"])

        print("── 판정 (Critical / Major) ───────────────────")
        f0 = findings(inv, None, None)
        check("S23 정상 입력에서 오탐 0건", f0 == [], f0)

        mixed = rows[:3] + [r("TC_G_001", "OTHERSOL", "SC-03", "P3", "표시",
                              "다른 화면", "목록", "[DESC 1항]")]
        inv_m = build_inventory(hdr, [("탭A", mixed)], p, s)
        f = findings(inv_m, None, None)
        check("S24 솔루션 혼재를 Major로 보고한다",
              any(x["code"] == "SOL_MIX" and x["level"] == MAJOR for x in f), f)

        inv_u = build_inventory(hdr, [("탭A", [r("TC_H_001", "UNKNOWNSOL", "SC-01",
                                                 "P3", "표시", "목록 화면", "목록",
                                                 "[DESC 1항]")])], p, s)
        f = findings(inv_u, None, None)
        check("S25 프로파일에 없는 솔루션값은 Critical",
              any(x["code"] == "NO_PROFILE" and x["level"] == CRITICAL for x in f), f)

        inv_d = build_inventory(hdr, [("탭A", [rows[4]])], p, s)
        f = findings(inv_d, None, None)
        check("S26 원본 케이스 0건(전부 파생분)은 Critical",
              any(x["code"] == "NO_SOURCE" and x["level"] == CRITICAL for x in f), f)
        check("S27 Critical 이 있으면 종료 코드 2", exit_code(f) == 2, exit_code(f))

        f = findings(inv, "컬럼 수 22개 ≠ 사양 23개", None)
        check("S28 원본 탭 헤더 불일치는 Critical",
              any(x["code"] == "SRC_HEADER" and x["level"] == CRITICAL for x in f), f)
        f = findings(inv, None, "3번째 `X` ≠ 사양 `기능테스트 ID`")
        check("S29 대상 탭 헤더 불일치도 Critical",
              any(x["code"] == "TGT_HEADER" and x["level"] == CRITICAL for x in f), f)
        check("S30 Major 만 있으면 종료 코드 0 (진행 가능)",
              exit_code(findings(inv_m, None, None)) == 0)
```

- [ ] **Step 2: selftest를 돌려 실패를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `S1`~`S9` 는 `ok`, 이어서 `NameError: name 'header_mismatch' is not defined`

- [ ] **Step 3: 집계 함수 5개를 구현**

`profile_solutions` 정의 **다음**, `# ─── selftest` 주석 **앞에** 아래를 삽입한다.

```python
# ─────────────────────────────────────────────── 인벤토리 집계

def header_mismatch(actual: list, spec: list[str]) -> str | None:
    """대상 헤더가 사양과 다르면 사람이 읽을 차이 설명, 같으면 None."""
    a = [str(c).strip() for c in actual]
    while a and not a[-1]:
        a.pop()
    if a == spec:
        return None
    if len(a) != len(spec):
        return f"컬럼 수 {len(a)}개 ≠ 사양 {len(spec)}개"
    diff = [
        f"{i + 1}번째 `{x}` ≠ 사양 `{y}`"
        for i, (x, y) in enumerate(zip(a, spec))
        if x != y
    ]
    return " / ".join(diff)


def tcid_max_by_prefix(tcids: list[str]) -> dict[str, dict]:
    """관측된 TC ID를 **접두별로** 묶어 최대값과 다음 번호를 낸다.

    프로파일에서 ID 형식을 파싱하지 않는 이유: TROMBONE은 `TC_{모듈코드}_{3자리}`
    로 **모듈별 연속**이고 VIOLA는 제품 전역 연속이다. 접두별로 세면 두 체계를
    한 코드로 다룰 수 있고, 어느 접두를 쓸지는 프로파일 규칙을 아는 쪽이 고른다.
    """
    out: dict[str, dict] = {}
    for t in tcids:
        m = re.match(r"^(.*?)(\d+)$", str(t).strip())
        if not m:
            continue
        pre, num = m.group(1), m.group(2)
        e = out.setdefault(pre, {"max": 0, "digits": len(num)})
        e["max"] = max(e["max"], int(num))
        e["digits"] = max(e["digits"], len(num))
    for pre, e in out.items():
        e["next"] = f"{pre}{e['max'] + 1:0{e['digits']}d}"
    return out


def _idx(header: list[str], name: str) -> int:
    try:
        return header.index(name)
    except ValueError:
        raise SpecParseError(f"헤더에 `{name}` 컬럼이 없다: {header!r}") from None


def _cell(row: list, i: int) -> str:
    return str(row[i]).strip() if i < len(row) else ""


def _one_line(s: str, limit: int = 60) -> str:
    """첫 줄만 남기고 길면 자른다. 인벤토리는 원본 전문을 담지 않는다."""
    t = s.replace("\r", "\n").split("\n")[0].strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def build_inventory(header: list[str], tabs: list, prefixes: list[str],
                    solutions: dict[str, str]) -> dict:
    """기능 단위 인벤토리 + 기존 커버리지 맵.

    `tabs`: `[(탭명, [데이터 행, …]), …]` — 헤더 행은 제외하고 넘긴다.

    기능 단위 키는 **`화면 ID` + `2 Depth` + `3 Depth`** 다. 시트에서 케이스를
    식별하는 축이 그 셋이므로, 파생 케이스가 어느 원본에 붙는지 이 키로 정해진다.
    """
    i_sol = _idx(header, "솔루션")
    i_tc = _idx(header, "기능테스트 ID")
    i_scr = _idx(header, "화면 ID")
    i_pri = _idx(header, "우선순위")
    i_cat = _idx(header, "구분")
    i_d1 = _idx(header, "1 Depth")
    i_d2 = _idx(header, "2 Depth")
    i_d3 = _idx(header, "3 Depth")
    i_step = _idx(header, "절차")
    i_exp = _idx(header, "예상 결과")
    i_note = _idx(header, "비고")

    units: dict[tuple, dict] = {}
    sol_count: dict[str, int] = {}
    all_tcids: list[str] = []
    total = derived = 0

    for tab, rows in tabs:
        for row in rows:
            if not any(str(c).strip() for c in row):
                continue                                    # 빈 행은 세지 않는다
            total += 1
            sol = _cell(row, i_sol)
            if sol:
                sol_count[sol] = sol_count.get(sol, 0) + 1
            tcid = _cell(row, i_tc)
            if tcid:
                all_tcids.append(tcid)

            key = (_cell(row, i_scr), _cell(row, i_d2), _cell(row, i_d3))
            u = units.setdefault(key, {
                "screen_id": key[0],
                "d1": _cell(row, i_d1),
                "d2": key[1],
                "d3": key[2],
                "tabs": [],
                "source_count": 0,
                "coverage": {},
                "cases": [],
            })
            if tab not in u["tabs"]:
                u["tabs"].append(tab)

            cat = _cell(row, i_cat)
            # 커버리지는 **파생분까지** 센다 — 중복 제거의 근거이기 때문이다
            u["coverage"][cat] = u["coverage"].get(cat, 0) + 1

            if any(pre in _cell(row, i_note) for pre in prefixes):
                derived += 1
                continue                     # 파생분은 원본 목록에 넣지 않는다
            u["source_count"] += 1
            u["cases"].append({
                "tc_id": tcid,
                "category": cat,
                "priority": _cell(row, i_pri),
                "step": _one_line(_cell(row, i_step)),
                "expected": _one_line(_cell(row, i_exp)),
            })

    profile, note = None, ""
    if sol_count:
        top = max(sol_count, key=lambda k: sol_count[k])
        profile = solutions.get(top)
        if len(sol_count) > 1:
            listed = ", ".join(
                f"`{k}` {v}행"
                for k, v in sorted(sol_count.items(), key=lambda kv: -kv[1])
            )
            note = f"한 원본에 솔루션값 혼재 — {listed} → 최다값 `{top}` 사용"

    return {
        "total_rows": total,
        "derived_rows": derived,
        "source_rows": total - derived,
        "solution_count": sol_count,
        "profile": profile,
        "solution_note": note,
        "tcid_by_prefix": tcid_max_by_prefix(all_tcids),
        "units": list(units.values()),
    }


def findings(inv: dict, src_header_issue: str | None,
             tgt_header_issue: str | None) -> list[dict]:
    """진행 가능성 판정. Critical 은 작성 착수를 막는다."""
    out: list[dict] = []
    if src_header_issue:
        out.append({"level": CRITICAL, "code": "SRC_HEADER",
                    "msg": f"원본 탭 헤더가 사양과 불일치 — {src_header_issue}. "
                           "원본을 잘못 읽으면 전 파생분이 어긋난다"})
    if tgt_header_issue:
        out.append({"level": CRITICAL, "code": "TGT_HEADER",
                    "msg": f"대상 탭 헤더가 사양과 불일치 — {tgt_header_issue}. "
                           "그냥 append하면 전 값이 밀린다"})
    if inv["source_rows"] == 0:
        out.append({"level": CRITICAL, "code": "NO_SOURCE",
                    "msg": "뒤집을 원본 케이스가 0건 — 전 행이 파생 태그 행이거나 빈 탭이다"})
    if inv["solution_count"] and inv["profile"] is None:
        vals = ", ".join(f"`{k}`" for k in inv["solution_count"])
        out.append({"level": CRITICAL, "code": "NO_PROFILE",
                    "msg": f"프로파일에 없는 솔루션값 {vals} — "
                           "참고 시트로 프로파일 신설(모드 B)이 필요하다"})
    if inv["solution_note"]:
        out.append({"level": MAJOR, "code": "SOL_MIX", "msg": inv["solution_note"]})
    return out


def exit_code(finds: list[dict]) -> int:
    return 2 if any(f["level"] == CRITICAL for f in finds) else 0
```

- [ ] **Step 4: selftest를 돌려 통과를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `S1`~`S30` 전부 `ok` + `PASS — selftest 통과` + 종료 코드 `0`

**`S23`(정상 입력 오탐 0건)이 통과하는지 반드시 본다.** 검출 케이스만 확인하면 판정이 늘 참을 돌려줘도 통과한다.

- [ ] **Step 5: 커밋**

```bash
git add .claude/skills/testcase-augment/scripts/read_tc_inventory.py
git commit -m "$(cat <<'EOF'
스크립트: read_tc_inventory 인벤토리 집계 + 판정

기능 단위 키는 화면 ID + 2/3 Depth 다 — 시트에서 케이스를 식별하는 축과
같아야 파생분이 어느 원본에 붙는지 정해진다.

커버리지 맵은 파생분까지 세고 원본 목록에서는 뺀다. 원본 탭과 대상 탭이
같을 수 있어, 빼지 않으면 재실행 때 파생분에서 또 파생이 나온다.

TC ID 는 프로파일 형식을 파싱하지 않고 접두별 최대값으로 센다 — TROMBONE
모듈별 연속과 VIOLA 전역 연속을 한 코드로 다룰 수 있다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `read_tc_inventory.py` — 시트 I/O · 산출물 렌더 · 심볼릭 링크

**Files:**
- Modify: `.claude/skills/testcase-augment/scripts/read_tc_inventory.py`
- Create: `scripts/read_tc_inventory.py` (심볼릭 링크)
- Test: 같은 파일의 `--selftest` (케이스 `S31`~`S33` 추가) + `--source-tsv` 로 실제 실행

**Interfaces:**
- Consumes: Task 3의 `build_inventory` · `findings` · `exit_code` · `header_mismatch` · `tcid_max_by_prefix`
- Produces:
  - `_find_sheets_api() -> str` / `_sheets_client()`
  - `load_tab(cli, sid, tab) -> tuple[list, list]`
  - `scan_tcids(cli, sid, header) -> list[str]`
  - `read_tsv(path) -> tuple[list[str], list[list[str]]]`
  - `render_md(inv, meta, finds) -> str`
  - 산출물 `10_tc_inventory.md` + `10_tc_inventory.json`

- [ ] **Step 1: 실패하는 selftest 케이스를 먼저 추가**

`selftest()` 의 `print("── 실제 사양으로도 파싱된다 …")` 블록 **앞에** 아래를 삽입한다.

```python
        print("── TSV 입력 · 산출물 렌더 ────────────────────")
        tsv = os.path.join(tmp, "rows.tsv")
        with open(tsv, "w", encoding="utf-8") as fh:
            fh.write("\t".join(hdr) + "\n")
            for row in rows:
                fh.write("\t".join(str(c) for c in row) + "\n")
        th, trows = read_tsv(tsv)
        check("S31 TSV 헤더·행을 읽는다", th == hdr and len(trows) == len(rows),
              (th, len(trows)))

        md = render_md(inv, {"source": "탭A", "target": None,
                             "formats_dir": fdir}, f0)
        check("S32 산출물에 기능 단위 표와 케이스 요약이 있다",
              "## 기능 단위" in md and "TC_F_004" in md, md[:200])
        check("S33 산출물에 원본 전문을 담지 않는다 (한 줄 요약만)",
              md.count("TC_F_001 예상 결과") == 1, md.count("TC_F_001 예상 결과"))
```

- [ ] **Step 2: selftest를 돌려 실패를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `S30` 까지 `ok`, 이어서 `NameError: name 'read_tsv' is not defined`

- [ ] **Step 3: 시트 I/O · TSV 입력 · 렌더 함수를 구현**

`exit_code` 정의 **다음**, `# ─── selftest` 주석 **앞에** 아래를 삽입한다.

```python
# ─────────────────────────────────────────────── 입력 (시트 / TSV)

def _find_sheets_api() -> str:
    """`sheets_api.py` 가 있는 디렉터리를 찾는다.

    이 파일은 루트 `scripts/` 에 심볼릭 링크로도 노출된다. `__file__` 은 호출
    경로를 가리키므로 링크 경유와 원본 경유에서 상대 경로가 달라진다.
    두 기점에서 위로 올라가며 실제 파일을 찾는다 (`verify_sheet_rows.py` 와 동일).
    """
    starts = {
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.realpath(__file__)),
        os.getcwd(),
    }
    rels = (
        ("sheets_api.py",),
        ("scripts", "sheets_api.py"),
        (".claude", "skills", "sheet-operator", "scripts", "sheets_api.py"),
        ("..", "..", "sheet-operator", "scripts", "sheets_api.py"),
    )
    for start in starts:
        cur = start
        for _ in range(6):
            for rel in rels:
                cand = os.path.join(cur, *rel)
                if os.path.isfile(cand):
                    return os.path.dirname(os.path.abspath(cand))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    raise RuntimeError(
        "sheets_api.py 를 찾지 못했다. 프로젝트 루트에서 실행하거나 --source-tsv 를 쓰십시오."
    )


def _sheets_client():
    sys.path.insert(0, _find_sheets_api())
    from sheets_api import SheetsClient  # type: ignore

    return SheetsClient


def load_tab(cli, sid: str, tab: str) -> tuple[list, list]:
    """(헤더 행, 데이터 행). 탭명은 호출자가 `metadata` 의 `title` 을 그대로 넘긴다."""
    head = cli.read(sid, f"'{tab}'!1:1")
    head = head[0] if head else []
    data = cli.read(sid, f"'{tab}'!2:100000")
    return head, data


def scan_tcids(cli, sid: str, header: list[str]) -> list[str]:
    """스프레드시트 **전 탭**에서 `기능테스트 ID` 컬럼만 읽는다.

    대상 탭의 마지막 값만 보면 다른 탭에 더 큰 값이 있을 때 중복이 난다
    (VIOLA는 탭 경계를 무시하고 제품 전역 연속이다). 컬럼 하나만 읽으므로
    전 탭을 훑어도 비용이 작다.
    """
    i = _idx(header, "기능테스트 ID")
    if i >= 26:
        raise RuntimeError(f"`기능테스트 ID` 열 위치가 Z를 넘는다: {i}")
    col = chr(ord("A") + i)
    out: list[str] = []
    for s in cli.get_metadata(sid).get("sheets", []):
        title = s.get("title")
        if not title:
            continue
        try:
            vals = cli.read(sid, f"'{title}'!{col}2:{col}100000")
        except Exception:
            continue                    # 보호된 탭 등은 건너뛴다 (최대값 실측은 최선 노력)
        out += [str(r[0]).strip() for r in vals if r and str(r[0]).strip()]
    return out


def read_tsv(path: str) -> tuple[list[str], list[list[str]]]:
    """헤더를 포함한 로컬 TSV. 시트 접근 없이 검증할 때 쓴다."""
    lines = open(path, encoding="utf-8").read().split("\n")
    rows = [ln.split("\t") for ln in lines if ln.strip()]
    if not rows:
        raise RuntimeError(f"{path}: 빈 파일")
    return [c.strip() for c in rows[0]], rows[1:]


# ─────────────────────────────────────────────── 산출물

def render_md(inv: dict, meta: dict, finds: list[dict]) -> str:
    """`10_tc_inventory.md` — 사람과 에이전트가 읽는 산출물.

    **원본 케이스 전문(절차·예상 결과)을 담지 않는다.** 검증 목표 한 줄이면
    뒤집기와 중복 판정에 충분하고, 전문을 담으면 원본 탭을 그대로 복사한 것이
    되어 「에이전트에게 시트를 읽히지 않는다」는 목적이 사라진다.
    """
    L: list[str] = ["# 원본 TC 인벤토리", ""]
    L.append(f"- 원본: {meta.get('source')}")
    L.append(f"- 대상: {meta.get('target') or '(지정 없음 — 번호 실측 건너뜀)'}")
    L.append(f"- 사양: {meta.get('formats_dir')}")
    L.append(f"- 전체 {inv['total_rows']}행 / 원본 {inv['source_rows']}행 "
             f"/ 파생 태그 행 제외 {inv['derived_rows']}행")
    sol = ", ".join(f"`{k}` {v}행" for k, v in inv["solution_count"].items()) or "(없음)"
    L.append(f"- `솔루션` 실측: {sol} → 프로파일 **{inv['profile'] or '판정 불가'}**")
    for pre, e in sorted(inv["tcid_by_prefix"].items()):
        L.append(f"- TC ID 접두 `{pre}` 최대 {e['max']} → 다음 **`{e['next']}`**")
    L.append("")

    L.append("## 판정")
    L.append("")
    if finds:
        L.append("| 등급 | 코드 | 내용 |")
        L.append("|------|------|------|")
        for f in finds:
            L.append(f"| {f['level']} | `{f['code']}` | {f['msg']} |")
        if any(f["level"] == CRITICAL for f in finds):
            L.append("")
            L.append("> **Critical 이 있다. 케이스 작성에 착수하지 않는다** — "
                     "사용자 확인이 먼저다.")
    else:
        L.append("판정 사항 없음 (Critical 0 / Major 0)")
    L.append("")

    L.append("## 기능 단위")
    L.append("")
    L.append("| 순번 | 화면 ID | 1 Depth | 2 Depth | 3 Depth | 원본 | 기존 구분 커버리지 | 출처 탭 |")
    L.append("|------|---------|---------|---------|---------|------|-----------------|--------|")
    for n, u in enumerate(inv["units"], 1):
        cov = " / ".join(f"{k} {v}" for k, v in sorted(
            u["coverage"].items(), key=lambda kv: -kv[1]) if k) or "-"
        L.append(f"| {n:02d} | {u['screen_id']} | {u['d1']} | {u['d2']} | {u['d3']} "
                 f"| {u['source_count']} | {cov} | {', '.join(u['tabs'])} |")
    L.append("")

    L.append("## 기능 단위별 원본 케이스 (검증 목표 한 줄 — 전문 아님)")
    L.append("")
    for n, u in enumerate(inv["units"], 1):
        L.append(f"### {n:02d} · {u['screen_id']} / {u['d2']} / {u['d3']}")
        L.append("")
        if not u["cases"]:
            L.append("- (원본 케이스 없음 — 전 행이 파생 태그 행이다)")
        for c in u["cases"]:
            L.append(f"- {c['tc_id']} [{c['category']} {c['priority']}] "
                     f"절차: {c['step']} / 예상: {c['expected']}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"
```

- [ ] **Step 4: `main()` 을 실제 실행 경로로 교체**

Task 2에서 넣은 `main()` 의 `print(__doc__)` / `return 3` 두 줄을 아래로 교체한다 (`--selftest` 분기는 그대로 둔다).

```python
    fdir = opts.get("--formats-dir") or os.path.join(".claude", "formats")
    out_dir = opts.get("--out-dir") or os.path.join("_workspace", "augment")
    if not isinstance(fdir, str) or not os.path.isdir(fdir):
        print(f"오류: 사양 디렉터리가 없다: {fdir}", file=sys.stderr)
        return 3

    src_sheet = opts.get("--source-sheet")
    src_tsv = opts.get("--source-tsv")
    src_tabs = opts.get("--source-tab") or []
    if not (isinstance(src_tsv, str) or (isinstance(src_sheet, str) and src_tabs)):
        print("오류: --source-tsv 또는 (--source-sheet + --source-tab) 이 필요하다\n",
              file=sys.stderr)
        print(__doc__)
        return 3

    try:
        spec = spec_header(fdir)
        prefixes = derived_prefixes(fdir)
        solutions = profile_solutions(fdir)
    except (SpecParseError, OSError) as e:
        print(f"오류(사양 파싱): {e}", file=sys.stderr)
        return 3

    tabs: list = []
    src_issue = tgt_issue = None
    all_tcids: list[str] = []
    meta = {"formats_dir": fdir, "target": None}

    try:
        if isinstance(src_tsv, str):
            head, rows = read_tsv(src_tsv)
            src_issue = header_mismatch(head, spec)
            tabs.append((os.path.basename(src_tsv), rows))
            meta["source"] = f"{src_tsv} (로컬 TSV)"
        else:
            Client = _sheets_client()
            cli = Client()
            sid = Client.extract_id(src_sheet)
            for tab in src_tabs:
                head, rows = load_tab(cli, sid, tab)
                issue = header_mismatch(head, spec)
                if issue and not src_issue:
                    src_issue = f"탭 `{tab}` — {issue}"
                tabs.append((tab, rows))
            meta["source"] = f"{src_sheet} / 탭 {', '.join(src_tabs)}"
            all_tcids += scan_tcids(cli, sid, spec)

            tgt_sheet, tgt_tab = opts.get("--target-sheet"), opts.get("--target-tab")
            if isinstance(tgt_sheet, str) and isinstance(tgt_tab, str):
                tsid = Client.extract_id(tgt_sheet)
                titles = [s.get("title") for s in cli.get_metadata(tsid).get("sheets", [])]
                meta["target"] = f"{tgt_sheet} / 탭 {tgt_tab}"
                if tgt_tab in titles:
                    thead, trows = load_tab(cli, tsid, tgt_tab)
                    if any(str(c).strip() for c in thead):
                        tgt_issue = header_mismatch(thead, spec)
                    meta["target"] += f" (기존 {len(trows)}행)"
                else:
                    meta["target"] += " (미존재 — Phase 2에서 생성)"
                if tsid != sid:
                    all_tcids += scan_tcids(cli, tsid, spec)
    except SpecParseError as e:
        print(f"오류(사양 파싱): {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"오류(입력 읽기): {e}", file=sys.stderr)
        return 3

    # 헤더가 사양과 다르면 컬럼 위치를 신뢰할 수 없다 — 집계하지 않고 보고만 한다.
    if src_issue:
        empty = {"total_rows": 0, "derived_rows": 0, "source_rows": 0,
                 "solution_count": {}, "profile": None, "solution_note": "",
                 "tcid_by_prefix": {}, "units": []}
        finds = findings(empty, src_issue, tgt_issue)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "10_tc_inventory.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_md(empty, meta, finds))
        for fd in finds:
            print(f"{fd['level']}  {fd['code']}  {fd['msg']}")
        print(f"\n{path} 생성 — 헤더 불일치로 집계를 건너뛰었다")
        return 2

    inv = build_inventory(spec, tabs, prefixes, solutions)
    # 시트 전 탭 실측이 있으면 그 값을 합쳐 다음 번호를 다시 낸다
    if all_tcids:
        merged = tcid_max_by_prefix(
            all_tcids + [c["tc_id"] for u in inv["units"] for c in u["cases"]])
        inv["tcid_by_prefix"] = merged

    finds = findings(inv, src_issue, tgt_issue)

    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "10_tc_inventory.md")
    js_path = os.path.join(out_dir, "10_tc_inventory.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(inv, meta, finds))
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "inventory": inv, "findings": finds},
                  f, ensure_ascii=False, indent=2)

    for fd in finds:
        print(f"{fd['level']}  {fd['code']}  {fd['msg']}")
    print(f"\n{md_path} / {js_path} 생성")
    print(f"기능 단위 {len(inv['units'])}개 · 원본 {inv['source_rows']}행 "
          f"· 파생 태그 행 제외 {inv['derived_rows']}행 "
          f"· 프로파일 {inv['profile'] or '판정 불가'}")
    return exit_code(finds)
```

- [ ] **Step 5: selftest를 돌려 통과를 확인**

Run: `python3 .claude/skills/testcase-augment/scripts/read_tc_inventory.py --selftest`
Expected: `S1`~`S33` 전부 `ok` + `PASS`

- [ ] **Step 6: 심볼릭 링크를 만든다 (이 저장소의 스크립트 노출 관행)**

Run:
```bash
ln -s ../.claude/skills/testcase-augment/scripts/read_tc_inventory.py scripts/read_tc_inventory.py
ls -l scripts/read_tc_inventory.py
python3 scripts/read_tc_inventory.py --selftest | tail -3
```
Expected: 링크가 걸리고, 링크 경유 실행에서도 `PASS`

- [ ] **Step 7: 실제 TSV로 산출물을 만들어 눈으로 확인**

Run:
```bash
mkdir -p /tmp/tcaug && python3 - <<'EOF'
import os, sys
sys.path.insert(0, ".claude/skills/testcase-augment/scripts")
from read_tc_inventory import spec_header
h = spec_header(".claude/formats")
def row(tc, cat, pri, d2, d3, note):
    v = [""] * len(h)
    for k, val in (("No", "1"), ("솔루션", "VIOLA"), ("기능테스트 ID", tc),
                   ("화면 ID", "VIOE-03_01_01-01"), ("우선순위", pri), ("구분", cat),
                   ("1 Depth", "Kubernetes Engine"), ("2 Depth", d2), ("3 Depth", d3),
                   ("4 Depth", "-"), ("5 Depth", "-"), ("사전조건", "목록 화면 진입"),
                   ("절차", f"1. `{d2}` 확인"), ("예상 결과", f"{tc} 표출"), ("비고", note)):
        v[h.index(k)] = val
    return v
rows = [row("TC_VIO_001", "표시", "P3", "파드 목록", "목록", "[DESC 1항]"),
        row("TC_VIO_002", "표시", "P3", "파드 목록", "목록", "[DESC 2항]"),
        row("TC_VIO_003", "정상", "P2", "파드 생성", "생성", "[DESC 1항]"),
        row("TC_VIO_004", "비정상", "P2", "파드 생성", "생성",
            "[예외 파생 TC_VIO_003] 필수값 누락")]
with open("/tmp/tcaug/rows.tsv", "w", encoding="utf-8") as f:
    f.write("\t".join(h) + "\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
print("fixture 작성 완료")
EOF
python3 scripts/read_tc_inventory.py --source-tsv=/tmp/tcaug/rows.tsv --out-dir=/tmp/tcaug/out
cat /tmp/tcaug/out/10_tc_inventory.md
```
Expected:
- 종료 코드 `0`, 판정 `Critical 0 / Major 0`
- `솔루션` 실측 `` `VIOLA` 4행 `` → 프로파일 **viola**
- 파생 태그 행 제외 **1행**, 원본 **3행**
- 기능 단위 **2개** (`파드 목록 / 목록`, `파드 생성 / 생성`)
- `파드 생성 / 생성` 의 커버리지가 `정상 1 / 비정상 1`, 원본은 `1`
- TC ID 접두 `TC_VIO_` 최대 `4` → 다음 `` `TC_VIO_005` ``

- [ ] **Step 8: 헤더 불일치가 실제로 Critical 로 잡히는지 확인**

Run:
```bash
python3 -c "
p='/tmp/tcaug/rows.tsv'; s=open(p,encoding='utf-8').read().split('\n')
s[0]=s[0].replace('기능테스트 ID','기능테스트ID'); open('/tmp/tcaug/bad.tsv','w',encoding='utf-8').write('\n'.join(s))"
python3 scripts/read_tc_inventory.py --source-tsv=/tmp/tcaug/bad.tsv --out-dir=/tmp/tcaug/bad; echo "exit=$?"
```
Expected: `Critical  SRC_HEADER  원본 탭 헤더가 사양과 불일치 — 3번째 …` + `헤더 불일치로 집계를 건너뛰었다` + `exit=2`

- [ ] **Step 9: 커밋**

```bash
rm -rf /tmp/tcaug
git add .claude/skills/testcase-augment/scripts/read_tc_inventory.py scripts/read_tc_inventory.py
git commit -m "$(cat <<'EOF'
스크립트: read_tc_inventory 시트 I/O·산출물 렌더 + 심볼릭 링크

TC ID 다음 번호는 관련 스프레드시트 전 탭에서 실측한다. 대상 탭의 마지막
값만 보면 다른 탭에 더 큰 값이 있을 때 중복이 난다 — VIOLA 는 탭 경계를
무시하고 제품 전역 연속이다. 컬럼 하나만 읽으므로 전 탭을 훑어도 싸다.

헤더가 사양과 다르면 컬럼 위치를 신뢰할 수 없으므로 집계하지 않고 보고만
하고 종료 코드 2 로 끝낸다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 예외 유형 카탈로그 참조 문서

**Files:**
- Create: `.claude/skills/testcase-generator/references/exception-catalog.md`
- Modify: `.claude/skills/testcase-generator/SKILL.md` (「읽을 참조 문서 결정」 라우팅 표)

**Interfaces:**
- Consumes: Task 1의 `[예외 파생 …]` 태그 정의
- Produces: `exception-catalog.md` — Task 8의 `tc-augmenter` 에이전트와 Task 9의 SKILL이 이 경로를 지시한다. 문서에는 **예외 유형 12종**(고정 번호 1~12)과 **적용 가능성 판정표**가 있다.

- [ ] **Step 1: `exception-catalog.md` 를 작성**

아래 내용으로 만든다. §5 표는 **스펙 `docs/superpowers/specs/2026-09-10-testcase-augment-design.md` §5 의 두 표를 그대로 옮긴다** (유형 12종 표 + 적용 가능성 판정표). 번호는 고정 식별자이므로 바꾸지 않는다.

```markdown
# 예외 유형 카탈로그 — 추가 작업(`예외 사항`) 전용

`testcase-augment` 의 `예외 사항` 모드에서만 읽는다. 기획서 기반 생성(`testcase-auto`)에서는
읽지 않는다 — 그쪽의 `비정상`·`엣지` 케이스는 기획서에 근거가 있다.

**원천은 기존 테스트 케이스다.** 기획서를 읽지 않으므로 예상 결과의 확정값을 단정하지 않는다
(`common.md` 「파생 케이스의 원천」 규칙 4).

## 도출 축 — 원본 케이스별 뒤집기 + 카탈로그 점검

1. **뒤집기(주 경로)** — 원본 케이스 1건마다 *"이 절차가 실패하는 조건"* 을 도출한다 (1:N).
   `비고` 에 `[예외 파생 {원본 기능테스트 ID}] {예외 유형명}` 을 남겨 역추적을 보장한다
2. **카탈로그 점검(보조 경로)** — 뒤집기를 마친 뒤 아래 12종을 훑어 **적용 가능한데 0건인 유형**을
   찾는다. 만들지 않기로 판단했으면 **사유를 산출물에 적는다**

> 카탈로그는 **상한이 아니라 하한**이다. 12종에 없는 예외를 발견하면 만들고
> **카탈로그 추가를 보고**한다.

## 유형 12종

(스펙 §5 「유형 12종」 표를 그대로 옮긴다 — # / 유형 / 검증 지점 예)

## 적용 가능성 판정 — 전 유형을 전 기능에 적용하지 않는다

조회 전용 화면에 「필수값 누락」을 만들면 검증 목표가 없는 행이 된다.

(스펙 §5 「적용 가능성 판정」 표를 그대로 옮긴다 — 원본 기능 단위의 성격 / 적용 유형)

- **판정 근거는 원본 케이스의 `절차` 와 `3 Depth` 다.** 화면 성격을 유추하지 않는다
- 적용 유형인데 만들지 않았으면 **사유를 `12_cases_{EX|PM}-B{NN}.md` 에 적는다**

## 중복 판정 — 이미 있는 검증 목표는 만들지 않는다

문자열 일치가 아니라 **검증 목표 일치**다. 판정 근거는 인벤토리의 **기존 커버리지 맵**이다.

| 상황 | 판정 |
|------|------|
| 원본에 `필수값 미입력 시 저장 차단` 이 있고 같은 것을 만듦 | **중복 — 만들지 않는다** |
| 원본에 `이름 필수값 미입력` 이 있고 `설명 필수값 미입력` 을 만듦 | 필드가 다르면 별개 검증 목표 — 만든다 |
| 원본 `구분` 이 `비정상` 이지만 내용은 다른 예외 | 만든다 |

중복으로 걸러낸 후보는 산출물의 「중복 제외」 절에 **원본 TC ID와 함께** 적는다.

## 양식 매핑

| 컬럼 | 값 |
|------|-----|
| `구분` | `비정상` 주력 / 경계값(유형 3·5·11) → `엣지` / 취소·비활성(유형 12) → `부수` |
| `우선순위` | **프로파일의 구분 × 우선순위 결합 규칙을 따른다.** 여기 값을 박지 않는다 |
| `화면 ID` · `1 Depth` · `2 Depth` · `3 Depth` | **원본 케이스에서 승계.** 유추 금지 |
| `사전조건` | 예외 진입 조건 1줄 (프로파일이 100% 채움을 요구하면 반드시 채운다) |
| `절차` | `N. ` 접두 100%, 1단계 원칙 |
| `예상 결과` | **명사형 종결.** 동작 수준까지만 |
| `비고` | `[예외 파생 {원본 기능테스트 ID}] {예외 유형명}` |
| `피드백` | `[기획 확인] {무엇이 미정의인가} — 확정값 확인 필요` |

> **결합 규칙을 이 문서에 박지 않는 이유.** VIOLA는 `정상` 에 `P1`·`P2` 만 주고 `P3`·`P4` 사례가
> 0건인데 TROMBONE `정상` 은 `P1`~`P4` 를 전부 쓴다. 한쪽 값을 옮겨 적으면 2026-08-24 분포
> 하드코딩 사고(`정상` −44.9%p)를 형태만 바꿔 재현한다. **브리핑의 프로파일 절에서 읽어라.**

## 예상 결과를 어디까지 쓰는가

```
좋은 예: `필수 입력값 누락` 오류 메시지 표출 및 저장 차단
        → 동작(차단)은 단정, 문구는 성격까지만

나쁜 예: "이름을 입력해 주세요" 토스트 메시지 표출
        → 기획서에 없는 문구를 단정 → 실행자가 잘못된 FAIL을 낸다
```

**문구·코드·지연 시간 같은 확정값은 단정하지 않고 `[기획 확인]` 으로 넘긴다.**
예상 결과를 단정해 놓고 확인 불가를 적으면 실행자가 PASS/FAIL을 내려 버린다
(`common.md` 자기모순 금지).
```

- [ ] **Step 2: 스펙의 두 표를 실제로 옮겨 넣는다**

Run: `grep -n -A 20 "^## 5. 예외 유형 카탈로그" docs/superpowers/specs/2026-09-10-testcase-augment-design.md`

출력의 「유형 12종」 표(`| # | 유형 | 검증 지점 예 |` 로 시작하는 14줄)와 「적용 가능성 판정」 표를 `exception-catalog.md` 의 해당 자리(`(스펙 §5 …를 그대로 옮긴다)` 두 줄)에 붙여 넣고 그 안내 문장은 지운다.

- [ ] **Step 3: 표가 온전히 들어갔는지 확인**

Run:
```bash
grep -c '^| [0-9]' .claude/skills/testcase-generator/references/exception-catalog.md
grep -n '입력 폼\|목록 조회\|전 성격 공통' .claude/skills/testcase-generator/references/exception-catalog.md
grep -n '(스펙 §5' .claude/skills/testcase-generator/references/exception-catalog.md || echo "안내 문장 제거 확인"
```
Expected: 유형 행 `12`, 적용 판정표의 세 행이 보이고, `(스펙 §5` 잔존 0건

- [ ] **Step 4: `testcase-generator` SKILL 라우팅 표에 등재**

`.claude/skills/testcase-generator/SKILL.md` 의 `## 읽을 참조 문서 결정 (먼저 이것부터)` 표에 아래 행을 추가한다.

```markdown
| **추가 작업 = `예외 사항`** (`testcase-augment`) | `references/exception-catalog.md` — 예외 유형 12종·적용 판정·중복 판정·양식 매핑 |
```

- [ ] **Step 5: 커밋**

```bash
git add .claude/skills/testcase-generator/references/exception-catalog.md \
        .claude/skills/testcase-generator/SKILL.md
git commit -m "$(cat <<'EOF'
참조: 예외 유형 카탈로그 12종 + 적용 가능성 판정

카탈로그를 상한이 아니라 하한으로 규정했다. 전 유형을 전 기능에 적용하면
조회 전용 화면에 「필수값 누락」 같은 검증 목표 없는 행이 생기므로,
원본 케이스의 절차·3 Depth 를 근거로 적용 유형을 가린다.

결합 규칙·분포는 이 문서에 박지 않고 프로파일에서 읽게 했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 권한 모드 참조 문서

**Files:**
- Create: `.claude/skills/testcase-generator/references/permission-mode.md`
- Modify: `.claude/skills/testcase-generator/SKILL.md` (라우팅 표에 1행 추가)

**Interfaces:**
- Consumes: Task 1의 `[권한 매트릭스 …]` 태그 정의
- Produces: `permission-mode.md` — Task 8·9가 이 경로를 지시한다. **셀 → 검증 지점 전개 규칙**(전체 허용 1건 / 전체 차단 1건 / 부분 허용 2건)이 규모 계산의 단일 출처다.

- [ ] **Step 1: `permission-mode.md` 를 작성**

```markdown
# 권한 케이스 사양 — 추가 작업(`권한`) 전용

`testcase-augment` 의 `권한` 모드에서만 읽는다.

**원천은 권한 매핑 자료 + 기존 테스트 케이스**다. 자료가 「어느 역할이 무엇을 할 수 있는가」를,
원본 TC가 「그 기능이 어느 화면인가」(`화면 ID`·`1~3 Depth`)를 준다.

## 권한값 enum 은 자료에서 실측한다

하네스가 어휘를 정해 두지 않는다. 자료마다 다르다 — `허용/불가`, `조회/편집/없음`, `O/X`, `R/W/-`.
판별할 수 없으면 **사용자에게 확인한다.** 추정 금지.

## 셀 → 검증 지점 전개 (규모 계산의 단일 출처)

케이스 1건 = **검증 지점 1개**. 매트릭스 셀 하나가 여러 지점을 가질 수 있다.

| 셀의 권한값 성격 | 검증 지점 |
|---|---|
| **전체 허용** | 1건 — 기능 정상 수행 |
| **전체 차단** | 1건 — 진입·실행 차단 (메뉴 미노출 / 버튼 비활성 / 접근 거부 중 자료·원본이 말하는 것) |
| **부분 허용** (조회 전용 등) | **2건** — ① 허용 동작 수행 ② 차단 동작 차단 |

**규모 게이트의 총 행 수는 셀 수가 아니라 검증 지점 수로 계산한다.**

## 기능 ↔ 원본 TC 기능 단위 매핑

자료의 기능명(`파드`)과 원본 TC의 기능 단위(`2 Depth`=`파드 목록`, `3 Depth`=`목록`)는
**문자열이 일치하지 않는다.** 임의 추정하면 셀 하나가 엉뚱한 화면에 붙어 케이스가 통째로 틀린다.

| 상황 | 처리 |
|------|------|
| 1:1로 잡힘 | 그대로 진행 |
| 자료에만 있고 원본 TC에 대응 없음 | **케이스를 만들지 않고 보고.** 사용자가 화면 ID를 직접 지정하면 포함 |
| 원본 TC에만 있고 자료에 없음 | 권한 미정의로 보고 (권한 케이스 대상이 아니다) |
| 후보가 여럿이라 확정 불가 | 후보를 나열해 사용자에게 확인. **임의 선택 금지** |

**화면 ID를 유추로 만들지 않는다** (`common.md` 「화면 ID 공통 원칙」).
매핑 대응표는 **오케스트레이터가 사용자 확인 게이트에서 확정**한 것을 받아 쓴다 —
에이전트가 다시 판정하지 않는다.

## 양식 매핑

| 컬럼 | 값 |
|------|-----|
| `구분` | 허용 → `정상` / 차단 → `부수` |
| `우선순위` | **프로파일의 구분 × 우선순위 결합 규칙을 따른다.** 여기 값을 박지 않는다 |
| `사전조건` | `{역할} 권한 계정으로 로그인된 상태` (1줄) |
| `화면 ID` · `1 Depth` · `2 Depth` · `3 Depth` | **원본 TC에서 승계** |
| `절차` | `N. ` 접두 100%, 1단계 원칙 |
| `예상 결과` | **명사형 종결.** 차단 방식이 자료·원본에 없으면 단정하지 않는다 |
| `비고` | `[권한 매트릭스 {역할}×{기능}] {권한값}` |
| `피드백` | 자료와 원본 TC가 상충할 때만 — 양쪽을 `/` 로 대비 인용 |

> **결합 규칙을 이 문서에 박지 않는 이유.** `부수` → `P4` 는 VIOLA·TROMBONE 모두 예외 0건이지만,
> `정상` 은 정반대다 — VIOLA는 `P1`·`P2` 만, TROMBONE은 `P1`~`P4` 전부. 한쪽 값을 옮겨 적으면
> 2026-08-24 분포 하드코딩 사고를 형태만 바꿔 재현한다. **브리핑의 프로파일 절에서 읽어라.**

## 자료 ↔ 원본 TC 상충 처리

자료가 `불가` 인데 원본 TC에 그 역할의 정상 동작 케이스가 있으면 **판단하지 않고 양쪽을 기록**한다.

```
피드백: [기획 확인] 권한 자료: 불가 / 원본 TC_VIO_031: 정상 수행 — 확정값 확인 필요
```

## 차단 케이스의 예상 결과

차단이 **어떻게** 드러나는지(메뉴 미노출 / 버튼 비활성 / 접근 거부 페이지 / 오류 토스트)는
자료가 말하지 않는 경우가 많다.

```
좋은 예: 기능 진입 불가 — 메뉴 미노출 또는 접근 차단
        ㄴ 기획 미정의 항목 — PASS/FAIL 판정 대신 실측 상태를 [실제 결과]에 기재

나쁜 예: `권한이 없습니다` 토스트 표출
        → 자료에 없는 문구를 단정 → 실행자가 잘못된 FAIL을 낸다
```
```

- [ ] **Step 2: `testcase-generator` SKILL 라우팅 표에 등재**

Task 5에서 추가한 행 **다음에** 아래를 추가한다.

```markdown
| **추가 작업 = `권한`** (`testcase-augment`) | `references/permission-mode.md` — 셀→검증 지점 전개·기능 매핑·양식 매핑·상충 처리 |
```

- [ ] **Step 3: 문서 정합성을 확인**

Run:
```bash
grep -n '부분 허용' .claude/skills/testcase-generator/references/permission-mode.md
grep -n '프로파일' .claude/skills/testcase-generator/references/permission-mode.md | head -5
grep -nE '\bP[0-9]\b' .claude/skills/testcase-generator/references/permission-mode.md
grep -n 'references/permission-mode\|references/exception-catalog' .claude/skills/testcase-generator/SKILL.md
```
Expected:
- `부분 허용` 이 검증 지점 표와 규모 문장에 보인다
- `프로파일` 참조가 여러 곳에 있다
- **`P0`~`P9` 리터럴은 「`부수` → `P4`」·「`P1`·`P2`」 를 인용한 경고 문단에만 나온다** — 양식 매핑 표에는 없다 (있으면 하드코딩이다)
- 라우팅 표에 두 참조가 모두 등재됐다

- [ ] **Step 4: 커밋**

```bash
git add .claude/skills/testcase-generator/references/permission-mode.md \
        .claude/skills/testcase-generator/SKILL.md
git commit -m "$(cat <<'EOF'
참조: 권한 케이스 사양 — 셀→검증 지점 전개

규모는 매트릭스 셀 수가 아니라 검증 지점 수로 센다. `조회 전용` 같은
부분 허용 셀은 허용 동작 1건 + 차단 동작 1건으로 2건이 된다.

권한값 enum 을 하네스가 정하지 않고 자료에서 실측하게 했다 — 자료마다
어휘가 다르고(허용/불가·조회/편집/없음·O/X) 정해 두면 반드시 어긋난다.

기능 ↔ 원본 TC 매핑은 오케스트레이터가 게이트에서 확정한 것을 받아 쓴다.
에이전트가 다시 판정하면 게이트를 우회하는 셈이다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 리뷰어 추가 작업 모드 참조 문서

**Files:**
- Create: `.claude/skills/testcase-reviewer/references/augment-mode.md`
- Modify: `.claude/skills/testcase-reviewer/SKILL.md` (라우팅 표 + 「추가 작업 모드에서 제외하는 점검」)

**Interfaces:**
- Consumes: Task 1의 사양 절, Task 5·6의 카탈로그·권한 규칙
- Produces: `augment-mode.md` — Task 9의 SKILL이 리뷰어 프롬프트에서 이 경로를 지시한다. 점검 항목 8개 + **오판 방지 목록 8개**를 담는다.

- [ ] **Step 1: `augment-mode.md` 를 작성**

§3-2 표와 §11 표는 **스펙 §3-2 · §11 을 그대로 옮긴다.**

```markdown
# 추가 작업 모드 리뷰 — `testcase-augment` 산출물 전용

기획서가 없는 절차의 산출물을 리뷰한다. **「기획 ↔ 케이스」 경계면을
「원본 TC ↔ 파생 케이스」 경계면으로 대체**한다.

## 먼저 — 결정적 점검은 스크립트가 이미 했다

```bash
python scripts/verify_sheet_rows.py --profile={프로파일} --sheet=<대상> --tab='{탭}' --rows=<범위>
python scripts/verify_sheet_rows.py --profile={프로파일} --tsv=<13_rows_all_{EX|PM}.tsv> \
    --sheet=<대상> --tab='{탭}' --diff
```

헤더·23컬럼·`피드백` 뒤 열 오염·enum 3종·결합 규칙·`솔루션` 단일값·TC ID 형식·중복·
`No` 연속성·`-` vs 빈칸·`비고`/`사전조건` 공란·절차 `N. ` 접두·명사형 종결·본문 열 문체·
셀 내 파이프는 **전수 판정이 끝나 있다.** 같은 것을 눈으로 다시 세지 않는다.

**이 스크립트는 추가 작업용으로 수정되지 않았다.** `비고` 를 공란 여부로만 보고 태그 어휘를
검사하지 않으므로 파생 태그가 위반으로 잡히지 않는다.

## 점검 항목 (판단이 필요한 것만)

(스펙 §3-2 「점검 / 판정」 표 8행을 그대로 옮긴다)

- 「원본 TC ↔ 파생」 대조의 근거는 `10_tc_inventory.md` 의 **기능 단위 표와 커버리지 맵**이다
- 「매트릭스 셀 ↔ 케이스」 대조의 근거는 `11_permission_matrix.md` 다
- **작성자 자기 점검 서술을 인용하지 말고 독립 실측하라**

## ⚠️ 오판 방지 — 이 절차에서는 여러 기준이 정반대다

(스펙 §11 「지적하면 오판인 것 / 이유」 표 8행을 그대로 옮긴다)

**반대 방향도 함께 점검한다.** 위 목록은 **실제 결함을 통과시키라는 뜻이 아니다.**
예컨대 "분포 점검 제외"는 `구분` 값 자체가 enum 밖인 것을 통과시키라는 뜻이 아니다
(그건 `verify_sheet_rows.py` 가 잡는다).

## 산출물

`_workspace/augment/14_review_report_{EX|PM}.md`

- 등급별 건수 + 항목별 판정 + 근거 (시트 행 번호·원본 TC ID·매트릭스 셀)
- **오케스트레이터에게 돌려주는 리턴은 20줄 이내** — 파일 경로·등급별 건수·
  사용자 결정이 필요한 항목 1~3개만. 위반 목록 전문을 리턴에 담지 않는다
```

- [ ] **Step 2: 스펙의 두 표를 실제로 옮겨 넣는다**

Run:
```bash
grep -n -A 14 '^\*\*3-2. 판단 리뷰' docs/superpowers/specs/2026-09-10-testcase-augment-design.md
grep -n -A 14 '^## 11. 오판 방지 목록' docs/superpowers/specs/2026-09-10-testcase-augment-design.md
```
두 표를 `augment-mode.md` 의 해당 자리에 붙여 넣고 `(스펙 §…를 그대로 옮긴다)` 안내 줄을 지운다.

- [ ] **Step 3: `testcase-reviewer` SKILL 에 라우팅과 제외 점검을 추가**

`.claude/skills/testcase-reviewer/SKILL.md` 의 「읽을 참조 문서 결정」 표에 아래 행을 추가한다.

```markdown
| **추가 작업 산출물** (`testcase-augment`) | `references/augment-mode.md` — 원본TC↔파생 경계면·오판 방지 8종. **`change-mode.md` 는 읽지 않는다** |
```

이어서 「분포 편차」 점검 절(`3-1`) 안에 아래 경고를 추가한다.

```markdown
> **⚠️ 추가 작업(`testcase-augment`) 산출물에는 이 점검을 적용하지 않는다.**
> 예외 파생은 정의상 `비정상`·`엣지` 만, 권한 파생은 `정상`·`부수` 만 만들어
> **어느 프로파일로 채점해도 지배 구분 역전이 반드시 뜬다.** 그것을 결함으로
> 지적하면 "그 작업이 만들라고 한 것을 만들지 말라"는 리뷰가 된다.
> 완전성은 **예외 카탈로그 커버리지**와 **권한 매트릭스 셀 커버리지**로 본다
> (`references/augment-mode.md`).
```

- [ ] **Step 4: 정합성 확인**

Run:
```bash
grep -c '^| ' .claude/skills/testcase-reviewer/references/augment-mode.md
grep -n '(스펙 §' .claude/skills/testcase-reviewer/references/augment-mode.md || echo "안내 문장 제거 확인"
grep -n 'augment-mode' .claude/skills/testcase-reviewer/SKILL.md
grep -n '추가 작업.*적용하지 않는다' .claude/skills/testcase-reviewer/SKILL.md
grep -n '분포 편차' .claude/skills/testcase-reviewer/references/augment-mode.md
```
Expected: 표 행이 20개 이상, `(스펙 §` 잔존 0건, SKILL에 라우팅 1건 + 제외 경고 1건, `augment-mode.md` 안에 분포 편차가 **오판 방지 항목으로만** 등장

- [ ] **Step 5: 커밋**

```bash
git add .claude/skills/testcase-reviewer/references/augment-mode.md \
        .claude/skills/testcase-reviewer/SKILL.md
git commit -m "$(cat <<'EOF'
참조: 리뷰어 추가 작업 모드 — 원본TC↔파생 경계면

기획서가 없으므로 「기획 ↔ 케이스」 경계면을 「원본 TC ↔ 파생」으로 바꿨다.
완전성 지표도 기획 커버리지에서 카탈로그·매트릭스 셀 커버리지로 바꿨다.

분포 편차 점검을 세 곳(사양·리뷰어 SKILL·이 참조)에 걸쳐 제외로 못 박았다.
한 곳만 적으면 리뷰가 반복해 지적해 재작업 루프가 생긴다.

오판 방지 목록에 반대 방향도 넣었다 — 제외는 실제 결함을 통과시키라는
뜻이 아니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: `tc-augmenter` 에이전트 정의

**Files:**
- Create: `.claude/agents/tc-augmenter.md`

**Interfaces:**
- Consumes: Task 1의 `--role=augmenter` 브리핑, Task 4의 `10_tc_inventory.md`, Task 5의 `exception-catalog.md`, Task 6의 `permission-mode.md`
- Produces: 에이전트 `tc-augmenter`. Task 9의 SKILL이 `Agent` 도구로 `subagent_type: tc-augmenter` 로 호출한다. 산출물은 `_workspace/augment/12_cases_{EX|PM}-B{NN}.md` + `13_rows_{EX|PM}-B{NN}.tsv`, 리턴은 20줄 이내.

- [ ] **Step 1: `.claude/agents/tc-augmenter.md` 를 작성**

```markdown
---
name: tc-augmenter
description: 기존 테스트 케이스를 원천으로 예외 사항·권한 파생 케이스를 생성하고 구글 시트에 작성하는 전문가. 기획서를 읽지 않는다.
type: general-purpose
model: sonnet
---

# TC Augmenter

**기존 테스트 케이스 인벤토리**(`10_tc_inventory.md`)와 (권한 모드면) **권한 매트릭스**
(`11_permission_matrix.md`)를 입력으로 받아 파생 케이스를 만들고 구글 시트에 작성하는 에이전트.

> **기획서를 읽지 않는다.** 이 절차의 원천은 기존 테스트 케이스이며, 기획서 분석 산출물
> (`01_prd_analysis_*.md`)을 찾지 마라. 없는 것이 정상이다.

> **착수 전에 반드시 읽는다** — 오케스트레이터가 준 `_workspace/augment/10_brief_augmenter.md`
> (사양 발췌 원문: 23컬럼 A~W · `-` vs 빈칸 · 태그 체계 · 프로파일 분포·결합 규칙·문체·TC ID 체계)
> **+ 작업 유형별 참조 1개**:
>
> | 작업 유형 | 참조 |
> |----------|------|
> | `예외 사항` | `.claude/skills/testcase-generator/references/exception-catalog.md` |
> | `권한` | `.claude/skills/testcase-generator/references/permission-mode.md` |
>
> 브리핑에 없는 규칙이 필요하면 `.claude/formats/common.md` + 제품 프로파일을 직접 열어도 된다.
> 브리핑은 기본 로드를 줄이는 장치이고 원천 접근을 막는 장치가 아니다.

## 핵심 역할

인벤토리 + 양식 → 파생 케이스 + 시트 기록:
1. 배치에 속한 기능 단위마다 파생 케이스 도출
2. 팀 양식에 정확히 맞춰 작성 (23컬럼 · 문체 · enum · 결합 규칙)
3. TC ID·`No` 를 오케스트레이터가 준 시작 번호부터 부여
4. `12_cases_*.md`(메타·요약·근거 매핑) + `13_rows_*.tsv`(23컬럼 원본) 산출
5. 구글 시트에 batch append

## 작업 원칙

0. **오케스트레이터가 준 값을 그대로 쓴다. 추정하지 않는다.** 하나라도 없으면 요청한다.

   | 항목 | 쓰임 |
   |------|------|
   | **작업 유형** (`예외 사항` / `권한`) | 읽을 참조와 근거 태그를 정한다. **한 배치에 두 유형이 섞여 있으면 진행하지 말고 보고한다** |
   | **프로파일** (`viola` / `trombone` / `bootfactory`) | 분포·결합 규칙·문체·TC ID 체계. **인벤토리의 `솔루션` 실측으로 이미 판정됐다 — 다시 판정하지 않는다** |
   | **배치 ID** (`EX-B01` / `PM-B01` …) | 산출물 파일명 |
   | **기능 단위 목록** | 이 배치에서 다룰 대상. 목록에 없는 기능 단위를 임의로 추가하지 않는다 |
   | **TC ID 시작 번호 · `No` 시작 번호** | 인벤토리 실측값. 스스로 세지 않는다 |
   | **대상 시트 URL · 탭명** | 탭명은 `metadata` 의 `title` 문자열 그대로 (NFD/NFC 함정) |
   | (권한) **확정된 기능 대응표** | 사용자 게이트에서 확정됐다. **다시 매핑하지 않는다** |

1. **원본 케이스 승계** — `화면 ID`·`1 Depth`·`2 Depth`·`3 Depth` 는 인벤토리의 기능 단위 값을
   그대로 옮긴다. **유추로 만들지 않는다.**

2. **중복 제거** — 인벤토리의 **기존 커버리지 맵**이 판정 근거다. 같은 검증 목표가 이미 있으면
   만들지 않고, 걸러낸 후보를 산출물의 「중복 제외」 절에 **원본 TC ID와 함께** 적는다.

3. **예상 결과는 동작 수준까지만.** 문구·코드·지연 시간을 단정하지 않고 `피드백` 에
   `[기획 확인] … — 확정값 확인 필요` 를 남긴다. **예상 결과를 단정해 놓고 확인 불가를 적는
   자기모순을 만들지 않는다** — 실행자가 잘못된 PASS/FAIL을 낸다.

4. **파생 태그(근거 태그)를 비우지 않는다.**
   - 예외: `[예외 파생 {원본 기능테스트 ID}] {예외 유형명}`
   - 권한: `[권한 매트릭스 {역할}×{기능}] {권한값}`
   - **두 원천의 태그를 한 케이스에 섞지 않는다**
   - 접두 목록의 단일 출처는 `common.md` 「파생 케이스의 원천」 코드블록이다. **이 파생 태그가
     붙은 행은 다음 실행에서 원본으로 읽히지 않는다** — 태그를 빠뜨리면 그 행이 원본이 되어
     파생의 파생이 생긴다

5. **분포를 프로파일에 맞추려 하지 않는다.** 이 절차는 정의상 일부 구분만 만든다. 지배 구분을
   맞추려고 없는 케이스를 만들면 근거 없는 행이 된다. `12_cases_*.md` 에는 **실제 작성분을 센
   정확한 값**만 적는다 (추정 금지).

6. **atomic 유지** — 검증 항목 1개 = TC 1건. 절차 1단계 원칙, 사전조건 1줄.

7. **`구분`·`우선순위` 결합은 브리핑의 프로파일 절에서 읽는다.** 기억으로 채우지 않는다 —
   VIOLA `정상` 은 `P1`·`P2` 만인데 TROMBONE `정상` 은 `P1`~`P4` 를 전부 쓴다.

## 산출물

### `12_cases_{EX|PM}-B{NN}.md` — 메타 · 요약 · 근거 매핑

**케이스 본문(절차·예상 결과 전문)을 담지 않는다.** 시트가 단일 출처다.
실측에서 `.md` 의 65%가 시트와 같은 텍스트였고 리뷰어가 같은 것을 두 번 읽었다.

```markdown
# 파생 케이스 — 배치 {배치 ID} / {작업 유형}

## 메타정보
- 프로파일: {프로파일} · 대상 탭: {탭명} · 시트 행: {시작}~{끝}
- TC ID: {시작}~{끝} · `No`: {시작}~{끝}
- 기능 단위: {개수}개

## 케이스 요약 (구분별 — 실측 카운트)
| 구분 | 건수 |

## 근거 매핑 (역추적용 — 이 파일의 본체다)
| TC ID | 기능 단위 | 근거 태그 | 유형/셀 |

## 중복 제외
| 만들지 않은 검증 목표 | 이미 있는 원본 TC ID |

## 카탈로그 미적용 (예외 모드) / 미대응 셀 (권한 모드)
| 유형/셀 | 사유 |

## 기획 확인 필요 항목
| TC ID | 확인 사항 |
```

### `13_rows_{EX|PM}-B{NN}.tsv` — 23컬럼 원본 (스크립트 전용)

1행은 사양의 **헤더 원문**, 2행부터 시트에 보낼 값 그대로. `verify_sheet_rows.py --diff` 의
대조 원본이며 **사람도 모델도 읽지 않으므로 컨텍스트 비용이 0**이다. append 부분 실패 시
복구 경로가 된다.

## 시트 작성 절차

1. 대상 탭이 없으면 `add_tab` → **생성 직후 `metadata` 의 `title` 을 복사** →
   사양의 **헤더 원문**을 `1행` 에 기입 → 2행부터 append
2. 기존 탭이면 그대로 batch append (헤더 대조는 Phase 1에서 끝났다)
3. **기능 단위별로 나눠 append** 하고 각 범위를 보고한다 (부분 재실행 정밀도)
4. `sheets_api.py` 의 write/append 기본값은 **RAW** 다. `--user-entered` 를 쓰지 않는다 —
   `-`·`1. ` 접두·`2026-01-02` 가 날짜·수식으로 변환된다
5. `updatedRange` 확인 후 보고

## 오케스트레이터 리턴 규약 (20줄 이내)

산출물은 **파일**이고 리턴은 **파일을 가리키는 영수증**이다. 케이스 표·근거 태그 나열·
자기 점검표를 리턴에 담으면 그 텍스트가 오케스트레이터 컨텍스트에 쌓여 **이후 모든 턴에서
다시 읽힌다** (실측: 오케스트레이터 평균 40만 토큰 · 전체 비용의 25.5%).

| 담을 것 | 담지 않을 것 |
|--------|-------------|
| 산출물 파일 경로 | 케이스 본문·근거 태그 나열 |
| 케이스 수 (구분별 합계까지) | 컬럼별 판정 근거 서술 |
| 시트 작성 행 범위 (기능 단위별) | 중복 제외 목록 전문 |
| 다음 배치에 넘길 TC ID·`No` | 자기 점검표 |
| 사용자 결정이 필요한 항목 1~3개 | 이미 파일에 쓴 내용의 재서술 |

## 배치 처리 (기능 단위 2~3개를 한 번에 받는 경우)

- **산출물은 배치 단위 파일 하나**이되, 「근거 매핑」·「시트 행」은 **기능 단위로 구분해** 적는다
- **시트 append 는 기능 단위로 나눠** 실행하고 범위를 각각 보고한다
- **한 기능 단위가 실패하면 그것만 실패로 보고**하고 나머지는 계속 진행한다
- **정책·작업 유형이 섞인 배치는 진행하지 말고 보고한다** — 섞인 채 진행하면 절반이 반대
  기준으로 만들어진다
- **첫 배치(`EX-B01` / `PM-B01`)는 기능 단위 1개로 온다.** 오케스트레이터가 그렇게 보장하며,
  그 결과는 사용자 검토 게이트를 거친다 — 첫 배치에 여럿이 들어왔으면 진행하지 말고 보고한다.
  문체·태그·enum 오류를 **전 행에 번지기 전에** 잡는 것이 그 게이트의 목적이다

## 하지 않는 것

| 항목 | 이유 |
|------|------|
| 기획서 읽기 | 이 절차의 원천이 아니다 |
| 프로파일 재판정 | 인벤토리의 `솔루션` 실측으로 확정됐다 |
| 권한 자료 재판독·재매핑 | 사용자 게이트에서 확정됐다 — 다시 하면 게이트를 우회하는 셈이다 |
| 분포를 프로파일에 맞추기 | 정의상 일부 구분만 만드는 작업이다 |
| TC ID·`No` 를 스스로 세기 | 인벤토리 실측값을 받아 쓴다 (전 탭 최대값 기준) |
| 엑셀 파일 읽기·쓰기 | 미지원. 경로가 오면 보고하고 중단 |
```

- [ ] **Step 2: 에이전트가 목록에 잡히는지 확인**

Run:
```bash
head -6 .claude/agents/tc-augmenter.md
grep -c '^## ' .claude/agents/tc-augmenter.md
grep -n 'model:' .claude/agents/tc-augmenter.md
```
Expected: frontmatter에 `name: tc-augmenter` / `type: general-purpose` / `model: sonnet`, `##` 절 8개 이상

- [ ] **Step 3: 규약 가드가 요구하는 문구가 들어 있는지 확인**

Task 10의 회귀 가드가 이 파일에서 「리턴은 20줄」 패턴을 찾는다.

Run: `grep -nE '리턴은 20줄|리턴 규약' .claude/agents/tc-augmenter.md`
Expected: 최소 1건 (`## 오케스트레이터 리턴 규약 (20줄 이내)`)

- [ ] **Step 4: 커밋**

```bash
git add .claude/agents/tc-augmenter.md
git commit -m "$(cat <<'EOF'
에이전트: tc-augmenter 신설 (model: sonnet)

기존 writer 에 모드를 얹지 않고 분리했다 — 입력이 분석서가 아니라 인벤토리
이고 근거 태그 체계가 다르며, 조건 분기를 넣으면 두 경로가 함께 무거워진다.

sonnet 인 근거는 2026-09-09 판단을 승계한다: 양식 준수의 기계 판정 가능한
부분이 verify_sheet_rows.py 로 전수 이관돼 있다.

「하지 않는 것」 표에 재판정 금지를 명시했다 — 프로파일·권한 매핑을 에이전트가
다시 정하면 인벤토리 실측과 사용자 게이트를 우회하는 셈이다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `testcase-augment` 오케스트레이터 SKILL

**Files:**
- Create: `.claude/skills/testcase-augment/SKILL.md`

**Interfaces:**
- Consumes: Task 1(`build_brief.py --role=augmenter --doc-type=추가`) · Task 4(`read_tc_inventory.py`) · Task 5·6·7(참조 3종) · Task 8(`tc-augmenter`)
- Produces: 스킬 `testcase-augment`. 트리거 `"테스트케이스 추가 작업 진행해줘."`. Task 10의 문서·가드가 이 파일을 참조한다.

- [ ] **Step 1: `SKILL.md` 의 머리말 · 트리거 · Phase 0 를 작성**

`.claude/skills/testcase-augment/SKILL.md` 를 만들고 아래를 쓴다.

```markdown
---
name: testcase-augment
description: 이미 작성된 테스트 케이스를 원천으로 예외 사항 케이스와 권한 케이스를 파생 생성해 구글 시트에 작성하는 오케스트레이터. "테스트케이스 추가 작업 진행해줘", "예외 사항 케이스 추가", "권한 케이스 만들어줘" 요청 시 반드시 이 스킬을 사용할 것. 기획서를 읽지 않는다.
---

# Testcase Augment Orchestrator

**기존 테스트 케이스** → 인벤토리 → 파생 케이스 생성/작성/리뷰까지 수행한다.
기획서를 원천으로 하는 `testcase-auto` 와 **나란한 두 번째 절차**다.

| | `testcase-auto` | `testcase-augment` (이 스킬) |
|---|---|---|
| 원천 | 기획서 (Figma / PDF / 이미지) | **구글 시트의 기존 테스트 케이스** |
| 제품 유형 | 사용자에게 묻는다 | **`솔루션` 컬럼 실측으로 판정** (묻지 않는다) |
| 산출 | 기획 근거 케이스 | **예외 사항** / **권한** 파생 케이스 |

> **기획서를 요구하지 않는다.** 사용자가 기획서를 주더라도 이 절차는 읽지 않는다 —
> 기획서 기반 케이스가 필요하면 `testcase-auto` 다.

## 트리거 키워드

- "테스트케이스 추가 작업 진행해줘" / "테스트 케이스 추가 작업"
- "예외 사항 케이스 추가해줘", "예외 케이스 뽑아줘"
- "권한 케이스 만들어줘", "권한별로 동작 확인 케이스 추가"

## 실행 모드

| 에이전트 | 역할 |
|---------|------|
| (스크립트) `read_tc_inventory.py` | 원본 탭 인벤토리 + 기존 커버리지 맵 + 번호 실측 |
| `tc-augmenter` | 배치별 파생 케이스 생성 + 시트 작성 |
| `testcase-reviewer` | 작업 유형별 리뷰 1회 (추가 작업 모드) |

**`prd-analyst`·`sheet-analyst`·`testcase-writer` 는 호출하지 않는다.**

## 워크플로우

### Phase 0: 기본 정보 수집 — 필수 게이트

**추정 금지.** 답이 없으면 진행하지 않는다 — 잘못 추정한 항목 하나가 전 행에 박힌다.
`AskUserQuestion` 으로 선택지를 제시하면 왕복이 줄어든다.

#### 0-1. 환경 검증

- `GOOGLE_APPLICATION_CREDENTIALS` 가 유효한 경로를 가리키는가 (또는
  `<프로젝트 루트>/.credentials/google-service-account.json` 이 있는가)
- 누락 시 안내 후 중단
- **`FIGMA_ACCESS_TOKEN` 은 검사하지 않는다** — 이 절차는 기획서를 읽지 않는다

#### 0-2. 추가 작업 유형 — 선택 필수 (복수 선택 허용)

| 값 | 산출 |
|----|------|
| **`예외 사항`** | 시스템이 기대하는 정상 흐름을 벗어나는 케이스 |
| **`권한`** | 권한 매핑대로 기능이 동작하는지 확인하는 케이스 |

둘 다 고르면 **고른 순서대로 순차 처리**한다 (예외를 끝낸 뒤 권한).
**한 배치에 두 유형을 섞지 않는다** — 도출 규칙과 근거 태그가 다르다.

#### 0-3. 유형별 입력 — 필수

공통 (두 유형 모두):

| 항목 | 내용 |
|------|------|
| **원본 TC 시트 URL** | 읽을 테스트 케이스가 있는 구글 시트 |
| **원본 탭** | `metadata` 로 **탭 목록을 보여주고 고르게 한다.** 복수 선택 허용 |
| **작성 대상 시트 URL** | 파생 케이스를 쓸 구글 시트 (원본과 같아도 된다) |
| **작성 대상 탭** | 없으면 생성 |

`권한` 을 골랐을 때 추가:

| 항목 | 내용 |
|------|------|
| **권한 자료 경로** | 구글 시트 URL / CSV·마크다운 로컬 파일 / 이미지·PDF |

- **탭명은 `metadata` 가 돌려주는 `title` 문자열을 그대로 쓴다** — 한글 탭 이름이 NFD 분해형으로
  저장되면 조합형으로 타이핑한 같은 문자열이 HTTP 400 `Unable to parse range` 로 실패한다.
  화면상 구분이 되지 않으므로 "탭이 없다"고 오판하거나 중복 탭을 만들 위험이 있다
- **원본 탭을 묻지 않고 추정하지 않는다.** 시트에 탭이 여러 개면 어디를 읽을지 모호하다
- **엑셀(.xlsx) 경로가 들어오면 미지원을 안내하고 중단한다.** 구글 시트로 옮기거나 CSV로
  내보내 달라고 요청한다. 임의로 변환하지 않는다

#### 0-4. 묻지 말아야 할 것

| 항목 | 왜 묻지 않는가 |
|------|--------------|
| **제품 유형 / 프로파일** | 원본 TC의 `솔루션` 컬럼 **실측**으로 판정한다 (Phase 1). 추정이 아니라 실측이므로 「추정 금지」와 충돌하지 않는다 |
| **기획서 경로 · 기획서 유형 · 정책 예외** | 이 절차의 개념이 아니다 |
| **취소선 · 변경 표시색** | 기획서 표기 개념이다 |
| **생성 모드** | atomic 고정 (전 제품 확정) |

#### 0-5. 확정값 요약 보고

수집이 끝나면 **확정값을 표로 보여주고 진행한다.** 사용자가 오타를 잡을 마지막 지점이다.

```
다음 조건으로 진행합니다.

| 항목 | 값 |
|------|-----|
| 추가 작업 | 예외 사항, 권한 (순서대로) |
| 원본 TC | https://docs.google.com/spreadsheets/d/AAA / 탭 "03_파드" |
| 작성 대상 | 같은 시트 / 탭 "03_파드_예외" (신규 생성) |
| 권한 자료 | docs/permission_matrix.png |
| 제품 유형 | 원본 TC의 `솔루션` 컬럼에서 판정합니다 (Phase 1) |
```

#### 0-6. 시트 권한 확인 안내

> "원본·작성 대상 구글 시트(권한 자료가 시트면 그것까지)에 서비스 계정 이메일
> `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com` 을 편집자로 공유했는지
> 확인해 주세요. (이미 했으면 그대로 진행)"

#### 0-7. 기존 산출물 확인

- `_workspace/augment/` 가 없음 → **초기 실행**
- 있고 사용자가 "다시" 요청 → `_workspace/augment_prev_{날짜}/` 로 이동 후 새 실행
- 있고 이어 진행 → 완료 안 된 배치부터
```

- [ ] **Step 2: Phase 1 (인벤토리 · 권한 판독 · 규모 게이트) 를 이어 쓴다**

같은 파일에 이어서:

```markdown
### Phase 1: 인벤토리 + 게이트

#### 1-A. 원본 TC 인벤토리 (스크립트, 에이전트 호출 0)

```bash
python scripts/read_tc_inventory.py \
    --source-sheet=<원본 URL> --source-tab='03_파드' \
    --target-sheet=<대상 URL> --target-tab='03_파드_예외' \
    --out-dir=_workspace/augment
```

- 원본 탭이 여럿이면 `--source-tab` 을 여러 번 준다
- 종료 코드 `2`(Critical)면 **진행하지 않는다.** `10_tc_inventory.md` 의 「판정」 절을
  사용자에게 보여주고 확인받는다
- 종료 코드 `3` 은 사양 파싱·입력 오류다. 하드코딩으로 우회하지 않는다

**스크립트가 내는 것:**

| 항목 | 쓰임 |
|------|------|
| 헤더 드리프트 판정 | 불일치는 **Critical 중단** — 원본을 잘못 읽으면 전 파생분이 어긋난다 |
| `솔루션` 실측 → **프로파일** | 브리핑 생성·리뷰어 프롬프트에 넘긴다 |
| 기능 단위 목록 (`화면 ID` + `2 Depth` + `3 Depth`) | 배치 계획의 단위 |
| **기존 커버리지 맵** | 중복 제거의 단일 출처 |
| 파생 태그 행 제외 건수 | 재실행 안전장치가 동작했는지 확인 |
| TC ID 접두별 다음 번호 · 대상 탭 마지막 `No` | 에이전트에게 넘길 시작 번호 |

> **⚠️ `10_tc_inventory.md` 를 확인차 통독하지 않는다.** 오케스트레이터가 알아야 하는 것은
> 기능 단위 표와 번호뿐이다. 케이스 요약 절까지 컨텍스트에 올리면 원본 탭을 옮겨 담은 것이
> 되어 이 스크립트의 목적이 사라진다. 필요할 때 해당 절만 열어라.

#### 1-B. 권한 자료 판독 + 확인 게이트 (`권한` 모드만)

| 자료 형태 | 경로 |
|----------|------|
| 구글 시트 URL | `python scripts/sheets_api.py read <URL> "'탭'!A1:Z200"` |
| CSV · 마크다운 | 로컬 파일 읽기 |
| PDF | `python scripts/pdf_to_images.py <pdf> --dpi=150 --tile=auto --output-dir=…` 후 판독 |
| 이미지 | `python scripts/check_image_quality.py <경로>` 게이트 통과 후 판독 |

산출물: `_workspace/augment/11_permission_matrix.md` — **역할 × 기능 → 권한값** 표 +
**기능 ↔ 원본 TC 기능 단위 대응표** (판정 컬럼: `확정` / `미대응` / `후보 여럿`).

**게이트 (필수):** 두 표를 사용자에게 보여주고 확인받는다.

- **권한값 enum 은 자료에서 실측한다.** 하네스가 어휘를 정하지 않는다
  (`허용/불가`·`조회/편집/없음`·`O/X`·`R/W/-` 등 자료마다 다르다)
- **기능 대응을 임의 추정하지 않는다.** 셀 하나가 엉뚱한 화면에 붙으면 케이스가 통째로 틀린다
- 판독 `불가` 항목은 추측하지 않고 `[판독 불가]` 로 표시해 **원본 재전달을 요청**한다
- 확정된 대응표는 **에이전트가 다시 매핑하지 않는다** — 게이트를 우회하는 셈이다

#### 1-C. 대상 범위 + 규모 확인 게이트 (필수)

**예외 모드** — 기능 단위마다 적용 예외 유형(`exception-catalog.md` 의 적용 판정표)과
기존 커버리지를 붙여 보여준다.

```
예외 사항 케이스를 다음 범위로 만듭니다. 확인해 주세요.

원본: 탭 "03_파드" 127행 → 기능 단위 24개 (파생 태그 행 0건 제외)
제품 유형: VIOLA (`솔루션` 실측 127/127) → profile-viola
예상 케이스: 약 86건  |  배치 9개  |  에이전트 사이클 10회

| 순번 | 기능 단위 (화면 ID / 2 Depth / 3 Depth) | 원본 | 적용 예외 유형 | 기존 커버 | 예상 | 배치 |
|------|--------------------------------------|------|--------------|---------|------|------|
| 01 | VIOE-03_01_01-01 / 파드 목록 / 목록 | 41건 | 6,8,9,11,12 | 비정상 2건 | 4건 | EX-B01 (단독) |
| 02 | VIOE-03_01_01-02 / 파드 생성 / 생성 | 18건 | 1,2,3,4,5,10,12 | 없음 | 9건 | EX-B02 |
...

작성 위치: 탭 "03_파드_예외" (신규 생성) / TC ID TC_VIO_128 부터 / No 1 부터
제외한 기능 단위: 없음

수정이 필요하면 알려주세요. (예: "01번은 제외", "9번 유형은 빼줘")
```

**권한 모드** — 검증 지점 수로 규모를 낸다 (셀 수가 아니다).

```
권한 케이스를 다음 규모로 만듭니다. 확인해 주세요.

역할 3개 × 기능 2개 = 매트릭스 셀 6개 → 검증 지점 8건
  (`조회 전용` 셀은 허용 동작 1건 + 차단 동작 1건으로 2건이 됩니다 — 해당 셀 2개)
미대응 기능 1개(`클러스터 설정`)는 제외 — 화면 ID를 승계할 원본 케이스가 없습니다

배치 2개 | 에이전트 사이클 3회
작성 위치: 탭 "03_파드_권한" (신규 생성) / TC ID TC_VIO_214 부터 / No 1 부터
```

- 사용자 OK → 확정. 수정 → 재계산 후 다시 보여준다 (OK까지 반복)
- **제외한 항목을 반드시 함께 보여준다** — 조용히 빠진 것이 누락의 원천이다
- 규모가 과다하면(예: 500행 초과) 사이클 수를 알리고 **범위 축소 여부를 확인한다**

#### 1-C-1. 배치 계획

**묶는 조건 — 셋을 모두 만족할 때만:**

| 조건 | 이유 |
|------|------|
| **같은 작업 유형** | 도출 규칙·근거 태그가 다르다 |
| **같은 화면 ID** | 승계할 `1~3 Depth` 가 같아 컨텍스트가 하나다 |
| **기능 단위 3개 이하** | 그 이상은 컨텍스트 한도·판독 누락 위험 |

- **첫 배치(`EX-B01` / `PM-B01`)는 반드시 기능 단위 1개다.** 첫 배치 검토 게이트의 목적이
  문체·태그·enum 오류를 **전 행에 번지기 전에** 잡는 것이므로, 첫 호출에 여러 단위를 넣으면
  게이트를 통과할 때 이미 여럿이 잘못 쓰여 있다
- **첫 배치 게이트는 작업 유형마다 한 번씩이다** — 한쪽 통과가 다른 쪽을 보증하지 않는다
- 묶지 못하는 단위는 자기 혼자 배치가 된다. 정상이다
- **산출물·시트 행은 기능 단위로 분리 기록한다.** 묶는 것은 호출뿐이다

#### 1-D. 역할별 브리핑 생성 (루프 진입 전 1회)

```bash
# Phase 0 확정값 표를 먼저 파일로 저장 → _workspace/augment/10_phase0.md
for R in augmenter reviewer; do
  python scripts/build_brief.py --role=$R \
      --profile={viola|trombone|bootfactory} --doc-type=추가 \
      --phase0=_workspace/augment/10_phase0.md \
      --out=_workspace/augment/10_brief_$R.md
done
```

- **프로파일은 1-A 인벤토리의 `솔루션` 실측값**을 쓴다. 묻지 않는다
- `--doc-type=추가` 는 **변경분 모드 절을 제외**한다 (기획서 표기 개념이라 쓰지 않는다)
- **요약이 아니라 사양 절 원문 발췌다.** 문장을 줄이지 않으므로 규칙이 빠지지 않는다
- 사양을 고친 뒤에는 `python scripts/build_brief.py --coverage-check` 를 돌린다 —
  미배정 절은 **어느 브리핑에도 들어가지 않아 조용히 사라진다**
```

- [ ] **Step 3: Phase 2~4 + 프로토콜 + 에러 처리 + 체크리스트를 이어 쓴다**

같은 파일에 이어서:

```markdown
### Phase 2~3: 배치 루프 (작업 유형별)

```
for 작업 유형 in 선택한 유형 (예외 → 권한 순):
    for 배치 in 그 유형의 배치 목록 (B01, B02, … 순):
        Phase 2: tc-augmenter 1회 호출
                 → 12_cases_{EX|PM}-B{NN}.md + 13_rows_{EX|PM}-B{NN}.tsv
                 → 기능 단위별 시트 append + 행 범위 기록
        첫 배치면 → 사용자 검토 게이트
    Phase 3: 검증 (스크립트 + 리뷰어 1회)
```

#### Phase 2: 파생 케이스 생성 + 시트 작성

`tc-augmenter` 에게 넘길 값 — **Phase 0·1에서 확정한 것을 그대로 넘긴다:**

| 항목 | 왜 넘겨야 하는가 |
|------|----------------|
| **작업 유형** (`예외 사항` / `권한`) | 읽을 참조와 근거 태그를 정한다 |
| **프로파일** | 분포·결합 규칙·문체·TC ID 체계. **에이전트가 재판정하지 않게 확정값을 준다** |
| **배치 ID** (`EX-B01` 등) | 산출물 파일명 |
| **기능 단위 목록** (화면 ID·1~3 Depth·원본 TC ID 범위·기존 커버리지·적용 예외 유형) | 승계·중복 제거의 근거 |
| **TC ID 시작 번호 · `No` 시작 번호** | 전 탭 실측값. 스스로 세지 않게 한다 |
| **대상 시트 URL · 탭명(`title` 원문)** | NFD/NFC 함정 |
| (권한) **확정된 매트릭스 + 기능 대응표** | 게이트에서 확정됐다 — 재매핑 금지 |
| **브리핑 경로** `10_brief_augmenter.md` | 사양 발췌 원문 |

**첫 배치 검토 게이트:**

- `12_cases_{EX|PM}-B01.md` 의 요약·근거 매핑을 사용자에게 보여주고 진행 확인
- 이후 배치는 자동 진행
- **여기서 문체·태그·enum을 잡아야 나머지 전 행에 번지지 않는다**

배치마다 **작성된 행 범위를 기록**한다 (기능 단위별).

#### Phase 3: 검증 (작업 유형별 1회)

**3-1. 결정적 양식 점검 (스크립트)**

```bash
cd _workspace/augment
head -1 $(ls 13_rows_EX-B*.tsv | sort | head -1) > 13_rows_all_EX.tsv
for f in $(ls 13_rows_EX-B*.tsv | sort); do tail -n +2 "$f" >> 13_rows_all_EX.tsv; done
cd ../..

python scripts/verify_sheet_rows.py --profile={프로파일} \
    --sheet=<대상> --tab='{탭}' --rows=<시작>-<끝>
python scripts/verify_sheet_rows.py --profile={프로파일} \
    --tsv=_workspace/augment/13_rows_all_EX.tsv --sheet=<대상> --tab='{탭}' --diff
```

- **이 스크립트는 수정되지 않았다.** `비고` 를 공란 여부로만 보고 태그 어휘를 검사하지 않으므로
  파생 태그가 위반으로 잡히지 않고, 나머지 결정적 점검은 그대로 유효하다
- 종료 코드 `2`(Critical)면 그 행을 `.tsv` 로 재작성한다

**3-2. 판단 리뷰 (`testcase-reviewer` 1회)**

- 입력: `10_tc_inventory.md` · (권한) `11_permission_matrix.md` · `12_cases_*.md` ·
  시트 작성 행 범위 · `10_brief_reviewer.md` ·
  **`.claude/skills/testcase-reviewer/references/augment-mode.md` 경로**
- 출력: `_workspace/augment/14_review_report_{EX|PM}.md`

**리뷰어 프롬프트에 반드시 넣을 오판 방지 항목** (상세는 `augment-mode.md`):

- **`구분` 분포가 프로파일과 다른 것은 정상이다** — 예외는 `비정상`·`엣지` 만, 권한은
  `정상`·`부수` 만 만드는 것이 이 작업의 정의다. **분포 편차를 지적하지 않는다**
- **기획서 근거 태그(`[DESC …]`)가 없는 것은 정상이다** — 원천이 기획서가 아니다
- **`예상 결과` 에 오류 문구가 없는 것은 규칙이다** — 문구를 적었다면 그쪽이 위반이다
- **`[기획 확인]` 이 많은 것은 정상이다** — 기획 미정의 영역을 다룬다
- **TC ID가 원본과 떨어진 것은 정상이다** — append-only 이므로 대상 탭 끝에 붙는다
- **미대응 기능이 빠진 것은 게이트에서 확인된 사항이다**
- **작성자 자기 점검표를 인용하지 말고 독립 실측하라**

**Critical 발생 시:** 리뷰어 → `tc-augmenter` 재작성 요청 → 재리뷰 (최대 1회 루프).
두 번째에도 Critical이 남으면 사용자에게 결정을 위임한다.

### Phase 4: 종합 보고

```markdown
## 추가 작업 완료 보고

### 작업 유형별 결과
| 유형 | 대상 | 생성 | 시트 행 | 리뷰 |
|------|------|------|--------|------|
| 예외 사항 | 기능 단위 24개 | 86건 | 2~87 | Critical 0 / Major 1 |
| 권한 | 매트릭스 셀 6개 → 지점 8건 | 8건 | 88~95 | Critical 0 |

### 제품 유형 판정
- `솔루션` 실측 `VIOLA` 127/127 → `profile-viola`

### 제외 항목 (없으면 "제외 없음" 으로 명시)
| 항목 | 사유 |
|------|------|
| `클러스터 설정` (권한 자료) | 원본 TC에 대응 기능 없음 — 화면 ID 승계 불가 |

### 산출물
- `_workspace/augment/10_tc_inventory.md` / `.json`
- `_workspace/augment/11_permission_matrix.md` (권한 모드)
- `_workspace/augment/12_cases_{EX|PM}-B{NN}.md` (배치별)
- `_workspace/augment/13_rows_{EX|PM}-B{NN}.tsv` + `13_rows_all_{EX|PM}.tsv`
- `_workspace/augment/14_review_report_{EX|PM}.md`

### 다음 단계 권장
- {Critical → 즉시 수정 제안} / {`[기획 확인]` 항목 → 기획 확인 목록 정리}
```

## 데이터 전달 프로토콜

| 자료 | 위치 | 생성자 | 소비자 |
|------|------|--------|--------|
| 원본 TC 인벤토리 | `_workspace/augment/10_tc_inventory.md` / `.json` | `read_tc_inventory.py` | 오케스트레이터(표·번호만), `tc-augmenter`(배치 발췌) |
| 권한 매트릭스 | `_workspace/augment/11_permission_matrix.md` | 오케스트레이터 (1-B) | 사용자 게이트, `tc-augmenter`, `testcase-reviewer` |
| 역할 브리핑 | `_workspace/augment/10_brief_{augmenter\|reviewer}.md` | `build_brief.py` | 각 에이전트 |
| 배치 케이스 요약·근거 매핑 | `_workspace/augment/12_cases_{EX\|PM}-B{NN}.md` | `tc-augmenter` | `testcase-reviewer`, 사용자 |
| 배치 **원본 행** | `_workspace/augment/13_rows_{EX\|PM}-B{NN}.tsv` | `tc-augmenter` | `verify_sheet_rows.py --diff` (**사람·모델이 읽지 않는다**) |
| 합본 원본 행 | `_workspace/augment/13_rows_all_{EX\|PM}.tsv` | 오케스트레이터 (셸 병합) | `verify_sheet_rows.py --diff` |
| 리뷰 보고 | `_workspace/augment/14_review_report_{EX\|PM}.md` | `testcase-reviewer` | 오케스트레이터, 사용자 |
| **케이스 본문** | **구글 시트 (단일 출처)** | `tc-augmenter` | 사람, `verify_sheet_rows.py` |
| 양식 사양 | `.claude/formats/common.md` + 제품 프로파일 | 사람 | 브리핑 경유 |

**⚠️ 서브에이전트 리턴은 20줄 이내로 제한한다.** 산출물은 **파일**이고 리턴은 **파일을 가리키는
영수증**이다. 케이스 표·위반 목록 전문을 리턴에 담으면 그 텍스트가 오케스트레이터 컨텍스트에
쌓이고 **이후 모든 턴에서 다시 읽힌다** (실측: 오케스트레이터 평균 40만 토큰 · 전체 비용의 25.5%).
오케스트레이터가 상세를 알아야 할 때는 **그때 파일을 열면 된다.**

## 에러 핸들링

| 에러 | 대응 |
|------|------|
| 엑셀(.xlsx) 경로 입력 | **미지원 안내 후 중단.** 구글 시트 이관 또는 CSV 내보내기 요청 |
| 원본 탭 헤더가 사양과 불일치 | **Critical 중단** — 원본을 잘못 읽으면 전 파생분이 어긋난다 |
| 대상 탭이 존재하는데 헤더가 사양과 불일치 | **Critical 중단** — append하면 전 값이 밀린다 |
| `솔루션` 값이 프로파일에 없음 | 진행 중단. 참고 시트로 프로파일 신설(모드 B) 제안 |
| `솔루션` 값이 한 탭에 혼재 | 최다값 사용 + 사용자 보고 (프로파일은 제품 단위) |
| 원본 탭에 유효 케이스 0건 (전 행이 파생 태그 행) | 진행 중단 — 뒤집을 원본이 없다. 다른 탭 지정 요청 |
| `read_tc_inventory.py` 종료 코드 `3` | 사양 파싱·입력 오류. **하드코딩으로 우회하지 않는다** |
| 권한 자료 판독 실패·품질 `불가` | 사용자 통보 + 재전달 요청. **추측 금지** |
| 권한 자료의 기능 ↔ 원본 TC 매핑 실패 | 그 기능 제외 + 보고. **화면 ID 유추 금지** |
| 권한값 enum 판별 불가 | 게이트에서 사용자 확인. 어휘를 하네스가 정하지 않는다 |
| 두 작업 유형이 한 배치에 섞임 | 배치를 유형별로 분리 후 재실행 |
| 배치 중 일부 기능 단위만 실패 | 그 단위만 `실패` 로 남기고 **나머지는 계속 진행** |
| `--diff` 대조 불일치 | **Critical** — 로컬 `.tsv` 로 해당 행 재작성 |
| 규모 과다 (예: 500행 초과) | 1-C 게이트에서 알리고 범위 축소 여부 확인 |
| 시트 권한 없음 (403) | 서비스 계정 공유 안내 + 확인 후 재시도 |
| API rate limit (429) | 60초 대기 후 1회 재시도, 실패 시 부분 결과 보고 |
| 원본·대상 탭이 같고 재실행 | 정상 — 파생 태그 행이 원본에서 제외된다. **제외 건수를 사용자에게 보고한다** |
| 사용자가 기획서를 함께 제공 | 이 절차는 읽지 않음을 알리고, 기획 기반 케이스가 필요하면 `testcase-auto` 를 안내 |

**원칙:** 1회 재시도 후 재실패 시 해당 기능 단위 없이 다음으로 진행하고, 보고서에 누락을 명시한다.

## 산출물 체크리스트

- [ ] `_workspace/augment/10_tc_inventory.md` / `.json` 존재 (Critical 0건 확인)
- [ ] (권한) `11_permission_matrix.md` 존재 + **사용자 확인 게이트 통과**
- [ ] `10_brief_{augmenter|reviewer}.md` 존재 (루프 전 1회 생성)
- [ ] 배치별 `12_cases_{EX|PM}-B{NN}.md` 모두 존재 (**첫 배치** 사용자 검토 완료)
- [ ] 배치별 `13_rows_{EX|PM}-B{NN}.tsv` 모두 존재
- [ ] `verify_sheet_rows.py` 위반 0건 + `--diff` 전 셀 일치
- [ ] `14_review_report_{EX|PM}.md` 존재 (작업 유형별)
- [ ] 시트 작성 행 범위가 기능 단위별로 기록됨
- [ ] **제외 항목이 사용자에게 보고됨** (없으면 "제외 없음" 명시)
- [ ] 사용자가 결과를 확인하고 피드백 기회를 제공받음
```

- [ ] **Step 4: 스킬이 요구 문구를 갖췄는지 확인**

Run:
```bash
grep -c '^## ' .claude/skills/testcase-augment/SKILL.md
for p in '리턴은 20줄' 'coverage-check' '첫 배치' '분포 편차를 지적하지 않는다' \
         'read_tc_inventory' 'verify_sheet_rows' '_workspace/augment' \
         '단일 출처' '엑셀' 'metadata'; do
  printf '%-32s %s\n' "$p" "$(grep -c "$p" .claude/skills/testcase-augment/SKILL.md)"
done
```
Expected: `##` 절 6개 이상, 위 10개 패턴 전부 1건 이상

- [ ] **Step 5: 스킬이 열 문자를 박지 않았는지 확인 (사양 규칙)**

Run: `grep -nE '\b(V열|W열|A1:W1|A~W 23)' .claude/skills/testcase-augment/SKILL.md || echo "열 문자 참조 0건 — ok"`
Expected: `열 문자 참조 0건 — ok`

열 문자가 나오면 **컬럼명으로 바꾼다.** 2026-08-25에 컬럼 하나를 삽입했다가 11개 파일의 열 문자 참조 78건을 재매핑해야 했던 사고가 있다.

- [ ] **Step 6: 커밋**

```bash
git add .claude/skills/testcase-augment/SKILL.md
git commit -m "$(cat <<'EOF'
스킬: testcase-augment 오케스트레이터 신설

기존 testcase-auto 에 모드를 얹지 않고 분리했다. 그쪽 Phase 0 질문 5개가
이 절차에서 하나도 그대로 쓰이지 않고(제품 유형은 실측 판정, 기획서 유형·
정책 예외는 개념 자체가 없다) Phase 1 의 이미지 변환·판독 게이트·변경 표시
검출도 전부 무관하다.

게이트 3곳을 두었다 — 권한 판독 확인 / 규모 확인 / 첫 배치 검토.
첫 배치는 작업 유형마다 기능 단위 1개 단독이다. 한쪽 통과가 다른 쪽을
보증하지 않는다(도출 규칙·태그가 다르다).

리뷰어 프롬프트의 오판 방지에 분포 편차 미지적을 넣었다 — 이 절차는 정의상
일부 구분만 만들어 어느 프로파일로 채점해도 지배 구분 역전이 뜬다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: 회귀 가드 + 사용자 문서 + `CLAUDE.md` 변경 이력

**Files:**
- Modify: `scripts/verify_unit_migration.sh` (신규 파일을 검사 대상에 추가 + 「추가 작업 절차의 안전장치」 가드 8개)
- Modify: `CLAUDE.md` (하네스 설명 · 트리거 · 변경 이력 1행)
- Modify: `README.md` · `docs/PROMPTS.md` · `HARNESS_OVERVIEW.md` · `HARNESS_WORKFLOW.md` · `HARNESS_PIPELINE.md`

**Interfaces:**
- Consumes: Task 1~9의 전 산출물
- Produces: `verify_unit_migration.sh` 가 새 절차의 안전장치를 영구 검사한다. 최종 태스크다.

- [ ] **Step 1: 가드 스크립트가 지금 통과하는지 먼저 확인 (기준선)**

Run: `bash scripts/verify_unit_migration.sh | tail -5`
Expected: `PASS — 처리 단위 재편 검사 통과`

여기서 이미 실패하면 Task 1~9 중 하나가 기존 규칙을 깼다는 뜻이다. **가드를 고치지 말고 원인을 고친다.**

- [ ] **Step 2: 실패하는 가드부터 추가한다**

`scripts/verify_unit_migration.sh` 의 `echo "── CLI 명령 오표기 가드 ─…"` 블록 **앞에** 아래를 삽입한다.

```bash
echo "── 회귀 가드: 추가 작업 절차의 안전장치 (2026-09-10) ─────"
# 새 절차가 기존 품질 장치를 우회하지 않았는가.
# `present` 는 열거한 **모든** 파일에 패턴이 있어야 통과한다 — 그 문구를 실제로
# 담는 파일만 열거한다. 넓게 잡으면 통과시키려고 문구를 억지로 흩뿌리게 된다.
present "원본 TC는 스크립트가 읽는다"   'read_tc_inventory' \
                                               .claude/skills/testcase-augment/SKILL.md
present "결정적 점검 재사용"            'verify_sheet_rows' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "분포 편차 점검 제외"           '분포 편차' \
                                               .claude/formats/common.md \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "파생 태그 행은 원본 제외"      '파생 태그' \
                                               .claude/formats/common.md \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "파생 태그 접두 파싱 블록"      '파생 태그 접두 \(스크립트 파싱 대상\)' \
                                               .claude/formats/common.md
present "첫 배치는 단독"                '첫 배치' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "리턴 20줄 제한"                '리턴은 20줄|리턴 규약' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "케이스 본문 시트 단일출처"     '단일 출처' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "엑셀 미지원 명시"              '엑셀' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "예외 카탈로그는 하한"          '상한이 아니라 하한' \
                                               .claude/skills/testcase-generator/references/exception-catalog.md
present "권한 규모 = 검증 지점 수"      '검증 지점' \
                                               .claude/skills/testcase-generator/references/permission-mode.md \
                                               .claude/skills/testcase-augment/SKILL.md
absent  "추가 작업 문서에 열 문자 박기" '\bV열\b|\bW열\b|A1:W1' \
                                               "${AUGMENT[@]}"
```

> **가드 하나를 추가할 때마다 「그 문구를 실제로 담는 파일이 어디인가」를 먼저 확인한다.**
> `present` 는 열거한 모든 파일을 요구하므로, 담지 않는 파일을 끼우면 통과시키려고 문구를
> 억지로 흩뿌리게 되고 문서가 망가진다. 반대로 `FAIL` 이 났을 때 **패턴을 느슨하게 바꾸면
> 가드가 아무것도 지키지 않는다.**

이어서 파일 상단의 배열 정의부(`DOCS=(...)` 다음 줄)에 아래를 추가한다.

```bash
AUGMENT=(.claude/skills/testcase-augment/SKILL.md
         .claude/agents/tc-augmenter.md
         .claude/skills/testcase-generator/references/exception-catalog.md
         .claude/skills/testcase-generator/references/permission-mode.md
         .claude/skills/testcase-reviewer/references/augment-mode.md)
```

그리고 기존 `CORE=(...)` **다음 줄**에 아래를 추가해 금지 패턴 검사에도 새 파일이 포함되게 한다.

```bash
CORE=("${CORE[@]}" "${AUGMENT[@]}")
```

- [ ] **Step 3: 가드를 돌려 통과를 확인**

Run: `bash scripts/verify_unit_migration.sh | tail -20`
Expected: 새로 추가한 「추가 작업 절차의 안전장치」 12개 항목이 전부 `ok` + `PASS`

`FAIL` 이 나면 그 패턴이 없는 파일을 열어 **문구를 넣는다** (가드의 패턴을 느슨하게 바꾸지 않는다 — 그러면 가드가 아무것도 지키지 않는다).

- [ ] **Step 4: 가드가 실제로 회귀를 잡는지 확인 (음성 대조)**

가드가 늘 통과하는 껍데기가 아닌지 본다.

Run:
```bash
cp .claude/skills/testcase-augment/SKILL.md /tmp/skill.bak
python3 -c "
p='.claude/skills/testcase-augment/SKILL.md'
s=open(p,encoding='utf-8').read().replace('첫 배치','최초 호출')
open(p,'w',encoding='utf-8').write(s)"
bash scripts/verify_unit_migration.sh | grep -E '첫 배치|^FAIL'; echo "exit=$?"
cp /tmp/skill.bak .claude/skills/testcase-augment/SKILL.md && rm /tmp/skill.bak
bash scripts/verify_unit_migration.sh | tail -2
```
Expected: 변조 상태에서 `FAIL  첫 배치는 단독 — 패턴 없음: …` 이 나오고, 복원 후 다시 `PASS`

- [ ] **Step 5: `CLAUDE.md` 의 하네스 설명과 트리거를 갱신**

`## 하네스: 테스트 케이스 자동 생성` 절의 `**트리거:**` 문단 **다음에** 아래를 삽입한다.

```markdown
**추가 작업 절차 (2026-09-10 신설):** 이미 작성된 테스트 케이스를 원천으로 **예외 사항**·**권한**
파생 케이스를 만드는 별도 절차가 있다. 트리거는 `"테스트케이스 추가 작업 진행해줘."` 이며
`testcase-augment` 스킬을 사용한다. **기획서를 읽지 않고**, 제품 유형은 원본 TC의 `솔루션` 컬럼
실측으로 판정한다(묻지 않는다). 구글 시트 전용이며 엑셀은 미지원이다. 산출물은
`_workspace/augment/` 에 격리된다. **파생 케이스는 프로파일 구분 분포 대조의 대상이 아니다** —
예외는 `비정상`·`엣지` 만, 권한은 `정상`·`부수` 만 만드는 것이 그 작업의 정의다.
```

`**환경:**` 목록의 팀 양식 사양 항목 뒤에 아래 한 줄을 추가한다.

```markdown
- **파생 케이스 근거 태그** — `[예외 파생 {원본 TC ID}]` / `[권한 매트릭스 {역할}×{기능}]`. 접두 목록은 `common.md` 「파생 케이스의 원천」의 코드블록이 단일 출처이며 `read_tc_inventory.py` 가 파싱한다
```

- [ ] **Step 6: `CLAUDE.md` 변경 이력에 1행 추가**

변경 이력 표의 **맨 아래**에 아래 행을 추가한다 (기존 행 형식·상세도를 따른다).

```markdown
| 2026-09-10 | **추가 작업 절차 신설 — 기존 테스트 케이스를 원천으로 `예외 사항`·`권한` 파생 케이스 생성** | `.claude/skills/testcase-augment/` 신규(SKILL + `read_tc_inventory.py`), `.claude/agents/tc-augmenter.md` 신규, `testcase-generator/references/{exception-catalog,permission-mode}.md` 신규, `testcase-reviewer/references/augment-mode.md` 신규, `.claude/formats/common.md`(v2.2), `build_brief.py`, `testcase-generator`·`testcase-reviewer` SKILL, `verify_unit_migration.sh`, 사용자 문서 5종 | 사용자 지시. **하네스의 원천이 기획서 하나여서 구조적으로 닿지 않는 영역이 둘 있었다** — ① **예외 흐름**: 기획서는 정상 흐름을 서술하고 필수값 미입력·형식 위반·중복·서버 오류·동시성 충돌·중단 이탈은 항목으로 존재하지 않는데, 하네스는 기획서에 없는 것을 단정하지 않는 규칙을 지키므로 이 영역이 통째로 비었다 ② **권한별 동작**: 역할마다 같은 기능이 다르게 동작하지만 그 매핑은 기획서가 아니라 별도 권한 자료에 있고 하네스에 읽는 경로가 없었다. 두 영역은 **이미 작성된 테스트 케이스를 원천으로 삼으면 닿는다** — 기존 케이스에 기능 단위(`화면 ID`·`1~3 Depth`)·절차·제품 유형(`솔루션`)·커버리지 현황(`구분`)이 다 들어 있다. **`testcase-auto` 에 모드를 얹지 않고 분리한 이유**는 그쪽 Phase 0 질문 5개가 하나도 그대로 쓰이지 않고(제품 유형은 실측 판정, 기획서 유형·정책 예외는 개념 자체가 없음) Phase 1의 이미지 변환·판독 게이트·변경 표시 검출도 전부 무관해, 한 파일에 넣으면 거의 모든 절에 `if 작업 유형` 분기가 붙어 **두 경로가 함께 무거워지기** 때문이다(2026-09-08에 `prd-analyzer` 를 조건별 `references/` 로 쪼갠 것과 같은 이유). 확정한 설계 결정 중 **가장 중요한 것은 「파생 케이스는 분포 편차 점검의 대상이 아니다」** 다 — 예외 파생은 정의상 `비정상`·`엣지` 만, 권한 파생은 `정상`·`부수` 만 만들어 **어느 프로파일로 채점해도 지배 구분 역전이 반드시 뜬다**(VIOLA `표시` 55.9% / TROMBONE `정상` 65.1%). 2026-08-24에 지배 구분 역전을 Critical로 규정한 것은 기획서 전수 케이스화를 전제한 판정이라, 그대로 적용하면 *"그 작업이 만들라고 한 것을 만들지 말라"* 는 리뷰가 되어 재작업 루프에 빠진다 → 사양·리뷰어 SKILL·`augment-mode` 참조 **세 곳**에 제외를 박고, 완전성 지표를 **예외 카탈로그 커버리지 / 매트릭스 셀 커버리지**로 대체했다. 그 밖에 정한 것 — ⓐ **원본 TC 읽기는 스크립트가 한다**(수백~수천 행을 에이전트에게 읽히면 2026-09-08 실측의 비용 구조가 재발한다. 인벤토리 집계에는 판단할 값이 없으므로 `verify_sheet_rows.py` 와 같은 논리) ⓑ **파생 태그가 붙은 행은 다음 실행에서 원본이 되지 않는다** — 원본 탭과 대상 탭이 같을 수 있어(허용된다) 빼지 않으면 재실행 때 **파생의 파생**이 생긴다. 접두 문자열은 사양의 코드블록이 단일 출처이며 스크립트가 파싱한다(스크립트에 박으면 태그 이름이 바뀔 때 조용히 깨진다) ⓒ **제품 유형은 `솔루션` 컬럼 실측으로 판정하고 묻지 않는다** — Phase 0 「추정 금지」와 충돌하지 않는다(추정이 아니라 실측이다) ⓓ **TC ID 다음 번호는 관련 스프레드시트 전 탭 최대값** 기준이며, 프로파일 형식을 파싱하지 않고 **접두별**로 센다 — TROMBONE `TC_{모듈코드}_{3자리}`(모듈별 연속)와 VIOLA(제품 전역 연속)를 한 코드로 다룰 수 있다 ⓔ **권한은 역할 × 기능 전수**이며 규모는 셀 수가 아니라 **검증 지점 수**로 센다(`조회 전용` 같은 부분 허용 셀은 허용 동작 1건 + 차단 동작 1건 = 2건) ⓕ **권한값 enum 을 하네스가 정하지 않고 자료에서 실측한다**(`허용/불가`·`조회/편집/없음`·`O/X` 등 자료마다 다르다) ⓖ **권한 자료의 기능 ↔ 원본 TC 기능 단위 매핑은 사용자 게이트에서 확정**하고 에이전트가 다시 매핑하지 않는다(셀 하나가 엉뚱한 화면에 붙으면 케이스가 통째로 틀린다. 미대응 기능은 화면 ID 승계 원본이 없으므로 **유추하지 않고 제외 후 보고**) ⓗ **예상 결과는 동작 수준까지만** 쓰고 문구·코드·지연 시간은 `[기획 확인]` 으로 넘긴다(단정하면 실행자가 잘못된 FAIL을 낸다). **엑셀은 미지원**으로 확정했다 — 현행 시트 I/O가 `sheets_api.py` 하나이고 엑셀을 넣으면 읽기·쓰기·`--diff` 까지 대응 계층이 필요하다. `verify_sheet_rows.py` 는 **수정하지 않았다**(`비고` 를 공란 여부로만 보고 태그 어휘를 검사하지 않아 신설 태그가 위반으로 잡히지 않으면서 나머지 결정적 점검이 그대로 유효하다). 재발 방지로 `verify_unit_migration.sh` 에 안전장치 가드 10개를 신설했다. 설계·계획: `docs/superpowers/specs/2026-09-10-testcase-augment-design.md`, `docs/superpowers/plans/2026-09-10-testcase-augment.md` |
```

- [ ] **Step 7: 사용자 문서 5종에 새 절차를 등재**

각 파일에 아래를 반영한다. 기존 문서의 절 구성·문체를 따른다.

| 파일 | 넣을 것 |
|------|--------|
| `README.md` | 「사용법」에 트리거 `"테스트케이스 추가 작업 진행해줘."` + 입력 4~5개 표 + **엑셀 미지원** 명시 |
| `docs/PROMPTS.md` | 새 절(「추가 작업 — 예외 사항 / 권한」) 신설. 프롬프트 예시 2개(예외만 / 권한 포함)와 **묻지 않는 것**(제품 유형·기획서) 안내 |
| `HARNESS_OVERVIEW.md` | 구성 요소 목록에 스킬 1·에이전트 1·스크립트 1·참조 3 추가. 도구 표에 `read_tc_inventory.py`(CLI 옵션·종료 코드) 추가 |
| `HARNESS_WORKFLOW.md` | 실행 절차에 「추가 작업」 흐름(Phase 0~4, 게이트 3곳) 추가 |
| `HARNESS_PIPELINE.md` | 흐름도에 **두 번째 파이프라인**을 나란히 표기. 원천이 기획서가 아니라 기존 TC임을 명시 |

`README.md` 에 넣을 문안:

```markdown
### 테스트케이스 추가 작업 (예외 사항 / 권한)

이미 작성된 테스트 케이스를 원천으로 **기획서에 없는 검증**을 파생 생성한다. 기획서를 읽지 않는다.

프롬프트에 `테스트케이스 추가 작업 진행해줘.` 를 입력하면 아래를 순서대로 묻는다.

| 순서 | 묻는 것 |
|------|--------|
| 1 | 추가 작업 유형 — `예외 사항` / `권한` (복수 선택 가능) |
| 2 | 원본 TC 시트 URL + **원본 탭** (탭 목록을 보여주고 고르게 한다) |
| 3 | 작성 대상 시트 URL + 탭 (없으면 생성) |
| 4 | (`권한` 일 때) 권한 자료 경로 — 시트 URL / CSV·마크다운 / 이미지·PDF |

**묻지 않는 것:** 제품 유형(원본 TC의 `솔루션` 컬럼 실측으로 판정), 기획서 경로·유형.

**구글 시트 전용이다.** 엑셀(.xlsx) 경로가 들어오면 미지원을 안내하고 중단한다 —
구글 시트로 옮기거나 CSV로 내보내면 된다.

진행 중 사용자 확인 게이트가 3곳 있다 — **권한 자료 판독 확인** / **규모 확인**(역할 × 기능
전수는 수백 행이 될 수 있다) / **첫 배치 검토**(문체·태그 오류가 전 행에 번지기 전에 잡는다).
```

- [ ] **Step 8: 문서 반영을 확인**

Run:
```bash
for f in README.md docs/PROMPTS.md HARNESS_OVERVIEW.md HARNESS_WORKFLOW.md HARNESS_PIPELINE.md CLAUDE.md; do
  printf '%-24s testcase-augment=%s 추가작업=%s\n' "$f" \
    "$(grep -c 'testcase-augment' "$f")" "$(grep -c '추가 작업' "$f")"
done
grep -c '2026-09-10' CLAUDE.md
bash scripts/verify_unit_migration.sh | tail -2
```
Expected: 여섯 파일 모두 `testcase-augment` ≥ 1, `CLAUDE.md` 에 `2026-09-10` ≥ 1, 가드 `PASS`

- [ ] **Step 9: 전체 검증을 한 번에 돌린다**

Run:
```bash
bash scripts/verify_unit_migration.sh | tail -3
python3 scripts/build_brief.py --coverage-check | tail -3
python3 scripts/read_tc_inventory.py --selftest | tail -3
python3 scripts/verify_sheet_rows.py --selftest | tail -3
```
Expected: 네 개 모두 `PASS` / `✅` / 종료 코드 `0`

**`verify_sheet_rows.py --selftest` 를 반드시 함께 돌린다** — Task 1이 `common.md` 를 고쳤으므로 그 스크립트의 사양 파서가 깨졌을 수 있다. 깨졌다면 태그표에 추가한 행이나 새 절이 파서의 정규식과 충돌한다는 뜻이다.

- [ ] **Step 10: 커밋**

```bash
git add scripts/verify_unit_migration.sh CLAUDE.md README.md docs/PROMPTS.md \
        HARNESS_OVERVIEW.md HARNESS_WORKFLOW.md HARNESS_PIPELINE.md
git commit -m "$(cat <<'EOF'
문서·가드: 추가 작업 절차 등재 + 회귀 가드 10개

verify_unit_migration.sh 에 새 절차의 안전장치를 영구 가드로 넣었다 —
원본 TC 스크립트 읽기·결정적 점검 재사용·분포 편차 제외·파생 태그 행 제외·
접두 파싱 블록·첫 배치 단독·리턴 20줄·시트 단일출처·엑셀 미지원·열 문자
금지. 비용을 줄이거나 기능을 늘리려다 품질 장치를 잃는 회귀를 막는다.

CLAUDE.md 변경 이력에 설계 결정과 그 사유를 남겼다. 규칙이 생긴 사유의
권위는 그 표다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 자기 점검 (계획 작성자가 수행함)

**1. 스펙 커버리지** — 스펙 15개 절 전부에 대응 태스크가 있다.

| 스펙 절 | 태스크 |
|---------|--------|
| §1~2 배경·변경 요지 | (배경 — 구현 대상 아님) |
| §3 결정 1 (별도 오케스트레이터) | Task 9 |
| §3 결정 2 (스크립트가 읽는다) | Task 2·3·4, 가드 Task 10 |
| §3 결정 3 (분포 점검 제외) | Task 1(사양) · 7(리뷰어) · 9(프롬프트), 가드 Task 10 |
| §3 결정 4 (`솔루션` 실측 판정) | Task 2(`profile_solutions`) · 3(`build_inventory`) · 9(Phase 0-4) |
| §3 결정 5 (파생 태그 행 제외) | Task 1(접두 블록) · 3(집계) , 가드 Task 10 |
| §3 결정 6 (전 탭 TC ID 최대값) | Task 3(`tcid_max_by_prefix`) · 4(`scan_tcids`) |
| §3 결정 7 (기능 매핑 게이트) | Task 6 · 9(Phase 1-B) |
| §3 결정 8 (게이트 3곳) | Task 9(Phase 1-B·1-C·2) |
| §4 Phase 0~4 | Task 9 |
| §5 예외 카탈로그 | Task 5 |
| §6 권한 사양 | Task 6 |
| §7 예외 양식 매핑·중복 판정 | Task 5 |
| §8 산출물 사양 | Task 4(인벤토리) · 8(케이스·TSV) · 9(프로토콜 표) |
| §9 `common.md` 변경 + 절 배정 | Task 1 |
| §10 파일별 변경 명세 | Task 1~10 전부 |
| §11 오판 방지 목록 | Task 7 · 9 |
| §12 신규 에러 처리 | Task 9(에러 표) · 3·4(종료 코드) |
| §13 리스크 완화 | Task 1·3·7·9 (각 완화 항목이 해당 태스크에 들어 있다) |
| §14 검증 방법 | Task 2·3·4(selftest) · 10(가드·전체 검증) |
| §15 유지되는 것 | Task 10 가드 |

**2. 플레이스홀더 스캔** — `TBD`·`TODO`·"적절히 처리"·"Task N과 유사" 없음. 스펙 표를 옮기라고 지시한 3곳(Task 5 Step 2 · Task 6 · Task 7 Step 2)은 **출처 절 번호와 확인 명령을 함께 준** 것이며, 옮긴 뒤 안내 문장이 남았는지 검사하는 단계가 붙어 있다.

**3. 타입·이름 일관성** — 태스크 간 계약을 대조했다.

| 이름 | 정의 | 사용 |
|------|------|------|
| `spec_header` · `derived_prefixes` · `profile_solutions` | Task 2 | Task 3 selftest · Task 4 `main` |
| `header_mismatch` · `tcid_max_by_prefix` · `build_inventory` · `findings` · `exit_code` | Task 3 | Task 4 `main` · selftest |
| `read_tsv` · `render_md` · `load_tab` · `scan_tcids` · `_sheets_client` | Task 4 | Task 4 `main` |
| `_cells` · `_plain` · `_ticks` · `_idx` · `_cell` · `_one_line` | Task 2·3 | Task 3·4 |
| `--role=augmenter` · `--doc-type=추가` | Task 1 | Task 9 Phase 1-D |
| `10_tc_inventory.md` / `.json` | Task 4 | Task 8 · 9 |
| `11_permission_matrix.md` | Task 9 Phase 1-B | Task 6 · 8 |
| `12_cases_{EX\|PM}-B{NN}.md` · `13_rows_{EX\|PM}-B{NN}.tsv` | Task 8 | Task 9 Phase 3-1 |
| `13_rows_all_{EX\|PM}.tsv` | Task 9 Phase 3-1 (셸 병합) | `verify_sheet_rows.py --diff` |
| `14_review_report_{EX\|PM}.md` | Task 7 | Task 9 Phase 3-2 |
| `AUGMENT` 배열 | Task 10 Step 2 | Task 10 가드 |

**고친 것 하나** — Task 4 Step 4의 `main()` 코드에 초안 흔적(`if False else None`)이 남아 있었다. 실행자가 그대로 붙여 넣으면 `inv` 가 `None` 이 되어 다음 줄에서 죽는다. **지우라는 주석을 다는 대신 코드에서 실제로 제거**하고, 헤더 불일치 분기의 중복된 빈 인벤토리 딕셔너리를 `empty` 지역 변수로 묶었다 — 같은 리터럴을 두 번 쓰면 한쪽만 고치는 사고가 난다.


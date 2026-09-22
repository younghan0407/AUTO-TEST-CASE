# 기획서 분석 절차(`prd-digest`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기획서에서 **모든 기능의 설명**(메뉴 구조 축)과 **신규·변경·삭제 기능**(화면 ID 축)을 뽑아 MD 2개로 내는 세 번째 절차를 하네스에 추가한다. 테스트 케이스를 만들지 않고 시트를 쓰지 않는다.

**Architecture:** `testcase-auto`·`testcase-augment` 와 나란한 독립 오케스트레이터 `prd-digest` 를 신설한다. 메뉴 트리는 **메뉴 IA 엑셀을 스크립트가 결정적으로 파싱**하고(판단할 값이 없는 일을 모델에게 시키지 않는다), 기획서 판독은 **기능 설명과 분류**에만 쓴다. 화면 에이전트는 사람이 읽을 `.md` 와 기계용 `.tsv` 를 함께 내고, 렌더러가 그 TSV를 **메뉴 트리 순서**와 **화면 ID 순서**로 두 번 배열한다 — 모델이 같은 사실을 두 번 적지 않으므로 두 MD가 어긋날 수 없다. 판독 규칙·이미지 변환·변경 표시 검출은 `prd-analyzer` 와 기존 스크립트를 그대로 재사용한다.

**Tech Stack:** Python 3.9 표준 라이브러리 + **`openpyxl`**(IA 엑셀 파싱 — 이 절차가 들여오는 유일한 새 의존성). 테스트는 저장소 관행대로 스크립트 내장 `--selftest`(pytest 미사용 — `requirements.txt` 에 테스트 의존성이 없고 `prd_cache.py`·`verify_sheet_rows.py`·`read_tc_inventory.py` 가 모두 같은 방식이다). 문서 회귀는 `scripts/verify_unit_migration.sh` 가 검사한다.

**Spec:** `docs/superpowers/specs/2026-09-19-prd-digest-design.md`

## Global Constraints

- **선행 스펙은 구현 완료다.** `{WS}` = `_workspace/{디렉터리명}/digest`, `{SHARED}` = `_workspace/{디렉터리명}/shared`.
  경로의 단일 출처는 `testcase-auto` SKILL **`0-0`** 절이며, `prd-digest` SKILL 도 **자기 `0-0` 절**을 갖고 거기서만 `_workspace` 를 쓴다.
- **`_workspace` 문자열은 오케스트레이터 SKILL 의 `0-0` 절에만 둔다.** 에이전트·참조 문서에는 한 번도 나오면 안 되며 `absent` 가드가 강제한다.
- **에이전트에게는 치환된 실제 경로를 준다.** `{WS}` 를 그대로 프롬프트에 넣지 않는다.
- **이미지 디렉터리는 `{SHARED}/images`·`{SHARED}/images_desc`** 이고 variant 는 `full`·`desc` 둘이다. `tiled` 는 없다(`prd-analyzer` PDF-2 가 전체 페이지 분할을 금지한다).
- **캐시 검사는 `python scripts/prd_cache.py check --pdf=<PDF> --shared={SHARED} --require=full,desc`.** `--require=` 를 빼면 아는 variant 만 검사해 반만 채워진 트리가 `CACHE_OK` 를 받는다.
- **`.claude/formats/` 와 `build_brief.py` 는 건드리지 않는다.** 이 절차엔 23컬럼도 분포도 문체 규칙도 없다. 프로파일에서는 화면 ID 체계만 읽는다.
- **시트를 쓰지 않는다.** `sheets_api.py` 를 호출하지 않는다.
- 명령은 `python3` 으로 실행한다(이 환경에 `python` 이 없다). **문서에 *쓰는* 예시 명령은 `python scripts/…` 표기를 유지한다.**
- **Python 3.9 호환.** 새 스크립트에 `from __future__ import annotations` 를 반드시 넣는다.
- 모든 문서는 **한국어 단정형 서술**. 규칙과 그 근거가 된 실측을 함께 적는 기존 문체를 따른다.
- **`.superpowers/` 아래는 커밋하지 않는다**(git-ignore 대상 스크래치). `git add` 는 경로 명시, **`-A`·`.` 금지** — 미추적 3경로(`.claude/jobs/`·`docs/HARNESS_INTRODUCTION.md`·`docs/slides/`)는 그대로 둔다.
- 커밋 메시지는 한국어 접두(`기능:`/`재편:`/`수정:`/`문서:`/`정정:`)를 쓰고 끝에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` 를 붙인다. 브랜치 생성·push·merge 하지 않는다.
- **검증 기준선 (착수 전 실측).** 어느 태스크도 이 다섯을 깨뜨린 채 완료하지 않는다.

  | 명령 | 기대 |
  |------|------|
  | `bash scripts/verify_unit_migration.sh` | `PASS` |
  | `python3 scripts/prd_cache.py --selftest` | `selftest PASS — 37건 통과` |
  | `python3 scripts/verify_sheet_rows.py --selftest` | 위반 17종 검출 + 오탐 0건 |
  | `python3 scripts/read_tc_inventory.py --selftest` | `PASS` |
  | `python3 scripts/build_brief.py --coverage-check` | `✅ 전 절 배정 완료 · 유령 배정 0건` |

## 착수 전 실측 — 계획이 근거로 삼는 값

이 계획을 쓰며 **두 IA 엑셀을 실제로 파싱해** 확인했다. 스펙의 수치 하나가 틀렸으므로 여기 값이 우선이다.

| | K8s IA | CI/CD IA |
|---|---|---|
| 파일 | `(4.0) VIOLA_메뉴IA구조도_v1.0_260727.xlsx` | `(4.0) VIOLA CICD_메뉴 IA 구조도 v1.0_260731.xlsx` |
| 시트 | `1. 메뉴구조도` | 같음 |
| 헤더 행 | 3 | 3 |
| **`LEVEL` 열 수** | **4** (`LEVEL 1`~`LEVEL 4 (Tab)`, D~G) | **2** (`LEVEL 1`·`LEVEL 2`, D~E) |
| `화면ID` 열 | **H** | **F** |
| `화면명` 열 | **I** | **G** |
| 화면 수 | **299** | 97 |

**두 가지가 설계를 좌우한다.**

1. **열 문자를 박으면 CI/CD 에서 조용히 엉뚱한 열을 읽는다.** 두 파일의 `화면ID` 가 H와 F로 다르고 `LEVEL` 열 수도 4와 2로 다르다. **헤더 이름으로 열을 찾고 `LEVEL` 열 수는 세어서 알아낸다.**
2. **화면 ID 접두로 거르면 안 된다.** 스펙이 적은 `292` 는 `VIOE` 접두로 걸러 나온 값이고, **실제는 299**다. 차이 7건은 K8s 메뉴 `기본 설정 > 클러스터 관리 > 이미지 저장소` 아래에 있는 **`CICD-` 접두 화면**이다. IA 는 메뉴 트리의 권위이고, 한 제품의 메뉴가 다른 접두의 화면을 담는 일이 실재한다.

## File Structure

| 파일 | 책임 |
|------|------|
| **신설** `.claude/skills/prd-digest/scripts/parse_menu_ia.py` | IA 엑셀 → 메뉴 트리(JSON + MD). `openpyxl`. `--selftest` |
| **신설** `.claude/skills/prd-digest/scripts/render_digest.py` | 화면별 TSV + 메뉴 트리 + 화면 인덱스 → MD 2개. 표준 라이브러리. `--selftest` |
| **신설** `.claude/skills/prd-digest/scripts/verify_digest.py` | 결정적 점검 + `--selftest` |
| **신설** `scripts/parse_menu_ia.py` · `render_digest.py` · `verify_digest.py` | 위 셋으로의 상대 심볼릭 링크 |
| **신설** `.claude/skills/prd-analyzer/references/digest-mode.md` | 이 모드 전용 판독 절 (기능 단위 요약 · 3분류 + 확인 필요) |
| **신설** `.claude/agents/prd-digester.md` | 화면 배치 처리 에이전트 |
| **신설** `.claude/skills/testcase-reviewer/references/digest-mode.md` | 집계 리뷰 절 + **역방향 오판 금지** |
| **신설** `.claude/skills/prd-digest/SKILL.md` | 오케스트레이터 (`0-0` 절 포함) |
| `CLAUDE.md` | 트리거 분기 · 절차 등재 · `openpyxl` 의존성 · 변경 이력 |
| `verify_setup.py` | 새 스킬·에이전트·링크 3개 검사 |
| `scripts/verify_unit_migration.sh` | 회귀 가드 — 이 절차 절에 **12개**(구현 중 6개 추가) + 가드 자체 점검 1개 |
| 사용자 문서 7종 | 세 번째 절차 등재 |

### 공용 계약 — 두 스크립트가 같은 것을 다르게 적지 않도록 여기 한 번만 정의한다

**화면별 TSV (`{WS}/02_features_s{NN}.tsv`)** — 헤더 없음, 탭 구분, 7열 고정:

```
화면ID	기능명	설명	분류	근거	페이지	메뉴경로_폴백
```

- `분류` enum은 **`신규` · `변경` · `삭제` · `확인 필요` · `미변경`** 5종뿐이다
  (계획 당시 4종으로 적었으나 구현 중 `미변경` 이 추가됐다 — 그 값이 없으면 변경 표기가
  붙지 않은 기능을 담을 자리가 없어 `03_기능_전체.md` 가 전체 목록이 아니게 된다)
- `메뉴경로_폴백` 은 IA에 없는 화면에만 채운다(`>` 로 구분). IA에 있으면 빈칸
- 셀 안에 탭·개행을 넣지 않는다

**메뉴 트리 JSON (`{WS}/00_menu_tree.json`)** — `parse_menu_ia.py` 산출:

```json
{
  "source": "(4.0) VIOLA_메뉴IA구조도_v1.0_260727.xlsx",
  "sheet": "1. 메뉴구조도",
  "level_count": 4,
  "screens": [
    {"screen_id": "VIOE-04_06_01", "name": "외부 알람 목록",
     "path": ["모니터링", "외부 알람 설정", "-", "-"]}
  ]
}
```

- `path` 길이는 항상 `level_count` 와 같고, 빈 칸은 `"-"` 다
- 렌더러는 `path` 에서 `"-"` 를 빼고 `" > "` 로 잇는다. 전부 `"-"` 면 **「공통 정의」** 절로 간다

**조회 우선순위 — 렌더러가 채운다. 에이전트가 옮겨 적지 않는다.**

| 값 | 1순위 | 폴백 | 둘 다 없으면 |
|----|------|------|------------|
| 메뉴 경로 | 메뉴 트리 JSON | TSV의 `메뉴경로_폴백` | `(경로 없음)` |
| 화면명 | 메뉴 트리 JSON | `00_screen_index.md` 의 `Page Title` | `(이름 없음)` |

---

### Task 1: `parse_menu_ia.py` — 메뉴 IA 엑셀 → 메뉴 트리

**Files:**
- Create: `.claude/skills/prd-digest/scripts/parse_menu_ia.py`
- Create: `scripts/parse_menu_ia.py` (상대 심볼릭 링크)
- Modify: `verify_setup.py` (링크 목록 + `openpyxl` 패키지 검사)
- Test: 스크립트 내장 `--selftest` (별도 테스트 파일 없음 — 저장소 관행)

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `parse_ia(path: str) -> dict` — `{source, sheet, level_count, screens:[{screen_id,name,path}]}`
  - `menu_path(entry: dict) -> str` — `"-"` 를 뺀 `" > "` 결합, 전부 `"-"` 면 빈 문자열
  - `render_tree_md(data: dict) -> str`
  - `IAParseError(code, detail)` — `code` 는 `IA_NO_SHEET`·`IA_NO_HEADER`·`IA_NO_COLUMN`·`IA_NO_OPENPYXL`
  - CLI: `parse_menu_ia.py <IA.xlsx> --out-json=<경로> --out-md=<경로>` · 종료 코드 0 성공 / 3 파싱 실패
  - Task 2(`render_digest.py`)가 `00_menu_tree.json` 을 읽고, Task 6(SKILL)이 이 CLI를 호출한다

- [ ] **Step 1: 스텁으로 파일을 만들고 실패를 본다**

아래 전문을 `.claude/skills/prd-digest/scripts/parse_menu_ia.py` 로 만들되, **`parse_ia` 의
본문만 `raise NotImplementedError` 로 두고** 나머지는 그대로 쓴다. 이 단계의 목적은
`--selftest` 가 실패하는 것을 보는 것이다.

- [ ] **Step 2: 실패 확인**

Run: `python3 .claude/skills/prd-digest/scripts/parse_menu_ia.py --selftest`
Expected: `NotImplementedError` 로 죽는다

- [ ] **Step 3: `parse_ia` 본문을 넣어 전문을 완성한다**

```python
#!/usr/bin/env python3
"""메뉴 IA 엑셀에서 메뉴 트리와 화면 ID 매핑을 뽑는다.

왜 스크립트인가
---------------
메뉴 경로는 판단할 값이 없다 — 엑셀에 이미 적혀 있다. 모델에게 트리 이미지를
판독시키면 들여쓰기 깊이를 오독하고, 개정판의 Menu Structure 페이지는 **바뀐
가지 위주로** 그려져 전체 트리가 나오지도 않는다.

⚠️ 열 문자를 박지 않는다 — 문서마다 다르다 (실측)
--------------------------------------------------
  K8s   : LEVEL 열 4개(D~G) · 화면ID = H · 화면명 = I · 화면 299
  CI/CD : LEVEL 열 2개(D~E) · 화면ID = F · 화면명 = G · 화면 97
열을 고정하면 CI/CD 에서 **조용히 엉뚱한 열**을 읽는다. 헤더 이름으로 찾고
LEVEL 열 수는 세어서 알아낸다.

⚠️ 화면 ID 접두로 거르지 않는다 (실측)
--------------------------------------
K8s IA 의 `기본 설정 > 클러스터 관리 > 이미지 저장소` 아래에 **`CICD-` 접두 화면이
7건** 있다. `VIOE` 만 남기면 그 7건이 사라진다. IA 는 메뉴 트리의 권위이고, 한
제품의 메뉴가 다른 접두의 화면을 담는 일이 실재한다.

사용:
  python parse_menu_ia.py <IA.xlsx> --out-json=<경로> --out-md=<경로>
  python parse_menu_ia.py --selftest

종료 코드: 0 성공 / 3 파싱 실패(IA_NO_SHEET·IA_NO_HEADER·IA_NO_COLUMN)
"""
from __future__ import annotations

import json
import os
import sys

SHEET_CANDIDATES = ("1. 메뉴구조도", "메뉴구조도")
HEADER_SCAN_ROWS = 12


class IAParseError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__("%s %s" % (code, detail))
        self.code = code


def _find_header_row(ws) -> int:
    for r in range(1, min(HEADER_SCAN_ROWS, ws.max_row) + 1):
        for c in ws[r]:
            if c.value and str(c.value).strip() == "화면ID":
                return r
    raise IAParseError("IA_NO_HEADER", "'화면ID' 헤더를 찾을 수 없다")


def _locate_columns(ws, header_row: int) -> dict:
    """헤더 이름으로 열을 찾는다. LEVEL 열 수는 문서마다 다르므로 세어서 알아낸다."""
    levels = []
    sid = name = None
    for c in ws[header_row]:
        v = str(c.value).strip() if c.value else ""
        if not v:
            continue
        if v.startswith("LEVEL"):
            levels.append(c.column)
        elif v == "화면ID":
            sid = c.column
        elif v == "화면명":
            name = c.column
    if sid is None or name is None:
        raise IAParseError("IA_NO_COLUMN", "화면ID 또는 화면명 열이 없다")
    return {"levels": sorted(levels), "sid": sid, "name": name}


def parse_ia(path: str) -> dict:
    try:
        import openpyxl
    except ImportError:
        raise IAParseError("IA_NO_OPENPYXL", "openpyxl 이 필요하다: pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    sheet = next((s for s in SHEET_CANDIDATES if s in wb.sheetnames), None)
    if sheet is None:
        raise IAParseError("IA_NO_SHEET", "메뉴구조도 시트가 없다: %s" % wb.sheetnames)
    ws = wb[sheet]
    hdr = _find_header_row(ws)
    cols = _locate_columns(ws, hdr)

    screens = []
    for r in range(hdr + 1, ws.max_row + 1):
        raw = ws.cell(r, cols["sid"]).value
        sid = str(raw).strip() if raw is not None else ""
        if not sid:
            continue
        path_parts = []
        for ci in cols["levels"]:
            v = ws.cell(r, ci).value
            v = str(v).strip() if v is not None and str(v).strip() else "-"
            path_parts.append(v)
        nm = ws.cell(r, cols["name"]).value
        screens.append({
            "screen_id": sid,
            "name": str(nm).strip() if nm is not None else "",
            "path": path_parts,
        })
    return {
        "source": os.path.basename(path),
        "sheet": sheet,
        "level_count": len(cols["levels"]),
        "screens": screens,
    }


def menu_path(entry: dict) -> str:
    parts = [p for p in entry["path"] if p != "-"]
    return " > ".join(parts) if parts else ""


def render_tree_md(data: dict) -> str:
    out = ["# 메뉴 트리 — %s" % data["source"], ""]
    out.append("- 시트: `%s` · `LEVEL` 열 %d개 · 화면 %d개"
               % (data["sheet"], data["level_count"], len(data["screens"])))
    out.append("- **화면 ID 접두로 거르지 않았다** — 한 제품의 메뉴가 다른 접두의 화면을 담는다")
    out.append("")
    groups = {}
    for s in data["screens"]:
        groups.setdefault(menu_path(s), []).append(s)
    if "" in groups:
        out.append("## 공통 정의 (메뉴 경로 없음)")
        out.append("")
        for s in groups.pop(""):
            out.append("- `%s` %s" % (s["screen_id"], s["name"]))
        out.append("")
    for path in sorted(groups):
        out.append("## %s" % path)
        out.append("")
        for s in groups[path]:
            out.append("- `%s` %s" % (s["screen_id"], s["name"]))
        out.append("")
    return "\n".join(out)


def _make_fixture(path: str, levels: int, sid_col_gap: int, header_row: int = 3) -> None:
    """검사용 엑셀을 만든다. `sid_col_gap` 으로 LEVEL 열 수에 따른 열 이동을 재현한다."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "1. 메뉴구조도"
    base = 4  # D열부터 LEVEL 시작
    for i in range(levels):
        ws.cell(header_row, base + i, "LEVEL %d" % (i + 1))
    sid_c = base + levels + sid_col_gap
    ws.cell(header_row, sid_c, "화면ID")
    ws.cell(header_row, sid_c + 1, "화면명")
    rows = [
        (["-"] * levels, "VIOE-00_00_00", "레이아웃 정의"),
        (["모니터링"] + ["-"] * (levels - 1), "VIOE-04_06_01", "외부 알람 목록"),
        (["기본 설정"] + ["이미지 저장소"] + ["-"] * (levels - 2) if levels >= 2
         else ["기본 설정"], "CICD-03_02_01", "이미지 저장소 목록"),
    ]
    r = header_row + 1
    for parts, sid, nm in rows:
        for i, v in enumerate(parts[:levels]):
            ws.cell(r, base + i, v)
        ws.cell(r, sid_c, sid)
        ws.cell(r, sid_c + 1, nm)
        r += 1
    ws.cell(r, sid_c, "")          # 빈 화면ID 행 — 건너뛰어야 한다
    ws.cell(r, sid_c + 1, "무시됨")
    wb.save(path)


def _selftest() -> int:
    import tempfile
    fails = []

    def chk(name, cond, detail=""):
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    with tempfile.TemporaryDirectory() as t:
        # S1 — K8s 모양: LEVEL 4개
        f1 = os.path.join(t, "k8s.xlsx")
        _make_fixture(f1, levels=4, sid_col_gap=0)
        d1 = parse_ia(f1)
        chk("S1 LEVEL 열 4개를 센다", d1["level_count"] == 4, d1["level_count"])
        chk("S1 빈 화면ID 행은 건너뛴다", len(d1["screens"]) == 3, len(d1["screens"]))
        chk("S1 path 길이 = level_count",
            all(len(s["path"]) == 4 for s in d1["screens"]))
        chk("S1 경로 없는 화면은 빈 문자열",
            menu_path(d1["screens"][0]) == "", menu_path(d1["screens"][0]))
        chk("S1 경로 조합", menu_path(d1["screens"][1]) == "모니터링",
            menu_path(d1["screens"][1]))

        # S2 — CI/CD 모양: LEVEL 2개, 화면ID 열이 앞당겨진다
        f2 = os.path.join(t, "cicd.xlsx")
        _make_fixture(f2, levels=2, sid_col_gap=0)
        d2 = parse_ia(f2)
        chk("S2 LEVEL 열 2개를 센다", d2["level_count"] == 2, d2["level_count"])
        chk("S2 열이 옮겨져도 화면ID를 찾는다",
            [s["screen_id"] for s in d2["screens"]][:1] == ["VIOE-00_00_00"])
        chk("S2 2단 경로 조합", menu_path(d2["screens"][2]) == "기본 설정 > 이미지 저장소",
            menu_path(d2["screens"][2]))

        # S3 — 접두가 다른 화면도 남는다
        chk("S3 CICD- 접두 화면이 걸러지지 않는다",
            any(s["screen_id"].startswith("CICD-") for s in d1["screens"]))

        # S4 — 헤더 행 위치가 달라도 찾는다
        f4 = os.path.join(t, "hdr7.xlsx")
        _make_fixture(f4, levels=4, sid_col_gap=0, header_row=7)
        d4 = parse_ia(f4)
        chk("S4 헤더 행이 7이어도 찾는다", len(d4["screens"]) == 3, len(d4["screens"]))

        # S5 — 시트 없음
        import openpyxl
        f5 = os.path.join(t, "nosheet.xlsx")
        wb = openpyxl.Workbook(); wb.active.title = "다른시트"; wb.save(f5)
        try:
            parse_ia(f5); chk("S5 시트 없으면 IA_NO_SHEET", False, "예외 없음")
        except IAParseError as e:
            chk("S5 시트 없으면 IA_NO_SHEET", e.code == "IA_NO_SHEET", e.code)

        # S6 — 화면ID 헤더 없음
        f6 = os.path.join(t, "nohdr.xlsx")
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "1. 메뉴구조도"
        ws.cell(3, 4, "LEVEL 1"); wb.save(f6)
        try:
            parse_ia(f6); chk("S6 헤더 없으면 IA_NO_HEADER", False, "예외 없음")
        except IAParseError as e:
            chk("S6 헤더 없으면 IA_NO_HEADER", e.code == "IA_NO_HEADER", e.code)

        # S7 — MD 렌더: 경로 없는 화면은 「공통 정의」로
        md = render_tree_md(d1)
        chk("S7 공통 정의 절이 있다", "## 공통 정의 (메뉴 경로 없음)" in md)
        chk("S7 공통 정의에 해당 화면이 들어간다",
            md.split("## 공통 정의")[1].split("##")[0].count("VIOE-00_00_00") == 1)
        chk("S7 경로 있는 화면은 경로 절로 간다", "## 모니터링" in md)

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — 15건 통과")
    return 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return _selftest()
    args = [a for a in argv if not a.startswith("--")]
    opt = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opt[k] = v
    if not args:
        print(__doc__)
        return 1
    try:
        data = parse_ia(args[0])
    except IAParseError as e:
        print(str(e))
        return 3
    if opt.get("out-json"):
        os.makedirs(os.path.dirname(opt["out-json"]) or ".", exist_ok=True)
        with open(opt["out-json"], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if opt.get("out-md"):
        os.makedirs(os.path.dirname(opt["out-md"]) or ".", exist_ok=True)
        with open(opt["out-md"], "w", encoding="utf-8") as f:
            f.write(render_tree_md(data))
    print("IA_OK 시트=%s LEVEL열=%d 화면=%d"
          % (data["sheet"], data["level_count"], len(data["screens"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인**

Run: `python3 .claude/skills/prd-digest/scripts/parse_menu_ia.py --selftest`
Expected: `selftest PASS — 15건 통과` · 종료 코드 `0`

- [ ] **Step 5: 실제 IA 두 파일로 확인한다 — 이 태스크의 핵심 검증**

```bash
cd /Users/hanflex/Git/testcase-auto
T=$(mktemp -d)
python3 scripts/parse_menu_ia.py "PDF/VIOLA_V4.0/(4.0) VIOLA_메뉴IA구조도_v1.0_260727.xlsx" --out-json=$T/k8s.json --out-md=$T/k8s.md
python3 scripts/parse_menu_ia.py "PDF/VIOLA_V4.0/(4.0) VIOLA CICD_메뉴 IA 구조도 v1.0_260731.xlsx" --out-json=$T/cicd.json
head -6 $T/k8s.md
rm -rf $T
```

Expected:

```
IA_OK 시트=1. 메뉴구조도 LEVEL열=4 화면=299
IA_OK 시트=1. 메뉴구조도 LEVEL열=2 화면=97
```

**두 줄의 `LEVEL열` 이 4와 2로 다른 것이 이 태스크가 옳게 됐다는 증거다.** 같은 값이
나오면 열을 헤더 이름이 아니라 위치로 찾고 있다는 뜻이다.

- [ ] **Step 6: 음성 대조 — 열 탐색이 실제로 이름 기반인지 확인한다**

`_locate_columns` 의 `if v.startswith("LEVEL"):` 을 잠시 `if False:` 로 바꾼다.

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/prd-digest/scripts/parse_menu_ia.py /tmp/pmi.bak
sed -i '' 's/        if v.startswith("LEVEL"):/        if False:/' .claude/skills/prd-digest/scripts/parse_menu_ia.py
python3 scripts/parse_menu_ia.py --selftest; echo "주입 후 종료코드=$?"
cp /tmp/pmi.bak .claude/skills/prd-digest/scripts/parse_menu_ia.py
python3 scripts/parse_menu_ia.py --selftest | tail -1
```

Expected: 주입 시 `FAIL  S1 LEVEL 열 4개를 센다` 등 + 종료 코드 `1`, 원복 후 `selftest PASS — 15건 통과`

- [ ] **Step 7: 심볼릭 링크 + `verify_setup.py` 등재**

```bash
cd /Users/hanflex/Git/testcase-auto
chmod +x .claude/skills/prd-digest/scripts/parse_menu_ia.py
ln -s ../.claude/skills/prd-digest/scripts/parse_menu_ia.py scripts/parse_menu_ia.py
ls -l scripts/parse_menu_ia.py
```

`verify_setup.py` 의 `check_symlinks()` `expected` 리스트에 `"parse_menu_ia.py"` 를 추가한다
(현재 11개 → 12개). `check_packages()` 에 **`openpyxl`** 을 추가한다 — 이 절차가 들여오는
유일한 새 의존성이고, 없으면 `IA_NO_OPENPYXL` 로 죽는다.

- [ ] **Step 8: 기준선 확인 후 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
python3 scripts/parse_menu_ia.py --selftest | tail -1
python3 verify_setup.py 2>&1 | grep -E "scripts/ 링크|Python 패키지"
bash scripts/verify_unit_migration.sh | tail -1
git add .claude/skills/prd-digest/scripts/parse_menu_ia.py scripts/parse_menu_ia.py verify_setup.py
```

커밋 메시지(본문에 실측 근거를 남긴다):

```
기능: parse_menu_ia.py 신설 — 메뉴 IA 엑셀에서 메뉴 트리를 뽑는다

메뉴 경로는 판단할 값이 없다. 엑셀에 이미 적혀 있고, 트리 이미지를 모델이 읽으면
들여쓰기 깊이를 오독하며 개정판의 Menu Structure 는 바뀐 가지 위주로만 그려져
전체 트리가 나오지 않는다.

실측이 설계를 둘 정했다 —
- 열 문자를 박지 않는다: K8s 는 LEVEL 4개에 화면ID 가 H, CI/CD 는 LEVEL 2개에
  화면ID 가 F 다. 고정하면 CI/CD 에서 조용히 엉뚱한 열을 읽는다
- 화면 ID 접두로 거르지 않는다: K8s IA 의 `기본 설정 > 클러스터 관리 > 이미지
  저장소` 아래에 CICD- 접두 화면이 7건 있다. VIOE 만 남기면 그 7건이 사라진다

--selftest 15건(두 레이아웃·접두 혼재·헤더 행 이동·시트 부재·헤더 부재·MD 렌더).
실제 IA 두 파일에서 각각 299·97 화면, LEVEL 열 4·2 로 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 2: `render_digest.py` — 한 벌의 TSV를 두 축으로 배열한다

**Files:**
- Create: `.claude/skills/prd-digest/scripts/render_digest.py`
- Create: `scripts/render_digest.py` (상대 심볼릭 링크)
- Modify: `verify_setup.py` (링크 목록)
- Test: 스크립트 내장 `--selftest`

**Interfaces:**
- Consumes: Task 1의 `00_menu_tree.json` 스키마 (`{source, sheet, level_count, screens:[{screen_id,name,path}]}`)
- Produces:
  - `read_features(ws) -> list[dict]` — 7열 TSV 파싱. 열 수가 7이 아니면 `ValueError("TSV_COLS …")`
  - `build_lookup(tree, titles) -> (path_of, name_of)` — 계획의 「조회 우선순위」 표를 구현
  - `render_features_md(rows, tree, titles, header) -> str` · `render_changes_md(...) -> str`
  - 상수 `CLASSES = ("신규","변경","삭제","확인 필요")` · `GLOBAL_ID = "문서 전역"` · `COLS = 7`
  - CLI: `render_digest.py --ws=<디렉터리> [--product=] [--doc=]` → `{WS}/03_기능_전체.md` · `{WS}/04_신규변경.md`
  - 종료 코드 0 성공 / 2 입력 이상(TSV 없음·열 수 불일치)
  - Task 3(`verify_digest.py`)이 같은 TSV 스키마와 `CLASSES` 를 쓰고, Task 5(에이전트)가 그 TSV를 쓴다

**`문서 전역` 행이 이 설계의 요점이다.** 전역 5개 섹션에서 나온 항목도 **같은 TSV 형식**으로
`화면ID = 문서 전역` 을 달아 낸다. 렌더러가 그 행을 `04` 의 「문서 전역」 절로 보내고
`03`(기능 목록)에서는 뺀다 — 전역 정책은 화면 기능이 아니다. 별도 경로를 만들지 않으므로
집계·검증이 한 메커니즘으로 끝난다.

- [ ] **Step 1: 스텁으로 만들고 실패를 본다**

아래 전문을 만들되 **`build_lookup` 의 본문만 `raise NotImplementedError`** 로 둔다.

- [ ] **Step 2: 실패 확인**

Run: `python3 .claude/skills/prd-digest/scripts/render_digest.py --selftest`
Expected: `NotImplementedError`

- [ ] **Step 3: `build_lookup` 본문을 넣어 전문을 완성한다**

```python
#!/usr/bin/env python3
"""화면별 TSV 를 메뉴 구조 축과 화면 ID 축으로 두 번 배열해 MD 2개를 만든다.

왜 렌더러가 따로 있나
---------------------
같은 사실을 두 축으로 배열하는 일을 모델에게 두 번 시키면 **두 문서가 어긋난다.**
화면 에이전트는 TSV 한 벌만 내고, 배열은 여기서 한다. 기획서를 다시 읽지 않고
재렌더할 수도 있다.

메뉴 경로·화면명은 **TSV 에 담지 않고 여기서 조회한다** — 에이전트가 옮겨 적으면
IA 와 어긋난다.

사용:
  python render_digest.py --ws=<디렉터리> [--product=<제품 유형>] [--doc=<기획서 표기>]
  python render_digest.py --selftest
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

CLASSES = ("신규", "변경", "삭제", "확인 필요")
GLOBAL_ID = "문서 전역"
COLS = 7


def read_features(ws: str) -> list:
    """`02_features_s*.tsv` 를 전부 읽어 행 목록으로 돌려준다."""
    rows = []
    for p in sorted(glob.glob(os.path.join(ws, "02_features_s*.tsv"))):
        with open(p, encoding="utf-8") as f:
            for ln, line in enumerate(f, 1):
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                cells = line.split("\t")
                if len(cells) != COLS:
                    raise ValueError("TSV_COLS %s:%d 열 %d개 (7개여야 한다)"
                                     % (os.path.basename(p), ln, len(cells)))
                rows.append({
                    "screen_id": cells[0].strip(), "feature": cells[1].strip(),
                    "desc": cells[2].strip(), "cls": cells[3].strip(),
                    "evidence": cells[4].strip(), "page": cells[5].strip(),
                    "path_fallback": cells[6].strip(), "src": os.path.basename(p),
                })
    return rows


def read_menu_tree(ws: str):
    p = os.path.join(ws, "00_menu_tree.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def read_index_titles(ws: str) -> dict:
    """`00_screen_index.md` 의 화면 ID → Page Title. 표의 2·3열을 읽는다."""
    p = os.path.join(ws, "00_screen_index.md")
    out = {}
    if not os.path.isfile(p):
        return out
    for line in open(p, encoding="utf-8"):
        m = re.match(r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def build_lookup(tree, titles: dict):
    """(경로 조회, 이름 조회) 두 함수를 돌려준다. 우선순위는 계획의 표와 같다."""
    by_id = {}
    if tree:
        for s in tree.get("screens", []):
            parts = [p for p in s.get("path", []) if p != "-"]
            by_id[s["screen_id"]] = (" > ".join(parts), s.get("name", ""))

    def path_of(sid: str, fallback: str) -> str:
        if sid in by_id and by_id[sid][0]:
            return by_id[sid][0]
        if fallback:
            return fallback
        return "" if sid in by_id else "(경로 없음)"

    def name_of(sid: str) -> str:
        if sid in by_id and by_id[sid][1]:
            return by_id[sid][1]
        if titles.get(sid):
            return titles[sid]
        return "(이름 없음)"

    return path_of, name_of


def render_features_md(rows, tree, titles, header: dict) -> str:
    """메뉴 구조 축 — 기획서에 실린 모든 기능."""
    path_of, name_of = build_lookup(tree, titles)
    scr = [r for r in rows if r["screen_id"] != GLOBAL_ID]

    groups = {}
    for r in scr:
        groups.setdefault(path_of(r["screen_id"], r["path_fallback"]), {}) \
              .setdefault(r["screen_id"], []).append(r)

    out = ["# %s 기능 정리 — 메뉴 구조 기준" % header.get("product", ""), ""]
    out.append("- 기획서: %s" % header.get("doc", "(미지정)"))
    if tree:
        out.append("- 메뉴 IA: `%s` (화면 %d개)" % (tree["source"], len(tree["screens"])))
    else:
        out.append("- 메뉴 IA: **없음 — Menu Structure 페이지와 Breadcrumb 으로 폴백했다**")
    ids = sorted({r["screen_id"] for r in scr})
    out += ["- 수록 범위: 기획서에 실린 화면 %d개 · 기능 %d건" % (len(ids), len(scr)), ""]

    def emit(path_label, title):
        out.append("## %s" % title)
        out.append("")
        for sid in sorted(groups[path_label]):
            rs = groups[path_label][sid]
            pages = sorted({r["page"] for r in rs if r["page"]})
            out.append("### %s %s  〈%s〉" % (sid, name_of(sid), ", ".join(pages)))
            out.append("")
            out.append("| 기능 | 설명 | 분류 |")
            out.append("|------|------|------|")
            for r in rs:
                out.append("| %s | %s | %s |" % (r["feature"], r["desc"], r["cls"]))
            out.append("")

    if "" in groups:
        emit("", "공통 정의 (메뉴 경로 없음)")
    for path_label in sorted(p for p in groups if p != ""):
        emit(path_label, path_label)
    return "\n".join(out)


def render_changes_md(rows, tree, titles, header: dict) -> str:
    """화면 ID 축 — 신규·변경·삭제·확인 필요."""
    path_of, name_of = build_lookup(tree, titles)
    scr = [r for r in rows if r["screen_id"] != GLOBAL_ID]
    glob_rows = [r for r in rows if r["screen_id"] == GLOBAL_ID]

    out = ["# %s 신규·변경·삭제 기능" % header.get("product", ""), "", "## 요약", "",
           "| 분류 | 기능 수 | 화면 수 |", "|------|--------|--------|"]
    for c in CLASSES:
        sel = [r for r in rows if r["cls"] == c]
        out.append("| %s | %d | %d |" % (c, len(sel), len({r["screen_id"] for r in sel})))
    out.append("")

    out += ["## 문서 전역", ""]
    if glob_rows:
        out += ["| 기능 | 설명 | 분류 | 근거 |", "|------|------|------|------|"]
        for r in glob_rows:
            out.append("| %s | %s | %s | %s |" % (r["feature"], r["desc"], r["cls"], r["evidence"]))
    else:
        out.append("해당 없음.")
    out.append("")

    for c in CLASSES:
        out.append("## %s" % c)
        out.append("")
        sel = [r for r in scr if r["cls"] == c]
        if not sel:
            out += ["해당 없음.", ""]
            continue
        for sid in sorted({r["screen_id"] for r in sel}):
            rs = [r for r in sel if r["screen_id"] == sid]
            pl = path_of(sid, rs[0]["path_fallback"]) or "경로 없음"
            pages = sorted({r["page"] for r in rs if r["page"]})
            out.append("### %s %s 〈%s〉 %s" % (sid, name_of(sid), pl, ", ".join(pages)))
            out.append("")
            out += ["| 기능 | 설명 | 근거 |", "|------|------|------|"]
            for r in rs:
                out.append("| %s | %s | %s |" % (r["feature"], r["desc"], r["evidence"]))
            out.append("")

    out += ["## IA ↔ 기획서 대조", ""]
    if tree:
        ia_ids = {s["screen_id"] for s in tree["screens"]}
        doc_ids = {r["screen_id"] for r in scr}
        only_doc = sorted(doc_ids - ia_ids)
        out.append("- IA 화면 %d · 기획서 화면 %d · 일치 %d"
                   % (len(ia_ids), len(doc_ids), len(doc_ids & ia_ids)))
        out.append("- **기획서에만 있음 %d건** — 신규 화면의 *신호*이지 근거가 아니다: %s"
                   % (len(only_doc), ", ".join("`%s`" % s for s in only_doc) or "없음"))
    else:
        out.append("메뉴 IA 가 없어 대조하지 않았다.")
    return "\n".join(out) + "\n"


def _selftest() -> int:
    import tempfile
    fails = []

    def chk(name, cond, detail=""):
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    with tempfile.TemporaryDirectory() as ws:
        tsv = [
            ["VIOE-04_06_01", "알람 목록 조회", "등록된 알람을 표출", "신규", "[스티커 p043] v1추가", "p043", ""],
            ["VIOE-04_06_01", "정렬", "이름 오름차순", "확인 필요", "[변경 범위 불명] 박스만", "p043", ""],
            ["VIOE-99_99_99", "외부 화면", "IA 에 없는 화면", "변경", "[DESC p200-1항]", "p200", "임시 > 경로"],
            ["VIOE-00_00_00", "레이아웃", "GNB 구성", "삭제", "[취소선 p015]", "p015", ""],
            [GLOBAL_ID, "신규 메뉴 4건", "Menu Structure 에 v1추가", "신규", "[Menu Structure p009]", "p009", ""],
        ]
        with open(os.path.join(ws, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
            for r in tsv:
                f.write("\t".join(r) + "\n")
        tree = {"source": "IA.xlsx", "sheet": "1. 메뉴구조도", "level_count": 4, "screens": [
            {"screen_id": "VIOE-04_06_01", "name": "외부 알람 목록", "path": ["모니터링", "외부 알람 설정", "-", "-"]},
            {"screen_id": "VIOE-00_00_00", "name": "레이아웃 정의", "path": ["-", "-", "-", "-"]},
        ]}
        with open(os.path.join(ws, "00_menu_tree.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False)
        with open(os.path.join(ws, "00_screen_index.md"), "w", encoding="utf-8") as f:
            f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
            f.write("| 01 | VIOE-99_99_99 | 인덱스에서 온 이름 |\n")

        rows = read_features(ws)
        chk("S1 TSV 5행을 읽는다", len(rows) == 5, len(rows))

        t = read_menu_tree(ws)
        titles = read_index_titles(ws)
        chk("S2 인덱스에서 Page Title 을 읽는다",
            titles.get("VIOE-99_99_99") == "인덱스에서 온 이름", titles)

        path_of, name_of = build_lookup(t, titles)
        chk("S3 경로는 IA 가 1순위",
            path_of("VIOE-04_06_01", "") == "모니터링 > 외부 알람 설정")
        chk("S3 IA 에 없으면 TSV 폴백", path_of("VIOE-99_99_99", "임시 > 경로") == "임시 > 경로")
        chk("S3 둘 다 없으면 (경로 없음)", path_of("VIOE-88_88_88", "") == "(경로 없음)")
        chk("S3 IA 에 있고 경로가 비면 공통 정의(빈 문자열)", path_of("VIOE-00_00_00", "") == "")
        chk("S4 화면명은 IA 가 1순위", name_of("VIOE-04_06_01") == "외부 알람 목록")
        chk("S4 IA 에 없으면 인덱스 Page Title", name_of("VIOE-99_99_99") == "인덱스에서 온 이름")
        chk("S4 둘 다 없으면 (이름 없음)", name_of("VIOE-88_88_88") == "(이름 없음)")

        hdr = {"product": "VIOLA K8s", "doc": "test.pdf"}
        f_md = render_features_md(rows, t, titles, hdr)
        c_md = render_changes_md(rows, t, titles, hdr)

        chk("S5 기능 목록에 전역 행이 들어가지 않는다", "신규 메뉴 4건" not in f_md)
        chk("S5 신규변경에는 문서 전역 절이 있다", "## 문서 전역" in c_md and "신규 메뉴 4건" in c_md)
        chk("S6 공통 정의 절이 앞에 온다",
            f_md.index("## 공통 정의 (메뉴 경로 없음)") < f_md.index("## 모니터링 > 외부 알람 설정"))
        chk("S7 분류 4종 절이 모두 있다", all(("## %s" % c) in c_md for c in CLASSES))
        only_new = [r for r in rows if r["cls"] == "신규"]
        c_only = render_changes_md(only_new, t, titles, hdr)
        chk("S7 비어 있는 분류 절은 '해당 없음'",
            c_only.split("## 삭제")[1].split("##")[0].strip() == "해당 없음.",
            repr(c_only.split("## 삭제")[1].split("##")[0].strip()))
        chk("S7 행이 있는 분류 절은 '해당 없음' 이 아니다",
            "해당 없음." not in c_md.split("## 변경")[1].split("##")[0])
        chk("S8 요약의 신규 기능 수 = 2(화면1 + 전역1)",
            re.search(r"\| 신규 \| 2 \|", c_md) is not None)
        chk("S9 IA 대조에 기획서 단독 화면이 나온다",
            "VIOE-99_99_99" in c_md.split("## IA ↔ 기획서 대조")[1])
        chk("S10 두 MD 의 화면 집합이 같다",
            {"VIOE-04_06_01", "VIOE-99_99_99", "VIOE-00_00_00"} ==
            set(re.findall(r"VIOE-\d\d_\d\d_\d\d", f_md)))

        # S11 — 열 수가 틀리면 즉시 실패
        with open(os.path.join(ws, "02_features_s02.tsv"), "w", encoding="utf-8") as f:
            f.write("A\tB\tC\n")
        try:
            read_features(ws)
            chk("S11 열 수가 틀리면 예외", False, "예외 없음")
        except ValueError as e:
            chk("S11 열 수가 틀리면 예외", "TSV_COLS" in str(e), str(e))

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — 19건 통과")
    return 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return _selftest()
    opt = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opt[k] = v
    ws = opt.get("ws")
    if not ws:
        print(__doc__)
        return 1
    try:
        rows = read_features(ws)
    except ValueError as e:
        print(str(e))
        return 2
    if not rows:
        print("RENDER_NO_INPUT %s 에 02_features_s*.tsv 가 없다" % ws)
        return 2
    tree = read_menu_tree(ws)
    titles = read_index_titles(ws)
    hdr = {"product": opt.get("product", ""), "doc": opt.get("doc", "(미지정)")}
    for name, text in (("03_기능_전체.md", render_features_md(rows, tree, titles, hdr)),
                       ("04_신규변경.md", render_changes_md(rows, tree, titles, hdr))):
        with open(os.path.join(ws, name), "w", encoding="utf-8") as f:
            f.write(text if text.endswith("\n") else text + "\n")
    print("RENDER_OK 기능 %d건 · 화면 %d개 · IA %s"
          % (len(rows), len({r["screen_id"] for r in rows if r["screen_id"] != GLOBAL_ID}),
             "있음" if tree else "없음(폴백)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인**

Run: `python3 .claude/skills/prd-digest/scripts/render_digest.py --selftest`
Expected: `selftest PASS — 19건 통과` · 종료 코드 `0`

- [ ] **Step 5: 음성 대조 — 조회 우선순위가 실제로 IA 우선인지 본다**

`build_lookup` 의 `if sid in by_id and by_id[sid][0]:` 을 잠시 `if False:` 로 바꾼다.

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/prd-digest/scripts/render_digest.py /tmp/rd.bak
sed -i '' 's/        if sid in by_id and by_id\[sid\]\[0\]:/        if False:/' .claude/skills/prd-digest/scripts/render_digest.py
python3 scripts/render_digest.py --selftest; echo "주입 후 종료코드=$?"
cp /tmp/rd.bak .claude/skills/prd-digest/scripts/render_digest.py
python3 scripts/render_digest.py --selftest | tail -1
```

Expected: 주입 시 `FAIL  S3 경로는 IA 가 1순위` + 종료 코드 `1`, 원복 후 `selftest PASS — 19건 통과`

- [ ] **Step 6: 심볼릭 링크 + `verify_setup.py` 등재 + 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
chmod +x .claude/skills/prd-digest/scripts/render_digest.py
ln -s ../.claude/skills/prd-digest/scripts/render_digest.py scripts/render_digest.py
python3 scripts/render_digest.py --selftest | tail -1
bash scripts/verify_unit_migration.sh | tail -1
git add .claude/skills/prd-digest/scripts/render_digest.py scripts/render_digest.py verify_setup.py
```

`verify_setup.py` 의 `expected` 에 `"render_digest.py"` 추가(12개 → 13개).

커밋 메시지:

```
기능: render_digest.py 신설 — 한 벌의 TSV 를 두 축으로 배열한다

같은 사실을 메뉴 구조 축과 화면 ID 축으로 두 번 배열하는 일을 모델에게 시키면
두 문서가 어긋난다. 화면 에이전트는 TSV 한 벌만 내고 배열은 스크립트가 한다 —
기획서를 다시 읽지 않고 재렌더할 수도 있다.

메뉴 경로와 화면명을 TSV 에 담지 않고 렌더러가 조회하는 것이 핵심이다. 에이전트가
옮겨 적으면 IA 와 어긋난다. 우선순위는 IA → TSV 폴백 → (경로 없음).

전역 5개 섹션 항목도 같은 TSV 형식으로 `화면ID = 문서 전역` 을 달아 낸다. 별도
경로를 만들지 않으므로 집계·검증이 한 메커니즘으로 끝난다.

--selftest 19건.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 3: `verify_digest.py` — 결정적 점검

**Files:**
- Create: `.claude/skills/prd-digest/scripts/verify_digest.py`
- Create: `scripts/verify_digest.py` (상대 심볼릭 링크)
- Modify: `verify_setup.py` (링크 목록 — 13개 → 14개)
- Test: 스크립트 내장 `--selftest`

**Interfaces:**
- Consumes: Task 2와 **같은 TSV 스키마·같은 `CLASSES`·같은 `GLOBAL_ID`**. 두 스크립트가 이 값을 각자 정의하므로 **바꿀 때 둘 다 바꾼다**
- Produces:
  - `check(ws, total_pages=None) -> list[(등급, 코드, 메시지)]`
  - 코드: `NO_TSV`·`TSV_COLS`·`CLASS_ENUM`·`NO_EVIDENCE`·`NO_SCREEN_ID`·`NO_MD`·`MD_MISSING`·`SCREEN_MISSING`(Critical) · `PAGE_GAP`(Major)
  - CLI: `verify_digest.py --ws=<디렉터리> [--pages=<총 페이지 수>]` · 종료 코드 0 / 2 Critical / 1 Major만
  - Task 6(SKILL) Phase 4가 이 CLI를 호출한다

**`확인 필요` 행에 근거를 요구하지 않는 것이 의도다.** 그 분류는 *종류를 단정할 수 없다*는
뜻이므로 근거 태그가 없을 수 있다. `신규`·`변경`·`삭제` 세 분류만 근거를 강제한다.

- [ ] **Step 1: 스텁으로 만들고 실패를 본다**

아래 전문을 만들되 **`check` 의 본문만 `raise NotImplementedError`** 로 둔다.

- [ ] **Step 2: 실패 확인** — `python3 .claude/skills/prd-digest/scripts/verify_digest.py --selftest` → `NotImplementedError`

- [ ] **Step 3: `check` 본문을 넣어 전문을 완성한다**

```python
#!/usr/bin/env python3
"""기획서 분석 산출물의 결정적 점검.

사람이 판단할 값이 없는 것만 본다 — 분류 enum, 근거 공란, 화면 누락, TSV ↔ MD 대조.
판정 타당성은 리뷰어가 본다.

⚠️ `--selftest` 를 함께 만든 이유 — **통과만 확인하면 아무것도 검사하지 않는 검사기도
   통과한다.** 심어 둔 위반을 실제로 잡는지 확인한다.

사용:
  python verify_digest.py --ws=<디렉터리> [--pages=<총 페이지 수>]
  python verify_digest.py --selftest

종료 코드: 0 위반 없음 / 2 Critical 있음 / 1 Major 만 있음
"""
from __future__ import annotations

import glob
import os
import re
import sys

CLASSES = ("신규", "변경", "삭제", "확인 필요")
GLOBAL_ID = "문서 전역"
COLS = 7
EVIDENCE_REQUIRED = ("신규", "변경", "삭제")


def _read_tsv(ws: str) -> list:
    rows = []
    for p in sorted(glob.glob(os.path.join(ws, "02_features_s*.tsv"))):
        for ln, line in enumerate(open(p, encoding="utf-8"), 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            rows.append((os.path.basename(p), ln, line.split("\t")))
    return rows


def _index_screens(ws: str) -> set:
    p = os.path.join(ws, "00_screen_index.md")
    out = set()
    if not os.path.isfile(p):
        return out
    for line in open(p, encoding="utf-8"):
        m = re.match(r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|", line)
        if m and m.group(1).strip() not in ("화면 ID(원문)", "화면 ID"):
            out.add(m.group(1).strip())
    return out


def check(ws: str, total_pages=None) -> list:
    """(등급, 코드, 메시지) 목록을 돌려준다."""
    v = []
    rows = _read_tsv(ws)
    if not rows:
        return [("Critical", "NO_TSV", "%s 에 02_features_s*.tsv 가 없다" % ws)]

    seen_pages = set()
    tsv_ids = set()
    for fn, ln, cells in rows:
        if len(cells) != COLS:
            v.append(("Critical", "TSV_COLS", "%s:%d 열 %d개 (7개여야 한다)" % (fn, ln, len(cells))))
            continue
        sid, feature, _desc, cls, evidence, page, _fb = [c.strip() for c in cells]
        tsv_ids.add(sid)
        if cls not in CLASSES:
            v.append(("Critical", "CLASS_ENUM",
                      "%s:%d 분류 %r — 허용: %s" % (fn, ln, cls, "·".join(CLASSES))))
        if cls in EVIDENCE_REQUIRED and not evidence:
            v.append(("Critical", "NO_EVIDENCE",
                      "%s:%d `%s` 의 %s 행에 근거가 없다" % (fn, ln, feature, cls)))
        if not sid:
            v.append(("Critical", "NO_SCREEN_ID", "%s:%d 화면 ID 가 비었다" % (fn, ln)))
        for m in re.findall(r"p(\d{1,4})", page):
            seen_pages.add(int(m))

    md_f = os.path.join(ws, "03_기능_전체.md")
    md_c = os.path.join(ws, "04_신규변경.md")
    for p in (md_f, md_c):
        if not os.path.isfile(p):
            v.append(("Critical", "NO_MD", "%s 가 없다 — render_digest.py 를 먼저 돌린다"
                      % os.path.basename(p)))
    if all(os.path.isfile(p) for p in (md_f, md_c)):
        tf = open(md_f, encoding="utf-8").read()
        tc = open(md_c, encoding="utf-8").read()
        for sid in sorted(tsv_ids - {GLOBAL_ID}):
            if sid not in tf:
                v.append(("Critical", "MD_MISSING", "`%s` 가 03_기능_전체.md 에 없다" % sid))
            if sid not in tc:
                v.append(("Critical", "MD_MISSING", "`%s` 가 04_신규변경.md 에 없다" % sid))
        for sid in sorted(_index_screens(ws) - tsv_ids):
            v.append(("Critical", "SCREEN_MISSING",
                      "인덱스의 `%s` 가 TSV 에 없다 — 처리되지 않은 화면이다" % sid))

    if total_pages:
        missing = [p for p in range(1, int(total_pages) + 1) if p not in seen_pages]
        if missing:
            v.append(("Major", "PAGE_GAP",
                      "어느 화면에도 귀속되지 않은 페이지 %d개: %s%s"
                      % (len(missing), ", ".join("p%03d" % p for p in missing[:10]),
                         " …" if len(missing) > 10 else "")))
    return v


def _selftest() -> int:
    import tempfile
    fails = []

    def chk(name, cond, detail=""):
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    def codes(ws, pages=None):
        return {c for _g, c, _m in check(ws, pages)}

    def build(ws, tsv_rows, md_ids=None, index_ids=None):
        with open(os.path.join(ws, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
            for r in tsv_rows:
                f.write("\t".join(r) + "\n")
        ids = md_ids if md_ids is not None else [r[0] for r in tsv_rows if r[0] != GLOBAL_ID]
        for nm in ("03_기능_전체.md", "04_신규변경.md"):
            with open(os.path.join(ws, nm), "w", encoding="utf-8") as f:
                f.write("\n".join("### %s" % s for s in ids) + "\n")
        with open(os.path.join(ws, "00_screen_index.md"), "w", encoding="utf-8") as f:
            f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
            for s in (index_ids if index_ids is not None else ids):
                f.write("| 01 | %s | 이름 |\n" % s)

    ok_row = ["VIOE-01", "기능", "설명", "신규", "[스티커 p001]", "p001", ""]

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S1 정상 입력은 위반 0건", codes(ws) == set(), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        chk("S2 TSV 가 없으면 NO_TSV", codes(ws) == {"NO_TSV"}, codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "신설", "[스티커 p001]", "p001", ""]])
        chk("S3 분류 enum 밖이면 CLASS_ENUM", "CLASS_ENUM" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "삭제", "", "p001", ""]])
        chk("S4 삭제 행의 근거 공란은 NO_EVIDENCE", "NO_EVIDENCE" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "확인 필요", "", "p001", ""]])
        chk("S5 확인 필요 행은 근거가 없어도 통과", "NO_EVIDENCE" not in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], md_ids=[])
        chk("S6 MD 에 화면이 없으면 MD_MISSING", "MD_MISSING" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["VIOE-01", "VIOE-02"])
        chk("S7 인덱스에 있는데 TSV 에 없으면 SCREEN_MISSING",
            "SCREEN_MISSING" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        os.remove(os.path.join(ws, "03_기능_전체.md"))
        chk("S8 MD 가 없으면 NO_MD", "NO_MD" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        with open(os.path.join(ws, "02_features_s02.tsv"), "w", encoding="utf-8") as f:
            f.write("A\tB\tC\n")
        chk("S9 열 수가 틀리면 TSV_COLS", "TSV_COLS" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S10 귀속 안 된 페이지는 PAGE_GAP(Major)", "PAGE_GAP" in codes(ws, 3), codes(ws, 3))
        chk("S11 전 페이지가 귀속되면 PAGE_GAP 없음",
            "PAGE_GAP" not in codes(ws, 1), codes(ws, 1))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row, [GLOBAL_ID, "신규 메뉴", "설명", "신규", "[Menu Structure p009]", "p009", ""]])
        c = codes(ws, None)
        chk("S12 문서 전역 행은 MD 등장 검사에서 빠진다", "MD_MISSING" not in c, c)

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — 12건 통과")
    return 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return _selftest()
    opt = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opt[k] = v
    ws = opt.get("ws")
    if not ws:
        print(__doc__)
        return 1
    viol = check(ws, opt.get("pages"))
    if not viol:
        print("✅ 결정적 점검 위반 0건")
        return 0
    crit = [x for x in viol if x[0] == "Critical"]
    for grade, code, msg in viol:
        print("%-9s %-15s %s" % (grade, code, msg))
    print()
    print("Critical %d · Major %d" % (len(crit), len(viol) - len(crit)))
    return 2 if crit else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인**

Run: `python3 .claude/skills/prd-digest/scripts/verify_digest.py --selftest`
Expected: `selftest PASS — 12건 통과` · 종료 코드 `0`

- [ ] **Step 5: 음성 대조 — 검사기가 실제로 무는지 본다**

`CLASS_ENUM` 검사를 죽여 S3가 FAIL 하는지 본다. **통과만 확인하면 아무것도 검사하지 않는
검사기도 통과한다.**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/prd-digest/scripts/verify_digest.py /tmp/vd.bak
sed -i '' 's/        if cls not in CLASSES:/        if False:/' .claude/skills/prd-digest/scripts/verify_digest.py
python3 scripts/verify_digest.py --selftest; echo "주입 후 종료코드=$?"
cp /tmp/vd.bak .claude/skills/prd-digest/scripts/verify_digest.py
python3 scripts/verify_digest.py --selftest | tail -1
```

Expected: 주입 시 `FAIL  S3 분류 enum 밖이면 CLASS_ENUM` + 종료 코드 `1`, 원복 후 `selftest PASS — 12건 통과`

- [ ] **Step 6: 심볼릭 링크 + 등재 + 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
chmod +x .claude/skills/prd-digest/scripts/verify_digest.py
ln -s ../.claude/skills/prd-digest/scripts/verify_digest.py scripts/verify_digest.py
python3 scripts/verify_digest.py --selftest | tail -1
bash scripts/verify_unit_migration.sh | tail -1
git add .claude/skills/prd-digest/scripts/verify_digest.py scripts/verify_digest.py verify_setup.py
```

커밋 메시지:

```
기능: verify_digest.py 신설 — 기획서 분석 산출물의 결정적 점검

사람이 판단할 값이 없는 것만 본다 — 분류 enum, 근거 공란, 화면 누락, TSV ↔ MD
대조, 페이지 귀속. 판정 타당성은 리뷰어가 본다.

`확인 필요` 분류에는 근거를 요구하지 않는다. 그 분류는 종류를 단정할 수 없다는
뜻이므로 근거 태그가 없는 것이 정상이다.

--selftest 12건 — 심어 둔 위반 9종을 잡고 정상 입력에 오탐 0건.
오탐을 내는 검사기는 무시당해 검사 자체가 무력해진다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 4: `prd-analyzer/references/digest-mode.md` — 이 모드 전용 판독 절

**Files:**
- Create: `.claude/skills/prd-analyzer/references/digest-mode.md`
- Modify: `.claude/skills/prd-analyzer/SKILL.md` — 「읽을 참조 문서 결정」 라우팅 표에 한 행 추가
- Modify: `scripts/verify_unit_migration.sh` — `NOWS` 배열에 새 파일 추가

**Interfaces:**
- Consumes: Task 2의 TSV 스키마와 `CLASSES`
- Produces: 판독 규칙 문서. Task 5의 에이전트가 이것을 읽는다

**이 파일이 담는 것 — 다른 모드와 겹치지 않는 것만.** 변경 표기 판독(불투명도·마커 색 번짐·
취소선 3경로)은 `change-mode.md` 가 이미 갖고 있으므로 **복제하지 않고 가리킨다.**

- [ ] **Step 1: `NOWS` 에 파일을 먼저 넣고 가드가 잡는 것을 본다**

`scripts/verify_unit_migration.sh` 의 `NOWS` 배열에 두 줄을 추가한다.

```bash
      .claude/skills/prd-analyzer/references/digest-mode.md
      .claude/skills/testcase-reviewer/references/digest-mode.md
      .claude/agents/prd-digester.md
```

Run: `bash scripts/verify_unit_migration.sh`
Expected: 파일이 아직 없으므로 `absent` 가드는 통과한다(`grep` 이 없는 파일을 조용히 건너뛴다).
**이 상태를 기록해 두고 Step 4에서 다시 확인한다.**

- [ ] **Step 2: 참조 문서를 만든다**

`.claude/skills/prd-analyzer/references/digest-mode.md` 에 아래 여섯 절을 쓴다.

1. **「이 모드가 만드는 것」** — 화면마다 `02_screen_s{NN}.md`(사람용)와 `02_features_s{NN}.tsv`
   (기계용 7열). 테스트 케이스를 만들지 않는다. 시트를 쓰지 않는다.
2. **「설명 깊이 — 기능 단위 요약」** — 화면마다 기능 3~10개, 각 1~2줄. **Description 전수
   전사를 하지 않는다**(산출물 분량이 기획서와 맞먹고 비용이 케이스 생성과 같아지는데,
   그러면 *읽기 위한 문서* 라는 목적을 잃는다).
3. **「분류 4종」** — `신규`·`변경`·`삭제`·**`확인 필요`**. 판정 표:

   | 근거 | 분류 |
   |------|------|
   | `v1추가` · Menu Structure 신규 메뉴 | `신규` |
   | `v1수정` | `변경` |
   | `v1삭제` · 취소선 · 반투명 오버레이 + `v1삭제` 배지 | `삭제` |
   | 종류 원문 없음 · 박스만 있고 항목 근거 0건 | **`확인 필요`** |

   **넷째 버킷을 둔 이유를 함께 적는다** — 3분류에 억지로 넣으면 기획서에 없는 종류를
   단정하게 된다. 색으로 종류를 추정하지 않는다(권위는 주석 원문이다).
4. **「전역 5개 섹션」** — Document History · Policy · Menu Structure · 기본 모드 공통 정의 ·
   Wireframe 공통 표출 모달 정의. 여기서 나온 항목은 **`화면ID = 문서 전역`** 으로 TSV 에 쓴다.
5. **「근거 태그」** — `common.md` 어휘를 따른다: `[DESC pNNN-N항]` · `[스티커 pNNN]` ·
   `[ChangeLog pNNN]` · `[취소선 pNNN]` · `[Menu Structure pNNN]` + 종류·일자 원문.
   `신규`·`변경`·`삭제` 행은 근거가 **필수**다(`verify_digest.py` 가 Critical 로 잡는다).
   `확인 필요` 행은 근거가 없어도 된다.
6. **「메뉴 경로·화면명을 적지 않는다」** — TSV 의 `메뉴경로_폴백` 은 **IA 에 없는 화면에만**
   채운다. 렌더러가 IA 에서 조회하므로 옮겨 적으면 어긋난다.

변경 표기 판독 규칙은 **`references/change-mode.md` 를 읽으라고 가리키고 복제하지 않는다.**

- [ ] **Step 3: `prd-analyzer` SKILL 의 라우팅 표에 한 행을 넣는다**

「읽을 참조 문서 결정 (먼저 이것부터)」 절의 표에 추가한다 — 작업 유형이 **기획서 분석
(`prd-digest`)** 이면 `references/digest-mode.md` + (변경 문서면) `references/change-mode.md`.

- [ ] **Step 4: 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -c "_workspace" .claude/skills/prd-analyzer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | grep -E "하드코딩|^PASS"
```

Expected: `0` · `ok    에이전트·비오케스트레이터 문서의 _workspace 하드코딩` · `PASS`

- [ ] **Step 5: 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
printf '\n`{SHARED}` 대신 _workspace/images 를 쓴다\n' >> .claude/skills/prd-analyzer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | grep "하드코딩"
git checkout -- .claude/skills/prd-analyzer/references/digest-mode.md 2>/dev/null || sed -i '' '$d' .claude/skills/prd-analyzer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 시 `FAIL` 이 그 파일을 지목, 원복 후 `PASS`

- [ ] **Step 6: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/prd-analyzer scripts/verify_unit_migration.sh
```

커밋 메시지 제목: `기능: prd-analyzer 에 기획서 분석 모드 판독 절 신설`
본문에 **변경 표기 판독을 복제하지 않고 `change-mode.md` 를 가리킨 이유**(복제본은 반드시
낡는다 — 2026-09-15 `HARNESS_SUMMARY` 폐지의 교훈)를 적는다.

---

### Task 5: `prd-digester` 에이전트 + 리뷰 모드 참조

**Files:**
- Create: `.claude/agents/prd-digester.md`
- Create: `.claude/skills/testcase-reviewer/references/digest-mode.md`
- Modify: `.claude/skills/testcase-reviewer/SKILL.md` — 리뷰 모드 표에 한 행
- Modify: `scripts/verify_unit_migration.sh` — 가드 2개

**Interfaces:**
- Consumes: Task 4의 판독 절, Task 2의 TSV 스키마
- Produces: 화면 배치를 처리하는 에이전트와 그 리뷰 기준. Task 6(SKILL)이 둘 다 호출한다

- [ ] **Step 1: 가드 2개를 먼저 넣고 실패를 본다**

`verify_unit_migration.sh` 의 「작업 디렉터리 재편」 절 다음에 새 절을 연다.

```bash
echo "── 기획서 분석 절차 (2026-09-21) ──────────────────────────"
present "분류 4종에 확인 필요 포함" '확인 필요' \
        .claude/skills/prd-analyzer/references/digest-mode.md \
        .claude/agents/prd-digester.md
present "리뷰 역방향 오판 금지" '역방향 오판|오판 금지' \
        .claude/skills/testcase-reviewer/references/digest-mode.md
```

Run: `bash scripts/verify_unit_migration.sh` → 두 가드 `FAIL`(파일 없음 또는 패턴 없음)

- [ ] **Step 2: `prd-digester` 에이전트를 만든다**

frontmatter — `name: prd-digester` · `description: 기획서를 기능 단위로 요약하고 신규·변경·삭제를 판정해 MD 와 TSV 를 내는 전문가. 테스트 케이스를 만들지 않는다.` · `type: general-purpose` · `model: opus`.

**`model: opus` 인 이유를 파일에 적는다** — 이 절차는 **판독 실패를 뒤 단계가 복구할 수
없다**(`prd-analyst` 와 같다). `testcase-writer` 가 `sonnet` 인 것은 양식 준수의 기계 판정
가능한 부분이 `verify_sheet_rows.py` 로 빠졌기 때문인데, 여기에는 그런 이관이 없다.

본문에 담을 것:

1. **경로 규약 블록**(frontmatter 바로 다음 첫 인용문) — 다른 에이전트 5종과 **같은 문구**:
   `> **경로는 오케스트레이터가 준다.** 이 문서의 `{WS}`·`{SHARED}` 는 표기일 뿐이고, 실제 프롬프트에는 치환된 경로가 적혀 온다. **스스로 치환하지 않는다** — 치환을 잘못하면 엉뚱한 곳에 쓰고도 성공한 것처럼 보인다.`
2. **착수 전 읽을 것** — `{WS}/00_brief_digester.md`(오케스트레이터가 준 Phase 0 확정값 + 판독 절 발췌) · 담당 화면의 이미지 경로 · (변경 문서면) 그 화면 페이지 분의 변경 표시 검출 결과
3. **산출물 2개** — `{WS}/02_screen_s{NN}.md` 와 `{WS}/02_features_s{NN}.tsv`(7열, 헤더 없음)
4. **TSV 작성 규칙** — 셀에 탭·개행 금지, 분류는 4종만, `메뉴경로_폴백` 은 IA 에 없는 화면만
5. **오케스트레이터 리턴 규약** — 20줄 이내. 파일 경로·기능 수·분류별 건수·확인 필요 항목 수·
   사용자 결정이 필요한 것만. **케이스 표나 판독 전문을 리턴에 담지 않는다**
6. **배치 처리** — 한 호출에 화면 1~3개. **정책이 섞인 배치는 진행하지 말고 보고한다**
7. **모르면 단정하지 않는다** — 종류를 알 수 없으면 `확인 필요` 로 두고 근거를 비운다

- [ ] **Step 3: 리뷰 모드 참조를 만든다**

`.claude/skills/testcase-reviewer/references/digest-mode.md` 에:

**점검 항목** — ① 분류 판정이 근거 태그와 맞는가 ② 전역 5개 섹션이 모두 다뤄졌는가
③ 기능 설명이 기획서 원문과 어긋나지 않는가 ④ 「확인 필요」 항목에 판정 시도 흔적이 있는가.

**역방향 오판 금지 4항 — 이것이 이 파일의 핵심이다.** 없으면 리뷰가 매 실행 재작업 루프를
만든다(같은 방어를 이미 6번 신설했다).

- 「분류 확인 필요」가 있는 것을 결함으로 지적 **금지** — **그것이 설계다**
- IA 에 없는 화면을 오류로 지적 **금지** — IA 부재는 신규의 *신호*이지 근거가 아니다
- **`구분` 분포 대조 대상 아님** — 테스트 케이스 개념이고 여기엔 없다
- 기획서에 없는 기능이 목록에 없다고 지적 **금지**

`testcase-reviewer` SKILL 의 리뷰 모드 표에 **기획서 분석 리뷰** 행을 추가한다
(대상 = 탭이 아니라 `{WS}` 산출물 전체, 절차 = 이 참조).

- [ ] **Step 4: 통과 확인 + 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -c "_workspace" .claude/agents/prd-digester.md .claude/skills/testcase-reviewer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | grep -E "확인 필요|역방향|^PASS"
cp .claude/skills/testcase-reviewer/references/digest-mode.md /tmp/dm.bak
sed -i '' 's/역방향 오판/뒤집힌 판단/g; s/오판 금지/판단 금지/g' .claude/skills/testcase-reviewer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | grep "역방향"
cp /tmp/dm.bak .claude/skills/testcase-reviewer/references/digest-mode.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: `grep -c` 둘 다 `0` · 두 가드 `ok` · 주입 시 `FAIL` · 원복 후 `PASS`

- [ ] **Step 5: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/agents/prd-digester.md .claude/skills/testcase-reviewer scripts/verify_unit_migration.sh
```

제목: `기능: prd-digester 에이전트 + 기획서 분석 리뷰 모드 신설`
본문에 **역방향 오판 금지를 넣은 이유**(같은 방어를 6번 신설했고, 없으면 리뷰가 "그 작업이
만들라고 한 것을 만들지 말라"는 지적을 내 재작업 루프가 돈다)를 적는다.

---

### Task 6: `prd-digest/SKILL.md` — 오케스트레이터

**Files:**
- Create: `.claude/skills/prd-digest/SKILL.md`
- Modify: `scripts/verify_unit_migration.sh` — `ORCH` 배열에 추가 + 가드 3개

**Interfaces:**
- Consumes: Task 1~3의 세 CLI, Task 4의 판독 절, Task 5의 에이전트와 리뷰 참조
- Produces: 이 절차의 **경로 단일 출처(`0-0` 절)**. Task 7이 문서에서 이것을 가리킨다

- [ ] **Step 1: 가드 3개를 먼저 넣고 실패를 본다**

「기획서 분석 절차」 절에 추가한다.

```bash
present "IA 는 권위가 아니다"     'IA (부재|에 없다).*(신호|근거가 아니)' \
        .claude/skills/prd-digest/SKILL.md
present "두 MD 는 한 TSV 에서 렌더" '한 벌의 TSV|같은 TSV 에서' \
        .claude/skills/prd-digest/SKILL.md
present "TROMBONE 미지원"          'TROMBONE.*(중단|미지원|추후)' \
        .claude/skills/prd-digest/SKILL.md
```

`ORCH` 배열에 `.claude/skills/prd-digest/SKILL.md` 를 추가한다 — 이로써
`present "작업 루트 변수 표기"` 와 `absent "오케스트레이터의 산출물 경로 하드코딩"` 이
이 파일에도 걸린다.

- [ ] **Step 2: SKILL 을 쓴다 — frontmatter + 9개 절**

frontmatter `description` 에 트리거를 명시한다: `"기획서 분석해줘", "기능 정리", "신규·변경 기능 파악" 요청 시 반드시 이 스킬을 사용할 것. 테스트 케이스를 만들지 않고 시트를 쓰지 않는다.`

**`0-0. 작업 디렉터리 — 이 절이 경로의 단일 출처다`**

```
_workspace/
├── VIOLA-K8s_4.0_v1/
│   ├── shared/      ← {SHARED} : 이미지 · 검출 결과 + manifest.json (testcase-auto 와 공용)
│   ├── digest/      ← {WS} : 이 절차의 산출물
│   └── testcase/    ← 테스트 케이스 (testcase-auto)
```

- **`{WS}` = `_workspace/{디렉터리명}/digest`**, **`{SHARED}` = `_workspace/{디렉터리명}/shared`**
- `{SHARED}` 기본값은 위 경로이고 **Phase 0 (7) 에서 이미 변환된 이미지 경로를 받으면 그 경로가 `{SHARED}` 가 된다**
- **다른 절과 에이전트 프롬프트에서는 `_workspace` 를 쓰지 않는다**
- **에이전트에게는 치환된 실제 경로를 적어 넘긴다**
- 스크립트 호출 시 **항상 `--output-dir`/`--json`/`--out-json` 에 실제 경로를 명시**한다

**`0-1. 이 절차가 하지 않는 것`** — 테스트 케이스를 만들지 않는다 · 시트를 쓰지 않는다
(`sheets_api.py` 미호출) · `.claude/formats/` 와 `build_brief.py` 를 쓰지 않는다.
케이스가 필요하면 `testcase-auto` 다.

**`0-2. 기본 정보 수집` (7항목, 추정 금지)** — 스펙 3절의 표 그대로.
**`TROMBONE` 을 고르면 진행하지 않고 안내한다** — 기획서가 6개 파일로 쪼개져 있고 IA 도 따로
있으며 Screen ID 체계·변경 표기 컨벤션을 실측한 적이 없다. VIOLA 규칙을 그대로 적용하면 전
항목이 틀린다(`profile-bootfactory` 를 실측 없이 파생으로 만들어 두고 계속 경고를 달아야 했던
것과 같은 함정이다).

**`0-3. 확정값 표로 되보여 준다`** — 작업 디렉터리명 포함.

**`1-A. 이미지 준비`** — `testcase-auto` 1-A 와 **같은 절차**다.

```bash
python scripts/prd_cache.py check --pdf=<PDF> --shared={SHARED} --require=full,desc
```

네 상태(`CACHE_OK`/`CACHE_MISMATCH`/`CACHE_NO_MANIFEST`/`CACHE_PARTIAL`) 처리는
`prd-analyzer` SKILL 「PDF-2.5」 를 가리킨다. 변환·검출 명령은 모두 `--output-dir={SHARED}/…`
를 명시한다.

**`1-B. 메뉴 트리`**

```bash
python scripts/parse_menu_ia.py <IA.xlsx> --out-json={WS}/00_menu_tree.json --out-md={WS}/00_menu_tree.md
```

**IA 가 없으면** Menu Structure 페이지 + 각 화면 Breadcrumb 으로 폴백하고 **그 사실을 산출물
머리말에 남긴다.**

**`1-C. IA 는 권위가 아니다`** — 이 절이 가드 대상이다. 실측 반례를 함께 적는다:
`VIOE-03_02_05-*` **19개는 신규인데 IA 에 이미 실려 있고**, CI/CD 는 IA(`260731`)가
기획서 v2(`260819`)보다 **낡았다**. 따라서 **IA 부재는 신규 화면의 *신호*이지 근거가 아니다.**
IA ↔ 기획서 차이는 판정에 쓰지 않고 `04_신규변경.md` 의 「IA ↔ 기획서 대조」 절로 **보고만** 한다.

**`1-D ~ 1-F`** — 전역 5개 섹션 판독(에이전트 1회) → `{WS}/01_global.md` +
`{WS}/02_features_s00.tsv`(`화면ID = 문서 전역`) · 화면 인덱스 얕은 스캔(1회) →
`{WS}/00_screen_index.md` · **사용자 확인 게이트**(화면 수·배치 수·사이클 수·IA 차이·제외 페이지).

**`2. 화면 배치 루프`** — `prd-digester` 호출. 배치 묶음 조건은 `testcase-auto` 1-B-1 을 따르고
**첫 배치는 화면 1개**다(문체·분류 오류를 전 행에 번지기 전에 잡는다).

**`3. 렌더`**

```bash
python scripts/render_digest.py --ws={WS} --product=<제품 유형> --doc=<기획서 표기>
```

**두 MD 는 한 벌의 TSV 에서 렌더된다** — 모델이 같은 사실을 두 번 옮겨 적지 않으므로 두 축이
어긋날 수 없고, 기획서를 다시 읽지 않고 재렌더할 수 있다. 이 절이 가드 대상이다.

**`4. 검증 + 리뷰`**

```bash
python scripts/verify_digest.py --ws={WS} --pages=<총 페이지 수>
```

Critical 이 있으면 통과할 때까지 고친다. 그다음 `testcase-reviewer` 를 **집계 1회** 호출하고
`references/digest-mode.md` 를 읽도록 지시한다.

- [ ] **Step 3: 통과 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -n "_workspace" .claude/skills/prd-digest/SKILL.md
bash scripts/verify_unit_migration.sh | grep -E "IA 는 권위|한 TSV|TROMBONE|작업 루트|산출물 경로|^PASS"
```

Expected: `_workspace` 는 **`0-0` 절 안에만** · 신설 3개 + 기존 2개 가드 전부 `ok` · `PASS`

- [ ] **Step 4: 음성 대조 3종**

가드 3개 각각에 대해 그 선언을 지우거나 바꿔 `FAIL` 을 확인하고 `git checkout --` 로 원복한다.
**특히 `IA 는 권위가 아니다` 패턴은 본문 다른 문장에 걸리기 쉽다** — 선언을 지웠는데도
통과하면 패턴을 그 문장에만 맞도록 좁힌다(2026-09-15 「권위 선언」 가드와 같은 실패다).

- [ ] **Step 5: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/prd-digest/SKILL.md scripts/verify_unit_migration.sh
```

제목: `기능: prd-digest 오케스트레이터 신설 — 기획서 분석 절차`

---

### Task 7: 트리거 분기 · 문서 등재 · 설치 검사

**Files:**
- Modify: `CLAUDE.md` — 트리거 절 · 절차 등재 · `openpyxl` · 변경 이력 1행
- Modify: `verify_setup.py` — 스킬 7개 · 에이전트 6개 · 링크 14개
- Modify: 사용자 문서 7종 — `README.md` · `SETUP.md` · `docs/PROMPTS.md` · `docs/BASICS.md` · `docs/AT_A_GLANCE.md` · `HARNESS_OVERVIEW.md` · `HARNESS_PIPELINE.md` · `HARNESS_WORKFLOW.md`
- Modify: `scripts/verify_unit_migration.sh` — 가드 1개 + `DOCS` 확인

**Interfaces:**
- Consumes: Task 1~6 전부
- Produces: 없음 (마지막 태스크)

- [ ] **Step 1: 트리거 가드를 먼저 넣고 실패를 본다**

```bash
present "기획서 분석 트리거 분기" 'prd-digest' CLAUDE.md
```

- [ ] **Step 2: `CLAUDE.md` 트리거 절을 고친다 — 이것이 이 태스크의 핵심이다**

현재 문장이 *"테스트 케이스 자동 생성·기획서 분석·시트 작성 관련 요청 시 `testcase-auto`"*
라서 **`"기획서 분석해줘"` 가 테스트 케이스 생성을 시작시킨다.** 분기 표로 바꾼다.

| 요청에 있는 말 | 가는 곳 |
|---|---|
| `테스트 케이스` · `TC` · `케이스 생성` | `testcase-auto` |
| **`기획서 분석` · `기능 정리` · `신규·변경 기능 파악`** (케이스 어휘 없음) | **`prd-digest`** |
| `테스트케이스 추가 작업` · `예외 사항` · `권한` | `testcase-augment` |
| 둘 이상에 걸리거나 애매 | **묻는다** — 추정하지 않는다 |

함께 「환경」 절에 **`openpyxl`**(IA 엑셀 파싱)을 등재하고, 「추가 작업 절차」 옆에
**「기획서 분석 절차」** 문단을 신설한다.

- [ ] **Step 3: 사용자 문서 7종에 세 번째 절차를 등재한다**

각 문서의 **독자에 맞춰** 쓴다 — `docs/BASICS.md` 는 초보자용이고 **흐름을 다시 설명하지
않는다**(가드가 그 문구를 검사한다), `docs/AT_A_GLANCE.md` 는 리더용 한 장,
`HARNESS_*` 는 기제 문서다. 문서에는 `{WS}` 대신 **실제 예시 경로**를 쓴다.

`HARNESS_OVERVIEW` 의 도구 표에 신규 스크립트 3개를, `HARNESS_PIPELINE`·`HARNESS_WORKFLOW`
의 흐름에 세 번째 절차를 넣는다. `docs/AT_A_GLANCE.md` 의 커버리지 절에는 **이 절차가 내는
지표가 기획서 Description 커버리지이지 제품 기능 대비 %가 아니라는 기존 서술과 모순되지
않게** 적는다.

- [ ] **Step 4: `verify_setup.py` 를 넓힌다**

`need_skills` 에 `"prd-digest"`, `need_agents` 에 `"prd-digester.md"`, `expected` 링크에
Task 1~3의 3개를 더한다(스킬 7 · 에이전트 6 · 링크 14).
**이 검사가 비어 있으면 절차가 통째로 없어도 「구성 OK」가 나온다** — `testcase-augment`
에서 실제로 그랬다.

- [ ] **Step 5: `CLAUDE.md` 변경 이력에 1행 추가**

날짜 `2026-09-21`. 담을 것: 트리거가 충돌하고 있었다는 사실 · IA 엑셀을 뼈대로 삼되
**권위로 삼지 않은 이유**(실측 반례 2건) · **열 문자를 박지 않은 이유**(K8s LEVEL 4 / CI·CD
LEVEL 2, 화면ID H / F) · **접두로 거르지 않은 이유**(K8s IA 에 `CICD-` 접두 7건) ·
**두 MD 를 한 TSV 에서 렌더하는 이유** · **넷째 버킷 `확인 필요`** · TROMBONE 미지원 ·
회귀 가드 6개 · 세 스크립트의 `--selftest` 건수(15·19·12).

- [ ] **Step 6: 전수 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
bash scripts/verify_unit_migration.sh | tail -3
python3 scripts/parse_menu_ia.py --selftest | tail -1
python3 scripts/render_digest.py --selftest | tail -1
python3 scripts/verify_digest.py --selftest | tail -1
python3 scripts/prd_cache.py --selftest | tail -1
python3 scripts/verify_sheet_rows.py --selftest | tail -1
python3 scripts/read_tc_inventory.py --selftest | tail -1
python3 scripts/build_brief.py --coverage-check | tail -1
python3 verify_setup.py 2>&1 | grep -E "링크|하네스 구성|패키지"
grep -rn "_workspace" .claude/skills .claude/agents .claude/formats --include="*.md" | grep -v "worktrees/" | grep -v "skills/harness/"
```

Expected: 마지막 `grep` 은 **오케스트레이터 SKILL 3종의 `0-0` 절만** 돌려준다.

- [ ] **Step 7: 커밋**

제목: `문서: 기획서 분석 절차 등재 + 트리거 분기`

---

## 완료 기준

> **표의 수치는 구현 후 실측으로 갱신했다.** 각 Task 본문에 적힌 `15`·`19`·`12` 건과
> 「가드 6개」는 **계획 시점의 의도**이고, 구현 중 검사가 늘어 실제는 아래 값이다.
> 본문은 기록이므로 고치지 않는다 — 판정 기준은 이 표다.

| 검사 | 기대 |
|------|------|
| `parse_menu_ia.py --selftest` | `selftest PASS — 17건 통과` |
| `render_digest.py --selftest` | `selftest PASS — 33건 통과` |
| `verify_digest.py --selftest` | `selftest PASS — 32건 통과` |
| `prd_cache.py --selftest` | `selftest PASS — 37건 통과` |
| `verify_sheet_rows.py --selftest` | 위반 17종 검출 + 오탐 0건 |
| `read_tc_inventory.py --selftest` | `PASS` |
| `verify_unit_migration.sh` | `PASS` (이 절차 절 **12개** + 가드 자체 점검 1개) |
| `build_brief.py --coverage-check` | `✅ 전 절 배정 완료 · 유령 배정 0건` |
| `verify_setup.py` | 링크 14개 · 스킬 7개 · 에이전트 6개 |
| `_workspace` 전수 | 오케스트레이터 SKILL 3종의 `0-0` 절만 |

**음성 대조를 건너뛴 가드는 완료로 치지 않는다.** 신설 가드 각각에 위반을 주입해 `FAIL` 을
확인하고 원복한 기록이 있어야 한다 — 통과만 확인하면 패턴이 약해 선언이 사라져도 통과하는
경우를 놓친다(2026-09-15 「권위 선언」, 2026-09-19 「작업 루트 변수 표기」 둘 다 그랬다).

## 이 계획이 다루지 않는 것

- **TROMBONE·BootFactory** — 실측 근거 0건 (스펙 결정 9)
- **`.claude/formats/`·`build_brief.py` 수정** (스펙 결정 10)
- **시트 작성** — 이 절차의 산출물은 MD 뿐이다
- **케이스 생성으로 이어가기** — 분석만 하고 끝낸다
- **IA 의 역할별 접근 권한(J~L 열) 활용** — `testcase-augment` 권한 모드의 원천이 될 수 있으나 이 절차의 산출물이 아니다
- **`.claude/skills/harness/`** (하네스 제작 메타 스킬)

## 미해결

- **`digest/` 와 `testcase/` 가 같은 `{SHARED}` 를 쓸 때의 동시 실행.** 두 절차를 동시에
  돌리면 한쪽의 변환이 다른 쪽의 `manifest.json` 과 겹칠 수 있다. 현 운용은 순차이므로
  규칙을 만들지 않는다 — 동시 실행 요구가 생기면 그때 정한다
- **제외 페이지 판정** — 간지·목차를 빼는 것은 `testcase-auto` 1-B 와 같으나, 이 절차는
  *모든 기능* 을 다루므로 간지의 요구사항 번호(`[VIO-FY2026-NNNN]`)가 정보일 수 있다.
  1-E 구현 시 실측으로 정한다

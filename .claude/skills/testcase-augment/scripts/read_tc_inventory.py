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

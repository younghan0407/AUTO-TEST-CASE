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

종료 코드: 0 성공 / 3 파싱 실패(IA_NO_SHEET·IA_NO_HEADER·IA_NO_COLUMN·IA_NO_LEVEL)
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
    level_count = len(cols["levels"])
    if level_count == 0 or not screens:
        raise IAParseError("IA_NO_LEVEL", "LEVEL 열이 없거나 화면이 없다")
    return {
        "source": os.path.basename(path),
        "sheet": sheet,
        "level_count": level_count,
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

        # S8 — LEVEL 헤더가 title-case이면 IA_NO_LEVEL
        f8 = os.path.join(t, "titlecase.xlsx")
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "1. 메뉴구조도"
        ws.cell(3, 4, "Level 1"); ws.cell(3, 5, "화면ID"); ws.cell(3, 6, "화면명")
        ws.cell(4, 4, "메뉴"); ws.cell(4, 5, "VIOE-00_00_00"); ws.cell(4, 6, "홈")
        wb.save(f8)
        try:
            parse_ia(f8); chk("S8 LEVEL이 없으면 IA_NO_LEVEL", False, "예외 없음")
        except IAParseError as e:
            chk("S8 LEVEL이 없으면 IA_NO_LEVEL", e.code == "IA_NO_LEVEL", e.code)

        # S9 — 헤더만 있고 화면 행이 없으면 IA_NO_LEVEL
        f9 = os.path.join(t, "nodata.xlsx")
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "1. 메뉴구조도"
        ws.cell(3, 4, "LEVEL 1"); ws.cell(3, 5, "화면ID"); ws.cell(3, 6, "화면명")
        wb.save(f9)
        try:
            parse_ia(f9); chk("S9 화면이 없으면 IA_NO_LEVEL", False, "예외 없음")
        except IAParseError as e:
            chk("S9 화면이 없으면 IA_NO_LEVEL", e.code == "IA_NO_LEVEL", e.code)

    # S1~S9의 chk 호출 횟수 자동 계산: S1:5 + S2:3 + S3:1 + S4:1 + S5:1 + S6:1 + S7:3 + S8:1 + S9:1 = 17
    total_chks = 17
    passes = total_chks - len(fails)
    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — %d건 통과" % passes)
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

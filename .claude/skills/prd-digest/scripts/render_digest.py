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

CLASSES = ("신규", "변경", "삭제", "확인 필요", "미변경")
# `04_신규변경.md` 에 절을 얻지 못하는 분류. `미변경` 은 **변경 문서의 값이 아니라 기능 목록의
# 값**이다 — `03` 에는 그대로 실리고 `04` 에서는 요약 표에만 집계된다. 절까지 주면 변경 문서가
# 미변경 수백 건으로 뒤덮여 목적을 잃는다(실측 규모: 화면 127개 · 변경 항목 165건).
# 집합 연산으로 뽑는 이유 — 분류가 늘면 **기본값이 "절을 준다"** 여야 새 분류가 조용히 빠지지 않는다.
NO_SECTION = ("미변경",)
SECTION_CLASSES = tuple(c for c in CLASSES if c not in NO_SECTION)
GLOBAL_ID = "문서 전역"
COLS = 7


def _escape_cell(text: str) -> str:
    """마크다운 표 셀 내 파이프 문자를 escape 한다. 개행과 탭은 공백으로 바꾼다."""
    return text.replace("|", r"\|").replace("\n", " ").replace("\t", " ")


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
    """`00_screen_index.md` 의 화면 ID → Page Title. 헤더에서 열을 찾는다."""
    p = os.path.join(ws, "00_screen_index.md")
    out = {}
    if not os.path.isfile(p):
        return out
    lines = open(p, encoding="utf-8").readlines()
    # 헤더 행 찾기 (파일 끝까지 스캔)
    title_col = None
    id_col = None
    header_idx = None
    for i, hdr_line in enumerate(lines):
        if not hdr_line.startswith("|"):
            continue
        cells = [c.strip() for c in hdr_line.split("|")[1:-1]]
        if cells and cells[0].startswith("-"):  # 구분선 건너뛰기
            continue
        # Page Title 열 찾기
        if "Page Title" in cells:
            title_col = cells.index("Page Title")
            # 화면 ID 열 찾기 (원문이나 기본 이름)
            for j, cell in enumerate(cells):
                if "화면 ID" in cell:
                    id_col = j
                    break
            if title_col is not None and id_col is not None:
                header_idx = i
                break  # 헤더 찾았음
    if title_col is None or id_col is None or header_idx is None:
        return out  # 필수 헤더 없음 — 폴백
    # 데이터 행 읽기 (헤더와 구분선 건너뛰고, 표 끝에서 멈춤)
    for i, line in enumerate(lines):
        if i <= header_idx + 1:  # 헤더와 구분선 건너뛰기
            continue
        # 표 끝 감지 (| 로 시작하지 않는 행 = 표 외 영역)
        if not line.startswith("|"):
            break
        # 구분선은 건너뛰기
        if re.match(r"\|\s*-", line):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) > max(id_col, title_col):
            sid = cells[id_col]
            title = cells[title_col]
            if sid and title:
                out[sid] = title
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

    # 화면당 폴백 경로 해석 1회 (첫 비어있지 않은 값)
    screen_fallbacks = {}
    for r in scr:
        sid = r["screen_id"]
        if sid not in screen_fallbacks and r["path_fallback"]:
            screen_fallbacks[sid] = r["path_fallback"]

    groups = {}
    for r in scr:
        sid = r["screen_id"]
        path = path_of(sid, screen_fallbacks.get(sid, ""))
        groups.setdefault(path, {}).setdefault(sid, []).append(r)

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
                out.append("| %s | %s | %s |" % (_escape_cell(r["feature"]), _escape_cell(r["desc"]), _escape_cell(r["cls"])))
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

    # 화면당 폴백 경로 해석 1회 (첫 비어있지 않은 값)
    screen_fallbacks = {}
    for r in scr:
        sid = r["screen_id"]
        if sid not in screen_fallbacks and r["path_fallback"]:
            screen_fallbacks[sid] = r["path_fallback"]

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
            out.append("| %s | %s | %s | %s |" % (_escape_cell(r["feature"]), _escape_cell(r["desc"]), _escape_cell(r["cls"]), _escape_cell(r["evidence"])))
    else:
        out.append("해당 없음.")
    out.append("")

    for c in SECTION_CLASSES:
        out.append("## %s" % c)
        out.append("")
        sel = [r for r in scr if r["cls"] == c]
        if not sel:
            out += ["해당 없음.", ""]
            continue
        for sid in sorted({r["screen_id"] for r in sel}):
            rs = [r for r in sel if r["screen_id"] == sid]
            pl = path_of(sid, screen_fallbacks.get(sid, "")) or "경로 없음"
            pages = sorted({r["page"] for r in rs if r["page"]})
            out.append("### %s %s 〈%s〉 %s" % (sid, name_of(sid), pl, ", ".join(pages)))
            out.append("")
            out += ["| 기능 | 설명 | 근거 |", "|------|------|------|"]
            for r in rs:
                out.append("| %s | %s | %s |" % (_escape_cell(r["feature"]), _escape_cell(r["desc"]), _escape_cell(r["evidence"])))
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
    pass_count = [0]  # 계산된 카운트

    def chk(name, cond, detail=""):
        if cond:
            print("  ok    %s" % name)
            pass_count[0] += 1
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
        chk("S7 절이 있는 분류는 모두 절을 갖는다", all(("## %s" % c) in c_md for c in SECTION_CLASSES))
        chk("S7 미변경은 절을 얻지 않는다", "## 미변경" not in c_md)
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
        # S10 — 두 MD 의 화면 집합이 같은지 확인 (### 헤딩만 비교)
        f_screens = set(re.findall(r"^### (VIOE-\d\d_\d\d_\d\d)", f_md, re.MULTILINE))
        c_screens = set(re.findall(r"^### (VIOE-\d\d_\d\d_\d\d)", c_md, re.MULTILINE))
        chk("S10 두 MD 의 화면 집합이 같다", f_screens == c_screens == {"VIOE-04_06_01", "VIOE-99_99_99", "VIOE-00_00_00"})

        # S11 — 열 수가 틀리면 즉시 실패
        with open(os.path.join(ws, "02_features_s02.tsv"), "w", encoding="utf-8") as f:
            f.write("A\tB\tC\n")
        try:
            read_features(ws)
            chk("S11 열 수가 틀리면 예외", False, "예외 없음")
        except ValueError as e:
            chk("S11 열 수가 틀리면 예외", "TSV_COLS" in str(e), str(e))

        # S12 — 파이프 문자가 있는 기능명도 표가 정상 렌더된다
        ws2 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws2, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
                f.write("VIOE-AA_AA_AA\t파이프 |기능\t설명\t신규\t근거\tp001\t\n")
            tree2 = {"source": "IA.xlsx", "sheet": "메뉴", "level_count": 1, "screens": [
                {"screen_id": "VIOE-AA_AA_AA", "name": "테스트", "path": ["경로"]},
            ]}
            with open(os.path.join(ws2, "00_menu_tree.json"), "w", encoding="utf-8") as f:
                json.dump(tree2, f, ensure_ascii=False)
            rs2 = read_features(ws2)
            c_md2 = render_changes_md(rs2, tree2, {}, {"product": "TEST", "doc": "test"})
            # escape 된 파이프가 있고, 셀 구조가 유지됨 (개행/탭도 공백으로 바뀐다는 의미)
            has_escaped = r"\|" in c_md2
            has_feature_word = "파이프" in c_md2 and "기능" in c_md2
            chk("S12 파이프 escape — 표 셀 구조 유지", has_escaped and has_feature_word)
        finally:
            import shutil
            shutil.rmtree(ws2)

        # S13 — 한 화면이 여러 행에서 다른 폴백값을 가져도 한 섹션에만 나타난다
        ws3 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws3, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
                f.write("VIOE-BB_BB_BB\t기능1\t설명1\t신규\t근거1\tp001\t경로1\n")
                f.write("VIOE-BB_BB_BB\t기능2\t설명2\t신규\t근거2\tp002\t경로2\n")
            tree3 = {"source": "IA.xlsx", "sheet": "메뉴", "level_count": 1, "screens": []}
            with open(os.path.join(ws3, "00_menu_tree.json"), "w", encoding="utf-8") as f:
                json.dump(tree3, f, ensure_ascii=False)
            rs3 = read_features(ws3)
            f_md3 = render_features_md(rs3, tree3, {}, {"product": "TEST", "doc": "test"})
            c_md3 = render_changes_md(rs3, tree3, {}, {"product": "TEST", "doc": "test"})
            # 03 에서 VIOE-BB_BB_BB 는 한 번만 나타나야 함
            count_in_03 = f_md3.count("### VIOE-BB_BB_BB")
            # 04 에서도 한 경로에만 나타나야 함
            c_sections = c_md3.split("###")
            bb_sections = [s for s in c_sections if "VIOE-BB_BB_BB" in s]
            chk("S13 화면당 폴백 1회 해석 — 03 단일 섹션", count_in_03 == 1, count_in_03)
            chk("S13 화면당 폴백 1회 해석 — 04 단일 섹션", len(bb_sections) == 1, len(bb_sections))
        finally:
            import shutil
            shutil.rmtree(ws3)

        # S14 — Page Title 헤더가 다른 위치에 있어도 찾아낸다
        ws4 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws4, "00_screen_index.md"), "w", encoding="utf-8") as f:
                # Page Title 이 3번째가 아닌 다른 위치
                f.write("| 순번 | Page Title | 화면 ID(원문) |\n|---|---|---|\n")
                f.write("| 01 | 화면명 레이블 | VIOE-CC_CC_CC |\n")
            titles4 = read_index_titles(ws4)
            chk("S14 Page Title 헤더 찾기", titles4.get("VIOE-CC_CC_CC") == "화면명 레이블", titles4)
        finally:
            import shutil
            shutil.rmtree(ws4)

        # S15 — 분류(cls) 에 파이프가 있어도 표 셀이 유지된다 (2-A)
        ws5 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws5, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
                f.write("VIOE-DD_DD_DD\t기능명\t설명 | 파이프포함\t신규\t근거|메모\tp001\t\n")
            tree5 = {"source": "IA.xlsx", "sheet": "메뉴", "level_count": 1, "screens": [
                {"screen_id": "VIOE-DD_DD_DD", "name": "테스트", "path": ["경로"]},
            ]}
            with open(os.path.join(ws5, "00_menu_tree.json"), "w", encoding="utf-8") as f:
                json.dump(tree5, f, ensure_ascii=False)
            rs5 = read_features(ws5)
            c_md5 = render_changes_md(rs5, tree5, {}, {"product": "TEST", "doc": "test"})
            # 표 행에서 여러 필드의 파이프가 escape 되었음을 확인
            has_escaped_desc = r"설명 \| 파이프포함" in c_md5
            has_escaped_evidence = r"근거\|메모" in c_md5
            chk("S15 분류/설명/근거 escape — 표 셀 구조 유지", has_escaped_desc and has_escaped_evidence)
        finally:
            import shutil
            shutil.rmtree(ws5)

        # S16 — 헤더가 21줄째에 있어도 올바르게 읽는다 (2-B)
        ws6 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws6, "00_screen_index.md"), "w", encoding="utf-8") as f:
                # 20줄의 preamble 다음에 헤더와 데이터
                for i in range(20):
                    f.write("# 머리말 %d\n" % (i+1))
                f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
                f.write("| 01 | VIOE-EE_EE_EE | 화면_롱_이름 |\n")
                f.write("| 02 | VIOE-FF_FF_FF | 다른_화면 |\n")
            titles6 = read_index_titles(ws6)
            chk("S16 preamble 후 헤더 — 데이터 읽음",
                len(titles6) == 2 and titles6.get("VIOE-EE_EE_EE") == "화면_롱_이름",
                "count=%d" % len(titles6))
        finally:
            import shutil
            shutil.rmtree(ws6)

        # S17 — 표 끝에서 멈춘다. 후속 다른 표 포함해도 무시 (3-B)
        ws7 = tempfile.mkdtemp()
        try:
            with open(os.path.join(ws7, "00_screen_index.md"), "w", encoding="utf-8") as f:
                f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
                f.write("| 01 | VIOE-GG_GG_GG | 화면_G |\n")
                f.write("| 02 | VIOE-HH_HH_HH | 화면_H |\n")
                f.write("\n")  # 표 끝 (빈 줄)
                f.write("## 간지 표\n\n")  # 다른 섹션
                f.write("| 색 | 제목 |\n|---|---|\n")
                f.write("| 남색 | 잘못된_제목_1 |\n")
                f.write("| 보라 | 잘못된_제목_2 |\n")
                f.write("| 색 | 잘못된_제목_3 |\n")
            titles7 = read_index_titles(ws7)
            # 첫 표만 읽어야 함 — 간지 표의 키는 없어야 함
            has_screen_ids = "VIOE-GG_GG_GG" in titles7 and "VIOE-HH_HH_HH" in titles7
            has_no_invalid = "남색" not in titles7 and "보라" not in titles7 and "색" not in titles7
            chk("S17 표 경계 인식 — 후속 표 무시",
                len(titles7) == 2 and has_screen_ids and has_no_invalid,
                "count=%d, invalid_keys=%s" % (len(titles7), [k for k in titles7 if k in ("남색", "보라", "색")]))
        finally:
            import shutil
            shutil.rmtree(ws7)

    # S18 — `미변경` 은 기능 목록에는 실리고 변경 문서에는 절을 얻지 않는다.
    #       요약 표에는 집계된다(전체 중 얼마가 그대로인지가 읽는 사람에게 필요한 맥락이다).
    ws8 = tempfile.mkdtemp()
    try:
        with open(os.path.join(ws8, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
            f.write("VIOE-11_11_11\t신규기능\t설명\t신규\t[스티커 p001] v1추가\tp001\t\n")
            f.write("VIOE-11_11_11\t변경기능\t설명\t변경\t[DESC p001-2항] v1수정\tp001\t\n")
            f.write("VIOE-11_11_11\t삭제기능\t설명\t삭제\t[취소선 p001] 날짜미표기\tp001\t\n")
            f.write("VIOE-11_11_11\t불명기능\t설명\t확인 필요\t\tp001\t\n")
            f.write("VIOE-11_11_11\t그대로기능\t설명\t미변경\t\tp001\t\n")
            f.write("VIOE-11_11_11\t그대로기능2\t설명\t미변경\t\tp001\t\n")
        rs8 = read_features(ws8)
        hdr8 = {"product": "TEST", "doc": "test"}
        f8 = render_features_md(rs8, None, {}, hdr8)
        c8 = render_changes_md(rs8, None, {}, hdr8)
        chk("S18 미변경 기능이 03 기능 목록에 실린다",
            "그대로기능" in f8 and "그대로기능2" in f8)
        chk("S18 03 의 분류 열에 미변경이 그대로 보인다", "| 미변경 |" in f8)
        chk("S18 04 에 미변경 절이 없다", "## 미변경" not in c8)
        chk("S18 04 본문에 미변경 기능이 실리지 않는다", "그대로기능" not in c8)
        chk("S18 04 요약 표는 미변경을 집계한다",
            re.search(r"\| 미변경 \| 2 \| 1 \|", c8) is not None,
            [l for l in c8.splitlines() if "미변경" in l])
        chk("S18 나머지 네 분류는 절을 갖는다",
            all(("## %s" % c) in c8 for c in SECTION_CLASSES))
    finally:
        import shutil
        shutil.rmtree(ws8)

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — %d건 통과" % pass_count[0])
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

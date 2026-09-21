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

# 작업 디렉터리 재편 + 기획서 이미지 재사용 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 작업 디렉터리를 제품·버전 단위로 나누고 하위를 절차별로 분리하며, 기획서 이미지·검출 결과를 두 절차가 공유해 재변환을 없앤다.

**Architecture:** 하네스 문서에서 `_workspace` 경로를 걷어내고 `{WS}`(절차별 작업 루트)·`{SHARED}`(제품·버전 공용) 두 변수로 바꾼다. 실제 경로 치환은 오케스트레이터가 하고 에이전트는 치환된 경로를 받는다. 이미지 재사용 판정은 신규 스크립트 `prd_cache.py` 가 `manifest.json`(PDF 내용 해시 + variant별 파일 수)으로 전담한다. 기존 변환·검출 스크립트는 고치지 않는다 — 전부 이미 `--output-dir` 를 받는다.

**Tech Stack:** Python 3.9 표준 라이브러리만 (`hashlib`·`json`·`os`). 테스트는 이 저장소 관행대로 스크립트 내장 `--selftest` (pytest 미사용 — `requirements.txt` 에 테스트 의존성이 없고 `verify_sheet_rows.py`·`read_tc_inventory.py` 가 같은 방식이다). 문서 회귀는 `scripts/verify_unit_migration.sh` 가 검사한다.

**Spec:** `docs/superpowers/specs/2026-09-19-workspace-layout-design.md`

## Global Constraints

- **`{WS}` = 절차별 작업 루트** — `_workspace/{디렉터리명}/testcase` · `…/digest` · `_workspace/augment`.
  **`{SHARED}` = `_workspace/{디렉터리명}/shared`.** `{디렉터리명}` 형식은 `{제품}_{제품버전}_{문서회차}` (예 `VIOLA-K8s_4.0_v1`).
- **`_workspace` 문자열을 적어도 되는 곳은 오케스트레이터 SKILL 2종뿐이다**
  (`testcase-auto`·`testcase-augment`). 거기서도 **루트를 정의하는 줄에서만** 쓰고,
  산출물 경로(`_workspace/00_…`·`_workspace/pdf_images`)로는 쓰지 않는다.
  에이전트 5종과 나머지 스킬·참조·사양에는 **한 번도 등장하지 않아야 한다.**
- **에이전트는 치환된 실제 경로를 받는다.** 에이전트 문서가 `{WS}` 표기를 쓰더라도,
  오케스트레이터는 프롬프트에 **실제 경로를 적어** 넘긴다. 에이전트가 스스로 치환하게
  하지 않는다 — 치환 실수는 엉뚱한 곳에 쓰고도 성공한 것처럼 보이는 조용한 오작동이 된다.
- **기존 스크립트는 수정하지 않는다** (`pdf_to_images.py`·`detect_red_regions.py`·
  `detect_strikethrough.py`·`check_image_quality.py`·`read_tc_inventory.py`·`build_brief.py`).
  기본값 4곳도 그대로 두고, 오케스트레이터가 **항상 명시적으로 경로를 넘긴다.**
- **기존 `_workspace/`·`_workspace_prev_*` 는 이관하지 않는다.** 새 구조는 다음 실행부터 적용한다.
- **`.gitignore` 는 고치지 않는다** — `_workspace/` 가 이미 하위를 덮는다.
- **`prd-digest` 신설은 이 계획의 범위가 아니다** (스펙 2 / 별도 계획).
- 모든 문서는 **한국어**로 쓴다. 기존 파일의 문체(단정형 서술, 실측 근거 병기)를 따른다.
- **명령은 `python3` 으로 실행한다.** 이 환경에 `python` 이 없다 (3.9.6만 있다).
  **다만 문서·스킬 본문에 *쓰는* 예시 명령은 `python scripts/…` 표기를 유지한다** —
  저장소 기존 문서가 그 표기이며 통일은 이 작업의 범위가 아니다.
- **Python 3.9 호환.** 새 스크립트에 `from __future__ import annotations` 를 반드시 넣는다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` 를 붙인다.
- 브랜치는 현재 `harness/testcase-augment` 다 (스펙 3커밋이 올라가 있다). 새 브랜치를 만들지 않는다.
- **검증 기준선 (변경 전 실측).** 어느 태스크도 이 셋을 깨뜨린 채 완료하지 않는다.

  | 명령 | 기대 |
  |------|------|
  | `bash scripts/verify_unit_migration.sh` | `PASS` · 종료 코드 `0` |
  | `python3 scripts/build_brief.py --coverage-check` | `✅ 전 절 배정 완료 · 유령 배정 0건` (사양 4개 · 절 76종) |
  | `python3 scripts/verify_sheet_rows.py --selftest` | 위반 17종 검출 + 오탐 0건 |

## File Structure

| 파일 | 책임 |
|------|------|
| **신설** `.claude/skills/prd-analyzer/scripts/prd_cache.py` | `manifest.json` 쓰기·검사. 표준 라이브러리만. `--selftest` 내장 |
| **신설** `scripts/prd_cache.py` | 위 파일로의 심볼릭 링크 |
| `.claude/skills/prd-analyzer/SKILL.md` + `references/` 3종 | `{SHARED}` 도입 + manifest 절차 |
| `.claude/agents/*.md` 5종 | `{WS}` 표기 + 「실제 경로를 받는다」 |
| `.claude/skills/testcase-reviewer/SKILL.md` · `testcase-generator/SKILL.md` · `references/augment-mode.md` · `.claude/formats/common.md` | `{WS}` 치환 |
| `.claude/skills/testcase-auto/SKILL.md` | 루트 정의 · Phase 0 신설 2항 · 0-5 재작성 · 1-A 캐시 분기 |
| `.claude/skills/testcase-augment/SKILL.md` | `{WS}` = `_workspace/augment` 정의 + 치환 |
| `scripts/verify_unit_migration.sh` | 회귀 가드 8개 |
| `verify_setup.py` | `prd_cache.py` 링크 검사 |
| 사용자 문서 7종 · `CLAUDE.md` | 예시 경로 갱신 · 변경 이력 |

**태스크 순서가 중요하다.** 가드 2(에이전트·비오케스트레이터 스킬에 `_workspace` 0건)는
Task 3과 Task 4가 모두 끝나야 통과하므로 **Task 4에서 추가한다.** 각 태스크는 자기 가드를
함께 넣어 **끝날 때 항상 `PASS`** 인 상태로 둔다.

---

### Task 1: `prd_cache.py` 신설 — manifest 쓰기·검사

**Files:**
- Create: `.claude/skills/prd-analyzer/scripts/prd_cache.py`
- Create: `scripts/prd_cache.py` (심볼릭 링크)
- Modify: `verify_setup.py:64-68` (링크 목록)
- Test: 스크립트 내장 `--selftest` (별도 테스트 파일 없음 — 저장소 관행)

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `sha256_file(path: str) -> str`
  - `write_manifest(pdf: str, shared: str, variants: list[dict], page_count: int | None = None) -> tuple[str, dict]`
    — 상태 `"WRITE_OK"` | `"WRITE_INCOMPLETE"`
  - `check_manifest(pdf: str, shared: str) -> tuple[str, dict]`
    — 상태 `"CACHE_OK"` | `"CACHE_MISMATCH"` | `"CACHE_NO_MANIFEST"` | `"CACHE_PARTIAL"`
  - `variants` 원소 형식: `{"name": str, "dir": str, "dpi": int | None, "tile": str | None}`
  - CLI 종료 코드: `CACHE_OK`/`WRITE_OK`=0, `CACHE_MISMATCH`=2, `CACHE_NO_MANIFEST`=3,
    `CACHE_PARTIAL`/`WRITE_INCOMPLETE`=4
  - Task 2·5가 이 CLI를 호출한다

- [ ] **Step 1: 실패하는 `--selftest` 를 먼저 쓴다 (함수는 스텁)**

`.claude/skills/prd-analyzer/scripts/prd_cache.py` 를 아래 내용으로 만든다.
**함수 본문은 `NotImplementedError` 다** — 이 단계의 목적은 테스트가 실패하는 것을 보는 것이다.

```python
#!/usr/bin/env python3
"""기획서 이미지 캐시의 매니페스트를 쓰고 검사한다.

왜 필요한가
-----------
이미지는 같은 PDF·같은 옵션이면 바이트까지 동일하므로 재사용이 안전하다(실측).
위험한 것은 **다른 판본으로 변환된 이미지를 재사용하는 것**이다 — 분석이 낡은
기획서를 읽는데 결과물은 정상으로 보이고 검증도 통과한다. 누락보다 해롭다.

그래서 재사용 판정의 근거를 **PDF 내용 해시**로 두고, 판정 로직을 스크립트에
담아 `--selftest` 로 *불일치를 실제로 잡는지* 확인할 수 있게 했다.

`manifest.json` 은 **완료 마커이기도 하다.** 전량 성공한 뒤에만 쓰므로, 변환이
중간에 끊긴 디렉터리는 매니페스트가 없어 캐시로 인정되지 않는다. 이 장치가 없으면
페이지가 조용히 빠진다.

사용:
  python prd_cache.py write --pdf=<PDF> --shared=<디렉터리> \\
      --variant=name=full,dir=images,dpi=150,tile=none \\
      --variant=name=desc,dir=images_desc,dpi=200,tile=auto \\
      [--page-count=181]
  python prd_cache.py check --pdf=<PDF> --shared=<디렉터리>
  python prd_cache.py --selftest
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

MANIFEST = "manifest.json"

EXIT = {
    "WRITE_OK": 0, "CACHE_OK": 0,
    "CACHE_MISMATCH": 2,
    "CACHE_NO_MANIFEST": 3,
    "CACHE_PARTIAL": 4, "WRITE_INCOMPLETE": 4,
}


def sha256_file(path: str) -> str:
    raise NotImplementedError


def count_images(directory: str) -> int:
    """`.png` 파일 수. 디렉터리가 없으면 -1."""
    raise NotImplementedError


def write_manifest(pdf, shared, variants, page_count=None):
    raise NotImplementedError


def check_manifest(pdf, shared):
    raise NotImplementedError


def _selftest() -> int:
    import shutil
    import tempfile

    fails = []

    def chk(name, cond, detail=""):
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    with tempfile.TemporaryDirectory() as t:
        pdf = os.path.join(t, "doc.pdf")
        with open(pdf, "wb") as f:
            f.write(b"%PDF-1.4 fake body")
        shared = os.path.join(t, "shared")
        img = os.path.join(shared, "images")
        os.makedirs(img)
        for i in (1, 2, 3):
            with open(os.path.join(img, "page_%03d.png" % i), "wb") as f:
                f.write(b"x")
        variants = [{"name": "full", "dir": "images", "dpi": 150, "tile": None}]

        st, d = check_manifest(pdf, shared)
        chk("S1 manifest 없으면 CACHE_NO_MANIFEST", st == "CACHE_NO_MANIFEST", st)

        st, d = write_manifest(pdf, shared, variants, page_count=3)
        chk("S2 write 성공", st == "WRITE_OK", st)
        st, d = check_manifest(pdf, shared)
        chk("S2 정상이면 CACHE_OK", st == "CACHE_OK", st)

        with open(pdf, "wb") as f:
            f.write(b"%PDF-1.4 fake body v2")
        st, d = check_manifest(pdf, shared)
        chk("S3 PDF 내용이 바뀌면 CACHE_MISMATCH", st == "CACHE_MISMATCH", st)
        with open(pdf, "wb") as f:
            f.write(b"%PDF-1.4 fake body")

        os.remove(os.path.join(img, "page_003.png"))
        st, d = check_manifest(pdf, shared)
        chk("S4 파일 수가 다르면 CACHE_PARTIAL", st == "CACHE_PARTIAL", st)
        with open(os.path.join(img, "page_003.png"), "wb") as f:
            f.write(b"x")

        shared2 = os.path.join(t, "shared2")
        os.makedirs(shared2)
        st, d = write_manifest(pdf, shared2, variants)
        chk("S5 variant 디렉터리가 없으면 write 거부", st == "WRITE_INCOMPLETE", st)
        chk("S5 거부 시 manifest 미생성",
            not os.path.exists(os.path.join(shared2, MANIFEST)))

        pdf2 = os.path.join(t, "copy.pdf")
        shutil.copyfile(pdf, pdf2)
        chk("S6 같은 내용이면 같은 해시", sha256_file(pdf) == sha256_file(pdf2))
        st, d = check_manifest(pdf2, shared)
        chk("S6 경로가 달라도 CACHE_OK", st == "CACHE_OK", st)

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — 9건 통과")
    return 0


def _parse_variant(s: str) -> dict:
    out = {}
    for part in s.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    tile = out.get("tile")
    return {
        "name": out.get("name", ""),
        "dir": out.get("dir", ""),
        "dpi": int(out["dpi"]) if out.get("dpi") else None,
        "tile": None if tile in (None, "", "none") else tile,
    }


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _selftest()
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    opt = {}
    variants = []
    for a in argv[1:]:
        if a.startswith("--variant="):
            variants.append(_parse_variant(a.split("=", 1)[1]))
        elif a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opt[k] = v
    pdf, shared = opt.get("pdf"), opt.get("shared")
    if not pdf or not shared:
        print("--pdf 와 --shared 는 필수다")
        return 1

    if cmd == "write":
        pc = int(opt["page-count"]) if opt.get("page-count") else None
        st, d = write_manifest(pdf, shared, variants, page_count=pc)
    elif cmd == "check":
        st, d = check_manifest(pdf, shared)
    else:
        print("알 수 없는 명령: %s" % cmd)
        return 1

    print("%s %s" % (st, json.dumps(d, ensure_ascii=False)))
    return EXIT.get(st, 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python3 .claude/skills/prd-analyzer/scripts/prd_cache.py --selftest`
Expected: `NotImplementedError` 로 죽는다 (종료 코드 1)

- [ ] **Step 3: 네 함수를 구현한다**

위 파일의 스텁 4개를 아래로 교체한다.

```python
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_images(directory: str) -> int:
    """`.png` 파일 수. 디렉터리가 없으면 -1."""
    if not os.path.isdir(directory):
        return -1
    return sum(1 for n in os.listdir(directory) if n.lower().endswith(".png"))


def write_manifest(pdf, shared, variants, page_count=None):
    """전량 성공한 뒤에만 manifest 를 쓴다 — 이 파일이 완료 마커다."""
    recorded = {}
    for v in variants:
        n = count_images(os.path.join(shared, v["dir"]))
        if n <= 0:
            return "WRITE_INCOMPLETE", {"variant": v["name"], "dir": v["dir"], "files": n}
        recorded[v["name"]] = {
            "dir": v["dir"], "dpi": v.get("dpi"), "tile": v.get("tile"), "files": n,
        }
    data = {
        "source_pdf": pdf,
        "sha256": sha256_file(pdf),
        "page_count": page_count,
        "variants": recorded,
        "created": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    os.makedirs(shared, exist_ok=True)
    with open(os.path.join(shared, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return "WRITE_OK", {"variants": sorted(recorded), "sha256": data["sha256"][:16]}


def check_manifest(pdf, shared):
    """재사용해도 되는지 판정한다. 근거는 경로가 아니라 PDF 내용 해시다."""
    mp = os.path.join(shared, MANIFEST)
    if not os.path.isfile(mp):
        return "CACHE_NO_MANIFEST", {"path": mp}
    try:
        with open(mp, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError) as e:
        return "CACHE_NO_MANIFEST", {"path": mp, "error": str(e)}

    actual = sha256_file(pdf)
    if m.get("sha256") != actual:
        return "CACHE_MISMATCH", {
            "manifest_pdf": m.get("source_pdf"),
            "manifest_sha256": (m.get("sha256") or "")[:16],
            "actual_sha256": actual[:16],
        }

    for name, v in (m.get("variants") or {}).items():
        n = count_images(os.path.join(shared, v.get("dir", "")))
        if n != v.get("files"):
            return "CACHE_PARTIAL", {
                "variant": name, "expected": v.get("files"), "actual": n,
            }
    return "CACHE_OK", {"variants": sorted((m.get("variants") or {}))}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `python3 .claude/skills/prd-analyzer/scripts/prd_cache.py --selftest`
Expected: `selftest PASS — 9건 통과` · 종료 코드 `0`

- [ ] **Step 5: 음성 대조 — 검사기가 실제로 잡는지 확인한다**

`check_manifest` 의 해시 비교 줄을 잠시 `if False:` 로 바꿔 S3가 FAIL 하는지 본다.
**통과만 확인하면 판정을 안 하는 검사기도 통과한다.**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/prd-analyzer/scripts/prd_cache.py /tmp/prd_cache.bak
python3 - <<'PY'
p = ".claude/skills/prd-analyzer/scripts/prd_cache.py"
s = open(p, encoding="utf-8").read()
s = s.replace('    if m.get("sha256") != actual:', '    if False:')
open(p, "w", encoding="utf-8").write(s)
PY
python3 .claude/skills/prd-analyzer/scripts/prd_cache.py --selftest; echo "종료코드=$?"
cp /tmp/prd_cache.bak .claude/skills/prd-analyzer/scripts/prd_cache.py
python3 .claude/skills/prd-analyzer/scripts/prd_cache.py --selftest; echo "원복 후 종료코드=$?"
```

Expected: 주입 시 `FAIL  S3 PDF 내용이 바뀌면 CACHE_MISMATCH` + 종료 코드 `1`,
원복 후 `selftest PASS` + 종료 코드 `0`

- [ ] **Step 6: 심볼릭 링크 + `verify_setup.py` 등재**

```bash
cd /Users/hanflex/Git/testcase-auto
chmod +x .claude/skills/prd-analyzer/scripts/prd_cache.py
ln -s ../.claude/skills/prd-analyzer/scripts/prd_cache.py scripts/prd_cache.py
ls -l scripts/prd_cache.py
```

`verify_setup.py:64-68` 의 `expected` 리스트에 `"prd_cache.py"` 를 추가한다.
현재:

```python
    expected = [
        "figma_api.py", "pdf_to_images.py", "detect_red_regions.py",
        "detect_strikethrough.py", "check_image_quality.py",
        "build_brief.py", "read_tc_inventory.py", "verify_sheet_rows.py",
        "sheets_api.py", "oauth_sheet.py",
    ]
```

교체:

```python
    expected = [
        "figma_api.py", "pdf_to_images.py", "detect_red_regions.py",
        "detect_strikethrough.py", "check_image_quality.py", "prd_cache.py",
        "build_brief.py", "read_tc_inventory.py", "verify_sheet_rows.py",
        "sheets_api.py", "oauth_sheet.py",
    ]
```

- [ ] **Step 7: 링크 경유 실행과 기준선을 확인한다**

```bash
cd /Users/hanflex/Git/testcase-auto
python3 scripts/prd_cache.py --selftest
python3 verify_setup.py 2>&1 | grep -E "scripts/ 링크"
bash scripts/verify_unit_migration.sh | tail -2
```

Expected: `selftest PASS — 9건 통과` / `scripts/ 링크 … 11개 정상` / `PASS`

- [ ] **Step 8: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/prd-analyzer/scripts/prd_cache.py scripts/prd_cache.py verify_setup.py
git commit -m "$(cat <<'MSG'
기능: prd_cache.py 신설 — 기획서 이미지 재사용 판정

같은 PDF·같은 옵션의 변환 결과가 바이트까지 동일하다는 실측을 근거로 이미지를
재사용하되, 판정 근거를 경로가 아니라 PDF 내용 해시로 둔다. 같은 경로에 다음
판본을 덮어쓰는 일이 실제로 일어나고(CI/CD 기획서 v1→v2), 그때 낡은 이미지를
읽으면 결과물이 정상으로 보이면서 분석만 틀린다.

manifest.json 은 완료 마커이기도 하다 — 전량 성공한 뒤에만 쓰므로 변환이 끊긴
디렉터리는 캐시로 인정되지 않는다. 이 장치가 없으면 페이지가 조용히 빠진다.

--selftest 9건. 음성 대조로 해시 비교를 무력화하면 S3가 FAIL 하는 것을 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: `prd-analyzer` — `{SHARED}` 도입 + manifest 절차

**Files:**
- Modify: `.claude/skills/prd-analyzer/SKILL.md` (`_workspace` 10곳: 66·166·170·190·191·193·219·246·338·362행) + 「PDF-2」 뒤에 절 신설
- Modify: `.claude/skills/prd-analyzer/references/image-input.md` (5곳)
- Modify: `.claude/skills/prd-analyzer/references/change-mode.md` (2곳)
- Modify: `.claude/skills/prd-analyzer/references/figma.md` (1곳)
- Modify: `scripts/verify_unit_migration.sh` (배열 2개 + 가드 1개)

**Interfaces:**
- Consumes: Task 1의 `prd_cache.py` CLI (`write` / `check`, 종료 코드 0/2/3/4)
- Produces: `{SHARED}` 표기 규약 — 이미지·검출 산출물은 전부 `{SHARED}/` 아래.
  Task 5의 `testcase-auto` 1-A 가 이 절차를 호출한다

- [ ] **Step 1: 가드를 먼저 넣는다 (배열 + manifest 가드)**

`scripts/verify_unit_migration.sh` 의 `AUGMENT=(...)` 정의 **바로 뒤**(29행 `CORE=` 앞)에 추가한다.

```bash
ORCH=(.claude/skills/testcase-auto/SKILL.md
      .claude/skills/testcase-augment/SKILL.md)
# _workspace 문자열이 한 번도 나오면 안 되는 파일들 (루트 정의는 ORCH 에만 둔다)
NOWS=(.claude/agents/prd-analyst.md
      .claude/agents/testcase-writer.md
      .claude/agents/testcase-reviewer.md
      .claude/agents/sheet-analyst.md
      .claude/agents/tc-augmenter.md
      .claude/skills/prd-analyzer/SKILL.md
      .claude/skills/prd-analyzer/references/image-input.md
      .claude/skills/prd-analyzer/references/change-mode.md
      .claude/skills/prd-analyzer/references/figma.md
      .claude/skills/testcase-generator/SKILL.md
      .claude/skills/testcase-reviewer/SKILL.md
      .claude/skills/testcase-reviewer/references/augment-mode.md
      .claude/formats/common.md)
```

파일 **맨 끝의 `PASS`/`FAIL` 출력 직전**에 가드 절을 새로 연다.

```bash
echo "── 작업 디렉터리 재편 (2026-09-19) ────────────────────────"
present "이미지 재사용 manifest 대조" 'manifest\.json' \
        .claude/skills/prd-analyzer/SKILL.md
present "manifest 키는 PDF 내용 해시"  'sha256' \
        .claude/skills/prd-analyzer/SKILL.md
```

- [ ] **Step 2: 실패를 확인한다**

Run: `bash scripts/verify_unit_migration.sh | grep -E "manifest|FAIL"`
Expected: `FAIL  이미지 재사용 manifest 대조` · `FAIL  manifest 키는 PDF 내용 해시`

- [ ] **Step 3: `PDF-2` 뒤에 「PDF-2.5. 이미지 캐시」 절을 신설한다**

`### PDF-3. 이미지 시각 분석`(226행) **바로 앞**에 넣는다.

````markdown
### PDF-2.5. 이미지 캐시 — 이미 변환된 것이 있으면 다시 만들지 않는다

이미지·검출 결과는 **`{SHARED}/` 에 두고 기획서 분석과 테스트 케이스 작성이
공유한다.** 같은 PDF·같은 옵션이면 출력이 **바이트까지 동일**하므로(실측)
재사용이 안전하다.

**착수 전에 반드시 검사한다.**

```bash
python scripts/prd_cache.py check --pdf=<PDF> --shared={SHARED}
```

| 결과 | 종료 코드 | 처리 |
|------|----------|------|
| `CACHE_OK` | 0 | **변환을 건너뛴다** |
| `CACHE_MISMATCH` | 2 | **중단하고 사용자에게 알린다.** 다른 판본으로 만든 이미지다 |
| `CACHE_NO_MANIFEST` | 3 | 페이지 수만 대조하고 **사용자 확인** 후 진행. 진행했다면 분석서에 그 사실을 남긴다 |
| `CACHE_PARTIAL` | 4 | 부족한 variant 만 다시 변환하고 manifest 를 다시 쓴다 |

**`CACHE_MISMATCH` 를 중단으로 두는 이유** — 낡은 판본의 이미지를 읽으면
**결과물이 정상으로 보이고 검증도 통과하는데 분석만 틀린다.** 누락보다 해롭다.

변환을 마쳤으면 **전량 성공한 뒤에만** manifest 를 쓴다.

```bash
python scripts/prd_cache.py write --pdf=<PDF> --shared={SHARED} \
    --variant=name=full,dir=images,dpi=150,tile=none \
    --variant=name=tiled,dir=images_tiled,dpi=150,tile=auto \
    --variant=name=desc,dir=images_desc,dpi=200,tile=auto \
    --page-count=<페이지 수>
```

`manifest.json` 이 **완료 마커**다. 변환이 중간에 끊긴 디렉터리는 매니페스트가
없어 캐시로 인정되지 않는다 — 이 장치가 없으면 **페이지가 조용히 빠진다.**

색 검출·취소선 검출·판독 품질 결과도 이미지의 결정적 함수이므로 같은 규칙으로
`{SHARED}/` 에서 재사용한다.
````

- [ ] **Step 4: 나머지 `_workspace` 참조를 치환한다**

| 대상 | 바꿀 것 |
|------|--------|
| 이미지·검출 산출물 (66·166·170·219행) | `_workspace/pdf_images/<name>` → `{SHARED}/images`, `_workspace/00_image_quality.json` → `{SHARED}/00_image_quality.json` |
| 분석 산출물 (190·191·193·246·338·362행) | `_workspace/` → `{WS}/` |

`references/` 3종도 같은 기준으로 바꾼다. 파일 맨 앞(제목 다음 줄)에 한 줄을 넣는다.

```markdown
> 경로의 `{WS}`·`{SHARED}` 는 오케스트레이터가 **실제 경로로 치환해 프롬프트에 적어** 준다. 스스로 치환하지 않는다.
```

- [ ] **Step 5: 치환 완료를 확인한다**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -c "_workspace" .claude/skills/prd-analyzer/SKILL.md \
  .claude/skills/prd-analyzer/references/*.md
```

Expected: 전부 `0`

- [ ] **Step 6: 가드 통과 + 기준선 확인**

```bash
bash scripts/verify_unit_migration.sh | grep -E "manifest|^FAIL|^PASS"
python3 scripts/build_brief.py --coverage-check | tail -1
```

Expected: `ok    이미지 재사용 manifest 대조` · `ok    manifest 키는 PDF 내용 해시` · `PASS` /
`✅ 전 절 배정 완료 · 유령 배정 0건`

- [ ] **Step 7: 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/prd-analyzer/SKILL.md /tmp/pa.bak
sed -i '' 's/manifest\.json/매니페스트/g; s/sha256/해시/g' .claude/skills/prd-analyzer/SKILL.md
bash scripts/verify_unit_migration.sh | grep -E "manifest"; echo "---"
cp /tmp/pa.bak .claude/skills/prd-analyzer/SKILL.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 시 두 가드 모두 `FAIL`, 원복 후 `PASS`

- [ ] **Step 8: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/prd-analyzer scripts/verify_unit_migration.sh
git commit -m "$(cat <<'MSG'
재편: prd-analyzer 에 {SHARED} 와 이미지 캐시 절차 도입

이미지·검출 결과는 기획서 분석과 테스트 케이스 작성이 같이 쓰는 것이라
{SHARED}/ 로 옮긴다. 한쪽 절차 안에 두면 다른 쪽이 남의 디렉터리를 보게 되고,
분석을 건너뛴 실행에서는 경로가 성립하지 않는다.

CACHE_MISMATCH 를 중단으로 둔 것이 핵심이다 — 낡은 판본의 이미지를 읽으면
결과물이 정상으로 보이고 검증도 통과하는데 분석만 틀린다.

회귀 가드 2개 신설, 음성 대조로 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: 에이전트 5종 — `{WS}` 표기 + 「실제 경로를 받는다」

**Files:**
- Modify: `.claude/agents/prd-analyst.md` (6곳) · `testcase-writer.md` (6) · `testcase-reviewer.md` (7) · `sheet-analyst.md` (4) · `tc-augmenter.md` (1)
- Modify: `scripts/verify_unit_migration.sh` (가드 1개)

**Interfaces:**
- Consumes: Task 2의 `{WS}`·`{SHARED}` 표기 규약
- Produces: 에이전트 5종이 경로를 **오케스트레이터에게 받는다**는 규약.
  Task 5의 `testcase-auto` 가 프롬프트에 실제 경로를 적는 근거가 된다

- [ ] **Step 1: 가드를 먼저 넣는다**

Task 2에서 연 「작업 디렉터리 재편」 절에 추가한다.

```bash
present "에이전트는 치환된 실제 경로를 받는다" '스스로 치환하지 않는다' \
        .claude/agents/prd-analyst.md .claude/agents/testcase-writer.md \
        .claude/agents/testcase-reviewer.md .claude/agents/sheet-analyst.md \
        .claude/agents/tc-augmenter.md
```

- [ ] **Step 2: 실패를 확인한다**

Run: `bash scripts/verify_unit_migration.sh | grep -E "치환된 실제 경로"`
Expected: `FAIL  에이전트는 치환된 실제 경로를 받는다 — 패턴 없음: …` (5개 파일 전부)

- [ ] **Step 3: 다섯 파일의 `_workspace` 를 치환한다**

- 이미지·검출 경로 → `{SHARED}/…`
- 그 밖의 산출물 → `{WS}/…`
- `tc-augmenter.md` 의 `_workspace/augment/10_brief_augmenter.md` → `{WS}/10_brief_augmenter.md`

- [ ] **Step 4: 다섯 파일 모두에 규약 문장을 넣는다**

각 파일의 **frontmatter 바로 다음, 제목 아래 첫 인용문**으로 넣는다.

```markdown
> **경로는 오케스트레이터가 준다.** 이 문서의 `{WS}`·`{SHARED}` 는 표기일 뿐이고,
> 실제 프롬프트에는 치환된 경로가 적혀 온다. **스스로 치환하지 않는다** —
> 치환을 잘못하면 엉뚱한 곳에 쓰고도 성공한 것처럼 보인다.
```

- [ ] **Step 5: 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -c "_workspace" .claude/agents/*.md
bash scripts/verify_unit_migration.sh | grep -E "치환된 실제 경로|^PASS"
```

Expected: 다섯 파일 모두 `0` · `ok    에이전트는 치환된 실제 경로를 받는다` · `PASS`

- [ ] **Step 6: 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/agents/prd-analyst.md /tmp/pa2.bak
sed -i '' 's/스스로 치환하지 않는다/직접 바꿔 쓴다/' .claude/agents/prd-analyst.md
bash scripts/verify_unit_migration.sh | grep -E "치환된 실제 경로"
cp /tmp/pa2.bak .claude/agents/prd-analyst.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 시 `FAIL` (파일명이 `prd-analyst.md` 로 찍힌다), 원복 후 `PASS`

- [ ] **Step 7: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/agents scripts/verify_unit_migration.sh
git commit -m "$(cat <<'MSG'
재편: 에이전트 5종에서 _workspace 를 걷어내고 경로 규약을 명시

에이전트 문서는 {WS}·{SHARED} 표기만 쓰고, 실제 경로는 오케스트레이터가
프롬프트에 적어 넘긴다. 에이전트가 스스로 치환하게 하면 치환 실수가 엉뚱한
곳에 쓰고도 성공한 것처럼 보이는 조용한 오작동이 된다.

회귀 가드 1개 신설, 음성 대조로 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: 비오케스트레이터 스킬·참조·사양 — `{WS}` 치환 + `absent` 가드 완성

**Files:**
- Modify: `.claude/skills/testcase-reviewer/SKILL.md` (11곳) · `testcase-generator/SKILL.md` (7) · `testcase-reviewer/references/augment-mode.md` (1) · `.claude/formats/common.md` (2)
- Modify: `scripts/verify_unit_migration.sh` (가드 1개)

**Interfaces:**
- Consumes: Task 2·3의 `{WS}`·`{SHARED}` 표기 규약
- Produces: `NOWS` 배열 전체가 `_workspace` 0건인 상태. 이후 태스크는 이 상태를 깨지 않는다

- [ ] **Step 1: 가드를 넣는다 (Task 2·3이 끝나야 통과하므로 여기서 추가)**

「작업 디렉터리 재편」 절에 추가한다.

```bash
absent "에이전트·비오케스트레이터 문서의 _workspace 하드코딩" '_workspace' "${NOWS[@]}"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `bash scripts/verify_unit_migration.sh | grep -A 6 "_workspace 하드코딩"`
Expected: `FAIL` + `testcase-reviewer/SKILL.md`·`testcase-generator/SKILL.md`·
`augment-mode.md`·`common.md` 의 해당 줄이 찍힌다
(Task 2·3에서 고친 파일들은 나오지 않는다)

- [ ] **Step 3: 네 파일을 치환한다**

`_workspace/` → `{WS}/`. 이미지·검출 경로가 있으면 `{SHARED}/`.
`common.md` 의 2곳은 산출물 예시이므로 `{WS}/`.

- [ ] **Step 4: 통과 + 기준선 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
bash scripts/verify_unit_migration.sh | grep -E "_workspace 하드코딩|^PASS"
python3 scripts/verify_sheet_rows.py --selftest | tail -2
python3 scripts/build_brief.py --coverage-check | tail -1
```

Expected: `ok    에이전트·비오케스트레이터 문서의 _workspace 하드코딩` · `PASS` /
위반 17종 검출 + 오탐 0건 / `✅ 전 절 배정 완료 · 유령 배정 0건`

**`common.md` 를 고쳐 `verify_sheet_rows.py --selftest` 가 깨지면
`common.md` 쪽 표기를 기존 표 형식에 맞춘다** (그 스크립트는 수정 대상이 아니다).

- [ ] **Step 5: 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/formats/common.md /tmp/cm.bak
printf '\n<!-- _workspace/00_test.md -->\n' >> .claude/formats/common.md
bash scripts/verify_unit_migration.sh | grep -E "_workspace 하드코딩"
cp /tmp/cm.bak .claude/formats/common.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 시 `FAIL` + `common.md` 줄이 찍힘, 원복 후 `PASS`

- [ ] **Step 6: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/testcase-reviewer .claude/skills/testcase-generator \
        .claude/formats/common.md scripts/verify_unit_migration.sh
git commit -m "$(cat <<'MSG'
재편: 나머지 스킬·참조·사양에서 _workspace 를 걷어낸다

이로써 _workspace 문자열을 적어도 되는 곳이 오케스트레이터 SKILL 2종으로
좁혀졌다. 허용 지점이 넓으면 가드가 있으나 마나다.

absent 가드 1개 신설 — 에이전트 5종 + 비오케스트레이터 스킬·참조·사양 13개
파일에 _workspace 가 한 번도 나오면 안 된다. 음성 대조로 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: `testcase-auto` SKILL — 루트 정의 · Phase 0 신설 2항 · 0-5 재작성 · 1-A 캐시 분기

**Files:**
- Modify: `.claude/skills/testcase-auto/SKILL.md` (`_workspace` 67곳 + 절 신설·재작성)
- Modify: `scripts/verify_unit_migration.sh` (가드 3개)

**Interfaces:**
- Consumes: Task 1의 `prd_cache.py` CLI · Task 2의 캐시 절차 · Task 3의 에이전트 경로 규약
- Produces: `{WS}`·`{SHARED}` 의 **실제 경로 정의**(이 파일이 단일 출처) ·
  Phase 0 신설 항목 2개 · 재실행 시 `shared/` 보존 규칙

- [ ] **Step 1: 가드 3개를 먼저 넣는다**

```bash
present "작업 루트 변수 표기"        '\{WS\}'                      "${ORCH[@]}"
absent  "오케스트레이터의 산출물 경로 하드코딩" '_workspace/[0-9]|_workspace/pdf_images' "${ORCH[@]}"
present "재실행 시 shared 보존"      'shared/.*(남긴다|제자리|이동하지)' \
        .claude/skills/testcase-auto/SKILL.md
```

- [ ] **Step 2: 실패를 확인한다**

Run: `bash scripts/verify_unit_migration.sh | grep -E "작업 루트 변수|산출물 경로 하드코딩|shared 보존"`
Expected: 세 가드 모두 `FAIL`

- [ ] **Step 3: 「작업 디렉터리」 절을 Phase 0 맨 앞에 신설한다**

`#### 0-1. 환경변수 검증` **바로 앞**에 넣는다. **`_workspace` 를 적어도 되는
유일한 곳이므로, 여기 말고 다른 절에는 쓰지 않는다.**

````markdown
#### 0-0. 작업 디렉터리 — 이 절이 경로의 단일 출처다

```
_workspace/
├── VIOLA-K8s_4.0_v1/          ← {디렉터리명}. 0-2 (6)에서 확정한다
│   ├── shared/                ← {SHARED} : 이미지 · 색 검출 · 취소선 · 판독 품질 + manifest.json
│   ├── digest/                ← 기획서 분석 (prd-digest)
│   └── testcase/              ← {WS} : 이 절차의 산출물
└── augment/                   ← testcase-augment (제품·버전 폴더 밖)
```

- **`{WS}` = `_workspace/{디렉터리명}/testcase`**, **`{SHARED}` = `_workspace/{디렉터리명}/shared`**
- **다른 절과 에이전트 프롬프트에서는 `_workspace` 를 쓰지 않는다.** 이 절에서 값을
  정하고, 이후로는 `{WS}`·`{SHARED}` 로만 지칭한다
- **에이전트에게는 치환된 실제 경로를 적어 넘긴다.** `{WS}` 를 그대로 프롬프트에
  넣지 않는다 — 에이전트가 치환하다 틀리면 엉뚱한 곳에 쓰고도 성공한 것처럼 보인다
- 스크립트를 호출할 때도 **항상 `--output-dir` / `--out-dir` 에 실제 경로를 명시**한다.
  스크립트 기본값(`_workspace/…`)에 기대지 않는다
````

- [ ] **Step 4: Phase 0 에 항목 2개를 신설한다**

`##### (5) 시트(탭)` 절 **뒤**에 넣는다.

````markdown
##### (6) 작업 디렉터리명 — 필수

형식은 **`{제품}_{제품버전}_{문서회차}`** (예 `VIOLA-K8s_4.0_v1`). 공백·슬래시는 `-` 로 바꾼다.

**파일명에서 자동으로 만들지 않는다.** 두 축이 다르기 때문이다 —
`[4.0] VIOLA_화면기획서_v1_260728.pdf` 는 제품 버전이 `4.0`, Document History 회차가
`v1` 이다. 회차가 없으면 **같은 제품 버전 안에서 판본이 겹치고**(CI/CD 기획서는 실제로
`v1` → `v2` 로 갱신됐는데 둘 다 `4.0` 이다), 제품 버전이 없으면 다음 릴리스의 `v1` 과
충돌한다. 셋을 다 써야 유일해진다.

**0-4 확정값 표에 넣어 되보여 준다.**

##### (7) 이미 변환된 이미지 경로 — 선택

기획서 분석(`prd-digest`)을 먼저 돌렸거나 전에 변환해 둔 이미지가 있으면 그
`shared` 디렉터리 경로를 받는다. 값이 있으면 **1-A 변환을 건너뛴다**(검사는 반드시 한다).

생략하면 `{SHARED}` 에 새로 변환한다. 같은 기획서를 다시 다루면
`{SHARED}` 에 이미 있으므로 **대개 생략해도 재사용된다.**
````

- [ ] **Step 5: `1-A` 에 캐시 분기를 넣는다**

`#### 1-A. 분석 이미지 준비` 의 PDF 변환 명령 **앞**에 넣는다.

````markdown
**변환 전에 캐시를 검사한다.**

```bash
python scripts/prd_cache.py check --pdf=<PDF> --shared={SHARED}
```

| 결과 | 처리 |
|------|------|
| `CACHE_OK` (0) | **변환을 건너뛰고 1-A-2 로 간다** |
| `CACHE_MISMATCH` (2) | **중단.** 다른 판본으로 만든 이미지다 — 사용자에게 알리고 판단을 받는다 |
| `CACHE_NO_MANIFEST` (3) | 페이지 수만 대조하고 **사용자 확인** 후 진행. 진행하면 그 사실을 분석서에 남긴다 |
| `CACHE_PARTIAL` (4) | 부족한 variant 만 변환하고 manifest 를 다시 쓴다 |

변환을 마쳤으면 **전량 성공한 뒤에만** manifest 를 쓴다 — 상세는
`prd-analyzer` SKILL 「PDF-2.5. 이미지 캐시」.

```bash
python scripts/prd_cache.py write --pdf=<PDF> --shared={SHARED} \
    --variant=name=full,dir=images,dpi=150,tile=none \
    --variant=name=tiled,dir=images_tiled,dpi=150,tile=auto \
    --variant=name=desc,dir=images_desc,dpi=200,tile=auto \
    --page-count=<페이지 수>
```
````

기존 변환 명령의 `--output-dir` 도 `{SHARED}/images` · `{SHARED}/images_desc` 로 바꾼다.

- [ ] **Step 6: `0-5` 를 재작성한다**

기존 `#### 0-5. 기존 산출물 확인 → 실행 모드 결정`(159~164행)의 본문 4줄을 교체한다.

````markdown
| 상황 | 처리 |
|------|------|
| `{WS}` 가 없음 | **초기 실행** (Phase 1부터) |
| 있고 "다시"/"재실행" 요청 | `_workspace/{디렉터리명}/testcase_prev_{설명}_{날짜}/` 로 이동. **`shared/` 는 제자리에 남긴다** |
| 있고 "특정 화면만 보완" 요청 | **부분 재실행** — 인덱스에서 그 순번을 찾아 해당 화면만 재처리 |
| 있고 변경 없이 다음 단계만 | **이어 실행** — 완료 안 된 단계부터 |

**`shared/` 를 남기는 것이 핵심이다.** 예전에는 `_workspace/` 를 통째로 옮겨
이미지가 함께 사라졌고, 그래서 같은 PDF의 이미지가 **780MB 중복**됐다
(실측: `_workspace` 484MB + 백업본 296MB). 이미지는 판본이 같으면 같은 것이므로
이동 대상이 아니다.

**제품·버전이 다르면 애초에 다른 디렉터리이므로 이동 자체가 대부분 사라진다** —
이동은 이제 *같은 제품의 같은 판본을 처음부터 다시 할 때* 만 일어난다.
````

- [ ] **Step 7: 나머지 `_workspace` 참조를 전부 치환한다**

- 이미지·검출: `_workspace/pdf_images/…` · `_workspace/red_regions` → `{SHARED}/…`
- 그 밖: `_workspace/…` → `{WS}/…`
- **0-0 절의 트리 그림과 변수 정의만 `_workspace` 를 남긴다**

- [ ] **Step 8: 통과 + 기준선 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -nE '_workspace/[0-9]|_workspace/pdf_images|_workspace/red_regions' \
     .claude/skills/testcase-auto/SKILL.md
bash scripts/verify_unit_migration.sh | grep -E "작업 루트 변수|산출물 경로 하드코딩|shared 보존|^PASS"
python3 scripts/build_brief.py --coverage-check | tail -1
```

Expected: 첫 `grep` 결과 **없음** · 세 가드 `ok` · `PASS` · `✅ 전 절 배정 완료`

- [ ] **Step 9: 음성 대조 (가드 3개 각각)**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/testcase-auto/SKILL.md /tmp/ta.bak

sed -i '' 's/{WS}/__WS__/g' .claude/skills/testcase-auto/SKILL.md
bash scripts/verify_unit_migration.sh | grep "작업 루트 변수"
cp /tmp/ta.bak .claude/skills/testcase-auto/SKILL.md

printf '\n`_workspace/00_bad.md`\n' >> .claude/skills/testcase-auto/SKILL.md
bash scripts/verify_unit_migration.sh | grep "산출물 경로 하드코딩"
cp /tmp/ta.bak .claude/skills/testcase-auto/SKILL.md

sed -i '' 's|`shared/` 는 제자리에 남긴다|shared 도 함께 옮긴다|' .claude/skills/testcase-auto/SKILL.md
bash scripts/verify_unit_migration.sh | grep "shared 보존"
cp /tmp/ta.bak .claude/skills/testcase-auto/SKILL.md

bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 때마다 해당 가드가 `FAIL`, 세 번 원복 후 `PASS`

**세 번째 주입이 `FAIL` 을 내지 않으면 가드 5의 패턴이 약한 것이다** — 다른 문장이
`shared/` 와 `남긴다` 를 함께 갖고 있어 걸린 것이므로, 패턴을 그 문장에만
맞도록 좁힌다. 2026-09-15 「권위 선언」 가드에서 같은 일이 있었다.

- [ ] **Step 10: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/testcase-auto/SKILL.md scripts/verify_unit_migration.sh
git commit -m "$(cat <<'MSG'
재편: testcase-auto 에 작업 디렉터리 정의·Phase 0 2항·캐시 분기

0-0 절을 신설해 _workspace 실제 경로를 여기 한 곳에만 둔다. 2026-08-25 C열
삽입 때 11개 파일 78건을 재매핑하고 얻은 "열 문자를 공용 문서에 박지 말라" 와
같은 처방이다.

0-5 에서 재실행 백업 시 shared/ 를 남긴다 — 예전에는 _workspace/ 를 통째로
옮겨 이미지가 함께 사라졌고 그래서 같은 PDF 이미지가 780MB 중복됐다.

Phase 0 에 작업 디렉터리명과 이미 변환된 이미지 경로를 받는 항목을 신설했다.
디렉터리명을 파일명에서 자동 추출하지 않는 이유는 제품 버전(4.0)과 문서
회차(v1)가 다른 축이기 때문이다.

회귀 가드 3개 신설, 각각 음성 대조로 확인했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: `testcase-augment` SKILL — `{WS}` 표기 통일

**Files:**
- Modify: `.claude/skills/testcase-augment/SKILL.md` (`_workspace` 23곳)
- Modify: `scripts/verify_unit_migration.sh` (가드 1개)

**Interfaces:**
- Consumes: Task 3의 `tc-augmenter` 경로 규약
- Produces: `{WS}` = `_workspace/augment` 정의. **실제 경로는 바뀌지 않는다**

- [ ] **Step 1: 가드를 넣는다**

```bash
present "augment 는 제품·버전 폴더 밖" '_workspace/augment' \
        .claude/skills/testcase-augment/SKILL.md
```

- [ ] **Step 2: 현재 상태를 확인한다**

Run: `bash scripts/verify_unit_migration.sh | grep "augment 는 제품"`
Expected: `ok` — **이 가드는 지금도 통과한다.** 이 태스크의 목적은 통과시키는 것이
아니라, Step 3 이후에도 **정의 한 줄이 살아남게 못 박는 것**이다.

- [ ] **Step 3: 루트 정의 절을 신설한다**

`#### 0-1. 환경 검증` **바로 앞**에 넣는다.

````markdown
#### 0-0. 작업 디렉터리

**`{WS}` = `_workspace/augment`** — 제품·버전 폴더 **밖**이다.

이 절차의 원천은 기획서가 아니라 **구글 시트**라 문서 판본 개념이 없다.
제품·버전 폴더 안에 두면 실행할 때마다 *어느 판본 폴더에 넣을지* 를 물어야 하는데
그 답에 의미가 없다.

`{SHARED}` 는 쓰지 않는다 — 이 절차는 기획서 이미지를 보지 않는다.
이후 본문에서는 `{WS}` 로만 지칭한다.
````

- [ ] **Step 4: 본문 22곳을 치환한다**

`_workspace/augment/` → `{WS}/`. **0-0 절의 정의 한 줄만 `_workspace` 를 남긴다.**

- [ ] **Step 5: 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -c "_workspace" .claude/skills/testcase-augment/SKILL.md
grep -nE '_workspace/[0-9]|_workspace/pdf_images' .claude/skills/testcase-augment/SKILL.md
bash scripts/verify_unit_migration.sh | grep -E "augment 는 제품|산출물 경로 하드코딩|^PASS"
```

Expected: 첫 `grep -c` = `1` (0-0 정의 한 줄) · 두 번째 `grep` **결과 없음** ·
`ok    augment 는 제품·버전 폴더 밖` · `ok    오케스트레이터의 산출물 경로 하드코딩` · `PASS`

- [ ] **Step 6: 음성 대조**

```bash
cd /Users/hanflex/Git/testcase-auto
cp .claude/skills/testcase-augment/SKILL.md /tmp/tg.bak
sed -i '' 's|_workspace/augment|{작업폴더}|g' .claude/skills/testcase-augment/SKILL.md
bash scripts/verify_unit_migration.sh | grep "augment 는 제품"
cp /tmp/tg.bak .claude/skills/testcase-augment/SKILL.md
bash scripts/verify_unit_migration.sh | tail -1
```

Expected: 주입 시 `FAIL`, 원복 후 `PASS`

- [ ] **Step 7: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add .claude/skills/testcase-augment/SKILL.md scripts/verify_unit_migration.sh
git commit -m "$(cat <<'MSG'
재편: testcase-augment 표기를 {WS} 로 통일 (실제 경로는 불변)

경로가 안 바뀌어도 표기는 통일한다 — 여기만 하드코딩을 남기면 다음에 이
절차를 옮길 때 또 같은 작업을 하게 되고, 그것이 이번 재편이 없애려는 것이다.

이 절차의 원천은 시트라 문서 판본 개념이 없으므로 제품·버전 폴더 밖에 둔다.
그 결정을 가드로 못 박았다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: 사용자 문서 9종 + `CLAUDE.md`

**Files:**
- Modify: `README.md` (1) · `SETUP.md` (2) · `docs/BASICS.md` (3) · `docs/PROMPTS.md` (1) · `docs/DESIGN_DECISIONS.md` (2) · `HARNESS_OVERVIEW.md` (7) · `HARNESS_PIPELINE.md` (6) · `HARNESS_WORKFLOW.md` (16) · `HARNESS_SETUP_PROMPT.md` (1)
- Modify: `CLAUDE.md` (7곳 + 변경 이력 1행)

**Interfaces:**
- Consumes: Task 5·6이 확정한 디렉터리 구조와 변수 정의
- Produces: 없음 (마지막 태스크)

- [ ] **Step 1: 사용자 문서 9종의 예시 경로를 갱신한다**

문서는 **읽는 사람을 위한 것이므로 `{WS}` 대신 실제 예시 경로**를 쓴다.

| 옛 표기 | 새 표기 |
|---------|--------|
| `_workspace/01_prd_analysis_s01.md` | `_workspace/VIOLA-K8s_4.0_v1/testcase/01_prd_analysis_s01.md` |
| `_workspace/pdf_images/…` | `_workspace/VIOLA-K8s_4.0_v1/shared/images/…` |
| `_workspace/augment/…` | `_workspace/augment/…` (불변) |

`HARNESS_PIPELINE.md`·`HARNESS_WORKFLOW.md`·`HARNESS_OVERVIEW.md` 에는
**0-0 의 디렉터리 트리 그림을 한 번씩** 싣는다.

`docs/DESIGN_DECISIONS.md` 의 2곳은 **과거 서술**이므로 바꾸지 않는다 —
그 문서는 *그때 무엇을 했나* 를 적는 곳이다. 대신 주제 ⑤(비용)에 이번 재편을
전환점으로 한 단락 추가한다.

- [ ] **Step 2: `CLAUDE.md` 의 산출물 경로 7곳을 갱신한다**

「처리 단위」 문단의 `_workspace/00_screen_index.md`·`_workspace/00_cid_register.md` 등을
`_workspace/{제품}_{버전}/testcase/…` 로 바꾸고, 「환경」 절에 한 줄 추가한다.

```markdown
- **작업 디렉터리** — `_workspace/{제품}_{제품버전}_{문서회차}/` 아래 `shared/`(이미지·검출 공용)
  · `digest/`(기획서 분석) · `testcase/`(테스트 케이스). 추가 작업은 `_workspace/augment/`.
  경로의 단일 출처는 `testcase-auto` SKILL **0-0** 이다
```

- [ ] **Step 3: `CLAUDE.md` 변경 이력에 1행 추가한다**

표 맨 아래에 붙인다.

```markdown
| 2026-09-19 | **작업 디렉터리 재편 — 제품·버전 단위 + 절차별 분리 + 이미지 재사용** | `scripts/prd_cache.py` 신설 + 링크, `testcase-auto`·`testcase-augment`·`prd-analyzer`·`testcase-generator`·`testcase-reviewer` SKILL, 에이전트 5종, `common.md`, 사용자 문서 9종, `verify_setup.py`, `verify_unit_migration.sh`(가드 8개) | 사용자 지시. 모든 절차가 `_workspace/` 한 곳을 써서 제품·판본을 바꾸려면 통째로 옮기는 수밖에 없었고, 그 이동이 **이미지를 함께 버렸다** — 실측 `_workspace` 495MB 중 이미지가 484MB, 백업본에 296MB 더 있어 **같은 PDF의 같은 이미지가 780MB**. `pdf_to_images.py` 에 캐시·스킵 로직이 0건이라 매 실행 전량 재변환했고 181p 전체 세트가 **약 10분**이다. → 제품·버전 디렉터리 아래 `shared/`·`digest/`·`testcase/` 로 나누고 **재실행 백업에서 `shared/` 를 남긴다.** **`shared/` 를 둔 것이 설계의 핵심** — 이미지는 기획서 분석과 케이스 작성이 같이 쓰는 것이라 한쪽 안에 두면 다른 쪽이 남의 디렉터리를 보게 되고, 분석을 건너뛴 실행에서는 경로가 성립하지 않는다. **재사용의 전제는 실측으로 확인했다** — 같은 PDF·같은 옵션이면 출력이 SHA-256 까지 동일하다(전체 150 DPI, DESC 크롭 200 DPI `--tile=auto` 둘 다). 위험한 것은 **다른 판본으로 변환된 이미지를 재사용하는 것**이라, 판정 근거를 경로가 아니라 **PDF 내용 해시**로 두고 `prd_cache.py` 가 전담한다(`manifest.json` = 완료 마커, 불일치는 **중단**). 셸로 해시를 계산하지 않은 이유는 **판정 로직이 검사 대상이어야 하기 때문**이다 — `--selftest` 9건으로 *불일치를 실제로 잡는지* 확인한다. 함께 **경로를 문서에 박지 않는 규약**을 세웠다(`{WS}`·`{SHARED}`). `_workspace` 를 적어도 되는 곳은 오케스트레이터 SKILL 2종의 `0-0` 절뿐이고 나머지 13개 파일은 `absent` 가드로 0건을 강제한다 — 2026-08-25 C열 삽입 때 78건을 재매핑하고 얻은 *"열 문자를 공용 문서에 박지 말라"* 와 같은 처방이다. **에이전트에게는 치환된 실제 경로를 준다**(스스로 치환하면 엉뚱한 곳에 쓰고도 성공한 것처럼 보인다). 기존 스크립트는 **한 줄도 고치지 않았다** — 전부 이미 `--output-dir` 를 받는다. `testcase-augment` 는 원천이 시트라 판본 개념이 없어 **제품·버전 폴더 밖**에 둔다(사용자 확정) |
```

- [ ] **Step 4: 전수 확인**

```bash
cd /Users/hanflex/Git/testcase-auto
bash scripts/verify_unit_migration.sh | tail -3
python3 scripts/build_brief.py --coverage-check | tail -1
python3 scripts/verify_sheet_rows.py --selftest | tail -2
python3 scripts/prd_cache.py --selftest | tail -1
python3 verify_setup.py 2>&1 | grep -E "scripts/ 링크|스킬|에이전트"
```

Expected: `PASS` / `✅ 전 절 배정 완료 · 유령 배정 0건` / 위반 17종 + 오탐 0건 /
`selftest PASS — 9건 통과` / `scripts/ 링크 … 11개 정상`

- [ ] **Step 5: 남은 하드코딩이 없는지 전수 검사**

```bash
cd /Users/hanflex/Git/testcase-auto
grep -rn "_workspace" .claude/skills .claude/agents .claude/formats \
  --include="*.md" | grep -v "worktrees/"
```

Expected: **`testcase-auto` SKILL 의 0-0 절과 `testcase-augment` SKILL 의 0-0 절만** 나온다
(트리 그림 + 변수 정의). 그 밖의 줄이 나오면 그 파일을 고친다.

- [ ] **Step 6: 커밋**

```bash
cd /Users/hanflex/Git/testcase-auto
git add README.md SETUP.md docs/ HARNESS_*.md CLAUDE.md
git commit -m "$(cat <<'MSG'
문서: 작업 디렉터리 재편을 사용자 문서 9종과 CLAUDE.md 에 반영

문서에는 {WS} 표기 대신 실제 예시 경로를 쓴다 — 읽는 사람을 위한 자리다.
DESIGN_DECISIONS 의 옛 경로 2곳은 과거 서술이므로 그대로 두고, 주제 5(비용)에
이번 재편을 전환점으로 추가했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

## 완료 기준

| 검사 | 기대 |
|------|------|
| `bash scripts/verify_unit_migration.sh` | `PASS` (신설 가드 **8개** 포함) |
| `python3 scripts/prd_cache.py --selftest` | `selftest PASS — 9건 통과` |
| `python3 scripts/build_brief.py --coverage-check` | `✅ 전 절 배정 완료 · 유령 배정 0건` |
| `python3 scripts/verify_sheet_rows.py --selftest` | 위반 17종 검출 + 오탐 0건 |
| `python3 verify_setup.py` | `scripts/ 링크 … 11개 정상` |
| `grep -rn "_workspace" .claude/{skills,agents,formats} --include="*.md" \| grep -v worktrees/` | 오케스트레이터 SKILL 2종의 `0-0` 절만 |

**음성 대조를 건너뛴 가드는 완료로 치지 않는다.** 가드 8개 각각에 대해 위반을
주입해 `FAIL` 을 확인하고 원복한 기록이 있어야 한다 — 통과만 확인하면 패턴이 약해
선언이 사라져도 통과하는 경우를 놓친다.

## 이 계획이 다루지 않는 것

- **`prd-digest` 신설** — 스펙 2 / 별도 계획
- **`.claude/skills/harness/` 45곳** (하네스 제작 메타 스킬). 새 하네스를 만들 때
  `_workspace/` 를 가르치는 템플릿이라 규약을 따르는 것이 맞지만, 이 하네스의 동작과는
  층이 다르다. **이 계획에서는 손대지 않는다** — 필요하면 별도 태스크로 올린다
- **`.claude/worktrees/augment-impl/`** — 저장소 전체의 낡은 사본(`.gitignore` 대상).
  검사에서 제외하며 정리 여부는 이 작업의 범위가 아니다
- **기존 `_workspace/`·`_workspace_prev_*` 이관** (스펙 결정 7)

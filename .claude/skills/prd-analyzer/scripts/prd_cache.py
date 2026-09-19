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

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
  python prd_cache.py check --pdf=<PDF> --shared=<디렉터리> [--require=full,desc]
  python prd_cache.py --selftest

`--require=` 는 **있어야 하는 variant 이름 목록**이다. 매니페스트가 그중 하나라도
기록하고 있지 않으면 `CACHE_PARTIAL` 이다. 이 인자가 없으면 `check` 는 *이미 아는
variant* 만 검사하므로, `full` 만 등록된 트리가 `desc` 없이도 `CACHE_OK` 를 받는다 —
그러면 분석 담당이 DESC 조각을 못 받고 150 DPI 전체 페이지만 읽는다(한글 1자 9.9px).
오류는 나지 않고 **판독 품질만 조용히 떨어진다.**
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
    # variant 가 하나도 없으면 쓰지 않는다. 아래 루프의 무결성 검사는 목록이 비면
    # 한 번도 돌지 않으므로, 빈 목록을 그대로 통과시키면 **이미지가 0장인 디렉터리가
    # 영구히 유효한 캐시**가 된다 — 완료 마커라는 이 파일의 존재 이유가 무너진다.
    if not variants:
        return "WRITE_INCOMPLETE", {"reason": "variant 가 하나도 없다",
                                    "hint": "--variant=name=…,dir=… 를 최소 하나 주라"}

    pdf_hash = sha256_file(pdf)
    mp = os.path.join(shared, MANIFEST)

    # 기존 매니페스트가 있으면 같은 PDF 버전이라면 병합한다.
    recorded = {}
    if os.path.isfile(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                existing = json.load(f)
            # PDF 해시가 일치하면 (같은 버전) 기존 variant들을 유지한다.
            if existing.get("sha256") == pdf_hash:
                recorded = dict(existing.get("variants") or {})
        except (OSError, ValueError):
            # 매니페스트가 깨지면 새로 시작한다.
            pass

    # 이번 호출의 variant들을 새로 계산해서 업데이트한다.
    for v in variants:
        n = count_images(os.path.join(shared, v["dir"]))
        if n <= 0:
            return "WRITE_INCOMPLETE", {"variant": v["name"], "dir": v["dir"], "files": n}
        recorded[v["name"]] = {
            "dir": v["dir"], "dpi": v.get("dpi"), "tile": v.get("tile"), "files": n,
        }

    data = {
        "source_pdf": pdf,
        "sha256": pdf_hash,
        "page_count": page_count,
        "variants": recorded,
        "created": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    os.makedirs(shared, exist_ok=True)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return "WRITE_OK", {"variants": sorted(recorded), "sha256": data["sha256"][:16]}


def check_manifest(pdf, shared, require=None):
    """재사용해도 되는지 판정한다. 근거는 경로가 아니라 PDF 내용 해시다.

    `require` 는 **있어야 하는 variant 이름 목록**이다. 주지 않으면 매니페스트에
    기록된 variant 만 검사하므로, 밖에서 만들어져 일부만 채워진 트리가 `CACHE_OK`
    를 받는다. 그 경우 오류 없이 **판독 품질만 떨어지므로** 호출부가 필요한 이름을
    넘겨야 한다.
    """
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

    recorded = m.get("variants") or {}

    # 빈 매니페스트는 완료 마커가 아니다 — 아무것도 기록하지 않은 파일이 캐시 판정을
    # 통과하면 이미지 0장인 디렉터리가 유효한 캐시가 된다.
    if not recorded:
        return "CACHE_NO_MANIFEST", {"path": mp, "reason": "variants 가 비어 있다"}

    if require:
        missing = [r for r in require if r not in recorded]
        if missing:
            return "CACHE_PARTIAL", {
                "missing": missing, "required": list(require),
                "recorded": sorted(recorded),
            }

    for name, v in recorded.items():
        n = count_images(os.path.join(shared, v.get("dir", "")))
        if n != v.get("files"):
            return "CACHE_PARTIAL", {
                "variant": name, "expected": v.get("files"), "actual": n,
            }
    return "CACHE_OK", {"variants": sorted(recorded)}


def _selftest() -> int:
    import shutil
    import tempfile

    fails = []
    total = [0]

    def chk(name, cond, detail=""):
        total[0] += 1
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

        # S7: variant 병합 테스트 — full 을 쓴 뒤 desc 를 쓰면 둘 다 manifest 에 남는다.
        shared3 = os.path.join(t, "shared3")
        img_full = os.path.join(shared3, "images_full")
        img_desc = os.path.join(shared3, "images_desc")
        os.makedirs(img_full)
        os.makedirs(img_desc)
        for i in (1, 2, 3):
            with open(os.path.join(img_full, "page_%03d.png" % i), "wb") as f:
                f.write(b"x")
            with open(os.path.join(img_desc, "page_%03d.png" % i), "wb") as f:
                f.write(b"y")

        st, d = write_manifest(pdf, shared3, [{"name": "full", "dir": "images_full", "dpi": 150, "tile": None}])
        chk("S7 첫 variant write", st == "WRITE_OK", st)
        st, d = write_manifest(pdf, shared3, [{"name": "desc", "dir": "images_desc", "dpi": 200, "tile": "auto"}])
        chk("S7 두 번째 variant write", st == "WRITE_OK", st)

        # 병합되었으므로 manifest 에는 both 가 있고
        with open(os.path.join(shared3, MANIFEST), encoding="utf-8") as f:
            m = json.load(f)
        chk("S7 full 이 manifest 에 남음", "full" in m.get("variants", {}))
        chk("S7 desc 가 manifest 에 추가됨", "desc" in m.get("variants", {}))

        # check_manifest 가 여전히 full 의 파일 수를 검증한다.
        st, d = check_manifest(pdf, shared3)
        chk("S7 병합 후 CACHE_OK", st == "CACHE_OK", st)
        os.remove(os.path.join(img_full, "page_001.png"))
        st, d = check_manifest(pdf, shared3)
        chk("S7 full 이미지 삭제하면 CACHE_PARTIAL", st == "CACHE_PARTIAL", st)
        chk("S7 PARTIAL 이 full 을 지적", d.get("variant") == "full")
        with open(os.path.join(img_full, "page_001.png"), "wb") as f:
            f.write(b"x")

        # S9: PDF 버전 변경 시 manifest 는 대체된다 (병합하지 않는다)
        with open(pdf, "wb") as f:
            f.write(b"%PDF-1.4 fake body v3")
        st, d = write_manifest(pdf, shared3, [{"name": "new", "dir": "images_desc", "dpi": 300, "tile": None}])
        chk("S9 버전 변경 후 write", st == "WRITE_OK", st)

        with open(os.path.join(shared3, MANIFEST), encoding="utf-8") as f:
            m = json.load(f)
        chk("S9 full 이 제거됨 (대체됨)", "full" not in m.get("variants", {}))
        chk("S9 desc 가 제거됨 (대체됨)", "desc" not in m.get("variants", {}))
        chk("S9 new 만 있음", m.get("variants", {}).get("new") is not None)

        # S10: _parse_variant 테스트
        pv = _parse_variant("name=full,dir=images,dpi=150,tile=none")
        chk("S10 parse tile=none → None", pv.get("tile") is None)
        chk("S10 parse dpi → int", pv.get("dpi") == 150 and isinstance(pv.get("dpi"), int))

        # S11-S15: CLI 통합 테스트
        shared4 = os.path.join(t, "shared4")
        img4 = os.path.join(shared4, "images")
        os.makedirs(img4)
        for i in (1, 2):
            with open(os.path.join(img4, "page_%03d.png" % i), "wb") as f:
                f.write(b"x")
        pdf3 = os.path.join(t, "doc3.pdf")
        with open(pdf3, "wb") as f:
            f.write(b"%PDF-1.4 fake body")

        rc = main(["check", "--pdf=%s" % pdf3, "--shared=%s" % shared4])
        chk("S11 check 명령: manifest 없으면 exit code 3", rc == 3)

        rc = main(["write", "--pdf=%s" % pdf3, "--shared=%s" % shared4,
                   "--variant=name=full,dir=images,dpi=150,tile=none"])
        chk("S12 write 명령: 성공하면 exit code 0", rc == 0)

        rc = main(["check", "--pdf=%s" % pdf3, "--shared=%s" % shared4])
        chk("S13 check 명령: 정상이면 exit code 0", rc == 0)

        with open(pdf3, "wb") as f:
            f.write(b"%PDF-1.4 fake body changed")
        rc = main(["check", "--pdf=%s" % pdf3, "--shared=%s" % shared4])
        chk("S14 check 명령: PDF 변경하면 exit code 2", rc == 2)

        os.remove(os.path.join(img4, "page_002.png"))
        with open(pdf3, "wb") as f:
            f.write(b"%PDF-1.4 fake body")
        rc = main(["check", "--pdf=%s" % pdf3, "--shared=%s" % shared4])
        chk("S15 check 명령: 파일 손실하면 exit code 4", rc == 4)

        # S16: variant 를 하나도 주지 않은 write 는 거부한다.
        # 빈 매니페스트를 쓰면 이미지 0장인 디렉터리가 영구 유효 캐시가 된다.
        shared5 = os.path.join(t, "shared5")
        os.makedirs(shared5)
        st, d = write_manifest(pdf, shared5, [])
        chk("S16 variant 없는 write 는 WRITE_INCOMPLETE", st == "WRITE_INCOMPLETE", st)
        chk("S16 거부 시 manifest 미생성",
            not os.path.exists(os.path.join(shared5, MANIFEST)))
        rc = main(["write", "--pdf=%s" % pdf, "--shared=%s" % shared5])
        chk("S16 write 명령: variant 없으면 exit code 4", rc == 4)

        # S17~S18: `full` 만 등록된 트리 — --require 유무로 판정이 갈린다.
        shared6 = os.path.join(t, "shared6")
        img6 = os.path.join(shared6, "images")
        os.makedirs(img6)
        for i in (1, 2):
            with open(os.path.join(img6, "page_%03d.png" % i), "wb") as f:
                f.write(b"x")
        st, d = write_manifest(
            pdf, shared6, [{"name": "full", "dir": "images", "dpi": 150, "tile": None}])
        chk("S17 full 만 등록한 write", st == "WRITE_OK", st)

        st, d = check_manifest(pdf, shared6, require=["full", "desc"])
        chk("S17 --require 로 누락 variant 를 잡는다", st == "CACHE_PARTIAL", st)
        chk("S17 누락 목록이 desc 를 지목", d.get("missing") == ["desc"], d)
        rc = main(["check", "--pdf=%s" % pdf, "--shared=%s" % shared6,
                   "--require=full,desc"])
        chk("S17 check --require 명령: exit code 4", rc == 4)

        st, d = check_manifest(pdf, shared6)
        chk("S18 --require 없으면 아는 variant 만 검사해 CACHE_OK",
            st == "CACHE_OK", st)

        # S19: variants 가 빈 매니페스트는 완료 마커가 아니다.
        shared7 = os.path.join(t, "shared7")
        os.makedirs(shared7)
        with open(os.path.join(shared7, MANIFEST), "w", encoding="utf-8") as f:
            json.dump({"source_pdf": pdf, "sha256": sha256_file(pdf),
                       "page_count": 2, "variants": {}}, f)
        st, d = check_manifest(pdf, shared7)
        chk("S19 빈 variants 는 CACHE_NO_MANIFEST", st == "CACHE_NO_MANIFEST", st)
        rc = main(["check", "--pdf=%s" % pdf, "--shared=%s" % shared7])
        chk("S19 check 명령: 빈 variants 면 exit code 3", rc == 3)

    print()
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    # 건수는 실행 중에 센다 — 하드코딩하면 케이스가 사라져도 같은 수가 찍힌다.
    print("selftest PASS — %d건 통과" % total[0])
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
        req = [s.strip() for s in (opt.get("require") or "").split(",") if s.strip()]
        st, d = check_manifest(pdf, shared, require=req or None)
    else:
        print("알 수 없는 명령: %s" % cmd)
        return 1

    print("%s %s" % (st, json.dumps(d, ensure_ascii=False)))
    return EXIT.get(st, 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

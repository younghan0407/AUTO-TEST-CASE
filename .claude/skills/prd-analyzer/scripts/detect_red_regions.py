"""기획서의 변경 표시(빨강) 영역을 검출하여 크롭 이미지로 저장.

개정판 기획서는 변경된 부분만 빨간색으로 표시하는 것이 팀 컨벤션이다.
  1. 빨간 테두리 박스  — 화면 와이어프레임에서 변경 영역을 감쌈
  2. 빨간 `변경사항` 스티커 — 변경 내역 요약
  3. Description 패널의 빨간 텍스트 — 신규·변경 스펙 서술

이 스크립트는 위 세 표기의 **후보 영역**을 픽셀 기반으로 찾아준다.

⚠️ 오탐 필수 주의
   필수 입력 표시 `*`, 에러·경고 아이콘, 실패 상태 badge, 삭제 버튼,
   차트의 빨강 계열 등 **원래부터 빨간 UI 요소**도 함께 잡힌다.
   반드시 이미지 육안 판독으로 변경분을 확정할 것. 이 출력은 보조 수단이다.

의존성: pymupdf, pillow, numpy

입력은 **PDF / 이미지 파일 / 이미지 디렉터리** 세 가지를 모두 받는다.
기획서가 PDF 없이 이미지(PNG 등)로만 전달된 경우에도 그대로 사용할 수 있다.

CLI 사용:
  python detect_red_regions.py <pdf_or_image_or_dir> [--pages=START-END] [--dpi=150]
                               [--output-dir=<dir>] [--min-area=400] [--pad=24]
                               [--no-crops] [--no-merge]

  --pages=START-END : 검출할 페이지 범위 (1-indexed, 양 끝 포함). 생략 시 전체
                      이미지 디렉터리 입력 시에는 파일명 정렬 순서의 인덱스를 의미한다
  --dpi             : **PDF 입력에만 적용**. 이미지 입력은 원본 해상도를 그대로 사용
  --dpi             : 렌더 DPI (기본 150). 얇은 테두리를 놓치면 200으로 올린다
  --output-dir      : 크롭 저장 위치 (기본 _workspace/red_regions/<pdf_basename>)
  --min-area        : 이 픽셀 수 미만의 영역은 노이즈로 버림 (기본 400)
  --pad             : 크롭 시 영역 주변 여유 픽셀 (기본 24)
  --no-crops        : 크롭 이미지를 저장하지 않고 좌표 목록만 출력
  --no-merge        : 조각 병합을 끈다 (글자 단위 원시 검출 결과 확인용)

빨간 텍스트는 글자마다 별개 영역으로 검출되므로, 기본적으로 줄 → 문단 순으로
병합하여 판독 가능한 단위로 묶는다 (`--no-merge`로 해제 가능).

출력:
  - `<output-dir>/pNNN_redMM.png` 크롭 이미지
  - `<output-dir>/red_regions.json` 영역 메타데이터
  - stdout: 페이지별 영역 요약 (좌표, 크기, 형태 추정)

형태 추정(`shape`)은 판독 우선순위를 정하는 힌트다:
  box       — 속이 빈 사각 테두리 (변경 영역 박스일 가능성 높음)
  text_line — 가로로 긴 저밀도 영역 (빨간 텍스트 한 줄일 가능성 높음)
  blob      — 채워진 덩어리 (스티커·아이콘·badge 등)

Python 사용:
  from detect_red_regions import detect
  regions = detect("input.pdf", pages=(70, 73), dpi=150)
  regions = detect("_workspace/prd_images/ch01")          # 이미지 디렉터리
  regions = detect("_workspace/prd_images/page_003.png")  # 이미지 단건
"""

from __future__ import annotations

import json
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print(
        "필수 라이브러리가 없습니다. 설치:\n  pip install pillow numpy",
        file=sys.stderr,
    )
    raise

# Pillow의 decompression bomb 경고 한도 해제 (기획서 페이지는 정상적으로 매우 큼)
Image.MAX_IMAGE_PIXELS = None

# 이미지 입력으로 인식하는 확장자
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

DEFAULT_DPI = 150
DEFAULT_MIN_AREA = 400
DEFAULT_PAD = 24

# 빨강 판정 임계값 (RGB)
# 기획서의 변경 표시는 순수한 빨강~주황빨강 계열이다.
RED_MIN = 110          # R 최소값
RED_DOMINANCE = 55     # R - max(G, B) 최소 차이
GRAY_MAX = 150         # G, B 최대값 (분홍·연빨강 배경 제외)


def _red_mask(arr: "np.ndarray") -> "np.ndarray":
    """RGB 배열에서 빨강 픽셀 마스크를 만든다."""
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    gb_max = np.maximum(g, b)
    return (r >= RED_MIN) & ((r - gb_max) >= RED_DOMINANCE) & (gb_max <= GRAY_MAX)


def _label_regions(mask: "np.ndarray", min_area: int) -> list[dict]:
    """연결 요소를 라벨링하여 영역 목록을 반환.

    scipy 의존을 피하기 위해 iterative flood fill(스택 기반)로 구현.
    빨강 픽셀은 페이지 전체에서 소수이므로 성능 문제 없음.
    """
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    ys, xs = np.nonzero(mask)
    regions: list[dict] = []

    # 근접 픽셀을 같은 영역으로 묶기 위한 탐색 반경
    # (점선 테두리·자간이 있는 텍스트가 조각나는 것을 방지)
    radius = 3
    offsets = [
        (dy, dx)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if not (dy == 0 and dx == 0)
    ]

    for sy, sx in zip(ys, xs):
        if visited[sy, sx]:
            continue
        stack = [(int(sy), int(sx))]
        visited[sy, sx] = True
        pts_y, pts_x = [], []
        while stack:
            cy, cx = stack.pop()
            pts_y.append(cy)
            pts_x.append(cx)
            for dy, dx in offsets:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((ny, nx))

        y0, y1 = min(pts_y), max(pts_y)
        x0, x1 = min(pts_x), max(pts_x)
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        bbox_area = bw * bh
        if bbox_area < min_area:
            continue
        fill_ratio = len(pts_y) / float(bbox_area)
        regions.append(
            {
                "x": int(x0),
                "y": int(y0),
                "w": int(bw),
                "h": int(bh),
                "red_pixels": len(pts_y),
                "fill_ratio": round(fill_ratio, 4),
                "shape": _guess_shape(bw, bh, fill_ratio),
            }
        )

    regions.sort(key=lambda r: (r["y"], r["x"]))
    return regions


def _merge_pass(regions: list[dict], mode: str) -> tuple[list[dict], bool]:
    """인접한 영역을 한 번 병합한다. (병합 결과, 변경 여부) 반환.

    mode="line"  : 같은 줄의 글자·단어를 가로로 이어붙인다
    mode="block" : 세로로 인접한 줄을 하나의 문단/영역으로 묶는다
    """
    merged: list[dict] = []
    used = [False] * len(regions)
    changed = False

    for i, a in enumerate(regions):
        if used[i]:
            continue
        cur = dict(a)
        used[i] = True
        # 병합이 연쇄될 수 있으므로 현재 영역이 커질 때마다 다시 훑는다
        grew = True
        while grew:
            grew = False
            for j, b in enumerate(regions):
                if used[j]:
                    continue
                ay0, ay1 = cur["y"], cur["y"] + cur["h"]
                ax0, ax1 = cur["x"], cur["x"] + cur["w"]
                by0, by1 = b["y"], b["y"] + b["h"]
                bx0, bx1 = b["x"], b["x"] + b["w"]

                if mode == "line":
                    v_overlap = min(ay1, by1) - max(ay0, by0)
                    ref_h = min(cur["h"], b["h"])
                    h_gap = max(bx0 - ax1, ax0 - bx1)
                    ok = (
                        ref_h > 0
                        and v_overlap >= 0.40 * ref_h
                        and h_gap <= max(30, 1.2 * ref_h)
                    )
                else:  # block
                    h_overlap = min(ax1, bx1) - max(ax0, bx0)
                    ref_w = min(cur["w"], b["w"])
                    v_gap = max(by0 - ay1, ay0 - by1)
                    avg_h = 0.5 * (cur["h"] + b["h"])
                    ok = (
                        ref_w > 0
                        and h_overlap >= 0.50 * ref_w
                        and v_gap <= 0.80 * avg_h
                    )

                if ok:
                    nx0, ny0 = min(ax0, bx0), min(ay0, by0)
                    nx1, ny1 = max(ax1, bx1), max(ay1, by1)
                    cur["x"], cur["y"] = nx0, ny0
                    cur["w"], cur["h"] = nx1 - nx0, ny1 - ny0
                    cur["red_pixels"] = cur["red_pixels"] + b["red_pixels"]
                    used[j] = True
                    changed = True
                    grew = True

        bbox_area = float(cur["w"] * cur["h"]) or 1.0
        cur["fill_ratio"] = round(cur["red_pixels"] / bbox_area, 4)
        cur["shape"] = _guess_shape(cur["w"], cur["h"], cur["fill_ratio"])
        merged.append(cur)

    merged.sort(key=lambda r: (r["y"], r["x"]))
    return merged, changed


def _merge_regions(regions: list[dict]) -> list[dict]:
    """글자 단위로 조각난 검출 결과를 줄 → 문단 순으로 병합한다.

    빨간 Description 텍스트는 글자마다 별개 영역으로 잡히므로
    병합 없이는 후보가 수백 개로 늘어나 판독에 쓸 수 없다.
    """
    for mode in ("line", "block", "line"):
        for _ in range(6):  # 연쇄 병합 수렴까지 반복
            regions, changed = _merge_pass(regions, mode)
            if not changed:
                break
    return regions


def _guess_shape(w: int, h: int, fill_ratio: float) -> str:
    """영역의 형태를 추정해 판독 우선순위 힌트를 준다."""
    aspect = w / float(h) if h else 0.0
    if fill_ratio < 0.22 and w > 60 and h > 60:
        return "box"          # 속이 빈 사각 테두리 → 변경 영역 박스 가능성 높음
    if aspect >= 4.0 and fill_ratio < 0.55:
        return "text_line"    # 가로로 긴 저밀도 → 빨간 텍스트 한 줄
    return "blob"             # 채워진 덩어리 → 스티커·아이콘·badge


def _classify_input(path: str) -> str:
    """입력 경로가 PDF / 이미지 파일 / 이미지 디렉터리 중 무엇인지 판별한다."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"입력 경로가 없습니다: {path}")
    if os.path.isdir(path):
        return "image_dir"
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    raise ValueError(
        f"지원하지 않는 입력 형식입니다: {path}\n"
        f"  PDF(.pdf) / 이미지({', '.join(sorted(IMAGE_EXTS))}) / 이미지 디렉터리만 가능"
    )


def _list_images(dir_path: str) -> list[str]:
    names = sorted(
        n for n in os.listdir(dir_path)
        if os.path.splitext(n)[1].lower() in IMAGE_EXTS
    )
    if not names:
        raise ValueError(f"디렉터리에 이미지 파일이 없습니다: {dir_path}")
    return [os.path.join(dir_path, n) for n in names]


def _clip_range(pages: "tuple[int, int] | None", total: int) -> tuple[int, int]:
    start, end = (pages if pages else (1, total))
    start = max(1, start)
    end = min(total, end)
    if start > end:
        raise ValueError(f"잘못된 범위: {start}-{end} (총 {total}개)")
    return start, end


def _open_image(path: str) -> "Image.Image":
    """이미지를 RGB로 연다. 손상 파일은 명확한 메시지로 실패시킨다."""
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:  # 손상·미지원 이미지
        raise ValueError(f"이미지를 읽을 수 없습니다(손상 가능): {path} — {e}") from e
    return img.convert("RGB")


def _iter_pages(input_path: str, input_type: str, pages, dpi: int):
    """(page_no, id_prefix, PIL.Image, source_path)를 순서대로 내놓는다."""
    if input_type == "pdf":
        try:
            import fitz  # pymupdf
        except ImportError:
            raise ImportError(
                "PDF 입력에는 pymupdf가 필요합니다. 설치:\n  pip install pymupdf"
            )
        doc = fitz.open(input_path)
        try:
            start, end = _clip_range(pages, doc.page_count)
            matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            for pno in range(start, end + 1):
                pix = doc.load_page(pno - 1).get_pixmap(matrix=matrix, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                yield pno, f"p{pno:03d}", img, f"{input_path}#p{pno}"
        finally:
            doc.close()
        return

    paths = [input_path] if input_type == "image" else _list_images(input_path)
    start, end = _clip_range(pages, len(paths))
    for pno in range(start, end + 1):
        path = paths[pno - 1]
        stem = os.path.splitext(os.path.basename(path))[0]
        yield pno, stem, _open_image(path), path


def detect(
    input_path: str,
    pages: tuple[int, int] | None = None,
    dpi: int = DEFAULT_DPI,
    output_dir: str | None = None,
    min_area: int = DEFAULT_MIN_AREA,
    pad: int = DEFAULT_PAD,
    save_crops: bool = True,
    merge: bool = True,
) -> dict:
    """PDF / 이미지 파일 / 이미지 디렉터리에서 빨강 영역을 검출한다.

    반환: {'input', 'input_type', 'dpi', 'pages': [{'page', 'source', 'width',
           'height', 'region_count', 'regions': [...]}]}

    `dpi`는 PDF 입력에만 적용된다. 이미지 입력은 원본 해상도를 그대로 쓴다.
    """
    input_type = _classify_input(input_path)

    if output_dir is None:
        base = os.path.basename(input_path.rstrip(os.sep))
        if input_type != "image_dir":
            base = os.path.splitext(base)[0]
        output_dir = os.path.join("_workspace", "red_regions", base)
    if save_crops:
        os.makedirs(output_dir, exist_ok=True)

    result = {
        "input": input_path,
        "input_type": input_type,
        "pdf": input_path if input_type == "pdf" else None,
        "dpi": dpi if input_type == "pdf" else None,
        "output_dir": output_dir,
        "pages": [],
    }

    for pno, id_prefix, img, source in _iter_pages(input_path, input_type, pages, dpi):
        arr = np.asarray(img)

        mask = _red_mask(arr)
        regions = _label_regions(mask, min_area)
        if merge:
            regions = _merge_regions(regions)

        for idx, reg in enumerate(regions, start=1):
            reg["id"] = f"{id_prefix}_red{idx:02d}"
            if save_crops:
                x0 = max(0, reg["x"] - pad)
                y0 = max(0, reg["y"] - pad)
                x1 = min(img.width, reg["x"] + reg["w"] + pad)
                y1 = min(img.height, reg["y"] + reg["h"] + pad)
                crop_path = os.path.join(output_dir, f"{reg['id']}.png")
                img.crop((x0, y0, x1, y1)).save(crop_path)
                reg["crop"] = crop_path

        result["pages"].append(
            {
                "page": pno,
                "source": source,
                "width": img.width,
                "height": img.height,
                "region_count": len(regions),
                "regions": regions,
            }
        )

    if save_crops:
        meta_path = os.path.join(output_dir, "red_regions.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["meta"] = meta_path

    return result


def _page_label(page: dict) -> str:
    """PDF는 pNNN, 이미지 입력은 파일명을 라벨로 쓴다."""
    src = page.get("source") or ""
    if src and "#p" not in src:
        return os.path.splitext(os.path.basename(src))[0]
    return f"p{page['page']:03d}"


def _print_summary(result: dict) -> None:
    total_regions = sum(p["region_count"] for p in result["pages"])
    dpi_note = f", DPI {result['dpi']}" if result.get("dpi") else ", 원본 해상도"
    print(
        f"빨강 영역 검출 완료 — 입력 {result['input_type']}, "
        f"{len(result['pages'])}페이지, 총 {total_regions}개 후보 영역{dpi_note}"
    )
    for p in result["pages"]:
        label = _page_label(p)
        if not p["region_count"]:
            print(f"\n{label} ({p['width']}x{p['height']}): 빨강 영역 없음")
            continue
        print(f"\n{label} ({p['width']}x{p['height']}): {p['region_count']}개")
        for reg in p["regions"]:
            print(
                f"  {reg['id']}  shape={reg['shape']:<9} "
                f"pos=({reg['x']},{reg['y']}) size={reg['w']}x{reg['h']} "
                f"fill={reg['fill_ratio']:.2f}"
                + (f"  → {reg['crop']}" if reg.get("crop") else "")
            )
    if result.get("meta"):
        print(f"\n메타데이터: {result['meta']}")
    print(
        "\n⚠️  이 결과에는 오탐이 섞여 있다 (필수 표시 `*`, 에러 아이콘, 실패 상태 badge,\n"
        "    삭제 버튼, 차트의 빨강 등 원래부터 빨간 UI 요소). 반드시 이미지를 직접 읽어\n"
        "    변경 표기인지 확정할 것. shape=box / text_line 을 우선 판독하면 효율적이다."
    )


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else True)
            for a in argv[1:] if a.startswith("--")}

    if not args:
        print(__doc__)
        return 1

    input_path = args[0]
    pages = None
    if isinstance(opts.get("--pages"), str):
        raw = opts["--pages"]
        if "-" in raw:
            s, e = raw.split("-", 1)
            pages = (int(s), int(e))
        else:
            pages = (int(raw), int(raw))

    try:
        result = detect(
            input_path,
            pages=pages,
            dpi=int(opts.get("--dpi", DEFAULT_DPI)),
            output_dir=opts.get("--output-dir") if isinstance(opts.get("--output-dir"), str) else None,
            min_area=int(opts.get("--min-area", DEFAULT_MIN_AREA)),
            pad=int(opts.get("--pad", DEFAULT_PAD)),
            save_crops="--no-crops" not in opts,
            merge="--no-merge" not in opts,
        )
    except (FileNotFoundError, ValueError, ImportError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    _print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

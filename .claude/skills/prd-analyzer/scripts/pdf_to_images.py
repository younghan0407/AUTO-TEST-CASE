"""PDF를 페이지별 PNG 이미지로 변환.

의존성: pymupdf (pip install pymupdf)

CLI 사용:
  python pdf_to_images.py <pdf_path> [--dpi=150] [--output-dir=<dir>] [--pages=START-END]
  python pdf_to_images.py <pdf_path> --crop-desc [--dpi=200] [--output-dir=<dir>] [--pages=START-END]
  python pdf_to_images.py <pdf_path> --crop-desc --tile=auto        # 판독용 분할 (권장)
  python pdf_to_images.py <pdf_path> --crop-desc --tile=4 --tile-overlap=24

  --crop-desc: Description 패널 영역(x 53%~100%)만 크롭하여 저장.
               스펙 페이지 판독에 사용. 전체 변환과 함께 쓰는 것을 권장.
  --pages=START-END: 변환할 페이지 범위 (1-indexed, 양 끝 포함).
                     예: --pages=1-13 → 1~13페이지만 변환.
                     생략 시 전체 페이지 변환.
  --tile=auto|N: 페이지(또는 크롭 영역)를 **세로 N조각**으로 나눠 저장한다.
                 `auto` 는 조각이 모델 전달 상한 안에 들어오도록 N을 계산한다.
  --tile-overlap=<pt>: 조각 간 겹침(PDF 포인트, 기본 24). 절단선에 걸친 텍스트 줄 유실 방지.
  출력: 변환된 파일 경로를 한 줄씩 stdout에 출력
  기본 출력 디렉토리: _workspace/pdf_images/<pdf_basename>/

⚠️ DPI를 올려도 그대로 전달되지 않는다 — `--tile` 이 필요한 이유:
  이미지는 모델에 전달될 때 **긴 변 1568px · 총 115만 픽셀** 안으로 축소된다.
  VIOLA 기획서 실측 — DESC 크롭 200 DPI 는 3525x5298 이라 전달 시 874x1314 로 줄어들고
  (유효배율 0.248) 한글 본문 1자가 40px → **9.9px** 가 되어 판독이 안 된다.
  같은 크롭을 세로 4분할하면 조각당 1568x589 로 전달되어 **17.8px** 가 되고,
  토큰도 오히려 줄어든다 (전체+크롭+재크롭 왕복 ~11.5K → 전체+4조각 ~6.5K).
  **DPI를 올려 판독을 개선하려는 시도는 상한에서 버려진다. 해상도는 분할로만 얻는다.**

DPI 권장값:
  - 전체 페이지 (UI 배치 파악): 150 DPI, 분할 없음
  - Description 패널 크롭 (스펙 텍스트 판독): 200 DPI + `--tile=auto`

페이지 범위 지정 예시:
  python pdf_to_images.py doc.pdf --pages=1-13

Python 사용:
  from pdf_to_images import convert_pdf, crop_description_panels, plan_tiles
  paths = convert_pdf("input.pdf", output_dir="_workspace/pdf_images/doc", dpi=150)
  paths = convert_pdf("input.pdf", output_dir="_workspace/pdf_images/doc", dpi=150, pages=(1, 13))
  desc_paths = crop_description_panels("input.pdf", output_dir="_workspace/pdf_images/doc_desc", dpi=200)
  desc_paths = crop_description_panels("input.pdf", output_dir=".../doc_desc", dpi=200, tile="auto")
"""

from __future__ import annotations

import os
import sys

# Description 패널이 시작하는 x 비율 (페이지 너비 기준)
# 스펙 페이지는 좌측 UI 화면(~53%) + 우측 Description 패널(53%~100%) 구조
_DESC_X_RATIO = 0.53

# 모델 전달 시 이미지 축소 상한. 이 값을 넘는 픽셀은 전달 전에 버려진다.
_MAX_EDGE = 1568
_MAX_PIXELS = 1_150_000

# --tile 조각 간 기본 겹침 (PDF 포인트). 절단선에 걸친 텍스트 줄 유실 방지.
_DEFAULT_TILE_OVERLAP_PT = 24

# --tile=auto 가 만들 수 있는 최대 조각 수 (폭주 방지)
_MAX_AUTO_TILES = 12


def delivered_size(width_px: float, height_px: float) -> tuple[int, int, float]:
    """모델에 실제로 전달되는 크기와 유효배율을 계산한다.

    긴 변 _MAX_EDGE, 총 픽셀 _MAX_PIXELS 두 상한을 순서대로 적용한다.
    Returns: (전달 폭, 전달 높이, 유효배율)
    """
    scale = min(_MAX_EDGE / max(width_px, height_px), 1.0)
    w, h = width_px * scale, height_px * scale
    if w * h > _MAX_PIXELS:
        k = (_MAX_PIXELS / (w * h)) ** 0.5
        w, h, scale = w * k, h * k, scale * k
    return int(w), int(h), scale


def plan_tiles(width_px: float, height_px: float) -> int:
    """세로 몇 조각으로 나누면 각 조각이 상한 안에 들어오는지 계산한다.

    가로는 나누지 않는다 — Description 패널은 단일 텍스트 컬럼이라
    가로로 자르면 문장이 끊긴다.
    """
    if width_px <= 0 or height_px <= 0:
        return 1
    scale_w = min(_MAX_EDGE / width_px, 1.0)
    max_h_src = (_MAX_PIXELS / (width_px * scale_w)) / scale_w
    n = 1
    while n < _MAX_AUTO_TILES and height_px / n > max_h_src:
        n += 1
    return n


def _resolve_tile_count(tile, width_px: float, height_px: float) -> int:
    """--tile 인자를 실제 조각 수로 해석한다."""
    if tile in (None, 0, 1, "1"):
        return 1
    if isinstance(tile, str) and tile.lower() == "auto":
        return plan_tiles(width_px, height_px)
    n = int(tile)
    if n < 1:
        raise ValueError(f"--tile 값은 1 이상이어야 합니다: {tile}")
    return min(n, _MAX_AUTO_TILES)


def _tile_clips(clip, n: int, overlap_pt: float):
    """clip 영역을 세로 n조각으로 나눈 Rect 목록. 조각 경계에 overlap_pt 만큼 겹침을 준다."""
    import fitz

    if n <= 1:
        return [clip]
    step = (clip.y1 - clip.y0) / n
    rects = []
    for k in range(n):
        y0 = clip.y0 + step * k
        y1 = clip.y0 + step * (k + 1)
        if k > 0:
            y0 = max(clip.y0, y0 - overlap_pt)
        if k < n - 1:
            y1 = min(clip.y1, y1 + overlap_pt)
        rects.append(fitz.Rect(clip.x0, y0, clip.x1, y1))
    return rects


def _render(page, matrix, clip, out_base: str, tile, overlap_pt: float,
            paths: list, report: list) -> None:
    """한 페이지(또는 클립 영역)를 tile 수만큼 나눠 저장하고 경로를 paths에 넣는다."""
    import fitz

    box = clip if clip is not None else page.rect
    scale = matrix.a
    n = _resolve_tile_count(tile, box.width * scale, box.height * scale)
    clips = _tile_clips(box, n, overlap_pt)

    for k, c in enumerate(clips, start=1):
        pix = page.get_pixmap(matrix=matrix, clip=c)
        suffix = f"_t{k}" if n > 1 else ""
        out_path = f"{out_base}{suffix}.png"
        pix.save(out_path)
        paths.append(out_path)
        if k == 1:
            dw, dh, eff = delivered_size(pix.width, pix.height)
            report.append((n, pix.width, pix.height, dw, dh, eff))


def convert_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    pages: tuple[int, int] | None = None,
    tile=None,
    tile_overlap_pt: float = _DEFAULT_TILE_OVERLAP_PT,
) -> list[str]:
    """PDF 파일을 페이지별 전체 PNG로 변환하여 경로 목록 반환.

    Args:
        pages: (start, end) 1-indexed, 양 끝 포함. None이면 전체 변환.
               예: (1, 13) → 1~13페이지만 변환.
        tile: None/1 = 분할 없음, "auto" = 상한에 맞춰 자동 계산, N = N조각.
              분할 시 파일명에 `_t1`, `_t2` … 접미가 붙는다.
        tile_overlap_pt: 조각 간 겹침(PDF 포인트).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. 다음 명령 실행 후 재시도하세요:\n"
            "  pip install pymupdf"
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72  # 72 DPI가 PDF 기준 해상도
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    report: list = []
    for i in range(start_idx, end_idx):
        out_base = os.path.join(output_dir, f"page_{i + 1:03d}")
        _render(doc[i], matrix, None, out_base, tile, tile_overlap_pt, paths, report)

    doc.close()
    _print_delivery_report(report, "전체 페이지")
    return paths


def crop_description_panels(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    pages: tuple[int, int] | None = None,
    tile=None,
    tile_overlap_pt: float = _DEFAULT_TILE_OVERLAP_PT,
) -> list[str]:
    """각 페이지의 Description 패널 영역(우측 47%)만 크롭하여 저장.

    스펙 페이지의 Description 텍스트를 정밀 판독할 때 사용한다.
    전체 페이지 변환(convert_pdf)과 함께 사용하여 UI는 전체 이미지로,
    Description은 크롭 이미지로 분석하는 것을 권장한다.

    ⚠️ 크롭만으로는 판독 해상도가 확보되지 않는다. 전달 상한(긴 변 1568px)
    때문에 200 DPI 크롭도 유효배율 0.25로 줄어든다. **`tile="auto"` 를 함께 쓴다.**

    Args:
        pages: (start, end) 1-indexed, 양 끝 포함. None이면 전체 변환.
               예: (14, 26) → 14~26페이지만 크롭.
        tile: None/1 = 분할 없음, "auto" = 상한에 맞춰 자동 계산, N = N조각.
        tile_overlap_pt: 조각 간 겹침(PDF 포인트).
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. pip install pymupdf 실행 후 재시도하세요."
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    report: list = []
    for i in range(start_idx, end_idx):
        page = doc[i]
        rect = page.rect
        clip = fitz.Rect(rect.width * _DESC_X_RATIO, 0, rect.width, rect.height)
        out_base = os.path.join(output_dir, f"page_{i + 1:03d}_desc")
        _render(page, matrix, clip, out_base, tile, tile_overlap_pt, paths, report)

    doc.close()
    _print_delivery_report(report, "Description 크롭")
    return paths


def _print_delivery_report(report: list, label: str) -> None:
    """실제로 모델에 전달되는 해상도를 stderr에 알린다.

    유효배율이 낮으면 판독이 안 되므로 조용히 넘어가지 않는다. 다만
    **세로 분할로 도달 가능한 최적값과 비교**해서 알린다 — 폭이 상한을
    넘는 페이지는 아무리 나눠도 `_MAX_EDGE / 폭` 이상으로 올라가지 않으므로,
    최적에 도달한 상태를 결함처럼 경고하면 잘못된 신호가 된다.
    """
    if not report:
        return
    n, w, h, dw, dh, eff = report[0]
    tiles = f"{n}조각 분할" if n > 1 else "분할 없음"
    print(
        f"[{label}] {tiles} — 조각 원본 {w}x{h} → 모델 전달 {dw}x{dh} "
        f"(유효배율 {eff:.3f}, 한글 40px → {40 * eff:.1f}px)",
        file=sys.stderr,
    )

    # 세로 분할로 도달 가능한 최적 배율 = 폭 제약만 남은 상태
    best = min(_MAX_EDGE / w, 1.0)
    if eff < best * 0.95:
        want = plan_tiles(w, h * n if n > 1 else h)
        print(
            f"  ⚠️ 분할을 늘리면 유효배율 {best:.3f} (한글 {40 * best:.1f}px) 까지 오릅니다."
            f" `--tile=auto`(={want}조각) 를 쓰십시오.\n"
            f"     DPI를 올려도 상한에서 버려집니다 — 해상도는 분할로만 얻습니다.",
            file=sys.stderr,
        )
    elif best < 0.35:
        print(
            f"  ⓘ 조각 폭 {w}px 가 전달 상한({_MAX_EDGE}px)을 넘어 **폭이 제약**입니다."
            f" 세로 분할로는 {best:.3f} 이 한계이며 이미 도달했습니다.\n"
            f"     더 올리려면 크롭 폭을 좁혀야 합니다 (판독 실패 시 해당 영역만 별도 크롭).",
            file=sys.stderr,
        )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    pdf_path = argv[1]
    dpi = None  # crop-desc 여부에 따라 기본값 결정
    output_dir: str | None = None
    crop_desc = False
    pages: tuple[int, int] | None = None
    tile = None
    tile_overlap = _DEFAULT_TILE_OVERLAP_PT

    for arg in argv[2:]:
        if arg.startswith("--dpi="):
            dpi = int(arg.split("=", 1)[1])
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg == "--crop-desc":
            crop_desc = True
        elif arg.startswith("--pages="):
            raw = arg.split("=", 1)[1]
            parts = raw.split("-")
            if len(parts) != 2:
                print(f"오류: --pages 형식은 START-END여야 합니다. 예: --pages=1-13", file=sys.stderr)
                return 1
            pages = (int(parts[0]), int(parts[1]))
        elif arg.startswith("--tile="):
            tile = arg.split("=", 1)[1]
        elif arg.startswith("--tile-overlap="):
            tile_overlap = float(arg.split("=", 1)[1])
        else:
            print(f"오류: 알 수 없는 옵션: {arg}", file=sys.stderr)
            return 1

    base = os.path.splitext(os.path.basename(pdf_path))[0]

    try:
        if crop_desc:
            if dpi is None:
                dpi = 200
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", f"{base}_desc")
            paths = crop_description_panels(
                pdf_path, output_dir, dpi, pages=pages,
                tile=tile, tile_overlap_pt=tile_overlap,
            )
        else:
            if dpi is None:
                dpi = 150
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", base)
            paths = convert_pdf(
                pdf_path, output_dir, dpi, pages=pages,
                tile=tile, tile_overlap_pt=tile_overlap,
            )

        for p in paths:
            print(p)
        page_range = f" (p{pages[0]}~{pages[1]})" if pages else ""
        mode = "Description 크롭" if crop_desc else "전체 페이지"
        unit = f"{len(paths)}장" if tile not in (None, "1") else f"{len(paths)}페이지"
        print(f"\n총 {unit}{page_range} {mode} 변환 완료 → {output_dir}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

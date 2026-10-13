"""Делает из страницы документа «снимок с телефона»: большое фото, лист на столе, перспектива, тень, блик.

    python scripts/make_phone_photo.py data/samples/sample_02.png out.jpg --size 4000x3000
Нужен, чтобы проверять скорость и качество на реалистичных, а не «лабораторных» снимках.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make(src: Path, size: tuple[int, int], seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    page = cv2.imdecode(np.fromfile(str(src), np.uint8), cv2.IMREAD_COLOR)
    W, H = size
    desk = np.empty((H, W, 3), np.uint8)
    desk[:] = (62, 84, 112)
    grain = rng.normal(0, 9, (H, W)).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (0, 0), 6)
    desk = np.clip(desk.astype(np.float32) + grain[..., None] * 3, 0, 255).astype(np.uint8)
    ph, pw = page.shape[:2]
    scale = 0.84 * H / ph
    page_s = cv2.resize(page, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = page_s.shape[:2]
    src_pts = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    cx, cy = W / 2, H / 2
    dst = np.float32([[cx - sw / 2 + 60, cy - sh / 2 - 20], [cx + sw / 2 - 30, cy - sh / 2 + 25], [cx + sw / 2 + 25, cy + sh / 2 - 15], [cx - sw / 2 - 40, cy + sh / 2 + 20]])
    m = cv2.getPerspectiveTransform(src_pts, dst)
    warped = cv2.warpPerspective(page_s, m, (W, H), borderMode=cv2.BORDER_TRANSPARENT, dst=desk)
    mask = cv2.warpPerspective(np.full((sh, sw), 255, np.uint8), m, (W, H))
    out = desk.copy()
    out[mask > 0] = warped[mask > 0]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    shade = 1 - 0.35 * (xx / W) * (0.6 + 0.4 * yy / H)
    glare = np.exp(-(((xx - W * 0.62) / (W * 0.10)) ** 2 + ((yy - H * 0.30) / (H * 0.05)) ** 2)) * 90
    out = np.clip(out.astype(np.float32) * shade[..., None] + glare[..., None], 0, 255).astype(np.uint8)
    out = cv2.GaussianBlur(out, (0, 0), 1.1)
    noise = rng.normal(0, 4, out.shape).astype(np.int16)
    return np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--size", default="4000x3000")
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    w, h = (int(x) for x in args.size.lower().split("x"))
    img = make(Path(args.src), (w, h), args.seed)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    Path(args.out).write_bytes(buf.tobytes())
    print(f"{args.out}: {w}x{h}, {len(buf) / 1e6:.1f} МБ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

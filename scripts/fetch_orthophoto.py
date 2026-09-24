"""One-off script: download a real aerial orthophoto (DOP20, 20cm resolution)
covering the bundled DLR-UT sample's scene, from LGLN Niedersachsen's free,
no-auth Open Data WMS. Used as the map background so actual lane markings,
crosswalks etc. are visible (replacing a generic vector-street basemap).

License: Data licence Germany - attribution - version 2.0 (dl-de/by-2-0),
attribution: "Map background: Digital Orthophoto (DOP20), (c) LGLN 2026,
https://www.lgln.niedersachsen.de".

Usage: uv run python scripts/fetch_orthophoto.py
"""

from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from trajectory_explorer.data.loader import load_dataset

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "sample_data" / "dlr_ut" / "orthophoto.jpeg"

WMS_BASE = "https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms"
CRS = "EPSG:32632"  # matches the DLR-UT trajectory position CRS exactly
PADDING_M = 20.0
# Requested at full 20cm/px resolution, then downscaled before saving --
# the image is re-embedded (base64) in the pydeck spec on every app rerun,
# so a smaller JPEG keeps the animated-playback view responsive.
REQUEST_WIDTH_PX = 1200
SAVE_WIDTH_PX = 900
JPEG_QUALITY = 85


def main() -> None:
    dataset = load_dataset("dlr_ut_session_01")
    roi = np.asarray(dataset.roi)
    (min_e, min_n), (max_e, max_n) = roi[0], roi[1]

    bbox = (
        min_e - PADDING_M,
        min_n - PADDING_M,
        max_e + PADDING_M,
        max_n + PADDING_M,
    )
    width_m = bbox[2] - bbox[0]
    height_m = bbox[3] - bbox[1]
    height_px = round(REQUEST_WIDTH_PX * height_m / width_m)

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": "ni_dop20",
        "STYLES": "",
        "CRS": CRS,
        "BBOX": ",".join(str(v) for v in bbox),
        "WIDTH": REQUEST_WIDTH_PX,
        "HEIGHT": height_px,
        "FORMAT": "image/png",
    }

    print(f"Requesting {width_m:.0f}m x {height_m:.0f}m orthophoto at "
          f"{REQUEST_WIDTH_PX}x{height_px}px ...")
    response = requests.get(WMS_BASE, params=params, timeout=60)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content)).convert("RGB")
    save_height = round(SAVE_WIDTH_PX * image.height / image.width)
    image = image.resize((SAVE_WIDTH_PX, save_height), Image.LANCZOS)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT_PATH, "JPEG", quality=JPEG_QUALITY, optimize=True)
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1e3:.0f} KB, "
          f"{SAVE_WIDTH_PX}x{save_height}px)")
    print(f"Bounding box ({CRS}): {bbox}")


if __name__ == "__main__":
    main()

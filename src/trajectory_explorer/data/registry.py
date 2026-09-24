"""Registry of datasets available to the app.

TASI (`tasi.dlr.DLRTrajectoryDataset`) owns loading and schema mapping for
DLR-UT/DLR-HT recordings, so this module only tracks *which* recordings are
available and the metadata the UI/analysis layer needs but TASI does not
expose (license text, source CRS, human-readable time window).
"""

from dataclasses import dataclass
from pathlib import Path

# src/trajectory_explorer/data/registry.py -> repo root (sample_data/ lives
# at the repo root, not inside the installable package).
ROOT = Path(__file__).resolve().parents[3]

# CRS for the DLR-UT trajectory position/velocity/acceleration columns.
# Verified empirically: position.easting/northing values (e.g. ~604800,
# ~5792800) match plain UTM zone 32N for Braunschweig (10.53E, 52.28N), NOT
# the local tmerc CRS declared in the geoReference header of the bundled
# OpenDRIVE map (bs-inner-ring-road-ut.xodr) -- that header's offsets
# (x_0=-104763, y_0=-5792795) describe the *road file's own* local coordinate
# system, which is a different (offset, near-zero) frame from the trajectory
# CSVs.
DLR_UT_CRS = "EPSG:32632"


# Aerial orthophoto (DOP20, 20cm resolution) covering the sample scene,
# fetched from LGLN Niedersachsen's free, no-auth Open Data WMS (see
# scripts/fetch_orthophoto.py). Bounding box is in `DLR_UT_CRS` (the same
# projected CRS as the trajectory positions), matching the request that
# produced the bundled image exactly.
DLR_UT_ORTHOPHOTO_BBOX = (604629.71, 5792666.764, 604900.927, 5792879.091)
DLR_UT_ORTHOPHOTO_ATTRIBUTION = (
    "Map background: Digital Orthophoto (DOP20), (c) LGLN 2026, "
    "Data licence Germany - attribution - version 2.0"
)


@dataclass(frozen=True)
class DatasetInfo:
    key: str
    name: str
    description: str
    path: Path
    crs: str
    license_name: str
    license_url: str
    source_url: str
    orthophoto_path: Path | None = None
    orthophoto_bbox: tuple[float, float, float, float] | None = None
    orthophoto_attribution: str | None = None


REGISTRY: dict[str, DatasetInfo] = {
    "dlr_ut_session_01": DatasetInfo(
        key="dlr_ut_session_01",
        name="DLR-UT — Braunschweig inner ring road (09:00-09:03)",
        description=(
            "3-minute excerpt of a DLR Urban Traffic Dataset recording at the "
            "AIM research intersection in Braunschweig, Germany. 104 tracks: "
            "cars, bicycles, pedestrians, trucks and vans, at 20 Hz."
        ),
        path=ROOT / "sample_data" / "dlr_ut" / "session_01.csv",
        crs=DLR_UT_CRS,
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://zenodo.org/records/20919480",
        orthophoto_path=ROOT / "sample_data" / "dlr_ut" / "orthophoto.jpeg",
        orthophoto_bbox=DLR_UT_ORTHOPHOTO_BBOX,
        orthophoto_attribution=DLR_UT_ORTHOPHOTO_ATTRIBUTION,
    ),
}


def get_dataset(key: str) -> DatasetInfo:
    return REGISTRY[key]


def list_datasets() -> list[DatasetInfo]:
    return list(REGISTRY.values())

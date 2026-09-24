"""Coordinate conversion helpers.

DLR-UT positions are given as local projected easting/northing (meters), not
lon/lat. Map layers (pydeck) need WGS84 lon/lat; kinematics/interaction
metrics should stay in the projected meters CRS since distances/speeds are
directly meaningful there.
"""

import pandas as pd
from pyproj import Transformer


def to_lonlat(easting: pd.Series, northing: pd.Series, crs: str) -> tuple[pd.Series, pd.Series]:
    """Convert projected easting/northing (meters) to WGS84 lon/lat."""
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(easting.to_numpy(), northing.to_numpy())
    return (
        pd.Series(lon, index=easting.index, name="lon"),
        pd.Series(lat, index=easting.index, name="lat"),
    )

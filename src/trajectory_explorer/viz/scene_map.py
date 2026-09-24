"""pydeck scene/map views: animated playback scene and a static density heatmap.

Map background: a real aerial orthophoto (see `data/registry.py` /
`scripts/fetch_orthophoto.py`) rendered as a georeferenced `BitmapLayer`,
showing actual lane markings/crosswalks -- not a generic vector-street tile
basemap. Vehicles are drawn as oriented footprint polygons (real
length/width/heading from the dataset), not fixed-size dots.
"""

import math

import numpy as np
import pandas as pd
import pydeck as pdk
from pydeck.types import Image as PdkImage

from trajectory_explorer.analysis.aggregates import heatmap_points
from trajectory_explorer.data.geo import to_lonlat
from trajectory_explorer.viz.colors import CLASS_COLORS, RISK_COLORS

DEFAULT_TRACK_COLOR = (128, 128, 128)


def _filter_by_class(dataset, visible_classes: list[str] | None, class_by_id: pd.Series):
    """Return the subset of `dataset` (and aligned `class_by_id`) whose
    dominant class is in `visible_classes` (None = no filtering)."""
    if visible_classes is None:
        return dataset, class_by_id
    mask = class_by_id.isin(visible_classes)
    return dataset.loc[mask], class_by_id.loc[mask]


def _view_state_for(dataset, crs: str) -> pdk.ViewState:
    """Center on the dataset's ROI, at a zoom that frames the whole scene."""
    roi = np.asarray(dataset.roi)
    (min_e, min_n), (max_e, max_n) = roi[0], roi[1]
    center_e, center_n = (min_e + max_e) / 2, (min_n + max_n) / 2
    lon, lat = to_lonlat(pd.Series([center_e]), pd.Series([center_n]), crs)
    center_lon, center_lat = float(lon.iloc[0]), float(lat.iloc[0])

    span_m = max(max_e - min_e, max_n - min_n, 1.0)
    # Standard Web-Mercator "fit bounds" heuristic: meters-per-pixel at zoom z
    # is 156543.03392 * cos(lat) / 2**z. Solve for the z that fits `span_m`
    # into an assumed viewport width, with some padding so the scene isn't
    # touching the edges. (For this dataset's ~230m x 170m ROI and a ~800px
    # wide map panel, this lands at zoom ~18, matching the "frame a ~150m
    # urban intersection" target.)
    assumed_viewport_px = 800.0
    padding_factor = 1.3
    zoom = math.log2(156543.03392 * math.cos(math.radians(center_lat)) * assumed_viewport_px / (span_m * padding_factor))
    zoom = max(14.0, min(19.0, zoom))

    return pdk.ViewState(longitude=center_lon, latitude=center_lat, zoom=zoom, pitch=0, bearing=0)


def _with_lonlat(df: pd.DataFrame, crs: str) -> pd.DataFrame:
    lon, lat = to_lonlat(df[("position", "easting")], df[("position", "northing")], crs)
    df = df.copy()
    df["lon"] = lon.to_numpy()
    df["lat"] = lat.to_numpy()
    return df


def track_ids_at(
    dataset, timestamp: pd.Timestamp, tolerance: pd.Timedelta = pd.Timedelta(milliseconds=100)
) -> list:
    """Track ids that have a pose within `tolerance` of `timestamp`."""
    ts = dataset.index.get_level_values("timestamp")
    mask = (ts >= timestamp - tolerance) & (ts <= timestamp + tolerance)
    return dataset.index.get_level_values("id")[mask].unique().tolist()


def _orthophoto_layer(orthophoto_path, orthophoto_bbox, crs: str) -> pdk.Layer | None:
    """Georeferenced BitmapLayer for the aerial background image, or None if
    no orthophoto is configured for this dataset."""
    if orthophoto_path is None or orthophoto_bbox is None:
        return None

    min_e, min_n, max_e, max_n = orthophoto_bbox
    lon, lat = to_lonlat(
        pd.Series([min_e, max_e]), pd.Series([min_n, max_n]), crs
    )
    west, east = float(lon.iloc[0]), float(lon.iloc[1])
    south, north = float(lat.iloc[0]), float(lat.iloc[1])

    return pdk.Layer(
        "BitmapLayer",
        data=[],
        # `pdk.types.Image` base64-encodes the local file into a raw (no
        # "@@=" accessor-wrapping) JSON string -- passing a plain Python str
        # here instead would get auto-wrapped as a live accessor expression
        # by pydeck's JSON layer (same class of bug as width_units/
        # radius_units elsewhere in this module) and fail to parse on the
        # frontend (the data URI's "data:image/..." colon breaks the
        # expression parser).
        image=PdkImage(str(orthophoto_path)),
        bounds=[west, south, east, north],
    )
    # NOTE: `PdkImage` derives the data URI MIME type from the file suffix
    # verbatim (`orthophoto.jpg` -> "image/jpg"), which is not a real MIME
    # type and deck.gl's image loader rejects it ("No valid loader found").
    # The bundled asset is named "orthophoto.jpeg" specifically so this
    # produces the valid "image/jpeg" -- keep that extension if you replace
    # the file.


def _footprint_polygons(df: pd.DataFrame, crs: str) -> list[list[list[float]]]:
    """Oriented rectangle (4 corners, lon/lat) per row, from real
    position/heading/length/width -- not a fixed-size marker.

    `yaw` is the standard math heading (degrees, measured from east/easting,
    counter-clockwise positive) -- verified empirically against the
    velocity vector's atan2(northing, easting) on this dataset.
    """
    easting = df[("position", "easting")].to_numpy()
    northing = df[("position", "northing")].to_numpy()
    length = df[("dimension", "length")].to_numpy()
    width = df[("dimension", "width")].to_numpy()
    yaw_rad = np.radians(df[("yaw", "")].to_numpy())

    half_l = length / 2.0
    half_w = width / 2.0
    cos_yaw = np.cos(yaw_rad)
    sin_yaw = np.sin(yaw_rad)

    # Corners in the vehicle's local frame: x_local = forward, y_local = left.
    local_corners = np.array(
        [[1, 1], [1, -1], [-1, -1], [-1, 1]], dtype=float
    )  # (4, 2), each row (sign_forward, sign_left)

    n = len(df)
    all_e = np.empty((n, 4))
    all_n = np.empty((n, 4))
    for i, (sf, sl) in enumerate(local_corners):
        x_local = sf * half_l
        y_local = sl * half_w
        all_e[:, i] = easting + cos_yaw * x_local - sin_yaw * y_local
        all_n[:, i] = northing + sin_yaw * x_local + cos_yaw * y_local

    lon, lat = to_lonlat(
        pd.Series(all_e.ravel()), pd.Series(all_n.ravel()), crs
    )
    lon = lon.to_numpy().reshape(n, 4)
    lat = lat.to_numpy().reshape(n, 4)

    return [
        [[float(lon[i, j]), float(lat[i, j])] for j in range(4)]
        for i in range(n)
    ]


def build_scene_deck(
    dataset,
    crs: str,
    current_time: pd.Timestamp,
    class_by_id: pd.Series,
    trail_seconds: float = 5.0,
    visible_classes: list[str] | None = None,
    risk_by_track: dict[int, str] | None = None,
    orthophoto_path=None,
    orthophoto_bbox=None,
) -> pdk.Deck:
    """Animated-playback scene: aerial background + short recent trails +
    current vehicle footprints (oriented rectangles, real size/heading).

    `class_by_id` is the full dataset's per-pose dominant class (e.g. from
    `data.loader.load_classification`) -- passed in rather than recomputed
    here, since it's ~1s to compute and callers already have it cached.

    If `risk_by_track` is given (mapping track_id -> "low"/"medium"/"high",
    e.g. from `analysis.risk.current_risk_by_track`), current-position
    footprints for tracks present in it are colored by
    `viz.colors.RISK_COLORS` instead of by class -- tracks not in the
    mapping keep their class color.
    """
    ds, class_by_id = _filter_by_class(dataset, visible_classes, class_by_id)
    view_state = _view_state_for(dataset, crs)
    base_layer = _orthophoto_layer(orthophoto_path, orthophoto_bbox, crs)
    # No vector basemap when we have a real aerial photo -- it would just be
    # an unnecessary extra background underneath (and extra tile requests).
    map_kwargs = (
        {"map_provider": None}
        if base_layer is not None
        else {"map_provider": "carto", "map_style": pdk.map_styles.LIGHT}
    )

    if ds.shape[0] == 0:
        return pdk.Deck(
            layers=[l for l in [base_layer] if l is not None],
            initial_view_state=view_state,
            **map_kwargs,
        )

    timestamps = ds.index.get_level_values("timestamp")

    # --- recent trail, per track ------------------------------------------------
    trail_start = current_time - pd.Timedelta(seconds=trail_seconds)
    trail_mask = (timestamps > trail_start) & (timestamps <= current_time)
    trail_df = ds.loc[trail_mask]

    path_records = []
    if trail_df.shape[0] > 0:
        trail_df = _with_lonlat(trail_df, crs)
        trail_df["_class"] = class_by_id.loc[trail_mask].to_numpy()
        for track_id, group in trail_df.groupby(level="id", sort=False):
            group = group.sort_index(level="timestamp")
            path = group[["lon", "lat"]].to_numpy().tolist()
            if len(path) < 2:
                continue
            cls = group["_class"].iloc[-1]
            color = list(CLASS_COLORS.get(cls, DEFAULT_TRACK_COLOR))
            path_records.append({"path": path, "color": color, "track_id": int(track_id), "class": cls})

    path_layer = pdk.Layer(
        "PathLayer",
        data=pd.DataFrame(path_records) if path_records else pd.DataFrame(columns=["path", "color", "track_id", "class"]),
        get_path="path",
        get_color="color",
        get_width=0.3,
        width_min_pixels=2,
        # NOTE: do not pass width_units="meters" here -- pydeck auto-wraps
        # plain string kwargs as live "@@=<value>" accessor expressions, so a
        # literal enum string gets turned into a per-row column lookup for a
        # nonexistent "meters" column, which breaks rendering (deck.gl
        # defaults PathLayer's widthUnits to "meters" already, so omitting
        # it is equivalent and safe).
        pickable=True,
    )

    # --- current position, per track (nearest pose within 100ms) ---------------
    tol = pd.Timedelta(milliseconds=100)
    near_mask = (timestamps >= current_time - tol) & (timestamps <= current_time + tol)
    cur_df = ds.loc[near_mask]

    polygon_records = []
    if cur_df.shape[0] > 0:
        cur_ts = cur_df.index.get_level_values("timestamp")
        cur_df = cur_df.assign(_dt=np.abs((cur_ts - current_time).total_seconds()))
        cur_df["_class"] = class_by_id.loc[near_mask].to_numpy()
        cur_df = cur_df.sort_values("_dt").groupby(level="id", sort=False).first()

        track_ids = cur_df.index.get_level_values("id").to_numpy()
        classes = cur_df["_class"].to_numpy()
        polygons = _footprint_polygons(cur_df, crs)

        for track_id, cls, polygon in zip(track_ids, classes, polygons):
            risk_level = (risk_by_track or {}).get(int(track_id))
            if risk_level is not None:
                color = list(RISK_COLORS.get(risk_level, DEFAULT_TRACK_COLOR))
            else:
                color = list(CLASS_COLORS.get(cls, DEFAULT_TRACK_COLOR))
            polygon_records.append(
                {
                    "track_id": int(track_id),
                    "class": cls,
                    "color": color,
                    "polygon": polygon,
                }
            )

    polygon_layer = pdk.Layer(
        "PolygonLayer",
        data=polygon_records if polygon_records else [],
        get_polygon="polygon",
        get_fill_color="color",
        # NOTE: stroked=True + get_line_color breaks PolygonLayer rendering
        # entirely in this pydeck/deck.gl bundle (verified: the fill-only
        # layer below renders correctly; adding a stroke collapses every
        # polygon into a tiny mispositioned sliver near the viewport
        # origin instead of the intended fill). Filled-only is a minor
        # cosmetic loss (no white outline) but reliable.
        filled=True,
        stroked=False,
        pickable=True,
    )

    layers = [l for l in [base_layer, path_layer, polygon_layer] if l is not None]

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={"text": "{class}\ntrack {track_id}"},
        **map_kwargs,
    )


def build_heatmap_deck(dataset, crs: str, orthophoto_path=None, orthophoto_bbox=None) -> pdk.Deck:
    """Aggregate spatial-density view over every pose in `dataset`."""
    view_state = _view_state_for(dataset, crs)
    base_layer = _orthophoto_layer(orthophoto_path, orthophoto_bbox, crs)
    map_kwargs = (
        {"map_provider": None}
        if base_layer is not None
        else {"map_provider": "carto", "map_style": pdk.map_styles.LIGHT}
    )

    points = heatmap_points(dataset)
    lon, lat = to_lonlat(points["easting"], points["northing"], crs)
    df = pd.DataFrame({"lon": lon.to_numpy(), "lat": lat.to_numpy()})

    heat_layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["lon", "lat"],
        aggregation="MEAN",
        radius_pixels=40,
    )

    layers = [l for l in [base_layer, heat_layer] if l is not None]

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        **map_kwargs,
    )

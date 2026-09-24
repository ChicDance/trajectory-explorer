"""Plotly chart builders for object-detail and dataset-level views.

Styling follows the `dataviz` skill: thin marks, a legend for >=2 series
(never color-only identity), recessive gridlines, and a `plotly_white`-ish
neutral template so charts read fine in both Streamlit's light and dark
themes (Plotly doesn't hot-swap on the app's theme, so we avoid a
hardcoded dark or light chart background and let Streamlit's own chart
container supply it via `layout.paper_bgcolor = "rgba(0,0,0,0)"`, keeping
only the plotting area a very light neutral).
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trajectory_explorer.viz.colors import CLASS_COLORS_HEX, CLASS_ORDER

# Chrome shared across charts (kept close to the skill's documented tokens).
_GRIDLINE = "#e1e0d9"
_AXIS = "#c3c2b7"
_MUTED_TEXT = "#898781"
_TRANSPARENT = "rgba(0,0,0,0)"


def _base_layout(**overrides) -> dict:
    layout = dict(
        paper_bgcolor=_TRANSPARENT,
        plot_bgcolor=_TRANSPARENT,
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif"),
        margin=dict(l=60, r=20, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    layout.update(overrides)
    return layout


def _style_axis(**overrides) -> dict:
    axis = dict(
        showgrid=True,
        gridcolor=_GRIDLINE,
        zerolinecolor=_AXIS,
        linecolor=_AXIS,
        tickfont=dict(color=_MUTED_TEXT),
    )
    axis.update(overrides)
    return axis


def _ordered_classes_present(values) -> list[str]:
    present = set(values)
    ordered = [c for c in CLASS_ORDER if c in present]
    extra = sorted(present - set(CLASS_ORDER))
    return ordered + extra


def kinematics_chart(df: pd.DataFrame) -> go.Figure:
    """Single-object detail view: speed + acceleration (stacked subplots,
    since m/s and m/s^2 are different scales -- never a dual y-axis), with
    heading as a small third row.
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.4, 0.35, 0.25],
        subplot_titles=("Speed (m/s)", "Acceleration (m/s²)", "Heading (deg)"),
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["speed"],
            mode="lines",
            name="Speed",
            line=dict(color=CLASS_COLORS_HEX["car"], width=2),
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["acceleration"],
            mode="lines",
            name="Acceleration",
            line=dict(color=CLASS_COLORS_HEX["truck"], width=2),
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["heading"],
            mode="markers",
            name="Heading",
            marker=dict(color=CLASS_COLORS_HEX["van"], size=4),
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    fig.update_layout(**_base_layout(height=520, title=None))
    fig.update_xaxes(**_style_axis(title_text="Time"), row=3, col=1)
    fig.update_xaxes(**_style_axis(), row=1, col=1)
    fig.update_xaxes(**_style_axis(), row=2, col=1)
    fig.update_yaxes(**_style_axis(title_text="m/s"), row=1, col=1)
    fig.update_yaxes(**_style_axis(title_text="m/s²"), row=2, col=1)
    fig.update_yaxes(**_style_axis(title_text="deg", range=[0, 360]), row=3, col=1)
    return fig


def _distribution_chart(df: pd.DataFrame, value_col: str, y_title: str) -> go.Figure:
    classes = _ordered_classes_present(df["classification"])
    fig = go.Figure()
    for cls in classes:
        values = df.loc[df["classification"] == cls, value_col]
        color = CLASS_COLORS_HEX.get(cls, "#898781")
        fig.add_trace(
            go.Box(
                y=values,
                name=cls,
                marker=dict(color=color),
                line=dict(color=color, width=1.5),
                fillcolor=color,
                opacity=0.55,
                boxmean=True,
                showlegend=False,
            )
        )

    fig.update_layout(
        **_base_layout(
            height=420,
            xaxis=_style_axis(title_text="Class"),
            yaxis=_style_axis(title_text=y_title),
        )
    )
    return fig


def speed_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Speed distribution compared across object classes (box plot)."""
    return _distribution_chart(df, "speed", "Speed (m/s)")


def acceleration_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Acceleration distribution compared across object classes (box plot)."""
    return _distribution_chart(df, "acceleration", "Acceleration (m/s²)")


def traffic_flow_chart(df: pd.DataFrame) -> go.Figure:
    """Object count over time (bar chart of counts per time bin)."""
    fig = go.Figure(
        go.Bar(
            x=df.index,
            y=df["count"],
            marker=dict(color=CLASS_COLORS_HEX["car"]),
            showlegend=False,
        )
    )
    fig.update_layout(
        **_base_layout(
            height=360,
            xaxis=_style_axis(title_text="Time"),
            yaxis=_style_axis(title_text="Objects observed"),
        )
    )
    return fig

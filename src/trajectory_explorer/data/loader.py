"""Cached dataset loading for the Streamlit app."""

import pandas as pd
import streamlit as st
from tasi.dlr import DLRTrajectoryDataset

from trajectory_explorer.data.registry import get_dataset


@st.cache_data(show_spinner="Loading trajectory data...")
def load_dataset(key: str) -> DLRTrajectoryDataset:
    """Load a registered dataset by key as a TASI DLRTrajectoryDataset."""
    info = get_dataset(key)
    return DLRTrajectoryDataset.from_csv(str(info.path))


@st.cache_resource(show_spinner=False)
def load_classification(key: str) -> pd.Series:
    """Per-pose dominant class, aligned to the full dataset's pose index.

    `most_likely_class(by="trajectory", broadcast=True)` costs ~1s on the
    bundled sample and was previously called up to 4x per Streamlit rerun
    (scene filter, scene current-position color, speed/acceleration
    distributions) -- including on every ~150ms playback tick. Caching it
    once per dataset turns that into a single computation for the process
    lifetime; callers slice this (e.g. `.loc[subset.index]`) instead of
    recomputing for a filtered subset.
    """
    dataset = load_dataset(key)
    return dataset.most_likely_class(by="trajectory", broadcast=True)

import pandas as pd
import streamlit as st
import config


@st.cache_data
def load_kpi_data() -> pd.DataFrame:
    df = pd.read_csv(config.KPI_DATA_PATH, dtype={"rep_id": str})
    for col in config.KPI_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


@st.cache_data
def load_comments_data() -> pd.DataFrame:
    df = pd.read_csv(
        config.COMMENTS_DATA_PATH,
        dtype={"rep_id": str, "customer_id": str},
    )
    df["activity_date"] = pd.to_datetime(df["activity_date"], errors="coerce")
    return df

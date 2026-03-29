import pandas as pd
import config


def get_rep_list(kpi_df: pd.DataFrame) -> list[tuple[str, str]]:
    """Returns [(rep_id, rep_name), ...] sorted by rep_id."""
    pairs = (
        kpi_df[["rep_id", "rep_name"]]
        .drop_duplicates()
        .sort_values("rep_id")
    )
    return list(zip(pairs["rep_id"], pairs["rep_name"]))


def get_available_months(kpi_df: pd.DataFrame, rep_id: str) -> list[str]:
    """Returns sorted list of year_month strings for the selected rep."""
    months = (
        kpi_df[kpi_df["rep_id"] == rep_id]["year_month"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return months


def calculate_kpi_summary(
    kpi_df: pd.DataFrame, rep_id: str, year_month: str
) -> pd.DataFrame:
    """Returns DataFrame with current month actuals and month-over-month delta."""
    rep_df = kpi_df[kpi_df["rep_id"] == rep_id].sort_values("year_month").reset_index(drop=True)

    months = rep_df["year_month"].tolist()
    if year_month not in months:
        return pd.DataFrame(columns=["kpi_name", "actual", "delta"])

    idx = months.index(year_month)
    current = rep_df[rep_df["year_month"] == year_month][config.KPI_COLUMNS].iloc[0]

    if idx > 0:
        prev_month = months[idx - 1]
        previous = rep_df[rep_df["year_month"] == prev_month][config.KPI_COLUMNS].iloc[0]
        delta = current - previous
    else:
        delta = pd.Series({col: None for col in config.KPI_COLUMNS})

    rows = []
    for col in config.KPI_COLUMNS:
        rows.append({
            "kpi_name": col,
            "actual": int(current[col]),
            "delta": int(delta[col]) if delta[col] is not None else None,
        })
    return pd.DataFrame(rows)


def format_kpi_for_prompt(kpi_summary: pd.DataFrame) -> str:
    """Formats KPI summary as text for the LLM prompt."""
    lines = []
    for _, row in kpi_summary.iterrows():
        if row["delta"] is not None:
            sign = "+" if row["delta"] >= 0 else ""
            delta_str = f"（前月比 {sign}{row['delta']}件）"
        else:
            delta_str = "（前月データなし）"
        lines.append(f"- {row['kpi_name']}: 今月 {row['actual']}件{delta_str}")
    return "\n".join(lines)


def get_rep_comments(comments_df: pd.DataFrame, rep_id: str) -> pd.DataFrame:
    """Filters comments by rep_id and sorts by priority then activity_date descending."""
    df = comments_df[comments_df["rep_id"] == rep_id].copy()
    df["_priority_order"] = df["priority"].map(config.PRIORITY_ORDER).fillna(99)
    df = df.sort_values(["_priority_order", "activity_date"], ascending=[True, False])
    df = df.drop(columns=["_priority_order"])
    return df.reset_index(drop=True)


def format_comments_for_prompt(comments_df: pd.DataFrame) -> str:
    """Formats comments grouped by priority for the LLM prompt."""
    if comments_df.empty:
        return "（コメントなし）"

    groups = []
    for priority in ["高", "中", "低"]:
        subset = comments_df[comments_df["priority"] == priority]
        if subset.empty:
            continue
        lines = [f"[{priority}優先度]"]
        for _, row in subset.iterrows():
            date_str = (
                row["activity_date"].strftime("%Y-%m-%d")
                if pd.notna(row["activity_date"])
                else "日付不明"
            )
            lines.append(
                f"- {date_str} {row['customer_name']} ({row['author']}): {row['comment']}"
            )
        groups.append("\n".join(lines))
    return "\n\n".join(groups)

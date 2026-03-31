import pandas as pd
import config


def get_office_list(kpi_df: pd.DataFrame) -> list[str]:
    """Returns sorted list of unique office names."""
    return sorted(kpi_df["office"].dropna().unique().tolist())


def get_rep_list(kpi_df: pd.DataFrame, office: str | None = None) -> list[tuple[str, str]]:
    """Returns [(rep_id, rep_name), ...] sorted by rep_id, optionally filtered by office."""
    df = kpi_df[["rep_id", "rep_name", "office"]].drop_duplicates()
    if office:
        df = df[df["office"] == office]
    df = df.sort_values("rep_id")
    return list(zip(df["rep_id"], df["rep_name"]))


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


# ── チーム分析用関数 ────────────────────────────────────────────────────────

def add_composite_kpis(
    df: pd.DataFrame,
    composite_kpis: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """composite_kpis の定義に従って複合KPI列をDataFrameに追加して返す。
    composite_kpis=None の場合は何も追加せず元のDataFrameのコピーを返す。
    """
    df = df.copy()
    for name, sources in (composite_kpis or {}).items():
        df[name] = df[sources].sum(axis=1)
    return df


def calculate_group_kpi_average(
    kpi_df: pd.DataFrame,
    year_month: str,
    office: str | None = None,
    kpi_cols: list[str] | None = None,
    composite_kpis: dict[str, list[str]] | None = None,
) -> pd.Series:
    """指定月・グループの KPI（複合KPI含む）の平均を返す。
    office=None で全体平均、kpi_cols=None で config.KPI_COLUMNS を使用。
    """
    df = add_composite_kpis(kpi_df, composite_kpis)
    month_df = df[df["year_month"] == year_month]
    if office:
        month_df = month_df[month_df["office"] == office]
    cols = kpi_cols or config.KPI_COLUMNS
    return month_df[cols].mean()


def find_underperformers(
    kpi_df: pd.DataFrame,
    year_month: str,
    top_n: int = 5,
    baseline_office: str | None = None,
    target_office: str | None = None,
    kpi_cols: list[str] | None = None,
    composite_kpis: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """
    baseline_office の平均を基準に、target_office の担当者の偏差スコアを算出。
    baseline_office=None → 全体平均、target_office=None → 全担当者が対象。
    kpi_cols=None → config.KPI_COLUMNS を使用。
    偏差スコア昇順（最も乖離が大きい順）に top_n 件を返す。
    """
    df = add_composite_kpis(kpi_df, composite_kpis)
    month_df = df[df["year_month"] == year_month].copy()
    if month_df.empty:
        return pd.DataFrame()

    cols = kpi_cols or config.KPI_COLUMNS

    # 基準グループの平均
    base_df = month_df if baseline_office is None else month_df[month_df["office"] == baseline_office]
    if base_df.empty:
        return pd.DataFrame()
    group_avg = base_df[cols].mean()

    # 比較対象の候補
    candidates = month_df if target_office is None else month_df[month_df["office"] == target_office].copy()
    if candidates.empty:
        return pd.DataFrame()

    for col in cols:
        candidates[f"{col}_avg"] = round(group_avg[col], 1)
        denom = group_avg[col] if group_avg[col] > 0 else 1
        candidates[f"{col}_deviation_pct"] = (candidates[col] - group_avg[col]) / denom * 100

    deviation_cols = [f"{col}_deviation_pct" for col in cols]
    candidates["deviation_score"] = candidates[deviation_cols].sum(axis=1).round(1)

    return (
        candidates
        .sort_values("deviation_score")
        .head(top_n)
        .reset_index(drop=True)
    )


def get_recent_comments(
    comments_df: pd.DataFrame, rep_id: str, n: int = 5
) -> pd.DataFrame:
    """Returns the n most recent comments for a rep, sorted by activity_date descending."""
    df = comments_df[comments_df["rep_id"] == rep_id].copy()
    return df.sort_values("activity_date", ascending=False).head(n).reset_index(drop=True)


def format_team_comparison_for_prompt(
    rep_row: pd.Series,
    avg: pd.Series,
    kpi_cols: list[str] | None = None,
) -> str:
    """Formats rep KPI vs group average as text for the LLM prompt."""
    cols = kpi_cols or config.KPI_COLUMNS
    lines = []
    for col in cols:
        val = rep_row[col]
        actual = int(val) if col in config.KPI_COLUMNS else round(float(val), 1)
        group_avg = avg[col]
        diff = actual - group_avg
        pct = diff / group_avg * 100 if group_avg > 0 else 0
        sign = "+" if diff >= 0 else ""
        lines.append(
            f"- {col}: {actual}件"
            f"（基準平均 {group_avg:.1f}件、差分 {sign}{diff:.1f}件 / {sign}{pct:.1f}%）"
        )
    return "\n".join(lines)


# ── 既存関数（以下変更なし） ────────────────────────────────────────────────

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

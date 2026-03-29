import json
import pandas as pd
import streamlit as st
import data_loader
import data_processor
import agent
import semantic_loader
import config

st.set_page_config(page_title="営業サポートエージェント", layout="wide")


def get_api_key() -> str | None:
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return st.session_state.get("api_key") or None


# ── サイドバー ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("営業サポートエージェント")
    st.caption("営業担当者の活動データを分析し、AIがアドバイスを提供します。")
    st.divider()

    kpi_df = data_loader.load_kpi_data()
    comments_df = data_loader.load_comments_data()

    rep_list = data_processor.get_rep_list(kpi_df)
    rep_names = [name for _, name in rep_list]
    rep_ids = [rid for rid, _ in rep_list]

    selected_name = st.selectbox("担当者を選択", rep_names)
    selected_rep_id = rep_ids[rep_names.index(selected_name)]

    available_months = data_processor.get_available_months(kpi_df, selected_rep_id)
    selected_month = st.selectbox(
        "分析対象月",
        available_months,
        index=len(available_months) - 1,
    )

    st.divider()

    with st.expander("APIキー設定"):
        entered_key = st.text_input(
            "OpenAI APIキー",
            type="password",
            placeholder="sk-...",
            value=st.session_state.get("api_key", ""),
        )
        if entered_key:
            st.session_state["api_key"] = entered_key

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")


# ── 担当者・月が切り替わったらチャット履歴とアドバイスをリセット ────────────
context_key = f"{selected_rep_id}_{selected_month}"
if st.session_state.get("_context_key") != context_key:
    st.session_state["_context_key"] = context_key
    st.session_state["chat_messages"] = []
    st.session_state["advice_result"] = None


# ── セマンティックレイヤー読み込み ──────────────────────────────────────────
semantic = semantic_loader.load()
semantic_context = semantic_loader.format_for_prompt(semantic)


# ── 共通データ ──────────────────────────────────────────────────────────────
kpi_summary = data_processor.calculate_kpi_summary(kpi_df, selected_rep_id, selected_month)
rep_comments = data_processor.get_rep_comments(comments_df, selected_rep_id)
kpi_text = data_processor.format_kpi_for_prompt(kpi_summary)
comments_text = data_processor.format_comments_for_prompt(rep_comments)


# ── メインエリア ────────────────────────────────────────────────────────────
st.header(f"{selected_name} — {selected_month} 活動分析")

# KPIサマリー
st.subheader("KPIサマリー")
if kpi_summary.empty:
    st.info("選択された月のKPIデータがありません。")
else:
    cols = st.columns(len(kpi_summary))
    for col, (_, row) in zip(cols, kpi_summary.iterrows()):
        delta_val = int(row["delta"]) if row["delta"] is not None else None
        delta_str = f"{delta_val:+d}件" if delta_val is not None else None

        # セマンティックレイヤーのベンチマークを使ってヘルプテキストを生成
        kpi_info = semantic.get("kpis", {}).get(row["kpi_name"], {})
        benchmarks = kpi_info.get("benchmarks", {})
        help_text = None
        if benchmarks:
            parts = []
            if w := benchmarks.get("warning"):
                parts.append(f"要改善: {w.get('below')}件未満")
            if g := benchmarks.get("good"):
                parts.append(f"良好: {g.get('at_least')}件以上")
            if parts:
                help_text = " / ".join(parts)

        col.metric(
            label=row["kpi_name"],
            value=f"{row['actual']}件",
            delta=delta_str,
            help=help_text,
        )

# 上長コメント
with st.expander("上長コメント・指示事項", expanded=True):
    if rep_comments.empty:
        st.info("コメントデータがありません。")
    else:
        display_df = rep_comments[
            ["activity_date", "customer_name", "priority", "category", "author", "comment"]
        ].copy()
        display_df["activity_date"] = display_df["activity_date"].dt.strftime("%Y-%m-%d")
        display_df.columns = ["活動日", "顧客名", "優先度", "カテゴリ", "上長", "指示内容"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ── タブ：AIアドバイス / フリーチャット / セマンティックレイヤー設定 ──────────
tab_advice, tab_chat, tab_semantic, tab_team = st.tabs(
    ["AIアドバイス", "フリーチャット", "セマンティックレイヤー設定", "チーム指導分析"]
)

# ── AIアドバイスタブ ─────────────────────────────────────────────────────────
with tab_advice:
    generate_clicked = st.button(
        "AIアドバイスを生成",
        type="primary",
        disabled=not api_key,
        key="btn_generate",
    )

    if generate_clicked:
        st.session_state["advice_result"] = None
        with st.spinner("AIがアドバイスを生成中..."):
            try:
                result = st.write_stream(
                    agent.stream_advice(
                        api_key=api_key,
                        rep_name=selected_name,
                        year_month=selected_month,
                        kpi_text=kpi_text,
                        comments_text=comments_text,
                        semantic_context=semantic_context,
                    )
                )
                st.session_state["advice_result"] = result
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
    elif st.session_state.get("advice_result"):
        st.write(st.session_state["advice_result"])
    else:
        st.caption("「AIアドバイスを生成」ボタンを押すとアドバイスが表示されます。")

# ── フリーチャットタブ ───────────────────────────────────────────────────────
with tab_chat:
    st.caption(
        f"{selected_name}さんの営業活動について自由に質問できます。"
        f"KPIデータ・上長コメント・セマンティックレイヤーをコンテキストとして参照します。"
    )

    chat_system_prompt = agent.build_chat_system_prompt(
        rep_name=selected_name,
        year_month=selected_month,
        kpi_text=kpi_text,
        comments_text=comments_text,
        semantic_context=semantic_context,
    )

    for msg in st.session_state.get("chat_messages", []):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input(
        "質問を入力してください（例: 新規顧客獲得のためにどんなアプローチが有効ですか？）",
        disabled=not api_key,
    )

    if user_input:
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            try:
                messages_for_api = [
                    {"role": "system", "content": chat_system_prompt}
                ] + st.session_state["chat_messages"]

                response = st.write_stream(
                    agent.stream_chat(api_key=api_key, messages=messages_for_api)
                )
                st.session_state["chat_messages"].append(
                    {"role": "assistant", "content": response}
                )
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    if not api_key:
        st.info("APIキーをサイドバーで設定すると会話できます。")

# ── セマンティックレイヤー設定タブ ───────────────────────────────────────────
with tab_semantic:
    st.caption(
        "KPIの定義・ベンチマーク・コーチング観点などをJSON形式で管理します。"
        "ここで設定した内容はAIアドバイスとチャットの両方に反映されます。"
    )

    # ── JSONエディタ ────────────────────────────────────────────────────────
    try:
        with open(semantic_loader.SEMANTIC_LAYER_PATH, "r", encoding="utf-8") as f:
            current_json_str = f.read()
    except FileNotFoundError:
        current_json_str = "{}"

    edited_json_str = st.text_area(
        "セマンティックレイヤー（JSON）",
        value=current_json_str,
        height=500,
        help="KPI定義・ベンチマーク・カテゴリ定義などを編集できます。保存するとAIへの送信内容に即時反映されます。",
    )

    if st.button("保存", type="primary", key="btn_save_semantic"):
        try:
            parsed = json.loads(edited_json_str)
            semantic_loader.save(parsed)
            st.success("保存しました。次回のAI生成から反映されます。")
            st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"JSON形式エラー: {e}")

    st.divider()

    # ── AIへの送信内容プレビュー ────────────────────────────────────────────
    with st.expander("AIへの送信内容プレビュー", expanded=False):
        st.caption("現在のセマンティックレイヤーをAIに渡す際のテキスト形式です。")
        if semantic_context:
            st.code(semantic_context, language=None)
        else:
            st.info("セマンティックレイヤーが未設定です。")

# ── チーム指導分析タブ ────────────────────────────────────────────────────────
with tab_team:
    st.caption(
        "チーム全体のKPI平均と比較し、活動量が大きく乖離している担当者を抽出して指導コメントを生成します。"
    )

    # 全月リスト（担当者フィルタなし）
    all_months = sorted(kpi_df["year_month"].unique().tolist())
    team_month = st.selectbox(
        "分析対象月",
        all_months,
        index=len(all_months) - 1,
        key="team_month_select",
    )

    # 月が変わったらキャッシュをクリア
    if st.session_state.get("_team_month") != team_month:
        st.session_state["_team_month"] = team_month
        st.session_state["team_results"] = None

    # ── チームKPI一覧テーブル（常時表示） ────────────────────────────────
    st.subheader("チームKPI一覧")
    team_avg = data_processor.calculate_team_kpi_average(kpi_df, team_month)
    underperformers_df = data_processor.find_underperformers(kpi_df, team_month, top_n=5)

    all_month_df = kpi_df[kpi_df["year_month"] == team_month].copy()
    if all_month_df.empty:
        st.info("選択された月のデータがありません。")
    else:
        # 偏差スコアを計算して一覧に追加
        for col in config.KPI_COLUMNS:
            denom = team_avg[col] if team_avg[col] > 0 else 1
            all_month_df[f"{col}_dev"] = (all_month_df[col] - team_avg[col]) / denom * 100
        dev_cols = [f"{col}_dev" for col in config.KPI_COLUMNS]
        all_month_df["偏差スコア"] = all_month_df[dev_cols].sum(axis=1).round(1)
        all_month_df = all_month_df.sort_values("偏差スコア").reset_index(drop=True)

        display_team = all_month_df[["rep_name"] + config.KPI_COLUMNS + ["偏差スコア"]].copy()
        display_team.columns = ["担当者名"] + config.KPI_COLUMNS + ["偏差スコア"]

        # 偏差スコアが低い上位5名のインデックスを取得してハイライト
        low_idx = set(range(min(5, len(display_team))))

        def highlight_low(row):
            if row.name in low_idx:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            display_team.style.apply(highlight_low, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # チーム平均行
        avg_row = {col: f"{team_avg[col]:.1f}" for col in config.KPI_COLUMNS}
        avg_row["担当者名"] = "【チーム平均】"
        avg_row["偏差スコア"] = "0.0"
        st.caption(
            "チーム平均 — "
            + " / ".join(f"{col}: {team_avg[col]:.1f}件" for col in config.KPI_COLUMNS)
        )

    st.divider()

    # ── チーム指導分析 実行ボタン ────────────────────────────────────────
    run_team = st.button(
        "チーム指導分析を実行",
        type="primary",
        disabled=not api_key or underperformers_df.empty,
        key="btn_run_team",
    )

    if not api_key:
        st.info("APIキーをサイドバーで設定すると実行できます。")

    # ── 結果生成（ストリーミング） ────────────────────────────────────────
    if run_team:
        st.session_state["team_results"] = {"month": team_month, "items": []}
        st.subheader("チーム平均を大きく下回る担当者（上位5名）")

        for rank, (_, rep_row) in enumerate(underperformers_df.iterrows(), start=1):
            rep_id = rep_row["rep_id"]
            rep_name = rep_row["rep_name"]
            deviation_score = rep_row["deviation_score"]

            kpi_comparison_text = data_processor.format_team_comparison_for_prompt(
                rep_row, team_avg
            )
            recent_comments = data_processor.get_recent_comments(comments_df, rep_id, n=5)
            comments_text_team = data_processor.format_comments_for_prompt(recent_comments)

            # KPIメトリクス用データ
            kpi_metrics = [
                (col, int(rep_row[col]), float(rep_row[f"{col}_avg"]))
                for col in config.KPI_COLUMNS
            ]
            # 直近コメント表示用データ
            recent_rows = []
            for _, cr in recent_comments.iterrows():
                recent_rows.append([
                    cr["activity_date"].strftime("%Y-%m-%d") if pd.notna(cr["activity_date"]) else "",
                    cr["customer_name"],
                    cr["priority"],
                    cr["category"],
                    cr["author"],
                    cr["comment"],
                ])

            with st.container(border=True):
                st.markdown(f"### {rank}. {rep_name}　`偏差スコア: {deviation_score:+.1f}`")
                m_cols = st.columns(len(config.KPI_COLUMNS))
                for m_col, (kpi_name, actual, avg_val) in zip(m_cols, kpi_metrics):
                    diff = actual - avg_val
                    m_col.metric(
                        label=kpi_name,
                        value=f"{actual}件",
                        delta=f"{diff:+.1f}件（平均比）",
                        delta_color="normal",
                    )

                with st.expander("直近コメント"):
                    if recent_rows:
                        rc_df = pd.DataFrame(
                            recent_rows,
                            columns=["活動日", "顧客名", "優先度", "カテゴリ", "上長", "指示内容"],
                        )
                        st.dataframe(rc_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("コメントなし")

                st.markdown("**指導コメント**")
                with st.spinner(f"{rep_name}さんの指導コメントを生成中..."):
                    try:
                        coaching = st.write_stream(
                            agent.stream_team_coaching(
                                api_key=api_key,
                                rep_name=rep_name,
                                year_month=team_month,
                                kpi_comparison_text=kpi_comparison_text,
                                comments_text=comments_text_team,
                                semantic_context=semantic_context,
                            )
                        )
                    except Exception as e:
                        coaching = f"（生成エラー: {e}）"
                        st.error(coaching)

            st.session_state["team_results"]["items"].append({
                "rep_name": rep_name,
                "deviation_score": deviation_score,
                "kpi_metrics": kpi_metrics,
                "recent_rows": recent_rows,
                "coaching": coaching,
            })

    # ── キャッシュ結果の復元表示 ─────────────────────────────────────────
    elif (
        st.session_state.get("team_results")
        and st.session_state["team_results"].get("month") == team_month
        and st.session_state["team_results"].get("items")
    ):
        st.subheader("チーム平均を大きく下回る担当者（上位5名）")
        for rank, item in enumerate(st.session_state["team_results"]["items"], start=1):
            with st.container(border=True):
                st.markdown(
                    f"### {rank}. {item['rep_name']}　"
                    f"`偏差スコア: {item['deviation_score']:+.1f}`"
                )
                m_cols = st.columns(len(config.KPI_COLUMNS))
                for m_col, (kpi_name, actual, avg_val) in zip(m_cols, item["kpi_metrics"]):
                    diff = actual - avg_val
                    m_col.metric(
                        label=kpi_name,
                        value=f"{actual}件",
                        delta=f"{diff:+.1f}件（平均比）",
                        delta_color="normal",
                    )

                with st.expander("直近コメント"):
                    if item["recent_rows"]:
                        rc_df = pd.DataFrame(
                            item["recent_rows"],
                            columns=["活動日", "顧客名", "優先度", "カテゴリ", "上長", "指示内容"],
                        )
                        st.dataframe(rc_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("コメントなし")

                st.markdown("**指導コメント**")
                st.write(item["coaching"])

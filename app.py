import json
import streamlit as st
import data_loader
import data_processor
import agent
import semantic_loader

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
tab_advice, tab_chat, tab_semantic = st.tabs(
    ["AIアドバイス", "フリーチャット", "セマンティックレイヤー設定"]
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

import streamlit as st
import data_loader
import data_processor
import agent
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

    # APIキー設定 — session_stateに保存してから get_api_key() で参照する
    with st.expander("APIキー設定"):
        entered_key = st.text_input(
            "OpenAI APIキー",
            type="password",
            placeholder="sk-...",
            value=st.session_state.get("api_key", ""),
        )
        if entered_key:
            st.session_state["api_key"] = entered_key

    # ウィジェット処理後に取得するため rerun 不要
    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")


# ── 担当者・月が切り替わったらチャット履歴とアドバイスをリセット ────────────
context_key = f"{selected_rep_id}_{selected_month}"
if st.session_state.get("_context_key") != context_key:
    st.session_state["_context_key"] = context_key
    st.session_state["chat_messages"] = []
    st.session_state["advice_result"] = None


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
        col.metric(
            label=row["kpi_name"],
            value=f"{row['actual']}件",
            delta=delta_str,
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

# ── タブ：AIアドバイス / フリーチャット ─────────────────────────────────────
tab_advice, tab_chat = st.tabs(["AIアドバイス", "フリーチャット"])

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
        f"KPIデータと上長コメントをコンテキストとして参照します。"
    )

    chat_system_prompt = agent.build_chat_system_prompt(
        rep_name=selected_name,
        year_month=selected_month,
        kpi_text=kpi_text,
        comments_text=comments_text,
    )

    # 会話履歴を表示
    for msg in st.session_state.get("chat_messages", []):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ユーザー入力
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

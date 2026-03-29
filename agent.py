from typing import Generator
import openai
import config


def build_user_prompt(
    rep_name: str,
    year_month: str,
    kpi_text: str,
    comments_text: str,
) -> str:
    return (
        f"【担当者】{rep_name}\n"
        f"【分析対象月】{year_month}\n\n"
        f"【KPI実績サマリー】\n{kpi_text}\n\n"
        f"【上長からの指示・コメント】\n{comments_text}\n\n"
        f"上記の情報を踏まえ、{rep_name}さんへの営業活動アドバイスを生成してください。"
    )


def build_chat_system_prompt(
    rep_name: str,
    year_month: str,
    kpi_text: str,
    comments_text: str,
) -> str:
    return (
        f"{config.SYSTEM_PROMPT}\n\n"
        f"以下は現在選択されている担当者の情報です。この情報をもとに自由に会話してください。\n\n"
        f"【担当者】{rep_name}\n"
        f"【分析対象月】{year_month}\n\n"
        f"【KPI実績サマリー】\n{kpi_text}\n\n"
        f"【上長からの指示・コメント】\n{comments_text}"
    )


def stream_advice(
    api_key: str,
    rep_name: str,
    year_month: str,
    kpi_text: str,
    comments_text: str,
) -> Generator[str, None, None]:
    client = openai.OpenAI(api_key=api_key)
    user_prompt = build_user_prompt(rep_name, year_month, kpi_text, comments_text)

    stream = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMPERATURE,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta is not None:
            yield delta


def stream_chat(
    api_key: str,
    messages: list[dict],
) -> Generator[str, None, None]:
    client = openai.OpenAI(api_key=api_key)

    stream = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=messages,
        max_tokens=800,
        temperature=config.TEMPERATURE,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta is not None:
            yield delta

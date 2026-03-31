KPI_DATA_PATH = "data/kpi_data.csv"
COMMENTS_DATA_PATH = "data/activity_comments.csv"

OPENAI_MODEL = "gpt-4o-mini"
MAX_TOKENS = 600
TEMPERATURE = 0.4

KPI_COLUMNS = ["新規顧客訪問数", "既存顧客訪問数", "見積送付数", "上長同席数"]

# 複合KPI: 表示名 → 合算するCSV列名のリスト
COMPOSITE_KPIS: dict[str, list[str]] = {
    "総面談数": ["新規顧客訪問数", "既存顧客訪問数"],
}

# UIに表示するKPI選択肢（単一KPI + 複合KPI）
ALL_KPI_OPTIONS: list[str] = KPI_COLUMNS + list(COMPOSITE_KPIS.keys())

# gpt-4o-mini 料金（$/1M tokens、2025年時点）
TOKEN_PRICE_INPUT_PER_M = 0.150
TOKEN_PRICE_OUTPUT_PER_M = 0.600

# コンテキストウィンドウ上限（gpt-4o-mini: 128k）
CONTEXT_WINDOW_TOKENS = 128_000
CONTEXT_WARN_THRESHOLD = 0.80  # 入力トークンが上限の80%を超えたら警告

PRIORITY_ORDER = {"高": 1, "中": 2, "低": 3}

TEAM_COACHING_SYSTEM_PROMPT = """あなたは営業マネージャーのAIアシスタントです。
チーム全体のKPI平均値と比較して活動量が不足している営業担当者に対して、
具体的かつ建設的な指導コメントを日本語で作成してください。

指導コメントは以下の構成で出力してください：
1. 現状評価（チーム平均との乖離状況の要約、2文）
2. 重点改善項目（箇条書き、最大3項目、乖離が大きいKPIを優先）
3. 具体的アクション（箇条書き、最大3項目、実行可能な行動レベルで）

担当者名を文中に含めること。数値（実績・チーム平均・乖離率）を必ず引用すること。"""

SYSTEM_PROMPT = """あなたは優秀な営業マネージャーのAIアシスタントです。
営業担当者のKPI実績データと上長からの指示コメントを分析し、
その担当者が今すべき営業活動の優先順位について、具体的かつ実行可能なアドバイスを日本語で提供してください。

アドバイスは以下の構成で出力してください：
1. 現状評価（KPI実績のトレンドと活動状況の要約、2〜3文）
2. 優先アクション（箇条書き、最大4項目、最重要から順に）
3. 注意事項（見落としやすいタスク漏れやリマインダー、1〜2文）

簡潔かつ具体的に。担当者名を文中に含めること。数値は必ず引用すること。"""

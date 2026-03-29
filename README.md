# 営業サポートエージェント

営業員の育成を目的とした AI アドバイスアプリです。
営業員の KPI 実績データと上長からの指示コメントを分析し、OpenAI API を用いて今すべき営業活動を具体的に示唆します。

---

## デモ

<video src="action_sample.mp4" controls width="100%"></video>

---

## 機能

### 1. 個別 AI アドバイス

担当者・対象月を選択してボタンを押すと、KPI 実績と上長コメントを分析した上で

1. **現状評価** — KPI トレンドの要約
2. **優先アクション** — 今すぐ実行すべき活動（最大 4 項目）
3. **注意事項** — タスク漏れ・リマインダー

の 3 構成でアドバイスをストリーミング表示します。

---

### 2. フリーチャット

選択した担当者の KPI データ・上長コメントをコンテキストに持たせたチャット UI です。
アドバイス生成後に「なぜこの活動が必要か？」「具体的なトークスクリプトは？」といった深掘り質問が自由にできます。

- 担当者・月を切り替えると会話履歴は自動リセット
- セマンティックレイヤーで定義したビジネス定義も参照

---

### 3. セマンティックレイヤー設定

AI が参照する **KPI の意味・ベンチマーク・コーチング観点** を JSON 形式で管理します。
ここを編集するだけで AI の判断基準を変更でき、再デプロイ不要です。

| 設定項目 | 内容 |
|---|---|
| `business_context` | 自社営業プロセスの概要説明 |
| `kpis[].description` | KPI の定義・意味 |
| `kpis[].business_impact` | ビジネスへの影響説明 |
| `kpis[].benchmarks` | 要改善・良好の数値基準 |
| `kpis[].trend_analysis` | 前月比の解釈ルール |
| `kpis[].coaching_focus` | アドバイス生成時の着眼点 |
| `comment_categories[].urgency_note` | コメントカテゴリの緊急度説明 |

タブ内の「AI への送信内容プレビュー」で、実際に AI へ渡されるテキストを確認できます。

---

### 4. チーム指導分析

チーム全体の KPI 平均と各担当者を比較し、活動量が大きく乖離している担当者を自動抽出して一括で指導コメントを生成します。

**処理フロー**

```
① チーム全体の KPI 平均を算出（対象月）
        ↓
② 偏差スコア = 全 KPI の（実績 − 平均）/ 平均 × 100 の合計
        ↓
③ 偏差スコアが低い順に上位 5 名を抽出
        ↓
④ 各担当者の KPI vs 平均 ＋ 直近指示コメントを AI に送信
        ↓
⑤ 担当者カードとして指導コメントを順次ストリーミング表示
```

- **チーム KPI 一覧テーブル** — 月選択と同時に全担当者の実績と偏差スコアを表示。乖離上位 5 名を赤背景でハイライト
- **分析対象月はサイドバーと連動** — 個別分析と同じ月を参照
- 生成済み結果は `session_state` にキャッシュされ、タブを移動しても再生成不要

---

## データ構成

### `data/kpi_data.csv` — KPI 実績データ

| 列名 | 型 | 説明 |
|---|---|---|
| `rep_id` | str | 担当者 ID（例: S001） |
| `rep_name` | str | 担当者名 |
| `year_month` | str (YYYY-MM) | 対象月 |
| `新規顧客訪問数` | int | 月間実績値 |
| `既存顧客訪問数` | int | 月間実績値 |
| `見積送付数` | int | 月間実績値 |
| `上長同席数` | int | 月間実績値 |

主キー: `rep_id × year_month`

### `data/activity_comments.csv` — 上長コメントデータ

| 列名 | 型 | 説明 |
|---|---|---|
| `rep_id` | str | 担当者 ID |
| `rep_name` | str | 担当者名 |
| `customer_id` | str | 顧客 ID |
| `customer_name` | str | 顧客名 |
| `activity_date` | str (YYYY-MM-DD) | 活動日 |
| `author` | str | 上長名 |
| `priority` | str | 高 / 中 / 低 |
| `category` | str | 新規開拓 / 既存フォロー / 見積対応 / 同行依頼 / その他 |
| `comment` | str | 上長からの指示内容 |

主キー: `rep_id × customer_id × activity_date`

---

## ファイル構成

```
sales_support_agent/
├── app.py                  # Streamlit メインアプリ
├── config.py               # 定数・システムプロンプト
├── data_loader.py          # CSV 読み込み（@st.cache_data）
├── data_processor.py       # KPI 計算・プロンプトテキスト生成・チーム分析
├── agent.py                # OpenAI ストリーミング呼び出し
├── semantic_loader.py      # セマンティックレイヤー 読み書き・整形
├── semantic_layer.json     # KPI 定義・ベンチマーク設定ファイル
├── pyproject.toml          # uv 依存管理
├── data/
│   ├── kpi_data.csv        # KPI 実績サンプルデータ
│   └── activity_comments.csv  # 上長コメントサンプルデータ
└── .streamlit/
    └── secrets.toml        # OpenAI API キー（要設定 / git 管理外）
```

---

## セットアップ

### 必要環境

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- OpenAI API キー

### インストール・起動

```bash
# リポジトリをクローン
git clone https://github.com/Tatsuya50/sales_support_agent_cc.git
cd sales_support_agent_cc

# 依存パッケージをインストール
uv sync

# アプリを起動
uv run streamlit run app.py
```

### API キーの設定

**方法 A — UI から入力（ローカル開発向け）**

アプリ起動後、サイドバーの「APIキー設定」に OpenAI API キーを入力します。

**方法 B — secrets.toml（本番・共有環境向け）**

`.streamlit/secrets.toml` を作成し、以下を記載します（このファイルは `.gitignore` 済みです）。

```toml
OPENAI_API_KEY = "sk-..."
```

---

## 使用ライブラリ

| ライブラリ | 用途 |
|---|---|
| [streamlit](https://streamlit.io/) | Web UI フレームワーク |
| [pandas](https://pandas.pydata.org/) | データ処理・集計 |
| [openai](https://github.com/openai/openai-python) | OpenAI API クライアント |

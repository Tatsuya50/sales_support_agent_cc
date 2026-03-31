import json

SEMANTIC_LAYER_PATH = "semantic_layer.json"


def load() -> dict:
    """Load semantic layer from JSON. Returns empty dict if file not found."""
    try:
        with open(SEMANTIC_LAYER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(data: dict) -> None:
    """Persist semantic layer to JSON."""
    with open(SEMANTIC_LAYER_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_composite_kpis(semantic: dict) -> dict[str, list[str]]:
    """Returns {kpi_name: [source_col, ...]} for KPIs that have a 'sources' field."""
    result = {}
    for name, info in semantic.get("kpis", {}).items():
        if sources := info.get("sources"):
            result[name] = sources
    return result


def format_for_prompt(semantic: dict) -> str:
    """Format the semantic layer as structured text for injection into LLM prompts."""
    if not semantic:
        return ""

    lines = []

    if ctx := semantic.get("business_context"):
        lines.append(f"【ビジネスコンテキスト】\n{ctx}")
        lines.append("")

    kpis = semantic.get("kpis", {})
    if kpis:
        lines.append("【KPI定義・判断基準】")
        for kpi_name, info in kpis.items():
            block = [f"■ {kpi_name}"]
            if v := info.get("sources"):
                block.append(f"  合算元: {' + '.join(v)}")
            if v := info.get("description"):
                block.append(f"  定義: {v}")
            if v := info.get("business_impact"):
                block.append(f"  ビジネス影響: {v}")
            bm = info.get("benchmarks", {})
            if w := bm.get("warning"):
                block.append(f"  要改善水準: {w.get('below')}件未満 → {w.get('message', '')}")
            if g := bm.get("good"):
                block.append(f"  良好水準: {g.get('at_least')}件以上 → {g.get('message', '')}")
            if v := info.get("trend_analysis"):
                block.append(f"  トレンド解釈: {v}")
            if v := info.get("coaching_focus"):
                block.append(f"  コーチング観点: {v}")
            lines.append("\n".join(block))
        lines.append("")

    categories = semantic.get("comment_categories", {})
    if categories:
        lines.append("【コメントカテゴリ定義】")
        for cat_name, info in categories.items():
            desc = info.get("description", "")
            note = info.get("urgency_note", "")
            lines.append(f"■ {cat_name}: {desc}")
            if note:
                lines.append(f"  注意: {note}")

    return "\n".join(lines)

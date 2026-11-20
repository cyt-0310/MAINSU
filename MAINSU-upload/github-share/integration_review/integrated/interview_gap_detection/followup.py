"""十二、依資訊缺口與備審證據生成引導式追問（每次僅 1 題）。"""
from typing import List, Tuple

from .config import PASS_THRESHOLD, PDF_PROMPT_CHARS, load_prompt
from .assessment import format_qa_history
from .gap_detection import gap_field, pick_target_item, ITEM_INFO
from .llm_client import call_llm
from .schemas import FollowUp


def generate_followup(
    topic: dict,
    qa_history: List[Tuple[str, str]],
    gap_result: dict,
    pdf_portfolio: dict,
    allow_outside_portfolio: bool
) -> FollowUp:
    field = gap_field(gap_result["target_gap"])
    hidden = gap_result.get("hidden_items") or [{"field": field["key"], "item": gap_result.get("target_item") or
                                                 pick_target_item(gap_result["details"], field["key"],
                                                                  gap_result.get("not_applicable"))}]
    hidden_text = "\n".join(
        f"{i}. {gap_field(h['field'])['name']}›{ITEM_INFO[h['item']][0]}"
        f"（目前 {gap_result['details'][gap_field(h['field'])['detail_key']][h['item']]} 分）：{ITEM_INFO[h['item']][1]}"
        + ("　← 主要缺口" if i == 1 else "")
        for i, h in enumerate(hidden, 1))

    outside_rule = (
        "可以針對回答中出現、但備審未記載的重要內容追問。"
        if allow_outside_portfolio else
        "備審外內容的追問次數已用完，追問必須以備審中有記載的內容為依據。"
    )

    prompt = load_prompt("followup.txt").format(
        topic_type=topic["type"],
        topic_event=topic["event"],
        source=topic["source"],
        qa_history=format_qa_history(qa_history),
        gap_name=field["name"],
        gap_score=gap_result["scores"][field["key"]],
        pass_threshold=PASS_THRESHOLD,
        hidden_items=hidden_text,
        framework=field["framework"],
        pdf_text=pdf_portfolio.get("full_text", "")[:PDF_PROMPT_CHARS],
        outside_rule=outside_rule,
    )
    return call_llm(prompt, FollowUp)

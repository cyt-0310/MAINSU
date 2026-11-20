"""十二、依資訊缺口與備審證據生成引導式追問（每次僅 1 題）。"""
from typing import List, Tuple

from .config import PASS_THRESHOLD, PDF_PROMPT_CHARS, load_prompt
from .assessment import format_qa_history
from .gap_detection import gap_field
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
        gap_details=gap_result["details"][field["detail_key"]],
        framework=field["framework"],
        pdf_text=pdf_portfolio.get("full_text", "")[:PDF_PROMPT_CHARS],
        outside_rule=outside_rule,
    )
    return call_llm(prompt, FollowUp)

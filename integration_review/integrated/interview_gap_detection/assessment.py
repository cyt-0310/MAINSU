"""九-②③、由 LLM 給 STAR／ASK／Gibbs 細項分數，並比對備審一致性。"""
from typing import List, Tuple

from .config import PDF_PROMPT_CHARS, load_prompt
from .llm_client import call_llm
from .schemas import LLMCompletenessAssessment


def format_qa_history(qa_history: List[Tuple[str, str]]) -> str:
    return "\n".join(
        f"Q{i}（{'主問題' if i == 1 else '追問'}）：{q}\nA{i}：{a}"
        for i, (q, a) in enumerate(qa_history, 1)
    )


def assess_answer(topic: dict, qa_history: List[Tuple[str, str]], pdf_portfolio: dict) -> dict:
    """回傳本輪 LLM 原始細項分數（尚未做跨輪次累計，累計在 gap_detection.merge_factors）。"""
    prompt = load_prompt("assessment.txt").format(
        topic_type=topic["type"],
        topic_event=topic["event"],
        portfolio_role=topic["portfolio_role"],
        source=topic["source"],
        qa_history=format_qa_history(qa_history),
        pdf_text=pdf_portfolio.get("full_text", "")[:PDF_PROMPT_CHARS],
    )
    result: LLMCompletenessAssessment = call_llm(prompt, LLMCompletenessAssessment)

    return {
        "details": {
            "star": result.star.model_dump(),
            "ask": result.ask.model_dump(),
            "gibbs": result.gibbs.model_dump(),
        },
        "reasoning": result.reasoning,
        "consistency_issues": [c.model_dump() for c in result.consistency_issues],
        "mentions_outside_portfolio": result.mentions_outside_portfolio,
    }

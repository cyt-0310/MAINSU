"""六、建立基礎題庫：固定自我介紹與學習歷程事件。"""
from typing import List

from .config import (
    DEPARTMENT, QUESTION_BANK_CONFIG, PDF_PROMPT_CHARS, load_prompt,
    MAX_FOLLOWUPS_GENERAL, MAX_FOLLOWUPS_INTRO, INTRO_ANSWER_LIMIT, GENERAL_ANSWER_LIMIT,
)
from .llm_client import call_llm
from .schemas import QuestionBankPlan


def build_question_bank(pdf_portfolio: dict) -> List[dict]:
    pdf_text = pdf_portfolio.get("full_text", "")[:PDF_PROMPT_CHARS]
    prompt = load_prompt("question_bank.txt").format(department=DEPARTMENT, pdf_text=pdf_text)
    plan: QuestionBankPlan = call_llm(prompt, QuestionBankPlan)

    # ① 固定自我介紹
    intro = dict(QUESTION_BANK_CONFIG["intro"])
    intro["question"] = intro["question"].format(department=DEPARTMENT)
    intro["max_followups"] = MAX_FOLLOWUPS_INTRO
    intro["answer_limit"] = INTRO_ANSWER_LIMIT
    bank = [intro]

    # ② 學習歷程挑選 1~2 個事件（專業相關 > 社團競賽 > 其他）
    priority = QUESTION_BANK_CONFIG["event_priority"]
    events = sorted(plan.events, key=lambda e: priority.get(e.category, len(priority)))
    for ev in events[:QUESTION_BANK_CONFIG["max_events"]]:
        bank.append({
            "type": f"學習歷程（{ev.category}）",
            "event": ev.title,
            "source": f"備審 PDF（{pdf_portfolio['pdf_name']}）：{ev.summary}",
            "portfolio_role": ev.role_in_portfolio,
            "check_aspects": ev.check_aspects,
            "question": ev.main_question,
            "max_followups": MAX_FOLLOWUPS_GENERAL,
            "answer_limit": GENERAL_ANSWER_LIMIT,
        })

    for i, topic in enumerate(bank, 1):
        topic["order"] = i
    return bank

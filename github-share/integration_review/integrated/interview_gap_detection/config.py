"""讀取 config/ 下的設定檔與 prompts/ 下的 Prompt 範本。"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")


def _load_json(name: str) -> dict:
    with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


SETTINGS = _load_json("settings.json")
QUESTION_BANK_CONFIG = _load_json("question_bank.json")

DEPARTMENT = SETTINGS["department"]

# 十、全場與主題終止條件
MAX_TOTAL_QUESTIONS = SETTINGS["interview"]["max_total_questions"]
MAX_TOTAL_SECONDS = SETTINGS["interview"]["max_total_seconds"]
TOPIC_TIME_LIMIT = SETTINGS["interview"]["topic_time_limit_seconds"]

# 六、作答時間
INTRO_ANSWER_TARGET = SETTINGS["answer_time"]["intro_target_seconds"]
INTRO_ANSWER_LIMIT = SETTINGS["answer_time"]["intro_limit_seconds"]
GENERAL_ANSWER_LIMIT = SETTINGS["answer_time"]["general_limit_seconds"]

# 六、追問次數
MAX_FOLLOWUPS_GENERAL = SETTINGS["followup"]["max_general"]
MIN_FOLLOWUP_REMAINING_SECONDS = SETTINGS["followup"].get("min_remaining_seconds", 60)
MAX_FOLLOWUPS_INTRO = SETTINGS["followup"]["max_intro"]
MAX_OUTSIDE_PORTFOLIO_FOLLOWUPS = SETTINGS["followup"]["max_outside_portfolio"]

# 九-①、相關度
RELEVANT_THRESHOLD = SETTINGS["relevance"]["relevant_threshold"]
OFF_TOPIC_THRESHOLD = SETTINGS["relevance"]["off_topic_threshold"]
VECTOR_WEIGHT = SETTINGS["relevance"]["vector_weight"]
CROSS_WEIGHT = SETTINGS["relevance"]["cross_weight"]
VECTOR_MODEL_NAME = SETTINGS["relevance"]["vector_model"]
CROSS_MODEL_NAME = SETTINGS["relevance"]["cross_model"]

# 九-②、完整度
PASS_THRESHOLD = SETTINGS["completeness"]["pass_threshold"]

# 十一、資訊缺口欄位（陣列順序 = 同分時的優先順序）
GAP_FIELDS = SETTINGS["gap_fields"]

# LLM
PDF_PROMPT_CHARS = SETTINGS["llm"]["pdf_prompt_chars"]

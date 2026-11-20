"""
資訊缺口判斷（流程圖 九-② 完整度計算、十、終止條件、十一、資訊缺口排序）。

這個檔案只有純規則運算，不呼叫 AI API、不載入模型，可以單獨測試：
    python tests/test_gap_detection.py
"""
from typing import Dict, List, Optional

from .config import (
    PASS_THRESHOLD, GAP_FIELDS, MAX_TOTAL_QUESTIONS, MAX_TOTAL_SECONDS, TOPIC_TIME_LIMIT,
    MAX_HIDDEN_ITEMS,
)

# 各框架的細項數量：STAR 5 項、ASK 3 項、Gibbs 2 項
DETAIL_COUNTS = {"star": 5, "ask": 3, "gibbs": 2}


# ==============================================================================
# 九-②、累計完整度
# ==============================================================================

def merge_factors(new_details: Dict, previous_details: Optional[Dict] = None) -> Dict:
    """跨輪次 max 保障：同一主題內各細項分數只增不降。"""
    merged = {key: dict(values) for key, values in new_details.items()}
    if previous_details:
        for key, values in merged.items():
            prev = previous_details.get(key, {})
            for k in values:
                values[k] = max(prev.get(k, 0.0), values[k])
    return merged


def merge_not_applicable(new_na, previous_na, details: Dict) -> List[str]:
    """
    同一主題累計「不適用」細項：必須每一輪都被 LLM 判為不適用（取交集），
    而且累計分數仍是 0，才算不適用。只要有任何一輪判為適用或拿過分數，就恢復計分。
    previous_na 為 None 代表本主題第一輪。
    """
    na = set(new_na or [])
    if previous_na is not None:
        na &= set(previous_na)
    scored = {k for values in details.values() for k, v in values.items() if v > 0}
    return sorted(na - scored)


def compute_completeness(details: Dict, not_applicable=()) -> Dict[str, float]:
    """把 STAR／ASK／Gibbs 細項換算成三大欄位百分比；不適用的細項不算進分母。
    若某欄位的細項全部不適用，該欄位照常全部計分（避免整欄缺口被隱藏）。"""
    na = set(not_applicable or ())
    pct = {}
    for key in DETAIL_COUNTS:
        keys = [k for k in details[key] if k not in na] or list(details[key])
        pct[key] = round(sum(details[key][k] for k in keys) / len(keys) * 100, 1)
    return {
        "exp": pct["star"],     # 經驗內容 (STAR)
        "trait": pct["ask"],    # 個人特質 (ASK)
        "depth": pct["gibbs"],  # 深度邏輯 (Gibbs)
    }


def is_all_passed(scores: Dict[str, float]) -> bool:
    return all(v >= PASS_THRESHOLD for v in scores.values())


# ==============================================================================
# 十、檢查終止條件
# ==============================================================================

def check_interview_end(total_questions: int, interview_elapsed: float) -> Optional[str]:
    if total_questions >= MAX_TOTAL_QUESTIONS:
        return f"全場已達 {MAX_TOTAL_QUESTIONS} 題"
    if interview_elapsed >= MAX_TOTAL_SECONDS:
        return f"全場已達 {MAX_TOTAL_SECONDS // 60} 分鐘"
    return None


def check_topic_end(all_passed: bool, followup_count: int, max_followups: int, topic_elapsed: float) -> Optional[str]:
    if all_passed:
        return f"三項完整度均 >= {PASS_THRESHOLD}%"
    if followup_count >= max_followups:
        return f"追問已達上限 ({max_followups} 次)"
    if topic_elapsed >= TOPIC_TIME_LIMIT:
        return f"本主題時間已達 {TOPIC_TIME_LIMIT // 60} 分鐘"
    return None


# ==============================================================================
# 十一、資訊缺口排序
# ==============================================================================

def rank_information_gaps(scores: Dict[str, float]) -> List[str]:
    """只比較未達門檻的欄位，分數低者優先；同分依 GAP_FIELDS 順序（個人特質 → 深度邏輯 → 經驗內容）。"""
    gaps = [(scores[f["key"]], i, f["key"]) for i, f in enumerate(GAP_FIELDS) if scores[f["key"]] < PASS_THRESHOLD]
    gaps.sort()
    return [key for _, _, key in gaps]


def gap_field(key: str) -> Dict:
    return next(f for f in GAP_FIELDS if f["key"] == key)


# 每個細項的中文名稱與「追問時要問什麼」；字典順序 = 同分時的優先順序
ITEM_INFO = {
    "why_score": ("動機", "為什麼會想做這件事、當初的動機或契機"),
    "how_score": ("過程", "具體是怎麼進行的、有哪些步驟或方法"),
    "what_score": ("結果", "最後的成果、成效或具體產出（最好有數據）"),
    "role_score": ("角色", "在團隊中擔任什麼角色、負責哪些職責"),
    "action_score": ("行動", "自己親自做了哪些具體行動"),
    "skill_score": ("能力", "運用或培養了哪些具體能力或技術"),
    "attitude_score": ("態度", "面對這件事時展現的態度，用具體情境說明"),
    "knowledge_score": ("知識", "用到或學到的專業知識、原理或概念"),
    "reflection_score": ("反思", "事後的反思、學到什麼、想法或做法有什麼改變"),
    "challenge_score": ("挑戰", "遇到的困難或衝突，以及如何處理"),
}


def pick_target_item(details: Dict, field_key: str, not_applicable=()) -> Optional[str]:
    """在目標欄位中挑出「單一」最低分細項（排除不適用；同分依 ITEM_INFO 順序）。"""
    group = details[gap_field(field_key)["detail_key"]]
    na = set(not_applicable or ())
    candidates = [k for k in group if k not in na] or list(group)
    order = list(ITEM_INFO)
    return min(candidates, key=lambda k: (group[k], order.index(k) if k in order else len(order)))


def pick_hidden_items(details: Dict, gaps: List[str], not_applicable=(), limit: int = 3) -> List[Dict]:
    """
    挑出要「暗藏」在同一個追問裡的多個缺口細項：
    1. 第一個一定是最低欄位中最低的細項（主要缺口）；
    2. 其餘從所有未達門檻欄位中，挑分數 < 0.75（還沒講具體）的細項，分數低者優先，最多 limit 個。
    """
    if not gaps:
        return []
    na = set(not_applicable or ())
    order = list(ITEM_INFO)
    primary = pick_target_item(details, gaps[0], na)
    picked = [{"field": gaps[0], "item": primary}]
    candidates = []
    for field_rank, field_key in enumerate(gaps):
        group = details[gap_field(field_key)["detail_key"]]
        for k, v in group.items():
            if k == primary or k in na or v >= 0.75:
                continue
            candidates.append((v, field_rank, order.index(k) if k in order else len(order), field_key, k))
    for _, _, _, field_key, k in sorted(candidates)[:max(0, limit - 1)]:
        picked.append({"field": field_key, "item": k})
    return picked


# ==============================================================================
# 整合：九-② → 十 → 十一
# ==============================================================================

def detect_gap(
    new_details: Dict,
    previous_details: Optional[Dict],
    followup_count: int,
    max_followups: int,
    total_questions: int,
    interview_elapsed: float,
    topic_elapsed: float,
    new_not_applicable=None,
    previous_not_applicable=None,
) -> Dict:
    """
    輸入本輪 LLM 細項分數與目前面試狀態，輸出下一步決策：
      decision = "end_interview"（結束面試）／"switch_topic"（切換主題）／"follow_up"（追問 target_gap）
    """
    details = merge_factors(new_details, previous_details)
    not_applicable = merge_not_applicable(new_not_applicable, previous_not_applicable, details)
    scores = compute_completeness(details, not_applicable)
    all_passed = is_all_passed(scores)
    gaps = rank_information_gaps(scores)

    result = {
        "details": details,
        "not_applicable": not_applicable,
        "scores": scores,
        "is_all_passed": all_passed,
        "gaps": gaps,
        "target_gap": None,
        "target_item": None,
        "hidden_items": [],
        "decision": None,
        "reason": None,
    }

    end_reason = check_interview_end(total_questions, interview_elapsed)
    if end_reason:
        result.update(decision="end_interview", reason=end_reason)
        return result

    topic_end = check_topic_end(all_passed, followup_count, max_followups, topic_elapsed)
    if topic_end:
        result.update(decision="switch_topic", reason=topic_end)
        return result

    target = gaps[0]
    hidden = pick_hidden_items(details, gaps, not_applicable, MAX_HIDDEN_ITEMS)
    names = "、".join(f"{gap_field(h['field'])['name']}›{ITEM_INFO[h['item']][0]}" for h in hidden)
    result.update(
        decision="follow_up",
        target_gap=target,
        target_item=hidden[0]["item"],
        hidden_items=hidden,
        reason=f"{gap_field(target)['name']} {scores[target]}% 最低；用一個問題暗藏以下缺口：{names}",
    )
    return result

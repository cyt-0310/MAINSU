"""
資訊缺口判斷（流程圖 九-② 完整度計算、十、終止條件、十一、資訊缺口排序）。

這個檔案只有純規則運算，不呼叫 AI API、不載入模型，可以單獨測試：
    python tests/test_gap_detection.py
"""
from typing import Dict, List, Optional

from .config import (
    PASS_THRESHOLD, GAP_FIELDS, MAX_TOTAL_QUESTIONS, MAX_TOTAL_SECONDS, TOPIC_TIME_LIMIT,
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


def compute_completeness(details: Dict) -> Dict[str, float]:
    """把 STAR／ASK／Gibbs 細項換算成三大欄位百分比。"""
    pct = {key: round(sum(details[key].values()) / DETAIL_COUNTS[key] * 100, 1) for key in DETAIL_COUNTS}
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
) -> Dict:
    """
    輸入本輪 LLM 細項分數與目前面試狀態，輸出下一步決策：
      decision = "end_interview"（結束面試）／"switch_topic"（切換主題）／"follow_up"（追問 target_gap）
    """
    details = merge_factors(new_details, previous_details)
    scores = compute_completeness(details)
    all_passed = is_all_passed(scores)
    gaps = rank_information_gaps(scores)

    result = {
        "details": details,
        "scores": scores,
        "is_all_passed": all_passed,
        "gaps": gaps,
        "target_gap": None,
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
    result.update(
        decision="follow_up",
        target_gap=target,
        reason=f"{gap_field(target)['name']} {scores[target]}% 最低，優先追問",
    )
    return result

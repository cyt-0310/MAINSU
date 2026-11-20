"""九-①、三軌語意相關度：Bi-Encoder 雙塔向量 + Cross-Encoder 交叉注意力 + LLM 判斷。

計算流程（每一題的問題 vs 該題回答）：
1. Bi-Encoder（bge-base-zh-v1.5）：問題加檢索指令後編碼；回答整段與逐句各算一次餘弦相似度取最大，
   避免長回答被截斷或重點被稀釋。再把餘弦值線性校正到 0~1。
2. Cross-Encoder（bge-reranker-base）：取原始 logit，除以溫度後做「一次」sigmoid，讓分數有層次。
3. 模型混合分數 = 向量權重 × Bi + 交叉權重 × Cross。
4. 照抄題目檢查：回答與題目字面重疊率過高 → 分數上限壓低。
5. LLM 判斷（併在完整度評估同一次呼叫，不增加等待）：LLM 決定「等級區間」，
   模型混合分數決定區間內的位置（超出區間就夾回區間邊界）。
"""
import difflib
import math
import re
import sys

from .config import SETTINGS, RELEVANT_THRESHOLD, OFF_TOPIC_THRESHOLD

CFG = SETTINGS["relevance"]

_vector_model = None
_cross_model = None


def load_models():
    """第一次使用時才載入模型（首次執行會自動從 Hugging Face 下載）。"""
    global _vector_model, _cross_model
    if _vector_model is None:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        print("正在載入語意模型 (Bi-Encoder + Cross-Encoder)...", flush=True)
        try:
            _vector_model = SentenceTransformer(CFG["vector_model"])
            _cross_model = CrossEncoder(CFG["cross_model"])
            print("語意模型載入成功！\n", flush=True)
        except Exception as e:
            print(f"模型載入失敗，請確認已安裝 sentence-transformers 並可下載模型：{e}")
            sys.exit(1)
    return _vector_model, _cross_model


# ==============================================================================
# 純計算（不需模型，可單獨測試）
# ==============================================================================

def classify_relevance(score: float) -> tuple:
    if score >= RELEVANT_THRESHOLD:
        return "relevant", "切題"
    if score >= OFF_TOPIC_THRESHOLD:
        return "partial", "部分離題"
    return "off_topic", "離題"


def calibrate_vector(cosine: float) -> float:
    """把 bge 餘弦值（無關約 0.1~0.3、切題約 0.4~0.7）線性拉到 0~1。"""
    low, high = CFG["vector_cos_low"], CFG["vector_cos_high"]
    return min(1.0, max(0.0, (cosine - low) / (high - low)))


def soften_cross(logit: float) -> float:
    """Cross-Encoder logit 只做一次 sigmoid；溫度 > 1 讓分數不會全擠在 0 或 1。"""
    return 1 / (1 + math.exp(-logit / CFG["cross_temperature"]))


def copy_ratio(question: str, answer: str) -> float:
    """回答與題目的字面相似度（0~1），用來抓照抄題目。"""
    strip = lambda s: re.sub(r"[\s，。、？！?!「」：:；;]", "", s)
    return difflib.SequenceMatcher(None, strip(question), strip(answer)).ratio()


def split_sentences(text: str) -> list:
    parts = [s.strip() for s in re.split(r"(?<=[。！？!?；;\n])", text)]
    return [s for s in parts if s] or [text]


def combine_with_llm(relevance: dict, judgement) -> dict:
    """LLM 決定等級區間，模型混合分數決定區間內位置。judgement 為 None 時直接採用模型分數。"""
    result = dict(relevance)
    model_score = relevance["relevance_score"]
    if judgement and judgement.get("label") in CFG["llm_bands"]:
        low, high = CFG["llm_bands"][judgement["label"]]
        result["llm_label"] = judgement["label"]
        result["llm_reason"] = judgement.get("reason", "")
        result["relevance_score"] = round(min(high, max(low, model_score)), 4)
        result["method"] = "llm_band_with_model_position"
    else:
        result["method"] = result.get("method", "models_only")
    result["model_score"] = model_score
    result["level"], result["relevance_status"] = classify_relevance(result["relevance_score"])
    return result


# ==============================================================================
# 模型計算
# ==============================================================================

def _cross_logit(cross_model, question, answer) -> float:
    import torch
    try:
        out = cross_model.predict([(question, answer)], activation_fn=torch.nn.Identity())
    except TypeError:  # 舊版 sentence-transformers 參數名稱不同
        out = cross_model.predict([(question, answer)], activation_fct=torch.nn.Identity())
    return float(out[0])


def compute_relevance(question: str, answer: str) -> dict:
    """單題的模型相關度（尚未加入 LLM 判斷；LLM 判斷在 combine_with_llm）。"""
    vector_model, cross_model = load_models()

    q_vec = vector_model.encode([CFG["query_instruction"] + question], normalize_embeddings=True)[0]
    pieces = [answer] + split_sentences(answer)
    a_vecs = vector_model.encode(pieces, normalize_embeddings=True)
    cosine = max(float(v @ q_vec) for v in a_vecs)
    s_vec = calibrate_vector(cosine)

    logit = _cross_logit(cross_model, question, answer)
    s_cross = soften_cross(logit)

    score = CFG["vector_weight"] * s_vec + CFG["cross_weight"] * s_cross
    ratio = copy_ratio(question, answer)
    copied = ratio >= CFG["copy_ratio_threshold"]
    if copied:
        score = min(score, CFG["copy_score_cap"])
    score = round(score, 4)
    level, status = classify_relevance(score)

    return {
        "vector_cosine": round(cosine, 4),
        "vector_score": round(s_vec, 4),
        "cross_logit": round(logit, 4),
        "cross_score": round(s_cross, 4),
        "copy_ratio": round(ratio, 4),
        "copied_question": copied,
        "relevance_score": score,
        "level": level,
        "relevance_status": status,
        "method": "models_only",
    }

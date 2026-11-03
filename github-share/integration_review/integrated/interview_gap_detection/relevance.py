"""九-①、雙軌語意相關度 (Vector 70% + Cross-Encoder 30%)。"""
import sys

import numpy as np

from .config import (
    RELEVANT_THRESHOLD, OFF_TOPIC_THRESHOLD, VECTOR_WEIGHT, CROSS_WEIGHT,
    VECTOR_MODEL_NAME, CROSS_MODEL_NAME,
)

_vector_model = None
_cross_model = None


def load_models():
    """第一次使用時才載入模型（首次執行會自動從 Hugging Face 下載）。"""
    global _vector_model, _cross_model
    if _vector_model is None:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        print("🤖 正在載入雙軌語意模型 (Vector + Cross-Encoder)...")
        try:
            _vector_model = SentenceTransformer(VECTOR_MODEL_NAME)
            _cross_model = CrossEncoder(CROSS_MODEL_NAME)
            print("✅ 雙軌語意模型載入成功！\n")
        except Exception as e:
            print(f"⚠️ 模型載入失敗，請確認已安裝 sentence-transformers：{e}")
            sys.exit(1)
    return _vector_model, _cross_model


def classify_relevance(hybrid_score: float) -> tuple:
    if hybrid_score >= RELEVANT_THRESHOLD:
        return "relevant", f"✅ 切題 (>= {RELEVANT_THRESHOLD})"
    if hybrid_score >= OFF_TOPIC_THRESHOLD:
        return "partial", f"⚠️ 部分離題 ({OFF_TOPIC_THRESHOLD} ~ {RELEVANT_THRESHOLD})"
    return "off_topic", f"❌ 離題 (< {OFF_TOPIC_THRESHOLD})"


def compute_relevance(question: str, answer: str) -> dict:
    from sklearn.metrics.pairwise import cosine_similarity
    vector_model, cross_model = load_models()

    q_vec = vector_model.encode([question])
    a_vec = vector_model.encode([answer])
    s_vec = float(cosine_similarity(q_vec, a_vec)[0][0])

    s_cross_raw = cross_model.predict([(question, answer)])[0]
    s_cross = float(1 / (1 + np.exp(-s_cross_raw)))

    hybrid_score = round((VECTOR_WEIGHT * s_vec) + (CROSS_WEIGHT * s_cross), 4)
    level, status = classify_relevance(hybrid_score)

    return {
        "vector_score": round(s_vec, 4),
        "cross_score": round(s_cross, 4),
        "relevance_score": hybrid_score,
        "level": level,
        "relevance_status": status,
    }

"""Gemini 與 OpenAI 共用的 Pydantic 結構化輸出模型。"""
from typing import List
from pydantic import BaseModel, Field


# ---- 六、建立基礎題庫 ----
class PortfolioEvent(BaseModel):
    title: str = Field(..., description="事件名稱（繁體中文）")
    category: str = Field(..., description="事件類別，只能填：專業相關、社團競賽、其他")
    summary: str = Field(..., description="備審中描述此事件的原文關鍵句（繁體中文）")
    role_in_portfolio: str = Field(..., description="備審中記載的學生角色，例如組員、組長；未記載填『未提及』")
    check_aspects: List[str] = Field(..., description="此事件適合檢核的面向，例如動機、角色、行動、成果、反思")
    main_question: str = Field(..., description="針對此事件的主問題（繁體中文，一次只問一題）")


class QuestionBankPlan(BaseModel):
    events: List[PortfolioEvent] = Field(..., description="從備審中挑選 1~2 個事件，依 專業相關 > 社團競賽 > 其他 的優先順序")


# ---- 九、回答內容多維度檢驗 ----
class STARScore(BaseModel):
    why_score: float = Field(..., description="動機(Why): 1.0明確具體, 0.5概括提及, 0.0未提及")
    how_score: float = Field(..., description="過程(How): 1.0明確具體步驟/細節, 0.5概括原則/模糊, 0.0未提及")
    what_score: float = Field(..., description="結果(What/產出): 1.0明確成效/量化結果, 0.5概括產出/指導他人, 0.0未提及")
    role_score: float = Field(..., description="角色(STAR-T): 1.0明確職責/幹部, 0.5僅提及團隊/社團背景, 0.0未提及")
    action_score: float = Field(..., description="行動(STAR-A): 1.0具體執行動作, 0.5概括溝通/協調, 0.0未提及")


class ASKScore(BaseModel):
    skill_score: float = Field(..., description="能力(ASK-S): 1.0明確專業技術/技能實例, 0.5概括能力, 0.0未提及")
    attitude_score: float = Field(..., description="態度(ASK-A): 1.0具體展現積極/協調態度, 0.5概括溝通態度, 0.0未提及")
    knowledge_score: float = Field(..., description="知識(ASK-K): 1.0明確專業技術原理/理論, 0.5概括概念, 0.0未提及")


class GibbsScore(BaseModel):
    reflection_score: float = Field(..., description="反思(Gibbs): 1.0深刻反思/具體調整心態, 0.5概括心得, 0.0未提及")
    challenge_score: float = Field(..., description="矛盾與挑戰(Consistency): 1.0具體衝突解決案例, 0.5概括處理原則, 0.0未提及")


class ConsistencyIssue(BaseModel):
    issue_type: str = Field(..., description="只能填：可能誇大、角色差異、矛盾")
    portfolio_evidence: str = Field(..., description="備審原文（繁體中文）；備審未記載則填『備審未提及』")
    answer_evidence: str = Field(..., description="學生口述原文（繁體中文）")
    note: str = Field(..., description="繁體中文簡要說明差異")


class LLMCompletenessAssessment(BaseModel):
    star: STARScore
    ask: ASKScore
    gibbs: GibbsScore
    reasoning: str = Field(..., description="請務必使用繁體中文簡要說明給分原因，特別是給予0.5的原因")
    consistency_issues: List[ConsistencyIssue] = Field(..., description="比對備審與回答後發現的可能誇大、角色差異或矛盾；沒有則回傳空陣列")
    mentions_outside_portfolio: bool = Field(..., description="學生回答中是否出現備審未記載的重要經歷或內容")


# ---- 十二、生成引導式追問 ----
class FollowUp(BaseModel):
    follow_up_reason: str = Field(..., description="繁體中文說明為什麼要問這一題（對應哪個資訊缺口與備審證據）")
    follow_up_question: str = Field(..., description="繁體中文的引導式追問，只能有一個問題")
    targets_outside_portfolio: bool = Field(..., description="此追問是否針對備審未記載的內容")

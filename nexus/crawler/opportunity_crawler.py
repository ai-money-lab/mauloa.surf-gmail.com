"""
OPPORTUNITY CRAWLER — 稼ぎ方をAIが自動探索する

フロー:
1. 市場トレンドを分析（AIフリーランス、デジタル商品、API、自動化）
2. 具体的な収益機会を特定（プラットフォーム、単価、需要レベル）
3. 実行可能性を評価（難易度、初期コスト、時間、競合）
4. 優先順位をつけてTrialエンジンに渡す

ALPHA-OMEGAが議論して最良の機会を選ぶ。
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from anthropic import Anthropic


class OpportunityType(str, Enum):
    """収益機会の種別"""
    FREELANCE_GIG = "freelance_gig"         # フリーランス案件
    DIGITAL_PRODUCT = "digital_product"     # デジタル商品販売
    API_SERVICE = "api_service"             # API/SaaS
    CONTENT_MONETIZE = "content_monetize"   # コンテンツ収益化
    AUTOMATION_SELL = "automation_sell"      # 自動化ツール販売
    CONSULTING = "consulting"               # コンサル
    AFFILIATE = "affiliate"                 # アフィリエイト


class Feasibility(str, Enum):
    """実現可能性"""
    IMMEDIATE = "immediate"     # 即日着手可能
    SHORT_TERM = "short_term"   # 1週間以内
    MEDIUM_TERM = "medium_term" # 1ヶ月以内
    LONG_TERM = "long_term"     # 3ヶ月以上


@dataclass
class Opportunity:
    """発見された収益機会"""
    title: str
    opportunity_type: OpportunityType
    feasibility: Feasibility
    estimated_revenue: int          # 円/月
    confidence: float               # 0-1
    description: str = ""
    platform: str = ""              # 販売プラットフォーム
    competition_level: str = ""     # 低/中/高
    required_skills: list[str] = field(default_factory=list)
    action_steps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    opp_id: str = ""

    def __post_init__(self):
        if not self.opp_id:
            raw = f"{self.title}{self.opportunity_type}{self.discovered_at}"
            self.opp_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "opp_id": self.opp_id,
            "title": self.title,
            "opportunity_type": self.opportunity_type.value,
            "feasibility": self.feasibility.value,
            "estimated_revenue": self.estimated_revenue,
            "confidence": self.confidence,
            "description": self.description,
            "platform": self.platform,
            "competition_level": self.competition_level,
            "required_skills": self.required_skills,
            "action_steps": self.action_steps,
            "risks": self.risks,
            "discovered_at": self.discovered_at,
        }

    @property
    def priority_score(self) -> float:
        """優先度スコア: 収益 × 確度 × 実現速度"""
        speed_multiplier = {
            Feasibility.IMMEDIATE: 4.0,
            Feasibility.SHORT_TERM: 3.0,
            Feasibility.MEDIUM_TERM: 2.0,
            Feasibility.LONG_TERM: 1.0,
        }
        return self.estimated_revenue * self.confidence * speed_multiplier.get(self.feasibility, 1.0)


CRAWL_PROMPT = """あなたはAI収益化の市場分析エキスパートです。
現在のAI市場で、個人またはAIシステムが即座に取り組める収益機会を徹底的に探索してください。

重要: プロフィールや個人ブランドに依存しない、純粋に技術力とAI能力で稼げる機会を探すこと。

探索領域:
1. AIフリーランス案件（ランサーズ、ココナラ、Upwork、Fiverr）
2. デジタル商品（プロンプト集、テンプレート、自動化ツール）
3. API/マイクロSaaS（特定用途のAIサービス）
4. コンテンツ収益化（技術記事、チュートリアル、有料note）
5. 自動化サービス（業務効率化の受託/販売）
6. コンサルティング（AI導入支援）

各機会について以下を含めること:
- 具体的な収益見込み（月額/案件単位）
- 競合レベル（低/中/高）
- 必要スキル
- 着手までの期間
- 成功のための具体的アクションステップ

出力（JSON）:
- "opportunities": 収益機会リスト（最低8個）
  - 各機会: {
      "title": "",
      "opportunity_type": "freelance_gig/digital_product/api_service/content_monetize/automation_sell/consulting/affiliate",
      "feasibility": "immediate/short_term/medium_term/long_term",
      "estimated_revenue": 月額見込み（円）,
      "confidence": 0-1,
      "description": "",
      "platform": "",
      "competition_level": "低/中/高",
      "required_skills": [],
      "action_steps": [],
      "risks": []
    }
- "market_insights": 市場全体の洞察
- "top_3_recommendation": 最もおすすめの3つ（理由付き）"""


EVALUATE_PROMPT = """あなたはALPHAとOMEGAの協議を仲裁するメタAIです。

以下の収益機会リストについて、2つのAIの視点で厳密に評価してください。

ALPHA視点（楽観・実行重視）:
- この機会で実際に何が作れるか
- どれくらい早く着手できるか
- 成功した場合のインパクト

OMEGA視点（批判・リスク重視）:
- 本当にこの収益見込みは現実的か
- 競合に勝てるか
- 隠れたリスクは何か

出力（JSON）:
- "evaluated": 評価済み機会リスト
  - 各機会: {
      "opp_id": "",
      "alpha_verdict": {"score": 1-10, "reasoning": ""},
      "omega_verdict": {"score": 1-10, "reasoning": ""},
      "consensus_score": 平均スコア,
      "should_try": true/false,
      "try_order": 優先順位（1が最優先）
    }
- "debate_summary": 議論の要約
- "final_recommendation": 最終結論"""


class OpportunityCrawler:
    """
    収益機会の自動探索エンジン

    AIが市場をクロールし、実行可能な収益機会を発見する。
    ALPHA-OMEGAが議論して最良の機会を選定する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.client = Anthropic()
        self.data_dir = data_dir or Path("nexus/data/crawler")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.opportunities: list[Opportunity] = []
        self.crawl_history: list[dict] = []

    def crawl(self, focus: str = "", market_context: str = "") -> list[Opportunity]:
        """市場をクロールして収益機会を発見する"""
        user_content = "現在のAI市場で収益機会を徹底探索してください。"
        if focus:
            user_content += f"\n\n特にフォーカス: {focus}"
        if market_context:
            user_content += f"\n\n市場コンテキスト: {market_context}"

        # 過去の成功/失敗パターンがあれば含める
        history_context = self._get_history_context()
        if history_context:
            user_content += f"\n\n過去の試行結果:\n{history_context}"

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=CRAWL_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        opportunities = self._parse_opportunities(response.content[0].text)
        self.opportunities.extend(opportunities)
        self._save_crawl_result(opportunities)
        return opportunities

    def evaluate(self, opportunities: list[Opportunity] | None = None) -> list[dict]:
        """ALPHA-OMEGAの議論で機会を評価する"""
        targets = opportunities or self.opportunities[-10:]
        if not targets:
            return []

        opps_text = json.dumps(
            [o.to_dict() for o in targets],
            ensure_ascii=False,
            indent=2,
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=EVALUATE_PROMPT,
            messages=[{
                "role": "user",
                "content": f"以下の収益機会を評価してください:\n\n{opps_text}",
            }],
        )

        return self._parse_evaluation(response.content[0].text)

    def get_top_opportunities(self, limit: int = 5) -> list[Opportunity]:
        """優先度スコア上位の機会を取得"""
        sorted_opps = sorted(self.opportunities, key=lambda o: o.priority_score, reverse=True)
        return sorted_opps[:limit]

    def record_trial_result(self, opp_id: str, success: bool, actual_revenue: int = 0, notes: str = "") -> None:
        """試行結果を記録（Evolutionへのフィードバック）"""
        result = {
            "opp_id": opp_id,
            "success": success,
            "actual_revenue": actual_revenue,
            "notes": notes,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.crawl_history.append(result)

        results_file = self.data_dir / "trial_results.json"
        history = []
        if results_file.exists():
            try:
                history = json.loads(results_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        history.append(result)
        results_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_history_context(self) -> str:
        """過去の試行結果からコンテキストを生成"""
        results_file = self.data_dir / "trial_results.json"
        if not results_file.exists():
            return ""

        try:
            history = json.loads(results_file.read_text(encoding="utf-8"))
            if not history:
                return ""

            successes = [h for h in history if h.get("success")]
            failures = [h for h in history if not h.get("success")]

            context = ""
            if successes:
                context += f"成功パターン({len(successes)}件): "
                context += ", ".join(h.get("notes", "")[:50] for h in successes[-5:])
            if failures:
                context += f"\n失敗パターン({len(failures)}件): "
                context += ", ".join(h.get("notes", "")[:50] for h in failures[-5:])
            return context
        except json.JSONDecodeError:
            return ""

    def _parse_opportunities(self, raw_text: str) -> list[Opportunity]:
        """Claude応答をOpportunityリストにパース"""
        try:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        opps = []
        for item in parsed.get("opportunities", []):
            try:
                opp_type = OpportunityType(item.get("opportunity_type", "freelance_gig"))
            except ValueError:
                opp_type = OpportunityType.FREELANCE_GIG

            try:
                feasibility = Feasibility(item.get("feasibility", "short_term"))
            except ValueError:
                feasibility = Feasibility.SHORT_TERM

            opps.append(Opportunity(
                title=item.get("title", "Unknown"),
                opportunity_type=opp_type,
                feasibility=feasibility,
                estimated_revenue=item.get("estimated_revenue", 0),
                confidence=item.get("confidence", 0.5),
                description=item.get("description", ""),
                platform=item.get("platform", ""),
                competition_level=item.get("competition_level", "中"),
                required_skills=item.get("required_skills", []),
                action_steps=item.get("action_steps", []),
                risks=item.get("risks", []),
            ))

        return opps

    def _parse_evaluation(self, raw_text: str) -> list[dict]:
        """評価結果をパース"""
        try:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        return parsed.get("evaluated", [])

    def _save_crawl_result(self, opportunities: list[Opportunity]) -> None:
        """クロール結果を保存"""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.data_dir / f"crawl_{ts}.json"
        data = [o.to_dict() for o in opportunities]
        output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

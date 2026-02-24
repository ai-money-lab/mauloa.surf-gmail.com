"""
EVOLVER — 成功パターンを増殖させ、AIが改善を繰り返す

フロー:
1. 成功したTrialからパターンを抽出
2. パターンを横展開（別テーマ・別プラットフォームで再現）
3. 各世代の成果を追跡
4. 最も稼げるパターンを強化・進化させる
5. 失敗パターンを淘汰する

自然選択のように、稼げる戦略だけが生き残る。
"""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.common import call_api, parse_json
from nexus.trial.trial_runner import Trial, TrialResult
from nexus.crawler.opportunity_crawler import Opportunity, OpportunityType, Feasibility

logger = logging.getLogger("nexus.evolution")


@dataclass
class SuccessPattern:
    """成功パターン"""
    pattern_id: str
    title: str
    category: str
    description: str
    revenue: int
    success_factors: list[str]
    replication_count: int = 0
    total_revenue: int = 0
    avg_score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "revenue": self.revenue,
            "success_factors": self.success_factors,
            "replication_count": self.replication_count,
            "total_revenue": self.total_revenue,
            "avg_score": self.avg_score,
            "created_at": self.created_at,
        }


@dataclass
class Generation:
    """進化の世代"""
    gen_number: int
    patterns: list[SuccessPattern]
    new_opportunities: list[dict] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    fitness_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "gen_number": self.gen_number,
            "patterns_count": len(self.patterns),
            "patterns": [p.to_dict() for p in self.patterns],
            "new_opportunities": self.new_opportunities,
            "improvements": self.improvements,
            "fitness_score": self.fitness_score,
            "timestamp": self.timestamp,
        }


EVOLVE_PROMPT = """あなたは進化戦略の専門家です。

成功パターンを分析し、それを横展開・増殖させる方法を設計してください。

ルール:
- 成功要因を抽出し、別のテーマ/プラットフォームに適用する
- 改善できる点を特定し、次世代に反映する
- 失敗パターンの要素を排除する
- 具体的なアクションプランを含める

出力（JSON）:
- "success_factors": 成功要因のリスト
- "replication_ideas": 横展開アイデア（最低5個）
  - 各アイデア: {"title": "", "description": "", "estimated_revenue": 数値, "platform": "", "confidence": 0-1}
- "improvements": 改善提案リスト
- "kill_list": やめるべきこと
- "next_gen_strategy": 次世代の戦略概要"""


class Evolver:
    """
    成功パターンの増殖・進化エンジン

    成功したTrialから学習し、パターンを横展開・改善する。
    世代を重ねるごとに、より稼げるAIに進化する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/evolution")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns: list[SuccessPattern] = []
        self.generations: list[Generation] = []
        self.current_gen = 0
        self._load_state()

    def extract_pattern(self, trial: Trial) -> SuccessPattern | None:
        """成功Trialからパターンを抽出"""
        if trial.result != TrialResult.SUCCESS:
            return None

        raw = f"{trial.opportunity.title}{trial.trial_id}"
        pattern_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

        # Duplicate pattern detection: skip if pattern with same title already exists
        for existing in self.patterns:
            if existing.title == trial.opportunity.title:
                logger.info("Pattern with title '%s' already exists (id=%s), skipping extraction",
                            existing.title, existing.pattern_id)
                return existing

        pattern = SuccessPattern(
            pattern_id=pattern_id,
            title=trial.opportunity.title,
            category=trial.opportunity.opportunity_type.value,
            description=trial.opportunity.description,
            revenue=trial.opportunity.estimated_revenue,
            success_factors=trial.lessons,
            replication_count=1,
            total_revenue=trial.revenue_actual or trial.opportunity.estimated_revenue,
            avg_score=trial.evaluation.get("total_score", 0),
        )

        logger.info("Extracted new pattern '%s' (id=%s)", pattern.title, pattern.pattern_id)
        self.patterns.append(pattern)
        self._save_state()
        return pattern

    def evolve(self) -> Generation:
        """現在のパターンから次世代を生成する"""
        self.current_gen += 1
        logger.info("Evolving to generation %d with %d patterns", self.current_gen, len(self.patterns))

        if not self.patterns:
            logger.warning("No patterns available for evolution")
            return Generation(gen_number=self.current_gen, patterns=[])

        # 成功パターンをAIに分析させる
        patterns_text = json.dumps(
            [p.to_dict() for p in self.patterns],
            ensure_ascii=False,
            indent=2,
        )

        raw_text = call_api(
            system=EVOLVE_PROMPT,
            messages=[{
                "role": "user",
                "content": f"以下の成功パターンを分析し、進化戦略を設計してください:\n\n{patterns_text}",
            }],
            max_tokens=4096,
        )

        evolution_result = self._parse_evolution(raw_text)

        # 世代を記録
        gen = Generation(
            gen_number=self.current_gen,
            patterns=self.patterns.copy(),
            new_opportunities=evolution_result.get("replication_ideas", []),
            improvements=evolution_result.get("improvements", []),
            fitness_score=self._calculate_fitness(),
        )
        self.generations.append(gen)
        self._save_generation(gen)
        return gen

    def replicate(self, pattern: SuccessPattern) -> list[Opportunity]:
        """成功パターンを横展開して新しい機会を生成する"""
        logger.info("Replicating pattern '%s' (id=%s)", pattern.title, pattern.pattern_id)
        raw_text = call_api(
            system=EVOLVE_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"以下の成功パターンを別テーマ・別プラットフォームに横展開してください:\n\n"
                    f"パターン: {pattern.title}\n"
                    f"カテゴリ: {pattern.category}\n"
                    f"収益: {pattern.revenue}円/月\n"
                    f"成功要因: {pattern.success_factors}\n\n"
                    f"5つの横展開案を出してください。"
                ),
            }],
            max_tokens=4096,
        )

        result = self._parse_evolution(raw_text)
        new_opps = []

        for idea in result.get("replication_ideas", []):
            try:
                opp_type = OpportunityType(pattern.category)
            except ValueError:
                opp_type = OpportunityType.DIGITAL_PRODUCT

            opp = Opportunity(
                title=idea.get("title", "横展開案"),
                opportunity_type=opp_type,
                feasibility=Feasibility.SHORT_TERM,
                estimated_revenue=idea.get("estimated_revenue", pattern.revenue),
                confidence=idea.get("confidence", 0.7),
                description=idea.get("description", ""),
                platform=idea.get("platform", ""),
            )
            new_opps.append(opp)

        pattern.replication_count += len(new_opps)
        self._save_state()
        return new_opps

    def get_top_patterns(self, limit: int = 5) -> list[SuccessPattern]:
        """最も稼げるパターンを取得"""
        return sorted(self.patterns, key=lambda p: p.total_revenue, reverse=True)[:limit]

    def get_evolution_stats(self) -> dict[str, Any]:
        """進化統計"""
        return {
            "current_generation": self.current_gen,
            "total_patterns": len(self.patterns),
            "total_revenue_tracked": sum(p.total_revenue for p in self.patterns),
            "total_replications": sum(p.replication_count for p in self.patterns),
            "generations_history": len(self.generations),
            "fitness_trend": [g.fitness_score for g in self.generations[-10:]],
        }

    def _calculate_fitness(self) -> float:
        """現世代の適応度を計算"""
        if not self.patterns:
            return 0.0
        total_revenue = sum(p.total_revenue for p in self.patterns)
        avg_score = sum(p.avg_score for p in self.patterns) / len(self.patterns) if self.patterns else 0
        return total_revenue * (avg_score / 50.0)

    def _parse_evolution(self, raw_text: str) -> dict:
        """進化結果をパース"""
        return parse_json(raw_text)

    def _save_state(self) -> None:
        """状態を保存"""
        state_file = self.data_dir / "evolution_state.json"
        state = {
            "current_gen": self.current_gen,
            "patterns": [p.to_dict() for p in self.patterns],
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        """状態を読み込み"""
        state_file = self.data_dir / "evolution_state.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            self.current_gen = data.get("current_gen", 0)
            for p in data.get("patterns", []):
                self.patterns.append(SuccessPattern(
                    pattern_id=p["pattern_id"],
                    title=p["title"],
                    category=p["category"],
                    description=p.get("description", ""),
                    revenue=p.get("revenue", 0),
                    success_factors=p.get("success_factors", []),
                    replication_count=p.get("replication_count", 0),
                    total_revenue=p.get("total_revenue", 0),
                    avg_score=p.get("avg_score", 0),
                    created_at=p.get("created_at", ""),
                ))
        except json.JSONDecodeError:
            logger.error("evolution_state.json is corrupted — starting fresh. File: %s", state_file)
            backup = state_file.with_suffix(".json.bak")
            state_file.rename(backup)
            logger.info("Corrupted file backed up to %s", backup)
        except KeyError as e:
            logger.error("evolution_state.json missing required field %s — starting fresh", e)

    def _save_generation(self, gen: Generation) -> None:
        """世代を保存"""
        gen_file = self.data_dir / f"gen_{gen.gen_number:04d}.json"
        gen_file.write_text(
            json.dumps(gen.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

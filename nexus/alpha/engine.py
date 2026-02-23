"""
ALPHA Engine — 創造AI

役割:
- コンテンツ生成（記事、コード、マーケティング素材）
- サービス設計（API、ツール、自動化ワークフロー）
- 収益戦略の立案と実行
- 市場分析と機会発見

ALPHAは「生み出す側」。直接的に価値を創造し、収益化可能な成果物を出力する。
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from anthropic import Anthropic


class TaskType(str, Enum):
    """ALPHAが実行できるタスク種別"""
    CONTENT = "content"          # コンテンツ生成
    CODE = "code"                # コード/ツール生成
    STRATEGY = "strategy"        # 戦略立案
    ANALYSIS = "analysis"        # 市場分析
    SERVICE = "service"          # サービス設計
    OUTREACH = "outreach"        # 営業・アウトリーチ


class OutputQuality(str, Enum):
    """成果物の品質レベル"""
    DRAFT = "draft"
    REVIEW = "review"
    FINAL = "final"
    PREMIUM = "premium"


@dataclass
class AlphaOutput:
    """ALPHAの出力物"""
    task_type: TaskType
    content: str
    quality: OutputQuality
    metadata: dict[str, Any] = field(default_factory=dict)
    revenue_potential: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_id: str = ""

    def __post_init__(self):
        if not self.output_id:
            raw = f"{self.task_type}{self.content[:100]}{self.timestamp}"
            self.output_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task_type"] = self.task_type.value
        d["quality"] = self.quality.value
        return d


@dataclass
class AlphaTask:
    """ALPHAへの入力タスク"""
    task_type: TaskType
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10
    source: str = "manual"  # manual / omega / bridge / orchestrator
    max_iterations: int = 3


class AlphaEngine:
    """
    ALPHA — 創造エンジン

    Claude APIを使い、コンテンツ・コード・戦略を自律的に生成する。
    OMEGAからのフィードバックを受けて自己改善する。
    """

    SYSTEM_PROMPT = """あなたはALPHA — 創造と収益生成に特化したAIエンジンです。

あなたの使命:
1. 与えられたタスクから最高品質の成果物を生み出す
2. 常に「これがどう収益につながるか」を考える
3. 具体的・実行可能な出力を生成する（抽象論は不要）
4. OMEGAからのフィードバックがあれば、それを活かして改善する

出力ルール:
- 必ずJSON形式で出力すること
- "content": 生成した成果物（本文）
- "revenue_strategy": この成果物をどう収益化するか
- "next_actions": 次に取るべきアクション（リスト）
- "quality_score": 自己評価スコア（1-10）
- "improvement_notes": 改善の余地"""

    def __init__(self, data_dir: Path | None = None):
        self.client = Anthropic()
        self.data_dir = data_dir or Path("nexus/data/alpha")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[AlphaOutput] = []

    def execute(self, task: AlphaTask) -> AlphaOutput:
        """タスクを実行し、成果物を生成する"""
        messages = self._build_messages(task)
        best_output = None

        for iteration in range(task.max_iterations):
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=self.SYSTEM_PROMPT,
                messages=messages,
            )

            raw_text = response.content[0].text
            parsed = self._parse_response(raw_text, task)

            if best_output is None or parsed.revenue_potential > best_output.revenue_potential:
                best_output = parsed

            # 品質スコアが8以上なら早期終了
            quality_score = parsed.metadata.get("quality_score", 0)
            if quality_score >= 8:
                best_output.quality = OutputQuality.PREMIUM
                break

            # 次のイテレーションへの改善指示
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({
                "role": "user",
                "content": (
                    f"品質スコア: {quality_score}/10。さらに改善してください。"
                    f"改善メモ: {parsed.metadata.get('improvement_notes', '特になし')}"
                ),
            })

        self._save_output(best_output)
        self.history.append(best_output)
        return best_output

    def execute_batch(self, tasks: list[AlphaTask]) -> list[AlphaOutput]:
        """複数タスクをバッチ実行"""
        tasks_sorted = sorted(tasks, key=lambda t: t.priority, reverse=True)
        return [self.execute(task) for task in tasks_sorted]

    def receive_feedback(self, output_id: str, feedback: dict[str, Any]) -> AlphaOutput | None:
        """OMEGAからのフィードバックを受けて再生成する"""
        original = self._find_output(output_id)
        if not original:
            return None

        improved_task = AlphaTask(
            task_type=original.task_type,
            instruction=(
                f"以下の成果物を改善してください。\n\n"
                f"元の成果物:\n{original.content}\n\n"
                f"フィードバック:\n{json.dumps(feedback, ensure_ascii=False)}"
            ),
            context={"original_id": output_id, "feedback": feedback},
            priority=8,
            source="omega",
        )
        return self.execute(improved_task)

    def _build_messages(self, task: AlphaTask) -> list[dict]:
        """タスクからメッセージリストを構築"""
        user_content = f"タスク種別: {task.task_type.value}\n\n指示:\n{task.instruction}"

        if task.context:
            user_content += f"\n\nコンテキスト:\n{json.dumps(task.context, ensure_ascii=False, indent=2)}"

        if task.source == "omega":
            user_content += "\n\n[OMEGAからのフィードバックに基づく改善タスク]"

        return [{"role": "user", "content": user_content}]

    def _parse_response(self, raw_text: str, task: AlphaTask) -> AlphaOutput:
        """Claude応答をAlphaOutputにパース"""
        try:
            # JSON部分を抽出
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        content = parsed.get("content", raw_text)
        quality_score = parsed.get("quality_score", 5)
        revenue_strategy = parsed.get("revenue_strategy", "")

        # 収益ポテンシャルをスコアから概算
        revenue_potential = quality_score * 1000.0  # 仮の概算

        quality = OutputQuality.DRAFT
        if quality_score >= 8:
            quality = OutputQuality.PREMIUM
        elif quality_score >= 6:
            quality = OutputQuality.FINAL
        elif quality_score >= 4:
            quality = OutputQuality.REVIEW

        return AlphaOutput(
            task_type=task.task_type,
            content=content,
            quality=quality,
            metadata={
                "quality_score": quality_score,
                "revenue_strategy": revenue_strategy,
                "next_actions": parsed.get("next_actions", []),
                "improvement_notes": parsed.get("improvement_notes", ""),
                "source": task.source,
            },
            revenue_potential=revenue_potential,
        )

    def _save_output(self, output: AlphaOutput) -> None:
        """成果物をファイルに保存"""
        output_file = self.data_dir / f"{output.output_id}.json"
        output_file.write_text(
            json.dumps(output.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_output(self, output_id: str) -> AlphaOutput | None:
        """履歴からoutput_idで検索"""
        for output in self.history:
            if output.output_id == output_id:
                return output

        # ファイルからも検索
        output_file = self.data_dir / f"{output_id}.json"
        if output_file.exists():
            data = json.loads(output_file.read_text(encoding="utf-8"))
            return AlphaOutput(
                task_type=TaskType(data["task_type"]),
                content=data["content"],
                quality=OutputQuality(data["quality"]),
                metadata=data.get("metadata", {}),
                revenue_potential=data.get("revenue_potential", 0),
                timestamp=data.get("timestamp", ""),
                output_id=data.get("output_id", output_id),
            )
        return None

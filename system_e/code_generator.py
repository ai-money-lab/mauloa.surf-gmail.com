"""Code Generator — AI議論の結論からPythonコードを自動生成する.

AI同士の議論(debate)や進化(evolution)の結果を受け取り、
実行可能なPythonモジュールを生成する。

フロー:
    debate_result (JSON) → CodeGenerator → Python source code → file path
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
GENERATED_DIR = Path(__file__).parent.parent / "generated"

# 生成コードで禁止するパターン（セキュリティ）
FORBIDDEN_PATTERNS = [
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bcompile\s*\(",
    r"\bsubprocess\b",
    r"\bos\.system\s*\(",
    r"\bos\.popen\s*\(",
    r"\bshutil\.rmtree\s*\(",
    r"\bopen\s*\(.*(w|a)\+?\s*\)",  # 書き込みモードの open（生成コードからは禁止）
]


class CodeGenerationResult:
    """コード生成の結果を保持する."""

    def __init__(
        self,
        source_code: str,
        module_name: str,
        description: str,
        target_path: Path,
        generation_context: dict,
    ):
        self.source_code = source_code
        self.module_name = module_name
        self.description = description
        self.target_path = target_path
        self.generation_context = generation_context
        self.generated_at = datetime.now(JST).isoformat()

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "description": self.description,
            "target_path": str(self.target_path),
            "generated_at": self.generated_at,
            "source_lines": self.source_code.count("\n") + 1,
            "generation_context": self.generation_context,
        }


class CodeGenerator:
    """AI議論結果からPythonコードを生成するエンジン.

    議論のaction_plan, key_insights, final_decisionを解析し、
    実装可能なPythonモジュールに変換する。
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    def generate_from_debate(self, debate_result: dict) -> CodeGenerationResult:
        """議論結果からコードを生成する.

        Args:
            debate_result: DebateProtocol.run_debate() の戻り値。
                synthesis.action_plan が主な入力。

        Returns:
            CodeGenerationResult: 生成されたコードとメタデータ。
        """
        synthesis = debate_result.get("synthesis", {})
        if isinstance(synthesis, str):
            synthesis = {"raw_response": synthesis}

        action_plan = synthesis.get("action_plan", [])
        key_insights = synthesis.get("key_insights", [])
        final_decision = synthesis.get("final_decision", "")
        topic = debate_result.get("topic", "unknown")

        logger.info(
            "[CodeGen] Generating from debate: topic=%s, actions=%d",
            topic[:60],
            len(action_plan),
        )

        # モジュール名を決定
        module_name = self._derive_module_name(topic)
        target_path = GENERATED_DIR / f"{module_name}.py"

        # AIにコード生成を依頼
        source_code = self._generate_code(
            topic=topic,
            action_plan=action_plan,
            key_insights=key_insights,
            final_decision=final_decision,
        )

        # セキュリティチェック
        source_code = self._sanitize(source_code)

        return CodeGenerationResult(
            source_code=source_code,
            module_name=module_name,
            description=f"Auto-generated from debate: {topic}",
            target_path=target_path,
            generation_context={
                "source": "debate",
                "topic": topic,
                "action_count": len(action_plan),
                "insight_count": len(key_insights),
            },
        )

    def generate_from_evolution(self, evolution_result: dict) -> CodeGenerationResult:
        """進化結果からコードを生成する.

        Args:
            evolution_result: EvolutionEngine.evolve_strategy() の戻り値。

        Returns:
            CodeGenerationResult: 生成されたコードとメタデータ。
        """
        version = evolution_result.get("version", 0)
        history = evolution_result.get("optimization_history", [])
        latest_changes = history[-1].get("changes", []) if history else []

        logger.info(
            "[CodeGen] Generating from evolution: v%d, changes=%d",
            version,
            len(latest_changes),
        )

        module_name = f"evolution_v{version}"
        target_path = GENERATED_DIR / f"{module_name}.py"

        source_code = self._generate_evolution_code(
            version=version,
            changes=latest_changes,
            strategy=evolution_result,
        )

        source_code = self._sanitize(source_code)

        return CodeGenerationResult(
            source_code=source_code,
            module_name=module_name,
            description=f"Auto-generated from evolution v{version}",
            target_path=target_path,
            generation_context={
                "source": "evolution",
                "version": version,
                "change_count": len(latest_changes),
            },
        )

    def generate_module(
        self,
        spec: dict,
    ) -> CodeGenerationResult:
        """仕様書(spec)からモジュールを生成する.

        Args:
            spec: モジュール仕様。必須キー:
                - name: モジュール名
                - purpose: 目的
                - functions: 関数定義のリスト
                - dependencies: 依存モジュール
        """
        name = spec.get("name", "unnamed_module")
        purpose = spec.get("purpose", "")
        functions = spec.get("functions", [])
        dependencies = spec.get("dependencies", [])

        logger.info("[CodeGen] Generating module: %s", name)

        target_path = GENERATED_DIR / f"{name}.py"

        source_code = self._generate_module_code(
            name=name,
            purpose=purpose,
            functions=functions,
            dependencies=dependencies,
        )

        source_code = self._sanitize(source_code)

        return CodeGenerationResult(
            source_code=source_code,
            module_name=name,
            description=purpose,
            target_path=target_path,
            generation_context={
                "source": "spec",
                "function_count": len(functions),
                "dependencies": dependencies,
            },
        )

    def _generate_code(
        self,
        topic: str,
        action_plan: list,
        key_insights: list,
        final_decision: str,
    ) -> str:
        """AIを使って議論結果からPythonコードを生成."""
        prompt = f"""以下のAI議論の結論に基づき、実装可能なPythonモジュールを生成してください。

## 議論トピック
{topic}

## 最終決定
{final_decision}

## 重要な洞察
{json.dumps(key_insights, ensure_ascii=False, indent=2)}

## アクションプラン
{json.dumps(action_plan, ensure_ascii=False, indent=2)}

## コード生成ルール
1. 完全に動作するPythonモジュールを1つ生成すること
2. 型ヒントを使用すること
3. docstringを含めること
4. logging モジュールを使用すること（print禁止）
5. eval(), exec(), subprocess, os.system は絶対に使わないこと
6. 外部APIキーをハードコードしないこと
7. エラーハンドリングを含めること
8. テスト可能な構造にすること（クラスベース推奨）

## 出力形式
Pythonコードのみを出力してください。マークダウンのコードブロックで囲んでください。
```python
# ここにコード
```"""

        raw = self.claude.generate(
            prompt=prompt,
            system=(
                "あなたはPythonコード生成の専門AIです。"
                "AI議論の結論を実装可能なPythonモジュールに変換します。"
                "安全で、テスト可能で、本番品質のコードを生成してください。"
            ),
            temperature=0.3,
            max_tokens=4096,
        )

        return self._extract_code(raw)

    def _generate_evolution_code(
        self,
        version: int,
        changes: list,
        strategy: dict,
    ) -> str:
        """進化結果をPythonコードに変換."""
        prompt = f"""以下の戦略進化の結果に基づき、戦略を実装するPythonモジュールを生成してください。

## 戦略バージョン
v{version}

## 変更点
{json.dumps(changes, ensure_ascii=False, indent=2)}

## 現在の戦略全体
{json.dumps(strategy, ensure_ascii=False, indent=2)}

## コード生成ルール
1. 戦略の変更点を実装するPythonクラスを生成すること
2. 設定値はクラス属性またはdataclassで定義すること
3. 前バージョンとの差分が明確にわかるコメントを入れること
4. 型ヒントを使用すること
5. eval(), exec(), subprocess は絶対に使わないこと

## 出力形式
Pythonコードのみを出力してください。マークダウンのコードブロックで囲んでください。
```python
# ここにコード
```"""

        raw = self.claude.generate(
            prompt=prompt,
            system=(
                "あなたはPythonコード生成の専門AIです。"
                "戦略進化の結果を実装可能なPythonモジュールに変換します。"
            ),
            temperature=0.3,
            max_tokens=4096,
        )

        return self._extract_code(raw)

    def _generate_module_code(
        self,
        name: str,
        purpose: str,
        functions: list,
        dependencies: list,
    ) -> str:
        """モジュール仕様からPythonコードを生成."""
        prompt = f"""以下の仕様に基づきPythonモジュールを生成してください。

## モジュール名
{name}

## 目的
{purpose}

## 関数定義
{json.dumps(functions, ensure_ascii=False, indent=2)}

## 依存モジュール
{json.dumps(dependencies, ensure_ascii=False, indent=2)}

## コード生成ルール
1. 仕様に忠実に実装すること
2. 型ヒントを使用すること
3. docstringを含めること
4. logging モジュールを使用すること
5. eval(), exec(), subprocess, os.system は絶対に使わないこと
6. テスト可能な構造にすること

## 出力形式
Pythonコードのみを出力してください。マークダウンのコードブロックで囲んでください。
```python
# ここにコード
```"""

        raw = self.claude.generate(
            prompt=prompt,
            system=(
                "あなたはPythonコード生成の専門AIです。"
                "仕様書から本番品質のPythonモジュールを生成します。"
            ),
            temperature=0.3,
            max_tokens=4096,
        )

        return self._extract_code(raw)

    def _extract_code(self, raw: str) -> str:
        """AIレスポンスからPythonコードを抽出."""
        text = raw.strip()

        # ```python ... ``` ブロックを抽出
        match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # ``` ... ``` ブロックを抽出
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # コードブロックなしの場合、そのまま返す
        return text

    def _sanitize(self, code: str) -> str:
        """生成コードのセキュリティチェック.

        危険なパターンを検出した場合、該当行をコメントアウトする。
        """
        lines = code.split("\n")
        sanitized = []

        for line in lines:
            flagged = False
            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    sanitized.append(f"# SECURITY: removed → {line.strip()}")
                    logger.warning(
                        "[CodeGen] Sanitized forbidden pattern: %s", line.strip()
                    )
                    flagged = True
                    break
            if not flagged:
                sanitized.append(line)

        return "\n".join(sanitized)

    def _derive_module_name(self, topic: str) -> str:
        """トピック文字列からPythonモジュール名を導出."""
        # 日本語トピックから英語モジュール名を生成
        timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        # 簡単な変換: 全角→半角、空白→アンダースコア
        name = re.sub(r"[^\w]", "_", topic[:40])
        name = re.sub(r"_+", "_", name).strip("_").lower()
        if not name or not name[0].isalpha():
            name = f"debate_{timestamp}"
        return name

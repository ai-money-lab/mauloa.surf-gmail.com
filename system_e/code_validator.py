"""Code Validator — 生成されたPythonコードの安全性と品質を検証する.

検証ステップ:
    1. 構文チェック (ast.parse)
    2. セキュリティスキャン (禁止パターン検出)
    3. ruff lint チェック
    4. インポート解決チェック
"""

import ast
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from system_e.code_generator import CodeGenerationResult, FORBIDDEN_PATTERNS

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """検証で発見された問題."""

    severity: str  # "error", "warning", "info"
    category: str  # "syntax", "security", "lint", "import"
    message: str
    line: Optional[int] = None


@dataclass
class ValidationResult:
    """検証の全体結果."""

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    syntax_ok: bool = False
    security_ok: bool = False
    lint_ok: bool = False
    import_ok: bool = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "syntax_ok": self.syntax_ok,
            "security_ok": self.security_ok,
            "lint_ok": self.lint_ok,
            "import_ok": self.import_ok,
            "issue_count": len(self.issues),
            "errors": [
                {"category": i.category, "message": i.message, "line": i.line}
                for i in self.issues
                if i.severity == "error"
            ],
            "warnings": [
                {"category": i.category, "message": i.message, "line": i.line}
                for i in self.issues
                if i.severity == "warning"
            ],
        }


class CodeValidator:
    """生成コードの品質と安全性を検証するエンジン."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent

    def validate(self, gen_result: CodeGenerationResult) -> ValidationResult:
        """生成コードの全検証を実行.

        Args:
            gen_result: CodeGenerator が返した CodeGenerationResult。

        Returns:
            ValidationResult: 検証結果。passed=True なら安全。
        """
        code = gen_result.source_code
        issues: list[ValidationIssue] = []

        # 1. 構文チェック
        syntax_ok = self._check_syntax(code, issues)

        # 2. セキュリティスキャン
        security_ok = self._check_security(code, issues)

        # 3. ruff lint
        lint_ok = self._check_lint(code, gen_result.target_path, issues)

        # 4. インポート解決
        import_ok = self._check_imports(code, issues)

        passed = syntax_ok and security_ok and (not any(
            i.severity == "error" and i.category == "lint" for i in issues
        ))

        result = ValidationResult(
            passed=passed,
            issues=issues,
            syntax_ok=syntax_ok,
            security_ok=security_ok,
            lint_ok=lint_ok,
            import_ok=import_ok,
        )

        if passed:
            logger.info("[Validator] Code passed all checks: %s", gen_result.module_name)
        else:
            error_count = sum(1 for i in issues if i.severity == "error")
            logger.warning(
                "[Validator] Code FAILED validation: %s (%d errors)",
                gen_result.module_name,
                error_count,
            )

        return result

    def _check_syntax(self, code: str, issues: list[ValidationIssue]) -> bool:
        """Pythonの構文チェック."""
        try:
            ast.parse(code)
            logger.info("[Validator] Syntax check: OK")
            return True
        except SyntaxError as e:
            issues.append(ValidationIssue(
                severity="error",
                category="syntax",
                message=f"SyntaxError: {e.msg}",
                line=e.lineno,
            ))
            logger.error("[Validator] Syntax error at line %s: %s", e.lineno, e.msg)
            return False

    def _check_security(self, code: str, issues: list[ValidationIssue]) -> bool:
        """セキュリティ上の危険なパターンを検出."""
        found_issues = False

        for i, line in enumerate(code.split("\n"), 1):
            # コメント行はスキップ（サニタイズ済み行含む）
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    issues.append(ValidationIssue(
                        severity="error",
                        category="security",
                        message=f"Forbidden pattern detected: {pattern}",
                        line=i,
                    ))
                    found_issues = True

        # 追加チェック: ハードコードされた秘密情報
        secret_patterns = [
            r"(?:api_key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]",
            r"sk-[a-zA-Z0-9]{20,}",
            r"AKIA[A-Z0-9]{16}",
        ]
        for i, line in enumerate(code.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(ValidationIssue(
                        severity="error",
                        category="security",
                        message="Possible hardcoded secret detected",
                        line=i,
                    ))
                    found_issues = True

        if not found_issues:
            logger.info("[Validator] Security check: OK")
        return not found_issues

    def _check_lint(
        self,
        code: str,
        target_path: Path,
        issues: list[ValidationIssue],
    ) -> bool:
        """ruff を使ったlintチェック."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--stdin-filename",
                 str(target_path), "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("[Validator] Lint check: OK")
                return True

            # ruff の出力をパース
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # ruff出力: path:line:col: CODE message
                match = re.match(r".*?:(\d+):\d+:\s+(\S+)\s+(.*)", line)
                if match:
                    line_no = int(match.group(1))
                    rule = match.group(2)
                    msg = match.group(3)
                    # E501 (行長) は warning、それ以外の E/F は error
                    severity = "warning" if rule == "E501" else "error"
                    issues.append(ValidationIssue(
                        severity=severity,
                        category="lint",
                        message=f"{rule}: {msg}",
                        line=line_no,
                    ))

            has_errors = any(
                i.severity == "error" and i.category == "lint" for i in issues
            )
            return not has_errors

        except FileNotFoundError:
            logger.warning("[Validator] ruff not found, skipping lint check")
            issues.append(ValidationIssue(
                severity="info",
                category="lint",
                message="ruff not installed, lint check skipped",
            ))
            return True
        except subprocess.TimeoutExpired:
            logger.warning("[Validator] ruff timed out")
            issues.append(ValidationIssue(
                severity="warning",
                category="lint",
                message="ruff check timed out",
            ))
            return True

    def _check_imports(self, code: str, issues: list[ValidationIssue]) -> bool:
        """インポートが解決可能かチェック."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()

        all_ok = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in stdlib_modules:
                        continue
                    # プロジェクト内モジュールは許可
                    if self._is_project_module(top):
                        continue
                    # サードパーティはインストール済みか確認
                    if not self._is_importable(top):
                        issues.append(ValidationIssue(
                            severity="warning",
                            category="import",
                            message=f"Module '{alias.name}' may not be available",
                            line=node.lineno,
                        ))

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in stdlib_modules:
                        continue
                    if self._is_project_module(top):
                        continue
                    if not self._is_importable(top):
                        issues.append(ValidationIssue(
                            severity="warning",
                            category="import",
                            message=f"Module '{node.module}' may not be available",
                            line=node.lineno,
                        ))

        if all_ok:
            logger.info("[Validator] Import check: OK")
        return all_ok

    def _is_project_module(self, name: str) -> bool:
        """プロジェクト内のモジュールか判定."""
        project_modules = {
            "system_e", "system_a", "system_b", "system_c", "system_d",
            "nexus", "core", "inquiry_bot", "config", "generated",
        }
        return name in project_modules

    def _is_importable(self, name: str) -> bool:
        """モジュールがインポート可能か確認."""
        import importlib.util
        try:
            return importlib.util.find_spec(name) is not None
        except (ModuleNotFoundError, ValueError):
            return False

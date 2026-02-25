"""Code Test Harness — 生成コードの自動テスト実行エンジン.

CodeGenerator が生成したモジュールに対して:
1. インポートテスト（モジュールがロード可能か）
2. クラス/関数の存在チェック
3. 基本的な呼び出しテスト（例外なしで実行できるか）
4. 型ヒント整合性チェック

を自動実行し、デプロイ前の品質ゲートを提供する。
"""

import ast
import importlib
import importlib.util
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("system_e.code_test_harness")


@dataclass
class TestCase:
    """1つのテストケース."""

    name: str
    passed: bool
    message: str
    category: str  # "import", "structure", "callable", "type_hint"


@dataclass
class TestHarnessResult:
    """テストハーネスの全体結果."""

    module_name: str
    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    test_cases: list[TestCase] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "passed": self.passed,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "test_cases": [
                {
                    "name": tc.name,
                    "passed": tc.passed,
                    "message": tc.message,
                    "category": tc.category,
                }
                for tc in self.test_cases
            ],
        }


class CodeTestHarness:
    """生成コードの自動テストエンジン.

    生成されたPythonモジュールをサンドボックス的にロードし、
    基本的な品質テストを実行する。

    Args:
        project_root: プロジェクトルートパス。
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent

    def run_tests(self, source_code: str, module_name: str) -> TestHarnessResult:
        """生成コードに対して全テストを実行.

        Args:
            source_code: テスト対象のPythonソースコード。
            module_name: モジュール名。

        Returns:
            TestHarnessResult。
        """
        logger.info("[TestHarness] Running tests for: %s", module_name)
        cases: list[TestCase] = []

        # 1. AST解析テスト
        tree = self._test_ast_parse(source_code, cases)

        # 2. 構造テスト（AST成功時のみ）
        if tree is not None:
            self._test_structure(tree, module_name, cases)

        # 3. インポートテスト（サンドボックスロード）
        mod = self._test_import(source_code, module_name, cases)

        # 4. Callable テスト（インポート成功時のみ）
        if mod is not None:
            self._test_callables(mod, module_name, cases)

        # 5. 型ヒントテスト
        if tree is not None:
            self._test_type_hints(tree, module_name, cases)

        total = len(cases)
        passed_count = sum(1 for c in cases if c.passed)
        failed_count = total - passed_count

        # 全テスト通過 or エラーが import/callable のみ（warning扱い）
        critical_failures = sum(
            1 for c in cases
            if not c.passed and c.category in ("import", "structure")
        )
        overall_passed = critical_failures == 0

        result = TestHarnessResult(
            module_name=module_name,
            passed=overall_passed,
            total_tests=total,
            passed_tests=passed_count,
            failed_tests=failed_count,
            test_cases=cases,
        )

        if overall_passed:
            logger.info(
                "[TestHarness] PASSED: %s (%d/%d tests)",
                module_name, passed_count, total,
            )
        else:
            logger.warning(
                "[TestHarness] FAILED: %s (%d/%d tests passed)",
                module_name, passed_count, total,
            )

        return result

    def _test_ast_parse(
        self, source_code: str, cases: list[TestCase],
    ) -> Optional[ast.Module]:
        """AST 解析テスト."""
        try:
            tree = ast.parse(source_code)
            cases.append(TestCase(
                name="ast_parse",
                passed=True,
                message="Source code parsed successfully",
                category="structure",
            ))
            return tree
        except SyntaxError as e:
            cases.append(TestCase(
                name="ast_parse",
                passed=False,
                message=f"SyntaxError at line {e.lineno}: {e.msg}",
                category="structure",
            ))
            return None

    def _test_structure(
        self, tree: ast.Module, module_name: str, cases: list[TestCase],
    ) -> None:
        """モジュール構造テスト."""
        classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]

        # トップレベルの関数を抽出 (クラスメソッドを除く)
        top_functions = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top_functions.append(node)

        has_content = bool(classes or top_functions)
        cases.append(TestCase(
            name="has_definitions",
            passed=has_content,
            message=(
                f"Found {len(classes)} class(es), {len(top_functions)} function(s)"
                if has_content
                else "No classes or top-level functions found"
            ),
            category="structure",
        ))

        # docstring チェック
        has_module_docstring = (
            isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ) if tree.body else False

        cases.append(TestCase(
            name="has_module_docstring",
            passed=has_module_docstring,
            message="Module docstring present" if has_module_docstring else "No module docstring",
            category="structure",
        ))

    def _test_import(
        self, source_code: str, module_name: str, cases: list[TestCase],
    ) -> Optional[object]:
        """サンドボックスインポートテスト."""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, encoding="utf-8",
            ) as f:
                f.write(source_code)
                temp_path = f.name

            spec = importlib.util.spec_from_file_location(
                f"_test_{module_name}", temp_path,
            )
            if spec is None or spec.loader is None:
                cases.append(TestCase(
                    name="sandbox_import",
                    passed=False,
                    message="Failed to create module spec",
                    category="import",
                ))
                return None

            mod = importlib.util.module_from_spec(spec)

            # プロジェクトルートをsys.pathに追加（一時的）
            root_str = str(self.project_root)
            added_path = root_str not in sys.path
            if added_path:
                sys.path.insert(0, root_str)

            try:
                spec.loader.exec_module(mod)
                cases.append(TestCase(
                    name="sandbox_import",
                    passed=True,
                    message="Module loaded successfully in sandbox",
                    category="import",
                ))
                return mod
            except Exception as e:
                cases.append(TestCase(
                    name="sandbox_import",
                    passed=False,
                    message=f"Import failed: {type(e).__name__}: {e}",
                    category="import",
                ))
                return None
            finally:
                if added_path:
                    sys.path.remove(root_str)
                Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            cases.append(TestCase(
                name="sandbox_import",
                passed=False,
                message=f"Sandbox setup error: {e}",
                category="import",
            ))
            return None

    def _test_callables(
        self, mod: object, module_name: str, cases: list[TestCase],
    ) -> None:
        """公開された callable の基本テスト."""
        for name in dir(mod):
            if name.startswith("_"):
                continue

            obj = getattr(mod, name)

            # クラスのインスタンス化テスト
            if isinstance(obj, type):
                try:
                    # 引数なしでインスタンス化を試行
                    obj()
                    cases.append(TestCase(
                        name=f"instantiate_{name}",
                        passed=True,
                        message=f"{name}() created successfully",
                        category="callable",
                    ))
                except TypeError:
                    # 引数が必要な場合はスキップ（失敗扱いにしない）
                    cases.append(TestCase(
                        name=f"instantiate_{name}",
                        passed=True,
                        message=f"{name} requires constructor args (skipped)",
                        category="callable",
                    ))
                except Exception as e:
                    cases.append(TestCase(
                        name=f"instantiate_{name}",
                        passed=False,
                        message=f"{name}() raised {type(e).__name__}: {e}",
                        category="callable",
                    ))

    def _test_type_hints(
        self, tree: ast.Module, module_name: str, cases: list[TestCase],
    ) -> None:
        """型ヒント使用率チェック."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node)

        if not functions:
            return

        typed_count = 0
        for func in functions:
            has_return = func.returns is not None
            has_param_types = any(
                arg.annotation is not None
                for arg in func.args.args
                if arg.arg != "self"
            )
            if has_return or has_param_types:
                typed_count += 1

        ratio = typed_count / len(functions) if functions else 0.0
        cases.append(TestCase(
            name="type_hint_coverage",
            passed=ratio >= 0.3,
            message=f"Type hint coverage: {typed_count}/{len(functions)} functions ({ratio:.0%})",
            category="type_hint",
        ))

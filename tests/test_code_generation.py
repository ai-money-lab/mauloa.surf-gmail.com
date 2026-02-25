"""Tests for System E: Code Generation Engine (generator, validator, deployer)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from system_e.code_generator import (
    CodeGenerator,
    CodeGenerationResult,
)
from system_e.code_validator import CodeValidator, ValidationResult, ValidationIssue
from system_e.code_deployer import CodeDeployer, DeploymentResult


# ─── CodeGenerationResult Tests ─────────────────────────


class TestCodeGenerationResult:
    def test_to_dict(self, tmp_path):
        result = CodeGenerationResult(
            source_code="print('hello')",
            module_name="test_module",
            description="A test module",
            target_path=tmp_path / "test_module.py",
            generation_context={"source": "test"},
        )
        d = result.to_dict()
        assert d["module_name"] == "test_module"
        assert d["description"] == "A test module"
        assert d["source_lines"] == 1
        assert d["generation_context"]["source"] == "test"
        assert "generated_at" in d

    def test_multiline_source_lines(self, tmp_path):
        code = "import os\n\ndef main():\n    pass\n"
        result = CodeGenerationResult(
            source_code=code,
            module_name="multi",
            description="",
            target_path=tmp_path / "multi.py",
            generation_context={},
        )
        assert result.to_dict()["source_lines"] == 5


# ─── CodeGenerator Tests ────────────────────────────────


class TestCodeGenerator:
    @patch("system_e.code_generator.ClaudeClient")
    def test_generate_from_debate(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = (
            '```python\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
            'class Strategy:\n    """Auto-generated strategy."""\n\n'
            '    def execute(self) -> str:\n        logger.info("Executing")\n'
            '        return "done"\n```'
        )

        gen = CodeGenerator(claude_client=mock_client)
        debate_result = {
            "topic": "テスト戦略",
            "synthesis": {
                "action_plan": [{"action": "implement strategy", "priority": "high"}],
                "key_insights": ["insight1"],
                "final_decision": "proceed with strategy",
            },
        }

        result = gen.generate_from_debate(debate_result)

        assert isinstance(result, CodeGenerationResult)
        assert "class Strategy" in result.source_code
        assert result.module_name  # not empty
        assert result.generation_context["source"] == "debate"
        mock_client.generate.assert_called_once()

    @patch("system_e.code_generator.ClaudeClient")
    def test_generate_from_evolution(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = (
            '```python\nfrom dataclasses import dataclass\n\n\n@dataclass\n'
            'class EvolutionConfig:\n    version: int = 3\n```'
        )

        gen = CodeGenerator(claude_client=mock_client)
        evo_result = {
            "version": 3,
            "optimization_history": [
                {"changes": ["changed timing", "added hook"]},
            ],
            "posting_strategy": {},
        }

        result = gen.generate_from_evolution(evo_result)

        assert isinstance(result, CodeGenerationResult)
        assert "EvolutionConfig" in result.source_code
        assert result.module_name == "evolution_v3"
        assert result.generation_context["source"] == "evolution"

    @patch("system_e.code_generator.ClaudeClient")
    def test_generate_module_from_spec(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = (
            '```python\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
            'def greet(name: str) -> str:\n    """Greet someone."""\n'
            '    return f"Hello, {name}"\n```'
        )

        gen = CodeGenerator(claude_client=mock_client)
        spec = {
            "name": "greeter",
            "purpose": "Greeting utility",
            "functions": [{"name": "greet", "args": ["name: str"], "returns": "str"}],
            "dependencies": [],
        }

        result = gen.generate_module(spec)

        assert result.module_name == "greeter"
        assert "greet" in result.source_code
        assert result.generation_context["source"] == "spec"

    @patch("system_e.code_generator.ClaudeClient")
    def test_sanitize_removes_eval(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        dangerous_code = 'result = eval("1+1")\nprint(result)'
        sanitized = gen._sanitize(dangerous_code)

        assert "eval" not in sanitized.split("\n")[0] or "SECURITY" in sanitized.split("\n")[0]

    @patch("system_e.code_generator.ClaudeClient")
    def test_sanitize_removes_exec(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        dangerous_code = 'exec("import os")\nx = 1'
        sanitized = gen._sanitize(dangerous_code)

        assert "SECURITY" in sanitized.split("\n")[0]

    @patch("system_e.code_generator.ClaudeClient")
    def test_sanitize_preserves_safe_code(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        safe_code = "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('ok')"
        sanitized = gen._sanitize(safe_code)

        assert sanitized == safe_code

    @patch("system_e.code_generator.ClaudeClient")
    def test_extract_code_python_block(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        raw = "Here is the code:\n```python\nx = 1\n```\nDone."
        assert gen._extract_code(raw) == "x = 1"

    @patch("system_e.code_generator.ClaudeClient")
    def test_extract_code_plain_block(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        raw = "```\ny = 2\n```"
        assert gen._extract_code(raw) == "y = 2"

    @patch("system_e.code_generator.ClaudeClient")
    def test_extract_code_no_block(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        raw = "import os\nprint('hi')"
        assert gen._extract_code(raw) == raw

    @patch("system_e.code_generator.ClaudeClient")
    def test_derive_module_name(self, mock_client_cls):
        mock_client = MagicMock()
        gen = CodeGenerator(claude_client=mock_client)

        name = gen._derive_module_name("テスト戦略の実装")
        assert name  # not empty
        assert " " not in name

    @patch("system_e.code_generator.ClaudeClient")
    def test_generate_from_debate_string_synthesis(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = '```python\nx = 1\n```'

        gen = CodeGenerator(claude_client=mock_client)
        debate_result = {
            "topic": "test",
            "synthesis": "raw string synthesis",
        }

        result = gen.generate_from_debate(debate_result)
        assert isinstance(result, CodeGenerationResult)
        assert result.generation_context["action_count"] == 0


# ─── CodeValidator Tests ────────────────────────────────


class TestCodeValidator:
    def _make_gen_result(self, code: str, tmp_path: Path) -> CodeGenerationResult:
        return CodeGenerationResult(
            source_code=code,
            module_name="test_mod",
            description="test",
            target_path=tmp_path / "test_mod.py",
            generation_context={"source": "test"},
        )

    def test_valid_code_passes(self, tmp_path):
        code = "import logging\n\nlogger = logging.getLogger(__name__)\n\nx = 1\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.syntax_ok is True
        assert result.security_ok is True
        assert result.passed is True

    def test_syntax_error_fails(self, tmp_path):
        code = "def foo(\n    pass"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.syntax_ok is False
        assert result.passed is False
        assert any(i.category == "syntax" for i in result.issues)

    def test_security_eval_fails(self, tmp_path):
        code = "x = eval('1+1')\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.security_ok is False
        assert result.passed is False
        assert any(i.category == "security" for i in result.issues)

    def test_security_exec_fails(self, tmp_path):
        code = "exec('import os')\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.security_ok is False
        assert any(i.category == "security" for i in result.issues)

    def test_security_subprocess_fails(self, tmp_path):
        code = "import subprocess\nsubprocess.run(['ls'])\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.security_ok is False

    def test_security_comment_lines_ignored(self, tmp_path):
        code = "# eval('this is a comment')\nx = 1\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.security_ok is True

    def test_hardcoded_secret_detected(self, tmp_path):
        code = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz"\n'
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)

        assert result.security_ok is False
        assert any("secret" in i.message.lower() or "security" in i.category for i in result.issues)

    def test_to_dict(self, tmp_path):
        code = "x = 1\n"
        gen_result = self._make_gen_result(code, tmp_path)

        validator = CodeValidator()
        result = validator.validate(gen_result)
        d = result.to_dict()

        assert "passed" in d
        assert "syntax_ok" in d
        assert "security_ok" in d
        assert "errors" in d
        assert "warnings" in d

    def test_is_project_module(self):
        validator = CodeValidator()
        assert validator._is_project_module("system_e") is True
        assert validator._is_project_module("nexus") is True
        assert validator._is_project_module("nonexistent_xyz") is False

    def test_is_importable(self):
        validator = CodeValidator()
        assert validator._is_importable("json") is True
        assert validator._is_importable("totally_fake_module_xyz") is False


# ─── CodeDeployer Tests ─────────────────────────────────


class TestCodeDeployer:
    def _make_gen_result(self, tmp_path: Path) -> CodeGenerationResult:
        return CodeGenerationResult(
            source_code="import logging\n\nx = 1\n",
            module_name="test_deploy",
            description="Test deploy module",
            target_path=tmp_path / "generated" / "test_deploy.py",
            generation_context={"source": "test"},
        )

    def _make_val_result(self, passed: bool) -> ValidationResult:
        issues = []
        if not passed:
            issues.append(ValidationIssue(
                severity="error",
                category="syntax",
                message="SyntaxError",
            ))
        return ValidationResult(
            passed=passed,
            issues=issues,
            syntax_ok=passed,
            security_ok=True,
            lint_ok=True,
            import_ok=True,
        )

    def test_deploy_fails_if_validation_not_passed(self, tmp_path):
        deployer = CodeDeployer(project_root=tmp_path)
        gen_result = self._make_gen_result(tmp_path)
        val_result = self._make_val_result(passed=False)

        result = deployer.deploy(gen_result, val_result)

        assert result.success is False
        assert "Validation failed" in result.error

    @patch("system_e.code_deployer.subprocess.run")
    def test_deploy_writes_file_and_commits(self, mock_run, tmp_path):
        # Mock git commands
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123def\n",
            stderr="",
        )

        deployer = CodeDeployer(project_root=tmp_path, auto_push=False)
        gen_result = self._make_gen_result(tmp_path)
        val_result = self._make_val_result(passed=True)

        result = deployer.deploy(gen_result, val_result)

        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.exists()

        # ファイルの中身にヘッダーが含まれる
        content = result.file_path.read_text()
        assert "Auto-generated by System E" in content
        assert "import logging" in content

        # git add と git commit が呼ばれた
        assert mock_run.call_count >= 2  # add + commit + rev-parse

    @patch("system_e.code_deployer.subprocess.run")
    def test_deploy_with_auto_push(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123def\n",
            stderr="",
        )

        deployer = CodeDeployer(project_root=tmp_path, auto_push=True)
        gen_result = self._make_gen_result(tmp_path)
        val_result = self._make_val_result(passed=True)

        result = deployer.deploy(gen_result, val_result)

        assert result.success is True
        # git push も呼ばれる
        push_calls = [c for c in mock_run.call_args_list if "push" in str(c)]
        assert len(push_calls) >= 1

    @patch("system_e.code_deployer.subprocess.run")
    def test_deploy_git_failure(self, mock_run, tmp_path):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "git", stderr="fatal error")

        deployer = CodeDeployer(project_root=tmp_path)
        gen_result = self._make_gen_result(tmp_path)
        val_result = self._make_val_result(passed=True)

        result = deployer.deploy(gen_result, val_result)

        assert result.success is False
        assert result.error is not None

    def test_deployment_result_to_dict(self):
        result = DeploymentResult(
            success=True,
            file_path=Path("/tmp/test.py"),
            commit_hash="abc123",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["commit_hash"] == "abc123"
        assert "deployed_at" in d

    def test_deployment_result_failure(self):
        result = DeploymentResult(
            success=False,
            error="Something went wrong",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Something went wrong"
        assert d["file_path"] is None


# ─── Orchestrator CodeGen Integration Tests ─────────────


class TestOrchestratorCodeGen:
    @patch("system_e.orchestrator.ClaudeClient")
    def test_orchestrator_has_codegen(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        from system_e.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_client)

        assert orch.codegen is not None
        assert orch.validator is not None
        assert orch.deployer is not None

    @patch("system_e.code_deployer.subprocess.run")
    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_codegen(self, mock_client_cls, mock_subprocess):
        mock_client = MagicMock()
        # debate rounds + synthesis + codegen
        mock_client.generate.return_value = json.dumps({
            "analysis": "test",
            "confidence": 0.8,
            "consensus": "proceed",
            "key_insights": ["insight"],
            "final_decision": "implement",
            "action_plan": [{"action": "build", "priority": "high"}],
            "disagreements": [],
            "meta_learning": "learned",
        })
        mock_client_cls.return_value = mock_client

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="abc123\n",
            stderr="",
        )

        from system_e.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_client)
        result = orch.run_codegen("テスト機能の実装")

        assert "debate" in result
        assert "generation" in result
        assert "validation" in result
        assert "deployment" in result

    @patch("system_e.code_deployer.subprocess.run")
    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_full_cycle_includes_codegen(self, mock_client_cls, mock_subprocess):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "analysis": "ok",
            "changes": ["変更"],
            "posting_strategy": {},
            "content_strategy": {},
            "confidence": 0.8,
            "summary": "正常",
            "consensus": "合意",
            "key_insights": ["洞察"],
            "final_decision": "実行",
            "action_plan": [],
            "disagreements": [],
            "meta_learning": "学び",
            "system_scores": {"E": 85},
            "highlights": ["良い"],
            "concerns": [],
            "priorities": ["最適化"],
            "evolution_recommendations": ["進化"],
        })
        mock_client_cls.return_value = mock_client

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="abc123\n",
            stderr="",
        )

        from system_e.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_client)
        result = orch.run_full_cycle()

        assert "codegen" in result
        assert "diagnosis" in result
        assert "debate" in result
        assert "evolution" in result
        assert "report" in result

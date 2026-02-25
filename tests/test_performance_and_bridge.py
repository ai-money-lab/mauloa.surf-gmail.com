"""Tests for System E: Performance Tracker and NEXUS Bridge."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from system_e.performance_tracker import PerformanceTracker
from system_e.nexus_bridge import NexusBridge
from system_e.orchestrator import Orchestrator


# ─── PerformanceTracker Tests ────────────────────────────


class TestPerformanceTrackerLoadLog:
    def test_load_empty_log(self, tmp_path):
        tracker = PerformanceTracker(log_path=tmp_path / "nonexistent.jsonl")
        assert tracker.load_orchestrator_log() == []

    def test_load_valid_log(self, tmp_path):
        log_file = tmp_path / "log.jsonl"
        entries = [
            {"timestamp": "2026-01-01T00:00:00", "action": "debate", "details": {}},
            {"timestamp": "2026-01-02T00:00:00", "action": "evolve", "details": {}},
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )
        tracker = PerformanceTracker(log_path=log_file)
        result = tracker.load_orchestrator_log()
        assert len(result) == 2
        assert result[0]["action"] == "debate"

    def test_load_log_skips_malformed_lines(self, tmp_path):
        log_file = tmp_path / "log.jsonl"
        log_file.write_text(
            '{"action": "debate"}\nINVALID\n{"action": "evolve"}\n',
            encoding="utf-8",
        )
        tracker = PerformanceTracker(log_path=log_file)
        result = tracker.load_orchestrator_log()
        assert len(result) == 2


class TestPerformanceTrackerNexusData:
    def test_load_nexus_cycle_history_empty(self, tmp_path):
        tracker = PerformanceTracker(nexus_data_dir=tmp_path / "nonexistent")
        assert tracker.load_nexus_cycle_history() == []

    def test_load_nexus_cycle_history(self, tmp_path):
        nexus_dir = tmp_path / "nexus"
        nexus_dir.mkdir()
        history = [
            {"cycle_number": 1, "mode": "full", "assets_created": 3, "errors": []},
            {"cycle_number": 2, "mode": "debate", "assets_created": 0, "errors": ["err"]},
        ]
        (nexus_dir / "cycle_history.json").write_text(
            json.dumps(history), encoding="utf-8"
        )
        tracker = PerformanceTracker(nexus_data_dir=nexus_dir)
        result = tracker.load_nexus_cycle_history()
        assert len(result) == 2

    def test_load_nexus_run_results(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)
        run_data = {"mode": "daily", "results": []}
        (runs_dir / "run_daily_20260101.json").write_text(
            json.dumps(run_data), encoding="utf-8"
        )
        tracker = PerformanceTracker(nexus_data_dir=tmp_path)
        results = tracker.load_nexus_run_results()
        assert len(results) == 1
        assert results[0]["mode"] == "daily"


class TestActionStats:
    def test_empty_entries(self):
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        stats = tracker.compute_action_stats([])
        assert stats["total_actions"] == 0
        assert stats["by_action"] == {}

    def test_counts_actions(self):
        entries = [
            {"action": "debate", "details": {}, "timestamp": "2026-01-01"},
            {"action": "debate", "details": {}, "timestamp": "2026-01-02"},
            {"action": "evolve", "details": {}, "timestamp": "2026-01-02"},
        ]
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        stats = tracker.compute_action_stats(entries)
        assert stats["total_actions"] == 3
        assert stats["by_action"]["debate"]["count"] == 2
        assert stats["by_action"]["evolve"]["count"] == 1

    def test_success_rate_calculation(self):
        entries = [
            {"action": "codegen", "details": {"validation_passed": True, "deploy_success": True}, "timestamp": "t1"},
            {"action": "codegen", "details": {"validation_passed": False}, "timestamp": "t2"},
            {"action": "codegen", "details": {"error": "fail"}, "timestamp": "t3"},
        ]
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        stats = tracker.compute_action_stats(entries)
        codegen = stats["by_action"]["codegen"]
        assert codegen["count"] == 3
        assert codegen["success_count"] == 1
        assert codegen["failure_count"] == 2
        assert abs(codegen["success_rate"] - 1.0 / 3.0) < 0.01


class TestCodegenMetrics:
    def test_empty_codegen(self):
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        metrics = tracker.compute_codegen_metrics([])
        assert metrics["total_generations"] == 0
        assert metrics["validation_pass_rate"] == 0.0

    def test_codegen_metrics(self):
        entries = [
            {"action": "codegen", "details": {"validation_passed": True, "deploy_success": True, "module": "mod1"}},
            {"action": "codegen", "details": {"validation_passed": True, "deploy_success": False, "module": "mod2"}},
            {"action": "evo_codegen", "details": {"validation_passed": False, "deploy_success": False}},
            {"action": "debate", "details": {}},  # ignored
        ]
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        metrics = tracker.compute_codegen_metrics(entries)
        assert metrics["total_generations"] == 3
        assert abs(metrics["validation_pass_rate"] - 2.0 / 3.0) < 0.01
        assert abs(metrics["deploy_success_rate"] - 1.0 / 3.0) < 0.01
        assert metrics["modules_generated"] == ["mod1", "mod2"]


class TestTimeTrends:
    def test_empty_trends(self):
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        trends = tracker.compute_time_trends([])
        assert trends["trend"] == "stable"
        assert trends["daily_counts"] == {}

    def test_increasing_trend(self):
        entries = [
            {"action": "a", "timestamp": "2026-02-18T00:00:00+09:00"},
            {"action": "a", "timestamp": "2026-02-22T00:00:00+09:00"},
            {"action": "a", "timestamp": "2026-02-23T00:00:00+09:00"},
            {"action": "a", "timestamp": "2026-02-24T00:00:00+09:00"},
            {"action": "a", "timestamp": "2026-02-24T12:00:00+09:00"},
        ]
        tracker = PerformanceTracker(log_path=Path("/tmp/nonexistent.jsonl"))
        trends = tracker.compute_time_trends(entries, window_days=30)
        assert trends["trend"] == "increasing"


class TestNexusMetrics:
    def test_empty_nexus(self, tmp_path):
        tracker = PerformanceTracker(nexus_data_dir=tmp_path / "nonexistent")
        metrics = tracker.compute_nexus_metrics()
        assert metrics["total_cycles"] == 0

    def test_nexus_metrics(self, tmp_path):
        nexus_dir = tmp_path / "nexus"
        nexus_dir.mkdir()
        history = [
            {"assets_created": 3, "assets_distributed": 5, "debates_held": 1,
             "errors": [], "estimated_monthly_revenue": 10000, "mode": "full"},
            {"assets_created": 2, "assets_distributed": 2, "debates_held": 0,
             "errors": ["err"], "estimated_monthly_revenue": 15000, "mode": "create"},
        ]
        (nexus_dir / "cycle_history.json").write_text(json.dumps(history), encoding="utf-8")
        tracker = PerformanceTracker(nexus_data_dir=nexus_dir)
        metrics = tracker.compute_nexus_metrics()
        assert metrics["total_cycles"] == 2
        assert metrics["total_assets"] == 5
        assert metrics["total_distributed"] == 7
        assert metrics["total_debates"] == 1
        assert metrics["error_rate"] == 0.5
        assert metrics["revenue_trend"] == [10000, 15000]
        assert metrics["mode_distribution"] == {"full": 1, "create": 1}


class TestHealthScore:
    def test_perfect_score(self, tmp_path):
        tracker = PerformanceTracker(
            log_path=tmp_path / "empty.jsonl",
            nexus_data_dir=tmp_path / "empty",
        )
        score = tracker._calculate_health_score(
            action_stats={"by_action": {"a": {"success_rate": 1.0}}},
            codegen_metrics={"total_generations": 5, "validation_pass_rate": 1.0, "deploy_success_rate": 1.0},
            time_trends={"trend": "increasing"},
            nexus_metrics={"total_cycles": 10, "error_rate": 0.0, "total_assets": 20},
        )
        assert score > 80

    def test_no_data_score(self, tmp_path):
        tracker = PerformanceTracker(
            log_path=tmp_path / "empty.jsonl",
            nexus_data_dir=tmp_path / "empty",
        )
        score = tracker._calculate_health_score(
            action_stats={"by_action": {}, "total_actions": 0},
            codegen_metrics={"total_generations": 0},
            time_trends={"trend": "stable"},
            nexus_metrics={"total_cycles": 0},
        )
        assert 40 <= score <= 60  # mid-range for no data


class TestFullReport:
    def test_generates_report(self, tmp_path):
        log_file = tmp_path / "log.jsonl"
        log_file.write_text(
            json.dumps({"action": "debate", "details": {}, "timestamp": "2026-02-25T00:00:00+09:00"}),
            encoding="utf-8",
        )
        perf_dir = tmp_path / "performance"
        perf_dir.mkdir()
        tracker = PerformanceTracker(
            log_path=log_file,
            nexus_data_dir=tmp_path / "nexus",
        )
        # Override TRACKER_DIR for test isolation
        import system_e.performance_tracker as pt
        original = pt.TRACKER_DIR
        pt.TRACKER_DIR = perf_dir
        try:
            report = tracker.generate_full_report()
            assert "health_score" in report
            assert "recommendations" in report
            assert "system_e" in report
            assert report["system_e"]["action_stats"]["total_actions"] == 1
        finally:
            pt.TRACKER_DIR = original

    def test_evolution_metrics(self, tmp_path):
        log_file = tmp_path / "log.jsonl"
        entries = [
            {"action": "debate", "details": {}, "timestamp": "2026-02-25"},
            {"action": "codegen", "details": {"validation_passed": True, "deploy_success": True}, "timestamp": "2026-02-25"},
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )
        tracker = PerformanceTracker(
            log_path=log_file,
            nexus_data_dir=tmp_path / "empty",
        )
        metrics = tracker.generate_evolution_metrics()
        assert metrics["source"] == "performance_tracker"
        assert metrics["system_e_total_actions"] == 2
        assert metrics["codegen_pass_rate"] == 1.0


class TestRecommendations:
    def test_low_success_rate(self, tmp_path):
        tracker = PerformanceTracker(
            log_path=tmp_path / "empty.jsonl",
            nexus_data_dir=tmp_path / "empty",
        )
        recs = tracker._generate_recommendations(
            action_stats={"by_action": {"codegen": {"count": 10, "success_rate": 0.3}}},
            codegen_metrics={"total_generations": 10, "validation_pass_rate": 0.5, "deploy_success_rate": 0.3},
            time_trends={"trend": "decreasing"},
            nexus_metrics={"total_cycles": 10, "error_rate": 0.5},
        )
        assert len(recs) >= 3  # at least action, codegen, trend, nexus recommendations


# ─── NexusBridge Tests ───────────────────────────────────


class TestNexusBridgeCollect:
    def test_collect_empty_state(self, tmp_path):
        bridge = NexusBridge(
            claude_client=MagicMock(),
            nexus_data_dir=tmp_path / "nonexistent",
        )
        state = bridge.collect_nexus_state()
        assert state["state"] == {}
        assert state["cycle_history"] == []
        assert state["portfolio"]["total_assets"] == 0
        assert state["latest_debate"] == {}
        assert state["creation_queue"] == []
        assert "collected_at" in state

    def test_collect_with_data(self, tmp_path):
        nexus_dir = tmp_path / "nexus"
        nexus_dir.mkdir()

        # State
        (nexus_dir / "nexus_v2_state.json").write_text(
            json.dumps({"cycles_completed": 5, "total_assets": 10}),
            encoding="utf-8",
        )

        # History
        (nexus_dir / "cycle_history.json").write_text(
            json.dumps([{"cycle_number": 1}, {"cycle_number": 2}]),
            encoding="utf-8",
        )

        # Content
        content_dir = nexus_dir / "content"
        content_dir.mkdir()
        (content_dir / "asset1.json").write_text("{}", encoding="utf-8")
        (content_dir / "asset2.json").write_text("{}", encoding="utf-8")

        # Debate
        debate_dir = nexus_dir / "debate"
        debate_dir.mkdir()
        (debate_dir / "debate_001.json").write_text(
            json.dumps({"topic": "test"}), encoding="utf-8"
        )

        # Queue
        (nexus_dir / "creation_queue.json").write_text(
            json.dumps([{"asset_type": "template"}]), encoding="utf-8"
        )

        bridge = NexusBridge(claude_client=MagicMock(), nexus_data_dir=nexus_dir)
        state = bridge.collect_nexus_state()

        assert state["state"]["cycles_completed"] == 5
        assert len(state["cycle_history"]) == 2
        assert state["portfolio"]["total_assets"] == 2
        assert state["latest_debate"]["topic"] == "test"
        assert len(state["creation_queue"]) == 1


class TestNexusBridgeAnalysis:
    @patch("system_e.nexus_bridge.ClaudeClient")
    def test_analyze_revenue(self, mock_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"analysis": "good"})
        bridge = NexusBridge(
            claude_client=mock_client,
            nexus_data_dir=Path("/tmp/empty_nexus"),
        )
        result = bridge.analyze_revenue_performance(
            nexus_state={"state": {}, "cycle_history": [], "portfolio": {"total_assets": 0},
                         "latest_debate": {}, "creation_queue": []}
        )
        assert isinstance(result, dict)

    @patch("system_e.nexus_bridge.ClaudeClient")
    def test_generate_optimization_plan(self, mock_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "optimized_queue": [], "action_items": ["test"]
        })
        bridge = NexusBridge(
            claude_client=mock_client,
            nexus_data_dir=Path("/tmp/empty_nexus"),
        )
        plan = bridge.generate_optimization_plan(
            nexus_state={"state": {}, "cycle_history": [], "portfolio": {"total_assets": 0},
                         "latest_debate": {}, "creation_queue": []}
        )
        assert isinstance(plan, dict)


class TestNexusBridgeFeedback:
    def test_generate_feedback_empty(self, tmp_path):
        bridge = NexusBridge(
            claude_client=MagicMock(),
            nexus_data_dir=tmp_path / "nonexistent",
        )
        feedback = bridge.generate_nexus_feedback()
        assert feedback["source"] == "nexus_bridge"
        assert feedback["nexus_cycles_completed"] == 0
        assert feedback["nexus_error_rate"] == 0.0

    def test_generate_feedback_with_data(self, tmp_path):
        nexus_dir = tmp_path / "nexus"
        nexus_dir.mkdir()
        (nexus_dir / "nexus_v2_state.json").write_text(
            json.dumps({
                "cycles_completed": 10,
                "total_assets": 20,
                "total_distributed": 15,
                "estimated_monthly_revenue": 50000,
                "active_channels": ["streaming", "video"],
            }),
            encoding="utf-8",
        )
        (nexus_dir / "cycle_history.json").write_text(
            json.dumps([
                {"errors": [], "estimated_monthly_revenue": 10000},
                {"errors": ["err"], "estimated_monthly_revenue": 20000},
                {"errors": [], "estimated_monthly_revenue": 30000},
            ]),
            encoding="utf-8",
        )

        bridge = NexusBridge(claude_client=MagicMock(), nexus_data_dir=nexus_dir)
        feedback = bridge.generate_nexus_feedback()
        assert feedback["nexus_cycles_completed"] == 10
        assert feedback["nexus_total_assets"] == 20
        assert abs(feedback["nexus_error_rate"] - 1.0 / 3.0) < 0.01
        assert len(feedback["nexus_revenue_history"]) == 3


class TestNexusBridgeCycle:
    @patch("system_e.nexus_bridge.ClaudeClient")
    def test_bridge_cycle(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"result": "ok"})

        import system_e.nexus_bridge as nb
        original = nb.BRIDGE_LOG_DIR
        nb.BRIDGE_LOG_DIR = tmp_path / "bridge_logs"
        nb.BRIDGE_LOG_DIR.mkdir()

        try:
            bridge = NexusBridge(
                claude_client=mock_client,
                nexus_data_dir=tmp_path / "nexus",
            )
            result = bridge.run_bridge_cycle()
            assert "nexus_state" in result
            assert "revenue_analysis" in result
            assert "optimization_plan" in result
            assert "evolution_feedback" in result
        finally:
            nb.BRIDGE_LOG_DIR = original


class TestSummarize:
    def test_summarize_state(self, tmp_path):
        bridge = NexusBridge(
            claude_client=MagicMock(),
            nexus_data_dir=tmp_path,
        )
        nexus_state = {
            "state": {"cycles_completed": 5, "total_distributed": 10, "estimated_monthly_revenue": 30000, "active_channels": ["video"]},
            "portfolio": {"total_assets": 15},
            "cycle_history": [
                {"cycle_number": i, "mode": "full", "assets_created": i, "errors": [], "estimated_monthly_revenue": i * 1000}
                for i in range(1, 8)
            ],
            "creation_queue": [{"asset_type": "template", "priority": 9}],
            "latest_debate": {},
        }
        summary = bridge._summarize_nexus_state(nexus_state)
        assert summary["cycles_completed"] == 5
        assert summary["total_assets"] == 15
        assert len(summary["recent_cycles"]) == 5  # last 5


# ─── Orchestrator Integration Tests ─────────────────────


class TestOrchestratorNewModes:
    @patch("system_e.orchestrator.ClaudeClient")
    def test_orchestrator_has_tracker(self, mock_cls):
        mock_client = MagicMock()
        orch = Orchestrator(claude_client=mock_client)
        assert hasattr(orch, "tracker")
        assert isinstance(orch.tracker, PerformanceTracker)

    @patch("system_e.orchestrator.ClaudeClient")
    def test_orchestrator_has_bridge(self, mock_cls):
        mock_client = MagicMock()
        orch = Orchestrator(claude_client=mock_client)
        assert hasattr(orch, "bridge")
        assert isinstance(orch.bridge, NexusBridge)

    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_analytics(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        orch = Orchestrator(claude_client=mock_client)

        # Override tracker paths for test isolation
        import system_e.performance_tracker as pt
        original_tracker = pt.TRACKER_DIR
        pt.TRACKER_DIR = tmp_path / "perf"
        pt.TRACKER_DIR.mkdir()

        try:
            result = orch.run_analytics()
            assert "health_score" in result
            assert "recommendations" in result
        finally:
            pt.TRACKER_DIR = original_tracker

    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_bridge(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"ok": True})

        import system_e.nexus_bridge as nb
        original = nb.BRIDGE_LOG_DIR
        nb.BRIDGE_LOG_DIR = tmp_path / "bridge"
        nb.BRIDGE_LOG_DIR.mkdir()

        try:
            orch = Orchestrator(claude_client=mock_client)
            result = orch.run_bridge()
            assert "nexus_state" in result
            assert "evolution_feedback" in result
        finally:
            nb.BRIDGE_LOG_DIR = original

    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_smart_evolve(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "changes": ["test change"],
            "posting_strategy": {},
            "content_strategy": {},
        })

        import system_e.nexus_bridge as nb
        import system_e.self_improve as si
        original_bridge = nb.BRIDGE_LOG_DIR
        original_strategy = si.STRATEGY_FILE
        original_evo = si.EVOLUTION_DIR
        nb.BRIDGE_LOG_DIR = tmp_path / "bridge"
        nb.BRIDGE_LOG_DIR.mkdir()
        si.STRATEGY_FILE = tmp_path / "strategy.json"
        si.EVOLUTION_DIR = tmp_path / "evolution"
        si.EVOLUTION_DIR.mkdir()

        try:
            orch = Orchestrator(claude_client=mock_client)
            result = orch.run_smart_evolve()
            assert "performance_metrics" in result
            assert "nexus_feedback" in result
            assert "evolution" in result
        finally:
            nb.BRIDGE_LOG_DIR = original_bridge
            si.STRATEGY_FILE = original_strategy
            si.EVOLUTION_DIR = original_evo

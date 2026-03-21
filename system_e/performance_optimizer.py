"""System E — Performance Optimizer.

Analyzes engagement data to optimize posting times, run A/B tests,
and learn winning content patterns. Feeds recommendations back
into content_generator and posting_scheduler.
"""

import json
import logging
import math
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent.parent / "data" / "system_e"
ANALYTICS_DIR = DATA_DIR / "analytics"
AB_TESTS_DIR = DATA_DIR / "ab_tests"
GENERATED_DIR = DATA_DIR / "generated"
POSTED_LOG = DATA_DIR / "posted_log.json"
OPTIMIZATION_STATE = DATA_DIR / "analytics" / "optimization_state.json"

# Minimum sample size before we trust the data enough to act on it
MIN_SAMPLES_FOR_OPTIMIZATION = 10
# Statistical significance threshold for A/B tests (z-score for 90% confidence)
Z_SCORE_90 = 1.645


class PerformanceOptimizer:
    """Analyze performance data and optimize content strategy."""

    def __init__(self):
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        AB_TESTS_DIR.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    # ══════════════════════════════════════════════════════════
    #  1. POSTING TIME OPTIMIZATION
    # ══════════════════════════════════════════════════════════

    def analyze_posting_times(self) -> dict:
        """Analyze engagement by posting hour and recommend optimal times.

        Combines posted_log with daily engagement files to calculate
        average engagement rate per hour slot.

        Returns:
            Dict with 'by_hour' performance data and 'recommended_times'.
        """
        posted = self._load_posted_log()
        if not posted:
            return {"by_hour": {}, "recommended_times": [], "sample_size": 0, "enough_data": False}

        # Build per-hour engagement stats
        by_hour: dict[str, dict] = {}
        for record in posted:
            hour = self._extract_hour(record)
            if hour is None:
                continue

            h_key = f"{hour:02d}"
            if h_key not in by_hour:
                by_hour[h_key] = {
                    "count": 0,
                    "total_likes": 0,
                    "total_retweets": 0,
                    "total_replies": 0,
                    "total_impressions": 0,
                }

            stats = by_hour[h_key]
            stats["count"] += 1
            # Merge engagement from daily files
            engagement = self._get_engagement_for_tweet(record.get("tweet_id", ""))
            stats["total_likes"] += engagement.get("likes", 0)
            stats["total_retweets"] += engagement.get("retweets", 0)
            stats["total_replies"] += engagement.get("replies", 0)
            stats["total_impressions"] += engagement.get("impressions", 0)

        # Calculate avg engagement rate per hour
        for h_key, stats in by_hour.items():
            count = stats["count"]
            imps = stats["total_impressions"]
            interactions = (
                stats["total_likes"] + stats["total_retweets"] + stats["total_replies"]
            )
            stats["avg_engagement_rate"] = (
                round(interactions / imps * 100, 2) if imps > 0 else 0.0
            )
            stats["avg_impressions"] = round(imps / count) if count > 0 else 0

        # Rank hours by engagement rate (need minimum samples)
        ranked = sorted(
            [
                (h, s)
                for h, s in by_hour.items()
                if s["count"] >= max(3, MIN_SAMPLES_FOR_OPTIMIZATION // 3)
            ],
            key=lambda x: x[1]["avg_engagement_rate"],
            reverse=True,
        )

        recommended = [h for h, _ in ranked[:4]]

        total_samples = sum(s["count"] for s in by_hour.values())
        return {
            "by_hour": by_hour,
            "recommended_times": [f"{h}:00" for h in recommended],
            "sample_size": total_samples,
            "enough_data": total_samples >= MIN_SAMPLES_FOR_OPTIMIZATION,
        }

    def get_optimized_schedule(
        self,
        default_times: list[str] | None = None,
    ) -> list[str]:
        """Get optimized posting times, falling back to defaults if not enough data.

        Args:
            default_times: Fallback times (e.g., ["07:00", "12:00", "19:00", "23:00"]).

        Returns:
            List of 4 optimized posting times (HH:MM).
        """
        if default_times is None:
            default_times = ["07:00", "12:00", "19:00", "23:00"]

        analysis = self.analyze_posting_times()
        if not analysis["enough_data"] or len(analysis["recommended_times"]) < 4:
            logger.info(
                "Not enough data for time optimization (samples=%d), using defaults",
                analysis["sample_size"],
            )
            return default_times

        recommended = analysis["recommended_times"]
        logger.info("Optimized posting times: %s (from %d samples)", recommended, analysis["sample_size"])
        return recommended

    # ══════════════════════════════════════════════════════════
    #  2. A/B TESTING ENGINE
    # ══════════════════════════════════════════════════════════

    def create_ab_test(
        self,
        test_name: str,
        variants: list[dict],
        metric: str = "engagement_rate",
    ) -> dict:
        """Create a new A/B test.

        Args:
            test_name: Unique test identifier.
            variants: List of dicts with 'name' and 'content' keys.
            metric: Metric to optimize ('engagement_rate', 'impressions', 'likes').

        Returns:
            The created test dict.
        """
        test = {
            "test_name": test_name,
            "variants": [
                {
                    "name": v["name"],
                    "content": v.get("content", ""),
                    "impressions": 0,
                    "successes": 0,
                }
                for v in variants
            ],
            "metric": metric,
            "status": "running",
            "created_at": datetime.now(JST).isoformat(),
        }

        test_file = AB_TESTS_DIR / f"{test_name}.json"
        self._save_json(test_file, test)
        logger.info("A/B test created: %s (%d variants)", test_name, len(variants))
        return test

    def pick_variant(self, test_name: str) -> str | None:
        """Select a variant using Thompson Sampling (Bayesian bandit).

        Thompson Sampling balances exploration/exploitation by sampling
        from each variant's Beta distribution and picking the highest.

        Args:
            test_name: Test identifier.

        Returns:
            Selected variant name, or None if test doesn't exist.
        """
        test = self._load_test(test_name)
        if not test or test.get("status") != "running":
            return None

        best_name = None
        best_sample = -1.0

        for variant in test["variants"]:
            # Beta distribution: successes+1 as alpha, failures+1 as beta
            alpha = variant["successes"] + 1
            beta = max(1, variant["impressions"] - variant["successes"] + 1)
            sample = random.betavariate(alpha, beta)
            if sample > best_sample:
                best_sample = sample
                best_name = variant["name"]

        return best_name

    def record_ab_result(
        self,
        test_name: str,
        variant_name: str,
        impressions: int = 1,
        successes: int = 0,
    ) -> None:
        """Record results for an A/B test variant.

        Args:
            test_name: Test identifier.
            variant_name: Which variant was shown.
            impressions: Number of impressions (trials).
            successes: Number of success events (e.g., engagements).
        """
        test = self._load_test(test_name)
        if not test:
            return

        for variant in test["variants"]:
            if variant["name"] == variant_name:
                variant["impressions"] += impressions
                variant["successes"] += successes
                break

        # Auto-check for winner
        winner = self._check_ab_winner(test)
        if winner:
            test["status"] = "completed"
            test["winner"] = winner
            test["completed_at"] = datetime.now(JST).isoformat()
            logger.info("A/B test '%s' completed — winner: %s", test_name, winner)

        test_file = AB_TESTS_DIR / f"{test_name}.json"
        self._save_json(test_file, test)

    def get_ab_test_status(self, test_name: str) -> dict | None:
        """Get the current status of an A/B test."""
        return self._load_test(test_name)

    def list_ab_tests(self) -> list[dict]:
        """List all A/B tests with their status."""
        tests = []
        for f in AB_TESTS_DIR.glob("*.json"):
            test = self._load_json_dict(f)
            if test and "test_name" in test:
                tests.append({
                    "test_name": test["test_name"],
                    "status": test.get("status", "unknown"),
                    "variants": len(test.get("variants", [])),
                    "winner": test.get("winner"),
                    "total_impressions": sum(
                        v.get("impressions", 0) for v in test.get("variants", [])
                    ),
                })
        return tests

    def _check_ab_winner(self, test: dict) -> str | None:
        """Check if an A/B test has a statistically significant winner.

        Uses a z-test for proportions at 90% confidence level.
        Requires minimum 30 impressions per variant.
        """
        variants = test.get("variants", [])
        if len(variants) < 2:
            return None

        # Need minimum impressions
        for v in variants:
            if v["impressions"] < 30:
                return None

        # Calculate conversion rates
        rates = []
        for v in variants:
            rate = v["successes"] / v["impressions"] if v["impressions"] > 0 else 0
            rates.append((v["name"], rate, v["impressions"], v["successes"]))

        # Sort by rate descending
        rates.sort(key=lambda x: x[1], reverse=True)
        best = rates[0]
        second = rates[1]

        # Z-test for difference in proportions
        p1, n1 = best[1], best[2]
        p2, n2 = second[1], second[2]
        p_pool = (best[3] + second[3]) / (n1 + n2)

        if p_pool <= 0 or p_pool >= 1:
            return None

        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return None

        z = (p1 - p2) / se
        if z >= Z_SCORE_90:
            return best[0]

        return None

    # ══════════════════════════════════════════════════════════
    #  3. WINNING PATTERN LEARNING
    # ══════════════════════════════════════════════════════════

    def analyze_content_patterns(self) -> dict:
        """Analyze which content types and scenes perform best.

        Returns:
            Dict with performance rankings for content types and scenes.
        """
        posted = self._load_posted_log()
        if not posted:
            return {"content_types": {}, "scenes": {}, "sample_size": 0}

        type_stats: dict[str, dict] = {}
        scene_stats: dict[str, dict] = {}

        for record in posted:
            engagement = self._get_engagement_for_tweet(record.get("tweet_id", ""))
            likes = engagement.get("likes", 0)
            impressions = engagement.get("impressions", 0)
            retweets = engagement.get("retweets", 0)
            replies = engagement.get("replies", 0)

            # By content type
            ctype = record.get("type", "standard")
            if ctype not in type_stats:
                type_stats[ctype] = self._empty_stats()
            self._accumulate(type_stats[ctype], likes, retweets, replies, impressions)

            # By scene
            scene = record.get("scene", "unknown")
            if scene not in scene_stats:
                scene_stats[scene] = self._empty_stats()
            self._accumulate(scene_stats[scene], likes, retweets, replies, impressions)

        # Calculate averages
        for stats_dict in (type_stats, scene_stats):
            for key, stats in stats_dict.items():
                c = stats["count"]
                imps = stats["total_impressions"]
                interactions = stats["total_likes"] + stats["total_retweets"] + stats["total_replies"]
                stats["avg_engagement_rate"] = (
                    round(interactions / imps * 100, 2) if imps > 0 else 0.0
                )
                stats["avg_impressions"] = round(imps / c) if c > 0 else 0
                stats["avg_likes"] = round(stats["total_likes"] / c, 1) if c > 0 else 0

        return {
            "content_types": type_stats,
            "scenes": scene_stats,
            "sample_size": len(posted),
        }

    def get_optimized_scene_weights(
        self,
        default_weights: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """Calculate optimized scene weights based on engagement data.

        Higher-performing scenes get more weight. Uses a blend of
        default weights and performance data (50/50 when data is available).

        Args:
            default_weights: Fallback weights (scene -> weight).

        Returns:
            Dict mapping scene names to integer weights.
        """
        if default_weights is None:
            default_weights = {
                "morning_routine": 7,
                "workout": 3,
                "outdoor": 2,
                "lifestyle": 2,
                "vulnerable": 2,
                "studio": 1,
                "cat_moments": 1,
            }

        patterns = self.analyze_content_patterns()
        scene_data = patterns.get("scenes", {})
        total_samples = patterns.get("sample_size", 0)

        if total_samples < MIN_SAMPLES_FOR_OPTIMIZATION:
            return default_weights

        # Rank scenes by engagement rate
        scene_rates = {}
        for scene, stats in scene_data.items():
            if stats["count"] >= 3:
                scene_rates[scene] = stats["avg_engagement_rate"]

        if not scene_rates:
            return default_weights

        # Normalize performance scores to weights (1-10 range)
        max_rate = max(scene_rates.values()) if scene_rates else 1
        perf_weights = {}
        for scene, rate in scene_rates.items():
            perf_weights[scene] = max(1, round(rate / max(max_rate, 0.01) * 7))

        # Blend: 50% default + 50% performance
        blended = {}
        all_scenes = set(default_weights) | set(perf_weights)
        for scene in all_scenes:
            default_w = default_weights.get(scene, 1)
            perf_w = perf_weights.get(scene, default_w)
            blended[scene] = max(1, round((default_w + perf_w) / 2))

        logger.info("Optimized scene weights: %s", blended)
        return blended

    def get_optimized_content_mix(self) -> dict[str, str] | None:
        """Recommend content type assignments per time slot.

        Analyzes which content types work best and recommends
        the optimal content mix for the 4 daily slots.

        Returns:
            Dict mapping time slots to content types, or None if not enough data.
        """
        patterns = self.analyze_content_patterns()
        type_data = patterns.get("content_types", {})
        total = patterns.get("sample_size", 0)

        if total < MIN_SAMPLES_FOR_OPTIMIZATION:
            return None

        # Rank content types by engagement rate
        ranked = sorted(
            [
                (ctype, stats)
                for ctype, stats in type_data.items()
                if stats["count"] >= 3
            ],
            key=lambda x: x[1]["avg_engagement_rate"],
            reverse=True,
        )

        if len(ranked) < 2:
            return None

        # Assign best performers to prime time slots
        # 19:00 = prime time (EU+Asia), 07:00 = Asia peak, 12:00 = lunch, 23:00 = US
        slots = ["19:00", "07:00", "12:00", "23:00"]
        mix = {}
        used_types = set()
        for slot in slots:
            for ctype, _ in ranked:
                if ctype not in used_types:
                    mix[slot] = ctype
                    used_types.add(ctype)
                    break
            if slot not in mix:
                mix[slot] = ranked[0][0]  # fallback to best

        logger.info("Optimized content mix: %s", mix)
        return mix

    # ══════════════════════════════════════════════════════════
    #  4. WEEKLY OPTIMIZATION REPORT
    # ══════════════════════════════════════════════════════════

    def generate_optimization_report(self) -> dict:
        """Generate a comprehensive weekly optimization report.

        Returns:
            Dict with all optimization insights and recommendations.
        """
        time_analysis = self.analyze_posting_times()
        pattern_analysis = self.analyze_content_patterns()
        ab_tests = self.list_ab_tests()
        optimized_times = self.get_optimized_schedule()
        optimized_weights = self.get_optimized_scene_weights()
        content_mix = self.get_optimized_content_mix()

        report = {
            "generated_at": datetime.now(JST).isoformat(),
            "posting_times": {
                "current_recommendation": optimized_times,
                "by_hour": time_analysis.get("by_hour", {}),
                "enough_data": time_analysis.get("enough_data", False),
                "sample_size": time_analysis.get("sample_size", 0),
            },
            "content_patterns": {
                "content_types": pattern_analysis.get("content_types", {}),
                "scenes": pattern_analysis.get("scenes", {}),
                "optimized_scene_weights": optimized_weights,
                "optimized_content_mix": content_mix,
                "sample_size": pattern_analysis.get("sample_size", 0),
            },
            "ab_tests": ab_tests,
            "actions": self._generate_actions(
                time_analysis, pattern_analysis, content_mix
            ),
        }

        # Save report
        report_file = ANALYTICS_DIR / "optimization_report.json"
        self._save_json(report_file, report)
        logger.info("Optimization report generated")
        return report

    def _generate_actions(
        self,
        time_analysis: dict,
        pattern_analysis: dict,
        content_mix: dict | None,
    ) -> list[str]:
        """Generate actionable recommendations."""
        actions = []

        if not time_analysis.get("enough_data"):
            actions.append(
                f"Need more data: {time_analysis.get('sample_size', 0)}/{MIN_SAMPLES_FOR_OPTIMIZATION} posts analyzed. "
                "Continue posting to build baseline."
            )

        if time_analysis.get("enough_data") and time_analysis.get("recommended_times"):
            rec = time_analysis["recommended_times"]
            actions.append(f"Consider shifting posting times to {rec}")

        type_data = pattern_analysis.get("content_types", {})
        if type_data:
            best_type = max(
                [(t, s) for t, s in type_data.items() if s["count"] >= 3],
                key=lambda x: x[1].get("avg_engagement_rate", 0),
                default=None,
            )
            if best_type:
                actions.append(
                    f"Best content type: '{best_type[0]}' "
                    f"(avg engagement: {best_type[1].get('avg_engagement_rate', 0)}%)"
                )

        scene_data = pattern_analysis.get("scenes", {})
        if scene_data:
            best_scene = max(
                [(s, d) for s, d in scene_data.items() if d["count"] >= 3],
                key=lambda x: x[1].get("avg_engagement_rate", 0),
                default=None,
            )
            if best_scene:
                actions.append(
                    f"Best scene: '{best_scene[0]}' "
                    f"(avg engagement: {best_scene[1].get('avg_engagement_rate', 0)}%)"
                )

        if content_mix:
            actions.append(f"Recommended content mix: {content_mix}")

        return actions

    # ══════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "count": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "total_replies": 0,
            "total_impressions": 0,
        }

    @staticmethod
    def _accumulate(stats: dict, likes: int, retweets: int, replies: int, impressions: int) -> None:
        stats["count"] += 1
        stats["total_likes"] += likes
        stats["total_retweets"] += retweets
        stats["total_replies"] += replies
        stats["total_impressions"] += impressions

    def _extract_hour(self, record: dict) -> int | None:
        """Extract posting hour from a posted_log record."""
        time_str = record.get("time", "")
        if time_str:
            try:
                return int(time_str.split(":")[0])
            except (ValueError, IndexError):
                pass
        posted_at = record.get("posted_at", "")
        if posted_at:
            try:
                dt = datetime.fromisoformat(posted_at)
                return dt.hour
            except (ValueError, TypeError):
                pass
        return None

    def _get_engagement_for_tweet(self, tweet_id: str) -> dict:
        """Look up engagement metrics for a tweet across daily engagement files."""
        if not tweet_id:
            return {}

        for f in ANALYTICS_DIR.glob("engagement_*.json"):
            data = self._load_json_list(f)
            for record in data:
                if record.get("tweet_id") == tweet_id:
                    return record
        return {}

    def _load_posted_log(self) -> list:
        return self._load_json_list(POSTED_LOG)

    def _load_test(self, test_name: str) -> dict | None:
        test_file = AB_TESTS_DIR / f"{test_name}.json"
        return self._load_json_dict(test_file)

    def _load_state(self) -> dict:
        return self._load_json_dict(OPTIMIZATION_STATE) or {}

    def _save_state(self) -> None:
        self._save_json(OPTIMIZATION_STATE, self._state)

    @staticmethod
    def _load_json_list(path: Path) -> list:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _load_json_dict(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def _save_json(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    optimizer = PerformanceOptimizer()
    report = optimizer.generate_optimization_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))

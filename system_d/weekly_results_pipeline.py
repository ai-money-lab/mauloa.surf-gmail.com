"""System D - 実績発信パイプライン

実績データ収集 → 投稿生成 → 品質チェック → System Aスケジュールに統合。
毎晩23:15に実行（System Aのdaily_pipeline 23:00の後）。
"""

import logging
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.notifier import Notifier
from system_d.generate_results_content import ResultsContentGenerator
from system_d.schedule_results_posts import ResultsPostScheduler

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
LOGS_DIR = _ROOT / "logs"


def run_results_pipeline():
    """System D実績発信パイプラインを実行"""
    notifier = Notifier()
    start_time = datetime.now(JST)

    # 20時以降の実行は翌日分として扱う
    if start_time.hour >= 20:
        target_date = (start_time + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = start_time.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"System D results pipeline started at {start_time.isoformat()}")
    logger.info(f"Target date: {target_date}")
    logger.info("=" * 60)

    results = {
        "gathered": False,
        "generated": 0,
        "approved": 0,
        "injected": False,
        "target_date": target_date,
        "errors": [],
    }

    # Step 1: 実績データ収集
    try:
        logger.info("[1/3] Gathering results from all systems...")
        generator = ResultsContentGenerator()
        data = generator.gather_results()

        has_data = any(
            bool(v) for k, v in data.items()
            if k != "x_performance"
        )
        if has_data:
            results["gathered"] = True
            logger.info("Results gathered successfully")
        else:
            logger.info("No results data available (B/C systems may not have output yet)")
            results["errors"].append("No results data available")
    except Exception as e:
        results["errors"].append(f"Gather error: {e}")
        logger.error(f"Gather failed: {traceback.format_exc()}")
        return results

    if not results["gathered"]:
        elapsed = (datetime.now(JST) - start_time).total_seconds()
        logger.info(f"Pipeline skipped (no data), elapsed: {elapsed:.1f}s")
        return results

    # Step 2: 投稿生成 + 品質チェック
    try:
        logger.info("[2/3] Generating and checking results posts...")
        posts = generator.generate_posts(data)
        results["generated"] = len(posts)
        logger.info(f"Generated {len(posts)} posts")

        approved = generator.quality_check_posts(posts)
        results["approved"] = len(approved)
        logger.info(f"Approved {len(approved)} posts")

        if approved:
            generator.save_posts(approved, target_date=target_date)
        else:
            results["errors"].append("No posts passed quality check")
    except Exception as e:
        results["errors"].append(f"Generation error: {e}")
        logger.error(f"Generation failed: {traceback.format_exc()}")
        return results

    # Step 3: System Aスケジュールに統合（翌日分）
    if results["approved"] > 0:
        try:
            logger.info(f"[3/3] Injecting into System A schedule for {target_date}...")
            scheduler = ResultsPostScheduler()

            results_posts = scheduler.load_results_posts(target_date)
            schedule = scheduler.load_system_a_schedule(target_date)
            updated = scheduler.inject_results_post(schedule, results_posts, target_date)
            scheduler.save_schedule(updated, target_date)

            d_count = sum(
                1 for p in updated.get("posts", [])
                if p.get("source") == "system_d"
            )
            results["injected"] = d_count > 0
            logger.info(f"Schedule updated: {d_count} System D posts injected")
        except Exception as e:
            results["errors"].append(f"Schedule error: {e}")
            logger.error(f"Schedule injection failed: {traceback.format_exc()}")

    # 結果通知
    elapsed = (datetime.now(JST) - start_time).total_seconds()

    message = (
        f"【System D 実績発信パイプライン完了】\n"
        f"データ収集: {'成功' if results['gathered'] else '失敗'}\n"
        f"投稿生成: {results['generated']}本\n"
        f"品質通過: {results['approved']}本\n"
        f"スケジュール統合: {'済' if results['injected'] else '未'}\n"
        f"処理時間: {elapsed:.1f}秒"
    )

    if results["errors"]:
        message += f"\n⚠️ エラー: {len(results['errors'])}件"
        for err in results["errors"]:
            message += f"\n  - {err}"

    notifier.notify(message, urgent=bool(results["errors"]))
    logger.info(message)
    return results


def main():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"system_d_{datetime.now(JST).strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    results = run_results_pipeline()
    if results["errors"] and not results["injected"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

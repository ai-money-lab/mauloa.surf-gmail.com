"""System A - TASK A-7: デイリーパイプライン

1日の全フローを完全自動実行する。
前日23:00 - 収集 → 分析 → 変換 → 品質チェック → スケジュール（翌日分）
→ Sheetsに書き込み → ユーザーが夜〜朝に確認・修正可能
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# .envをプロジェクトルートから読み込む（他モジュールより先に）
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.notifier import Notifier
from system_a.collect_viral import ViralCollector
from system_a.analyze_tweets import TweetAnalyzer
from system_a.transform_tweets import TweetTransformer
from system_a.auto_post import AutoPoster

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def run_daily_pipeline():
    """デイリーパイプラインを実行

    23時実行の場合、翌日分のスケジュールを生成する。
    """
    notifier = Notifier()
    start_time = datetime.now(JST)

    # 20時以降の実行は翌日分として扱う
    if start_time.hour >= 20:
        target_date = (start_time + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = start_time.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"Daily pipeline started at {start_time.isoformat()}")
    logger.info(f"Target date: {target_date}")
    logger.info("=" * 60)

    results = {
        "collected": 0,
        "analyzed": 0,
        "transformed": 0,
        "scheduled": 0,
        "skipped": 0,
        "target_date": target_date,
        "errors": [],
    }

    # Step 0: System Cマーケットデータ収集（投稿ネタの参考情報）
    try:
        logger.info("[0/4] Running System C market watch...")
        from system_c.scheduler import AgentScheduler
        agent_scheduler = AgentScheduler()
        agent_scheduler.run_task("daily_watch")
        logger.info("System C market watch completed")
    except Exception as e:
        logger.warning(f"System C market watch failed (non-critical): {e}")
        # System Cの失敗はSystem Aのパイプラインを止めない

    try:
        # Step 1: バイラルツイート収集
        logger.info("[1/4] Collecting viral tweets...")
        collector = ViralCollector()
        tweets = collector.collect()
        if tweets:
            collector.save(tweets)
            results["collected"] = len(tweets)
            logger.info(f"Collected {len(tweets)} tweets")
        else:
            results["errors"].append("No tweets collected")
            logger.warning("No tweets collected")
    except Exception as e:
        results["errors"].append(f"Collection error: {e}")
        logger.error(f"Collection failed: {traceback.format_exc()}")

    try:
        # Step 2: AI分析
        logger.info("[2/4] Analyzing tweets...")
        analyzer = TweetAnalyzer()
        collected = analyzer.load_collected()
        if collected:
            analyses = analyzer.analyze(collected)
            top5 = analyzer.select_top5(analyses)
            analyzer.save(analyses, top5)
            results["analyzed"] = len(top5)
            logger.info(f"Analyzed, selected TOP{len(top5)}")
        else:
            results["errors"].append("No collected tweets to analyze")
    except Exception as e:
        results["errors"].append(f"Analysis error: {e}")
        logger.error(f"Analysis failed: {traceback.format_exc()}")

    try:
        # Step 3: ローカライズ変換
        logger.info("[3/4] Transforming tweets...")
        transformer = TweetTransformer()
        top5 = transformer.load_top5()
        if top5:
            transformed = transformer.transform_all(top5)
            transformer.save(transformed)
            results["transformed"] = len(transformed)
            logger.info(f"Transformed {len(transformed)} tweets")
        else:
            results["errors"].append("No analyzed tweets to transform")
    except Exception as e:
        results["errors"].append(f"Transform error: {e}")
        logger.error(f"Transform failed: {traceback.format_exc()}")

    try:
        # Step 4: 品質チェック＋スケジュール（翌日分としてSheets書き込み）
        logger.info(f"[4/4] Quality check & scheduling for {target_date}...")
        poster = AutoPoster()
        tweets = poster.load_transformed()
        if tweets:
            scheduled = poster.process_tweets(tweets, target_date=target_date)
            results["scheduled"] = len(scheduled)
            results["skipped"] = len(tweets) - len(scheduled)
            logger.info(f"Scheduled {len(scheduled)} posts for {target_date}")
        else:
            results["errors"].append("No transformed tweets to post")
    except Exception as e:
        results["errors"].append(f"Posting error: {e}")
        logger.error(f"Posting failed: {traceback.format_exc()}")

    # 結果通知
    elapsed = (datetime.now(JST) - start_time).total_seconds()

    message = (
        f"【System A デイリーパイプライン完了】\n"
        f"投稿日: {target_date}\n"
        f"収集: {results['collected']}件\n"
        f"分析: {results['analyzed']}件\n"
        f"変換: {results['transformed']}件\n"
        f"投稿予約: {results['scheduled']}件（Sheetsで編集可能）\n"
        f"スキップ: {results['skipped']}件\n"
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    results = run_daily_pipeline()

    if results["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

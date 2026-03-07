"""System C - TASK C-4: 自動スケジュール実行

エージェント群のタスクをスケジュール実行する。
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.notifier import Notifier
from core.quality_checker import QualityChecker
from system_c.agents.realestate_data_agent import RealEstateDataAgent
from system_c.agents.market_analysis_agent import MarketAnalysisAgent
from system_c.agents.regulation_watch_agent import RegulationWatchAgent
from system_c.agents.tech_trend_agent import TechTrendAgent

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent


class AgentScheduler:
    """エージェントタスクスケジューラー"""

    def __init__(self):
        self.notifier = Notifier()
        self.quality_checker = QualityChecker()
        self.agents = {
            "realestate_data": RealEstateDataAgent(),
            "market_analysis": MarketAnalysisAgent(),
            "regulation_watch": RegulationWatchAgent(),
            "tech_trend": TechTrendAgent(),
        }

    def run_task(self, task_name: str, **kwargs) -> dict:
        """指定タスクを実行"""
        logger.info(f"Running task: {task_name}")
        date_str = datetime.now(JST).strftime("%Y-%m-%d")

        if task_name == "daily_watch":
            return self._run_daily_watch(date_str)
        elif task_name == "weekly_tech":
            return self._run_weekly_tech(date_str)
        elif task_name == "area_analysis":
            area = kwargs.get("area", "")
            if not area:
                raise ValueError("area parameter required for area_analysis")
            return self._run_area_analysis(area, date_str)
        elif task_name == "rental_valuation":
            area = kwargs.get("area", "")
            property_id = kwargs.get("property_id", "")
            return self._run_rental_valuation(area, property_id, date_str)
        elif task_name == "renovation_cost":
            work_type = kwargs.get("work_type", "")
            job_id = kwargs.get("job_id", "")
            return self._run_renovation_cost(work_type, job_id, date_str)
        else:
            raise ValueError(f"Unknown task: {task_name}")

    def _run_daily_watch(self, date_str: str) -> dict:
        """日次マーケットウォッチ"""
        regulation = self.agents["regulation_watch"].check_regulations()
        market = self.agents["market_analysis"].daily_market_watch()

        combined = {
            "task": "daily_watch",
            "date": date_str,
            "regulation_updates": regulation,
            "market_overview": market,
        }

        output_path = BASE_DIR / "data" / "system_c" / "daily" / f"market_watch_{date_str}.json"
        self._save(combined, str(output_path))

        self.notifier.notify(f"日次マーケットウォッチ完了: {date_str}")
        return combined

    def _run_weekly_tech(self, date_str: str) -> dict:
        """週次テックトレンド"""
        trends = self.agents["tech_trend"].collect_weekly_trends()

        output_path = BASE_DIR / "data" / "system_c" / "weekly" / f"tech_trends_{date_str}.json"
        self._save(trends, str(output_path))

        self.notifier.notify(f"週次テックトレンドレポート完了: {date_str}")
        return trends

    def _run_area_analysis(self, area: str, date_str: str) -> dict:
        """エリア分析"""
        area_data = self.agents["realestate_data"].collect_area_data(area)
        market_data = self.agents["market_analysis"].analyze_market(area, area_data)

        combined = {
            "task": "area_analysis",
            "area": area,
            "date": date_str,
            "area_data": area_data,
            "market_analysis": market_data,
        }

        safe_area = area.replace("/", "_").replace("\\", "_")
        output_path = (
            BASE_DIR / "data" / "system_c" / "reports" / f"area_{safe_area}_{date_str}.json"
        )
        self._save(combined, str(output_path))
        return combined

    def _run_rental_valuation(self, area: str, property_id: str, date_str: str) -> dict:
        """賃料査定"""
        data = self.agents["realestate_data"].collect_rental_data(area)
        data["property_id"] = property_id

        pid = property_id or "unknown"
        output_path = (
            BASE_DIR / "data" / "system_c" / "valuations" / f"rental_{pid}_{date_str}.json"
        )
        self._save(data, str(output_path))
        return data

    def _run_renovation_cost(self, work_type: str, job_id: str, date_str: str) -> dict:
        """リフォーム費用調査"""
        data = self.agents["realestate_data"].collect_renovation_costs(work_type)
        data["job_id"] = job_id

        jid = job_id or "unknown"
        output_path = (
            BASE_DIR / "data" / "system_c" / "costs" / f"renovation_{jid}_{date_str}.json"
        )
        self._save(data, str(output_path))
        return data

    def _save(self, data: dict, output_path: str):
        """結果を保存"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Task result saved: {path}")


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="Task name to run")
    parser.add_argument("--area", default="", help="Area for area-specific tasks")
    parser.add_argument("--property-id", default="", help="Property ID")
    parser.add_argument("--work-type", default="", help="Renovation work type")
    parser.add_argument("--job-id", default="", help="Job ID")
    args = parser.parse_args()

    scheduler = AgentScheduler()
    result = scheduler.run_task(
        args.task,
        area=args.area,
        property_id=args.property_id,
        work_type=args.work_type,
        job_id=args.job_id,
    )
    print(f"Task '{args.task}' completed")


if __name__ == "__main__":
    main()

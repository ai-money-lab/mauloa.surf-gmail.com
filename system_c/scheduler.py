"""Scheduler for System C agent tasks."""

import argparse
import logging
from datetime import timezone, timedelta

from core.notifier import Notifier
from system_c.agents.realestate_data_agent import RealEstateDataAgent
from system_c.agents.market_analysis_agent import MarketAnalysisAgent
from system_c.agents.regulation_watch_agent import RegulationWatchAgent
from system_c.agents.tech_trend_agent import TechTrendAgent

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class SystemCScheduler:
    """Schedule and execute System C agent tasks."""

    def __init__(self):
        self.realestate_agent = RealEstateDataAgent()
        self.market_agent = MarketAnalysisAgent()
        self.regulation_agent = RegulationWatchAgent()
        self.tech_agent = TechTrendAgent()
        self.notifier = Notifier()

    def run_daily_watch(self) -> None:
        """Daily market watch + regulation check."""
        logger.info("System C: Running daily watch tasks...")

        try:
            self.market_agent.daily_market_watch()
            logger.info("Market watch complete")
        except Exception as e:
            logger.error("Market watch failed: %s", e)

        try:
            self.regulation_agent.run_daily()
            logger.info("Regulation watch complete")
        except Exception as e:
            logger.error("Regulation watch failed: %s", e)

        self.notifier.send_line("System C: 日次情報収集完了")

    def run_weekly_tech(self) -> None:
        """Weekly tech trends report."""
        logger.info("System C: Running weekly tech trends...")

        try:
            self.tech_agent.run()
            logger.info("Tech trends report complete")
        except Exception as e:
            logger.error("Tech trends failed: %s", e)

        self.notifier.send_line("System C: 週次テックトレンドレポート完了")

    def run_area_analysis(self, area: str) -> dict:
        """On-demand area analysis (triggered by System B)."""
        logger.info("System C: Area analysis for %s", area)
        return self.realestate_agent.analyze_area(area)

    def run_rental_valuation(self, property_id: str, params: dict = None) -> dict:
        """On-demand rental valuation."""
        logger.info("System C: Rental valuation for %s", property_id)
        return self.realestate_agent.rental_valuation(property_id, params)

    def run_renovation_cost(self, job_id: str, params: dict = None) -> dict:
        """On-demand renovation cost research."""
        logger.info("System C: Renovation cost for %s", job_id)
        return self.realestate_agent.renovation_cost(job_id, params)

    def run_task(self, task_name: str, **kwargs) -> None:
        """Route to the correct task handler."""
        handlers = {
            "daily_watch": self.run_daily_watch,
            "weekly_tech": self.run_weekly_tech,
            "area_analysis": lambda: self.run_area_analysis(kwargs.get("area", "")),
            "rental_valuation": lambda: self.run_rental_valuation(
                kwargs.get("property_id", ""), kwargs
            ),
            "renovation_cost": lambda: self.run_renovation_cost(
                kwargs.get("job_id", ""), kwargs
            ),
        }

        handler = handlers.get(task_name)
        if handler:
            handler()
        else:
            logger.error("Unknown task: %s", task_name)


def main():
    parser = argparse.ArgumentParser(description="System C Scheduler")
    parser.add_argument("--task", required=True, help="Task name to execute")
    parser.add_argument("--area", default="", help="Area for area_analysis")
    parser.add_argument("--property-id", default="", help="Property ID for valuation")
    parser.add_argument("--job-id", default="", help="Job ID for renovation cost")
    args = parser.parse_args()

    scheduler = SystemCScheduler()
    scheduler.run_task(
        args.task,
        area=args.area,
        property_id=args.property_id,
        job_id=args.job_id,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

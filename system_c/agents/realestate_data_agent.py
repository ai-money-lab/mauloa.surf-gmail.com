"""不動産データリサーチャーエージェント

指定エリアの物件情報・成約事例・地価データを網羅的に収集し構造化する。
リアルタイムAPIから最新データを取得し、Claudeで分析を補完する。
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

import requests
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent

# 東京都の区コード（国交省API用）
TOKYO_CITY_CODES = {
    "千代田区": "13101", "中央区": "13102", "港区": "13103",
    "新宿区": "13104", "文京区": "13105", "台東区": "13106",
    "墨田区": "13107", "江東区": "13108", "品川区": "13109",
    "目黒区": "13110", "大田区": "13111", "世田谷区": "13112",
    "渋谷区": "13113", "中野区": "13114", "杉並区": "13115",
    "豊島区": "13116", "北区": "13117", "荒川区": "13118",
    "板橋区": "13119", "練馬区": "13120", "足立区": "13121",
    "葛飾区": "13122", "江戸川区": "13123",
}

# 都道府県コード（国交省API用）
PREFECTURE_CODES = {
    "北海道": "01", "青森県": "02", "岩手県": "03", "宮城県": "04",
    "秋田県": "05", "山形県": "06", "福島県": "07", "茨城県": "08",
    "栃木県": "09", "群馬県": "10", "埼玉県": "11", "千葉県": "12",
    "東京都": "13", "神奈川県": "14", "新潟県": "15", "富山県": "16",
    "石川県": "17", "福井県": "18", "山梨県": "19", "長野県": "20",
    "岐阜県": "21", "静岡県": "22", "愛知県": "23", "三重県": "24",
    "滋賀県": "25", "京都府": "26", "大阪府": "27", "兵庫県": "28",
    "奈良県": "29", "和歌山県": "30", "鳥取県": "31", "島根県": "32",
    "岡山県": "33", "広島県": "34", "山口県": "35", "徳島県": "36",
    "香川県": "37", "愛媛県": "38", "高知県": "39", "福岡県": "40",
    "佐賀県": "41", "長崎県": "42", "熊本県": "43", "大分県": "44",
    "宮崎県": "45", "鹿児島県": "46", "沖縄県": "47",
}


class RealEstateDataAgent:
    """不動産データ収集エージェント（リアルタイムAPI対応）"""

    # 新API（2024年4月〜）: reinfolib.mlit.go.jp
    # 旧API（land.mlit.go.jp）は廃止済み
    REINFOLIB_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker()
        self.rate_limit_delay = 0.5
        self.reinfolib_api_key = os.getenv("REINFOLIB_API_KEY", "")

    # ──────────────────────────────────────────────
    # Public: エリア総合データ収集
    # ──────────────────────────────────────────────
    def collect_area_data(self, area: str, params: dict | None = None) -> dict:
        """エリア総合データを収集（リアルタイムAPI + Claude分析）"""
        logger.info(f"Collecting area data for: {area}")

        pref_code, city_code = self._resolve_area_codes(area)

        # 各APIからリアルタイムデータを取得
        land_prices = self._get_land_prices(area, pref_code, city_code)
        trade_history = self._get_trade_history(area, pref_code, city_code)
        population = self._get_population_data(area, pref_code)

        data = {
            "area": area,
            "collected_at": datetime.now(JST).isoformat(),
            "data_sources": [],
            "land_prices": land_prices,
            "trade_history": trade_history,
            "population": population,
            "market_analysis": {},
        }

        # データソース記録
        if land_prices.get("data"):
            data["data_sources"].append({
                "name": "国土交通省 土地総合情報システム",
                "url": "https://www.land.mlit.go.jp/webland/",
                "type": "API",
                "fetched_at": datetime.now(JST).isoformat(),
            })
        if population:
            data["data_sources"].append({
                "name": "e-Stat 政府統計ポータル",
                "url": "https://www.e-stat.go.jp/",
                "type": "API",
                "fetched_at": datetime.now(JST).isoformat(),
            })

        # 不動産情報ライブラリからも補完
        reinfolib = self._get_reinfolib_data(area, pref_code)
        if reinfolib:
            data["reinfolib_data"] = reinfolib
            data["data_sources"].append({
                "name": "国交省 不動産情報ライブラリ",
                "url": "https://www.reinfolib.mlit.go.jp/",
                "type": "API",
                "fetched_at": datetime.now(JST).isoformat(),
            })

        # Claude APIで実データに基づく市場分析
        api_data_summary = self._summarize_api_data(data)
        prompt = (
            f"以下は{area}のリアルタイム公的APIデータです。\n"
            f"このデータに基づいて市場動向をJSON形式で分析してください。\n\n"
            f"## 実データ:\n{api_data_summary}\n\n"
            f"## 分析項目:\n"
            f"1. 地価トレンド（直近3年の傾向）\n"
            f"2. 取引価格の中央値と平均値\n"
            f"3. 人口動態と需要予測\n"
            f"4. エリアの強み・弱み\n"
            f"5. 投資判断サマリー\n\n"
            f"※ データに基づく客観的分析のみ。データが不足している場合はその旨を明記。"
        )

        try:
            analysis = self.claude.generate_json(prompt, max_tokens=4096)
            data["market_analysis"] = analysis
        except Exception as e:
            logger.error(f"Market analysis failed: {e}")

        # 品質チェック
        quality = self.quality_checker.check(
            profile="data_collection",
            content=json.dumps(data, ensure_ascii=False),
            context=f"area_data_{area}",
        )
        data["quality_score"] = quality.total_score
        data["quality_result"] = quality.result

        return data

    # ──────────────────────────────────────────────
    # Public: 賃料データ収集
    # ──────────────────────────────────────────────
    def collect_rental_data(
        self, area: str, property_type: str = "", params: dict | None = None
    ) -> dict:
        """賃料相場データを収集（リアルタイムAPI + Claude分析）"""
        logger.info(f"Collecting rental data for: {area}")
        params = params or {}

        pref_code, city_code = self._resolve_area_codes(area)

        # 国交省API: 賃貸取引事例を取得
        rental_trades = self._get_rental_trades(area, pref_code, city_code)

        # 地価データも取得（賃料の裏付け）
        land_prices = self._get_land_prices(area, pref_code, city_code)

        data = {
            "area": area,
            "property_type": property_type or params.get("property_type", ""),
            "collected_at": datetime.now(JST).isoformat(),
            "data_sources": [],
            "rental_trade_data": rental_trades,
            "land_price_data": land_prices,
            "rental_analysis": {},
        }

        if rental_trades.get("data"):
            data["data_sources"].append({
                "name": "国土交通省 土地総合情報システム（賃貸取引事例）",
                "url": "https://www.land.mlit.go.jp/webland/",
                "type": "API",
                "fetched_at": datetime.now(JST).isoformat(),
            })
        if land_prices.get("data"):
            data["data_sources"].append({
                "name": "国土交通省 土地総合情報システム（地価）",
                "url": "https://www.land.mlit.go.jp/webland/",
                "type": "API",
                "fetched_at": datetime.now(JST).isoformat(),
            })

        # Claude APIで実データに基づく賃料分析
        api_summary = self._summarize_rental_data(rental_trades, land_prices, params)
        prompt = (
            f"以下は{area}のリアルタイム公的取引データです。\n"
            f"このデータに基づいて賃料分析をJSON形式で行ってください。\n\n"
            f"## 物件情報:\n{json.dumps(params, ensure_ascii=False)}\n\n"
            f"## 実データ:\n{api_summary}\n\n"
            f"## 分析・出力項目:\n"
            f"1. 適正賃料レンジ（下限・推奨・上限）\n"
            f"2. 坪単価の相場\n"
            f"3. 周辺の類似取引事例（実データから抽出）\n"
            f"4. 空室リスク評価\n"
            f"5. 賃料設定の根拠（どのデータからその結論に至ったか明記）\n"
            f"6. 築年数・構造による補正説明\n\n"
            f"※ 実データに基づく分析のみ。推測の場合はその旨を明記。"
        )

        try:
            rental_analysis = self.claude.generate_json(prompt, max_tokens=4096)
            data["rental_analysis"] = rental_analysis
        except Exception as e:
            logger.error(f"Rental analysis failed: {e}")

        return data

    # ──────────────────────────────────────────────
    # Public: リフォーム費用収集
    # ──────────────────────────────────────────────
    def collect_renovation_costs(self, work_type: str, area: str = "", params: dict | None = None) -> dict:
        """リフォーム費用相場を収集"""
        logger.info(f"Collecting renovation costs for: {work_type}")
        params = params or {}

        # 地価データ（エリアの価格水準の参考）
        pref_code, _ = self._resolve_area_codes(area) if area else ("13", "")
        land_prices = self._get_land_prices(area or "東京都", pref_code, "")

        prompt = (
            f"以下のリフォーム工事の費用相場をJSON形式で出力してください。\n"
            f"工事種別: {work_type}\n"
            f"エリア: {area or '東京都内'}\n"
            f"物件情報: {json.dumps(params, ensure_ascii=False)}\n\n"
            f"## 参考データ（地価水準）:\n"
            f"取引件数: {len(land_prices.get('data', []))}件\n\n"
            f"## 必要項目:\n"
            f"1. 工事内容別の費用レンジ（最低〜標準〜高品質）\n"
            f"2. 工期目安\n"
            f"3. コストダウンのポイント\n"
            f"4. 注意事項\n\n"
            f"※ 2024-2025年の最新相場に基づいてください。"
        )

        try:
            data = self.claude.generate_json(prompt, max_tokens=4096)
            data["work_type"] = work_type
            data["area"] = area
            data["collected_at"] = datetime.now(JST).isoformat()
            data["data_sources"] = [{
                "name": "HIROKI AI分析（業界相場データベース）",
                "type": "AI分析",
                "fetched_at": datetime.now(JST).isoformat(),
            }]
            return data
        except Exception as e:
            logger.error(f"Renovation cost collection failed: {e}")
            return {"work_type": work_type, "error": str(e)}

    # ──────────────────────────────────────────────
    # Private: エリアコード解決
    # ──────────────────────────────────────────────
    def _resolve_area_codes(self, area: str) -> tuple[str, str]:
        """住所文字列から都道府県コード・市区町村コードを推定"""
        pref_code = "13"  # デフォルト: 東京都
        city_code = ""

        for pref_name, code in PREFECTURE_CODES.items():
            if pref_name in area:
                pref_code = code
                break

        for city_name, code in TOKYO_CITY_CODES.items():
            if city_name in area:
                city_code = code
                break

        logger.info(f"Area codes resolved: pref={pref_code}, city={city_code} for '{area}'")
        return pref_code, city_code

    # ──────────────────────────────────────────────
    # Private: 国交省API - 地価・取引データ
    # ──────────────────────────────────────────────
    def _get_land_prices(self, area: str, pref_code: str = "13", city_code: str = "") -> dict:
        """国交省 不動産情報ライブラリAPI: 不動産取引価格データ取得

        2024年4月より reinfolib.mlit.go.jp に統合。API key必須。
        """
        if not self.reinfolib_api_key:
            logger.info("REINFOLIB_API_KEY not set, skipping land price API")
            return {"status": "skipped", "reason": "API key not configured", "data": []}

        now = datetime.now(JST)
        year = now.year

        params = {
            "year": str(year),
            "area": pref_code,
        }
        if city_code:
            params["city"] = city_code

        headers = {
            "Ocp-Apim-Subscription-Key": self.reinfolib_api_key,
        }

        try:
            logger.info(f"Fetching land prices (reinfolib): pref={pref_code}, city={city_code}")
            response = requests.get(
                f"{self.REINFOLIB_BASE}/XIT001",
                params=params,
                headers=headers,
                timeout=15,
            )
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                result = response.json()
                data_list = result.get("data", [])
                logger.info(f"Land price API: {len(data_list)} records fetched")

                if data_list:
                    result["summary"] = self._calc_trade_summary(data_list)
                return result
            else:
                logger.warning(f"Land price API returned {response.status_code}")
                return {"status": "error", "code": response.status_code, "data": []}
        except requests.RequestException as e:
            logger.error(f"Land price API error: {e}")
            return {"status": "error", "error": str(e), "data": []}

    def _get_rental_trades(self, area: str, pref_code: str = "13", city_code: str = "") -> dict:
        """国交省 不動産情報ライブラリAPI: 取引事例を取得"""
        if not self.reinfolib_api_key:
            logger.info("REINFOLIB_API_KEY not set, skipping rental trades API")
            return {"status": "skipped", "reason": "API key not configured", "data": []}

        now = datetime.now(JST)
        params = {
            "year": str(now.year),
            "area": pref_code,
        }
        if city_code:
            params["city"] = city_code

        headers = {
            "Ocp-Apim-Subscription-Key": self.reinfolib_api_key,
        }

        try:
            logger.info(f"Fetching rental trades (reinfolib): pref={pref_code}, city={city_code}")
            response = requests.get(
                f"{self.REINFOLIB_BASE}/XIT001",
                params=params,
                headers=headers,
                timeout=15,
            )
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                result = response.json()
                all_data = result.get("data", [])

                # 「中古マンション等」の取引に絞り込み（賃料参考）
                filtered = [
                    d for d in all_data
                    if d.get("Type", "") in [
                        "中古マンション等", "宅地(土地と建物)",
                        "宅地(土地)", "農地", "林地",
                    ]
                ]

                logger.info(
                    f"Rental trades: {len(all_data)} total, "
                    f"{len(filtered)} filtered"
                )

                result["data"] = filtered[:200]
                if filtered:
                    result["summary"] = self._calc_trade_summary(filtered)
                return result
            else:
                logger.warning(f"Trade API returned {response.status_code}")
                return {"status": "error", "code": response.status_code, "data": []}
        except requests.RequestException as e:
            logger.error(f"Trade API error: {e}")
            return {"status": "error", "error": str(e), "data": []}

    def _get_trade_history(self, area: str, pref_code: str = "13", city_code: str = "") -> list:
        """取引事例データ取得（国交省APIから）"""
        result = self._get_land_prices(area, pref_code, city_code)
        data = result.get("data", [])
        # 直近の取引を最大50件返す
        return data[:50]

    # ──────────────────────────────────────────────
    # Private: e-Stat API - 人口統計
    # ──────────────────────────────────────────────
    def _get_population_data(self, area: str, pref_code: str = "13") -> dict:
        """e-Stat API: 人口動態データ取得"""
        api_key = os.getenv("ESTAT_API_KEY")
        if not api_key:
            logger.warning("ESTAT_API_KEY not set")
            return {}

        try:
            # 国勢調査データ: 都道府県別人口
            logger.info(f"Fetching population data: pref={pref_code}")
            response = requests.get(
                "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData",
                params={
                    "appId": api_key,
                    "statsDataId": "0003448233",  # 国勢調査 人口等基本集計
                    "cdArea": pref_code,
                    "limit": 200,
                },
                timeout=15,
            )
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                raw = response.json()
                # データの簡略化
                stats = raw.get("GET_STATS_DATA", {})
                stat_data = stats.get("STATISTICAL_DATA", {})
                data_inf = stat_data.get("DATA_INF", {})
                values = data_inf.get("VALUE", [])

                summary = {
                    "source": "e-Stat 国勢調査",
                    "prefecture_code": pref_code,
                    "record_count": len(values),
                    "fetched_at": datetime.now(JST).isoformat(),
                }

                # 人口値を抽出
                if values:
                    pop_values = []
                    for v in values[:50]:  # 最大50件
                        pop_values.append({
                            "value": v.get("$", ""),
                            "tab": v.get("@tab", ""),
                            "cat01": v.get("@cat01", ""),
                            "area": v.get("@area", ""),
                            "time": v.get("@time", ""),
                        })
                    summary["data"] = pop_values

                return summary
            else:
                logger.warning(f"e-Stat API returned {response.status_code}")
                return {"status": "error", "code": response.status_code}
        except requests.RequestException as e:
            logger.error(f"e-Stat API error: {e}")
            return {"status": "error", "error": str(e)}

    # ──────────────────────────────────────────────
    # Private: 不動産情報ライブラリ
    # ──────────────────────────────────────────────
    def _get_reinfolib_data(self, area: str, pref_code: str = "13") -> dict:
        """国交省 不動産情報ライブラリ API（市区町村コード取得）"""
        if not self.reinfolib_api_key:
            logger.info("REINFOLIB_API_KEY not set, skipping reinfolib API")
            return {}

        try:
            logger.info(f"Fetching Reinfolib city codes for pref={pref_code}")
            response = requests.get(
                f"{self.REINFOLIB_BASE}/XIT002",
                params={"area": pref_code},
                headers={"Ocp-Apim-Subscription-Key": self.reinfolib_api_key},
                timeout=10,
            )
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                return response.json()
            else:
                logger.info(f"Reinfolib API returned {response.status_code}")
                return {}
        except requests.RequestException as e:
            logger.info(f"Reinfolib API not available: {e}")
            return {}

    # ──────────────────────────────────────────────
    # Private: データ集計ヘルパー
    # ──────────────────────────────────────────────
    def _calc_trade_summary(self, trades: list) -> dict:
        """取引データの要約統計を計算"""
        prices = []
        areas = []
        unit_prices = []

        for t in trades:
            # 取引価格
            price_str = t.get("TradePrice", "")
            if price_str and price_str.isdigit():
                prices.append(int(price_str))

            # 面積
            area_str = t.get("Area", "")
            if area_str:
                try:
                    areas.append(float(area_str))
                except (ValueError, TypeError):
                    pass

            # 坪単価
            unit_str = t.get("UnitPrice", "")
            if unit_str and unit_str.isdigit():
                unit_prices.append(int(unit_str))

        summary = {
            "total_records": len(trades),
            "price_stats": {},
            "area_stats": {},
            "unit_price_stats": {},
        }

        if prices:
            prices.sort()
            summary["price_stats"] = {
                "min": prices[0],
                "max": prices[-1],
                "median": prices[len(prices) // 2],
                "average": sum(prices) // len(prices),
                "count": len(prices),
            }

        if areas:
            areas.sort()
            summary["area_stats"] = {
                "min": areas[0],
                "max": areas[-1],
                "median": areas[len(areas) // 2],
                "average": round(sum(areas) / len(areas), 1),
                "count": len(areas),
            }

        if unit_prices:
            unit_prices.sort()
            summary["unit_price_stats"] = {
                "min": unit_prices[0],
                "max": unit_prices[-1],
                "median": unit_prices[len(unit_prices) // 2],
                "average": unit_prices[len(unit_prices) // 2],
                "count": len(unit_prices),
            }

        # 物件種別の内訳
        type_counts: dict[str, int] = {}
        for t in trades:
            tp = t.get("Type", "不明")
            type_counts[tp] = type_counts.get(tp, 0) + 1
        summary["type_breakdown"] = type_counts

        # 地域の内訳
        district_counts: dict[str, int] = {}
        for t in trades:
            dist = t.get("Municipality", "") or t.get("DistrictName", "不明")
            district_counts[dist] = district_counts.get(dist, 0) + 1
        summary["district_breakdown"] = dict(
            sorted(district_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return summary

    def _summarize_api_data(self, data: dict) -> str:
        """APIデータを分析用に要約"""
        parts = []

        lp = data.get("land_prices", {})
        if lp.get("summary"):
            s = lp["summary"]
            parts.append(
                f"【地価・取引データ】{s.get('total_records', 0)}件\n"
                f"  価格: {s.get('price_stats', {})}\n"
                f"  種別内訳: {s.get('type_breakdown', {})}\n"
                f"  地域内訳: {s.get('district_breakdown', {})}"
            )

        pop = data.get("population", {})
        if pop.get("data"):
            parts.append(
                f"【人口データ】{pop.get('record_count', 0)}レコード\n"
                f"  出典: {pop.get('source', 'e-Stat')}"
            )

        th = data.get("trade_history", [])
        if th:
            parts.append(f"【取引事例】直近{len(th)}件の取引データあり")

        reinfolib = data.get("reinfolib_data", {})
        if reinfolib:
            parts.append(f"【不動産情報ライブラリ】データ取得済み")

        if not parts:
            parts.append("（APIデータの取得に失敗。一般的な市場知識で分析してください）")

        return "\n\n".join(parts)

    def _summarize_rental_data(self, rental_trades: dict, land_prices: dict, params: dict) -> str:
        """賃料分析用にデータを要約"""
        parts = []

        rt = rental_trades
        if rt.get("summary"):
            s = rt["summary"]
            parts.append(
                f"【周辺取引事例】{s.get('total_records', 0)}件\n"
                f"  取引価格: {s.get('price_stats', {})}\n"
                f"  面積: {s.get('area_stats', {})}\n"
                f"  種別内訳: {s.get('type_breakdown', {})}"
            )

            # 類似物件の取引事例を詳細表示（最大10件）
            data = rt.get("data", [])
            similar = [
                d for d in data
                if d.get("Type", "") == "中古マンション等"
            ][:10]
            if similar:
                parts.append("【類似物件（中古マンション）取引事例】")
                for i, s_item in enumerate(similar, 1):
                    parts.append(
                        f"  {i}. {s_item.get('Municipality', '')}{s_item.get('DistrictName', '')} "
                        f"築{s_item.get('BuildingYear', '?')} "
                        f"{s_item.get('Area', '?')}㎡ "
                        f"¥{s_item.get('TradePrice', '?')} "
                        f"({s_item.get('Period', '')})"
                    )

        lp = land_prices
        if lp.get("summary"):
            s = lp["summary"]
            parts.append(
                f"\n【地価データ】{s.get('total_records', 0)}件\n"
                f"  価格帯: {s.get('price_stats', {})}"
            )

        if not parts:
            parts.append("（APIデータの取得に失敗。一般的な市場知識で分析してください）")

        return "\n".join(parts)

    # ──────────────────────────────────────────────
    # Public: 保存
    # ──────────────────────────────────────────────
    def save_result(self, data: dict, output_path: str) -> str:
        """収集結果を保存"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Data saved: {path}")
        return str(path)

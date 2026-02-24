#!/usr/bin/env python3
"""
NEXUS デモ実行 — モック付きで全自律ループを体験

APIキー不要。全Claude API呼び出しをモックで差し替えて
NEXUSの CRAWL → TRY → DEBATE → EVOLVE フローを実演する。
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch
from tempfile import mkdtemp

# モックレスポンス定義
MOCK_CRAWL = json.dumps({
    "opportunities": [
        {
            "title": "不動産AI査定ツール SaaS",
            "opportunity_type": "api_service",
            "feasibility": "short_term",
            "estimated_revenue": 150000,
            "confidence": 0.85,
            "description": "AIによる賃料査定APIを不動産会社向けに月額提供",
            "platform": "自社サイト",
            "competition_level": "低",
            "required_skills": ["Python", "Claude API", "不動産知識"],
            "action_steps": ["APIプロトタイプ", "テストデータ収集", "β版提供"],
            "risks": ["精度の検証が必要"],
        },
        {
            "title": "業務効率化プロンプトパック for 不動産",
            "opportunity_type": "digital_product",
            "feasibility": "immediate",
            "estimated_revenue": 30000,
            "confidence": 0.9,
            "description": "不動産業務をAIで効率化するプロンプト50選",
            "platform": "coconala",
            "competition_level": "中",
            "required_skills": ["プロンプト設計"],
            "action_steps": ["プロンプト作成", "テスト", "Coconala出品"],
            "risks": ["競合増加"],
        },
        {
            "title": "AIチャットボット導入コンサル",
            "opportunity_type": "consulting",
            "feasibility": "immediate",
            "estimated_revenue": 80000,
            "confidence": 0.75,
            "description": "中小不動産会社向けAIチャットボット導入支援",
            "platform": "lancers",
            "competition_level": "低",
            "required_skills": ["LINE API", "Claude API", "コンサルティング"],
            "action_steps": ["事例資料作成", "提案活動"],
            "risks": ["営業工数"],
        },
    ],
    "market_insights": "不動産×AI市場は急速に拡大中。特にチャットボットと査定AIの需要が高い",
    "top_3_recommendation": ["プロンプトパック", "コンサル", "SaaS"],
})

MOCK_PRODUCT = json.dumps({
    "product_name": "不動産業務効率化AIプロンプト50選",
    "description": "物件説明文の自動生成、顧客対応テンプレート、市場分析レポート生成など50種類のプロンプトを収録",
    "prompts": [
        {"title": "物件説明文ジェネレーター", "prompt": "以下の物件情報から魅力的な説明文を生成...",
         "use_case": "物件紹介", "expected_output": "物件説明文"},
        {"title": "賃料交渉対応テンプレ", "prompt": "入居希望者からの賃料交渉に対して...",
         "use_case": "賃料交渉", "expected_output": "交渉回答文"},
        {"title": "設備トラブル初期対応", "prompt": "入居者からの設備不具合報告に対して...",
         "use_case": "トラブル対応", "expected_output": "対応指示文"},
    ],
    "price_suggestion": 4980,
    "target_audience": "不動産管理会社・オーナー",
})

MOCK_LISTING = json.dumps({
    "title": "【AI×不動産】業務効率化プロンプト50選",
    "subtitle": "物件説明文・顧客対応・市場分析を一気に自動化",
    "description": "ChatGPT/Claudeで使える不動産業務特化プロンプト集",
    "bullet_points": ["即使用可能な50テンプレート", "物件説明文を1分で生成", "顧客対応時間80%削減"],
    "tags": ["AI", "不動産", "業務効率化", "プロンプト"],
    "category_suggestion": "ビジネス > 業務効率化",
})

MOCK_EVAL_SUCCESS = json.dumps({
    "scores": {"market_fit": 9, "quality": 8, "differentiation": 7, "pricing": 9, "scalability": 8},
    "total_score": 41,
    "verdict": "success",
    "strengths": ["不動産特化でニッチ需要を捉えている", "即使用可能な実用性", "価格設定が妥当"],
    "weaknesses": ["一部のプロンプトは汎用的すぎる"],
    "improvements": ["業種別カスタマイズ版の展開"],
    "would_you_buy": True,
})

MOCK_EVAL_FAIL = json.dumps({
    "scores": {"market_fit": 5, "quality": 6, "differentiation": 3, "pricing": 7, "scalability": 4},
    "total_score": 25,
    "verdict": "failure",
    "strengths": ["基本機能は揃っている"],
    "weaknesses": ["競合APIとの差別化が不十分", "精度の検証が不足"],
    "improvements": ["独自データセットで精度向上", "不動産特化の評価指標追加"],
    "would_you_buy": False,
})

MOCK_DEBATE_ALPHA = json.dumps({
    "argument": "SaaSモデルは長期的収益性が高い。精度を実データで磨けば差別化可能",
    "proposed_improvements": ["実際の成約データで学習", "大手管理会社とのβテスト"],
    "counter_to_omega": "初期の精度不足はβ版として許容される。まず市場投入が重要",
    "concessions": ["精度検証は確かに必要", "βテスト期間を設けるべき"],
})

MOCK_DEBATE_OMEGA = json.dumps({
    "argument": "精度なしにSaaSを出すと信頼を失う。まずプロンプトパックで実績を作るべき",
    "critical_issues": ["査定精度の検証不足"],
    "counter_to_alpha": "βとはいえ不動産は高額取引。精度問題は致命的",
    "constructive_suggestions": ["プロンプトパック → 顧客基盤構築 → SaaS展開の段階的アプローチ"],
})

MOCK_DEBATE_SYNTH = json.dumps({
    "consensus": "段階的アプローチで合意：Phase1でプロンプトパック販売→顧客獲得、Phase2でSaaS開発",
    "improvements": ["プロンプトパックを先行出品", "顧客フィードバック収集", "SaaS用データ蓄積"],
    "new_strategy": "プロンプトパック販売で不動産AI市場の理解を深め、SaaSのβ版を段階的に開発",
    "should_retry": True,
    "pivot_suggestion": "SaaSは一旦棚上げ、プロンプトパック→コンサル→SaaSの3段階で展開",
    "confidence": 0.82,
    "key_insight": "小さく始めて大きく育てる。プロンプトパックで市場の信頼を獲得してからSaaS化",
})

MOCK_EVOLVE = json.dumps({
    "success_factors": ["不動産業界特化", "即使用可能な実用性", "適正価格"],
    "replication_ideas": [
        {"title": "飲食店向けAIプロンプトパック", "description": "飲食業界特化版",
         "estimated_revenue": 30000, "platform": "coconala", "confidence": 0.7},
        {"title": "医療クリニック向けAI対応テンプレート", "description": "医療×AI",
         "estimated_revenue": 50000, "platform": "note", "confidence": 0.6},
    ],
    "improvements": ["動画チュートリアル追加", "業種横展開"],
    "kill_list": ["汎用プロンプト集（差別化不足）"],
    "next_gen_strategy": "不動産成功パターンを他業種に横展開。各業種の専門家とコラボ",
})


def run():
    """モック付きNEXUSデモ実行."""
    tmp_dir = Path(mkdtemp(prefix="nexus_demo_"))

    # 全Claude API呼び出しをモックに差し替え
    call_counts = {"crawl": 0, "factory": 0, "trial": 0, "debate": 0, "evolve": 0}

    def mock_crawl_api(**kwargs):
        call_counts["crawl"] += 1
        return MOCK_CRAWL

    def mock_factory_api(**kwargs):
        call_counts["factory"] += 1
        msg = kwargs.get("messages", [{}])[0].get("content", "")
        if "出品" in msg or "listing" in msg.lower():
            return MOCK_LISTING
        return MOCK_PRODUCT

    def mock_trial_api(**kwargs):
        call_counts["trial"] += 1
        msg = kwargs.get("messages", [{}])[0].get("content", "")
        if "SaaS" in msg or "api_service" in msg:
            return MOCK_EVAL_FAIL
        return MOCK_EVAL_SUCCESS

    def mock_debate_api(**kwargs):
        call_counts["debate"] += 1
        system = kwargs.get("system", "")
        if "ALPHA" in system:
            return MOCK_DEBATE_ALPHA
        elif "OMEGA" in system:
            return MOCK_DEBATE_OMEGA
        return MOCK_DEBATE_SYNTH

    def mock_evolve_api(**kwargs):
        call_counts["evolve"] += 1
        return MOCK_EVOLVE

    # 各モジュールのcall_apiをモック化
    patches = [
        patch("nexus.crawler.opportunity_crawler.call_api", side_effect=mock_crawl_api),
        patch("nexus.factory.product_generator.call_api", side_effect=mock_factory_api),
        patch("nexus.trial.trial_runner.call_api", side_effect=mock_trial_api),
        patch("nexus.debate.debate_engine.call_api", side_effect=mock_debate_api),
        patch("nexus.evolution.evolver.call_api", side_effect=mock_evolve_api),
    ]

    for p in patches:
        p.start()

    try:
        from nexus.orchestrator.nexus_core import NexusOrchestrator

        print()
        print("╔" + "═" * 58 + "╗")
        print("║" + "  NEXUS — AI自律収益化エンジン デモ実行".center(50) + "║")
        print("║" + "  CRAWL → TRY → DEBATE → EVOLVE".center(52) + "║")
        print("╚" + "═" * 58 + "╝")

        orchestrator = NexusOrchestrator(data_dir=tmp_dir)

        # ═══ Phase 1: CRAWL ═══
        print("\n" + "━" * 60)
        print("  Phase 1: CRAWL — 収益機会を探索")
        print("━" * 60)

        crawl_result = orchestrator.run(mode="crawl")
        opps = crawl_result.get("top_opportunities", [])

        for opp in opps:
            print(f"\n  ■ {opp['title']}")
            print(f"    想定月収: ¥{opp['estimated_revenue']:,}")
            print(f"    実現性: {opp['feasibility']} | 確度: {opp['confidence']:.0%}")

        print(f"\n  → {len(opps)}件の機会を発見")

        # ═══ Phase 2: TRIAL ═══
        print("\n" + "━" * 60)
        print("  Phase 2: TRIAL — 実際にTRY（商品生成→評価）")
        print("━" * 60)

        trial_result = orchestrator.run(mode="trial")
        trials = trial_result.get("trials", [])
        stats = trial_result.get("stats", {})

        for t in trials:
            mark = "OK" if t["result"] == "success" else "NG" if t["result"] == "failure" else ".."
            score = t.get("evaluation", {}).get("total_score", "?")
            print(f"\n  [{mark}] {t['opportunity_title']}")
            print(f"      スコア: {score}/50 → {t['result']}")
            if t.get("lessons"):
                print(f"      学び: {t['lessons'][0]}")

        print(f"\n  → 成功率: {stats.get('success_rate', 0):.0%}")

        # ═══ Phase 3: DEBATE ═══
        failures = [t for t in trials if t.get("result") != "success" and t.get("debate_requested")]
        if failures:
            print("\n" + "━" * 60)
            print("  Phase 3: DEBATE — 失敗をAI議論で改善策を導出")
            print("━" * 60)

            from nexus.trial.trial_runner import Trial, TrialMode, TrialResult
            from nexus.crawler.opportunity_crawler import Opportunity, OpportunityType, Feasibility

            debate_engine = orchestrator.debate

            for t in failures[:2]:
                opp = Opportunity(
                    title=t["opportunity_title"],
                    opportunity_type=OpportunityType.API_SERVICE,
                    feasibility=Feasibility.SHORT_TERM,
                    estimated_revenue=150000,
                    confidence=0.85,
                )
                trial_obj = Trial(
                    opportunity=opp,
                    mode=TrialMode.DRY_RUN,
                    result=TrialResult.FAILURE,
                    evaluation=t.get("evaluation", {}),
                    lessons=t.get("lessons", []),
                )

                debate_result = debate_engine.debate(trial_obj)
                print(f"\n  ▼ 議論: {t['opportunity_title']}")
                print(f"    ラウンド数: {len(debate_result.rounds)}")
                print(f"    合意: {debate_result.consensus[:60]}...")
                print(f"    再挑戦: {'はい' if debate_result.should_retry else 'いいえ'}")
                print(f"    確度: {debate_result.confidence:.0%}")
                if debate_result.improvements:
                    print(f"    改善策:")
                    for imp in debate_result.improvements[:3]:
                        print(f"      → {imp}")

        # ═══ Phase 4: EVOLVE ═══
        print("\n" + "━" * 60)
        print("  Phase 4: EVOLVE — 成功パターンを増殖・進化")
        print("━" * 60)

        evolve_result = orchestrator.run(mode="evolve")
        gen = evolve_result.get("generation", {})
        evo_stats = evolve_result.get("stats", {})

        print(f"\n  世代: {gen.get('gen_number', 0)}")
        print(f"  発見パターン: {evo_stats.get('total_patterns', 0)}")

        new_opps = evolve_result.get("new_opportunities", [])
        if new_opps:
            print(f"  新規複製機会:")
            for no in new_opps[:3]:
                print(f"    → {no.get('title', '?')} (¥{no.get('estimated_revenue', 0):,})")

        # ═══ 最終レポート ═══
        state = orchestrator.state
        print("\n" + "═" * 60)
        print("  NEXUS 実行結果レポート")
        print("═" * 60)
        print(f"""
  総サイクル:        {state.cycles_completed}
  発見機会:          {state.total_opportunities}件
  Trial実行:         {state.trials_run}件
  Trial成功:         {state.trials_succeeded}件
  成功率:            {state.trials_succeeded / max(state.trials_run, 1):.0%}
  発見パターン:      {state.patterns_discovered}個
  推定月間収益:      ¥{state.total_revenue_potential:,.0f}
  自律ループ完了:    {state.autonomous_loops}回
""")

        print("  API呼び出し回数（モック）:")
        for k, v in call_counts.items():
            print(f"    {k}: {v}回")

        print("\n" + "═" * 60)
        print("  NEXUS demo completed successfully.")
        print("═" * 60 + "\n")

    finally:
        for p in patches:
            p.stop()


if __name__ == "__main__":
    run()

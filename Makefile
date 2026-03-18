# ═══════════════════════════════════════════════════════════
# HIROKI AI Empire — Makefile
# 全操作をワンコマンドで実行
# ═══════════════════════════════════════════════════════════

.PHONY: help setup test bot-start bot-stop bot-dev deploy-render deploy-docker \
        report-daily report-monthly faq-check health logs clean system-e-launch

# プロジェクトルートをPYTHONPATHに追加（core/ 等のimport解決）
export PYTHONPATH := $(CURDIR):$(PYTHONPATH)

# デフォルト: ヘルプ表示
help:
	@echo ""
	@echo "═══════════════════════════════════════════════════"
	@echo " HIROKI AI Empire — コマンド一覧"
	@echo "═══════════════════════════════════════════════════"
	@echo ""
	@echo " セットアップ:"
	@echo "   make setup          ワンコマンド初期セットアップ"
	@echo "   make install        依存パッケージインストール"
	@echo "   make check          セットアップ確認"
	@echo ""
	@echo " Bot操作:"
	@echo "   make bot-start      本番起動"
	@echo "   make bot-dev        開発モード起動（ホットリロード）"
	@echo "   make bot-stop       Docker停止"
	@echo "   make bot-test       ターミナルでBotテスト"
	@echo ""
	@echo " デプロイ:"
	@echo "   make deploy-render  Render.comにデプロイ"
	@echo "   make deploy-docker  Docker Composeで起動"
	@echo ""
	@echo " レポート:"
	@echo "   make report-daily   日次レポート生成"
	@echo "   make report-monthly 月次サマリー生成"
	@echo ""
	@echo " 運用:"
	@echo "   make health         ヘルスチェック"
	@echo "   make faq-check      FAQ更新提案チェック"
	@echo "   make logs           直近のログ表示"
	@echo "   make x-posts        実績→X投稿案生成"
	@echo ""
	@echo " テスト:"
	@echo "   make test           全テスト実行"
	@echo "   make lint           コード品質チェック"
	@echo ""
	@echo " System A-E:"
	@echo "   make system-a       X投稿パイプライン実行"
	@echo "   make system-c       データ収集実行"
	@echo "   make system-d       実績コンテンツ生成"
	@echo "   make system-e       System E フルパイプライン"
	@echo "   make system-e-gen   System E コンテンツ生成のみ"
	@echo "   make system-e-post  System E 投稿のみ"
	@echo "   make system-e-engage System Eエンゲージメント収集+返信"
	@echo "   make system-e-check System E ローンチ準備チェック"
	@echo "   make system-e-launch System E ワンクリック起動セットアップ"
	@echo ""
	@echo " その他:"
	@echo "   make clean          キャッシュ/一時ファイル削除"
	@echo "   make cron-install   crontab一括登録"
	@echo "═══════════════════════════════════════════════════"

# ─── セットアップ ───
setup:
	@./inquiry_bot/setup.sh

install:
	pip install -r requirements.txt

check:
	python -m inquiry_bot.check_setup

# ─── Bot操作 ───
bot-start:
	uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080

bot-dev:
	uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --reload --log-level debug

bot-stop:
	docker compose -f inquiry_bot/docker-compose.yaml down

bot-test:
	python -m inquiry_bot.test_local

# ─── デプロイ ───
deploy-docker:
	docker compose -f inquiry_bot/docker-compose.yaml up -d --build

deploy-render:
	@echo "Render.com デプロイ手順:"
	@echo "  1. https://render.com にログイン"
	@echo "  2. New Web Service → GitHubリポジトリ接続"
	@echo "  3. render.yaml の設定が自動適用されます"
	@echo "  4. Environment Variables にAPIキーを設定"
	@echo ""
	@echo "  または Deploy Hook URL をセットして:"
	@echo "    curl -X POST \$$RENDER_DEPLOY_HOOK_URL"

# ─── レポート ───
report-daily:
	python -m inquiry_bot.scheduler daily_report

report-monthly:
	python -m inquiry_bot.scheduler weekly_summary

# ─── 運用 ───
health:
	python -m inquiry_bot.scheduler health_check

faq-check:
	python -m inquiry_bot.scheduler faq_update_check

x-posts:
	python -m inquiry_bot.scheduler results_to_x

logs:
	@echo "=== 直近のログ ==="
	@ls -la data/inquiry_bot_logs/ 2>/dev/null || echo "(ログファイルなし)"
	@echo ""
	@if [ -f data/inquiry_bot_logs/$$(date +%Y%m%d).jsonl ]; then \
		echo "=== 本日のログ ==="; \
		tail -20 data/inquiry_bot_logs/inquiries_$$(date +%Y%m%d).jsonl; \
	else \
		echo "(本日のログなし)"; \
	fi

# ─── テスト ───
test:
	PYTHONPATH=. python -m pytest tests/ -v --tb=short

lint:
	@pip install ruff -q 2>/dev/null
	ruff check inquiry_bot/ core/ system_a/ system_b/ system_c/ system_d/ system_e/ --select E,W,F --ignore E501

# ─── System A-E ───
system-a:
	python system_a/daily_pipeline.py

system-c:
	python system_c/scheduler.py --task daily_watch

system-d:
	python system_d/generate_results_content.py

system-e:
	python system_e/daily_pipeline.py --mode full

system-e-gen:
	python system_e/daily_pipeline.py --mode generate

system-e-post:
	python system_e/daily_pipeline.py --mode post

system-e-engage:
	PYTHONPATH=. python -c "from system_e.engagement_collector import EngagementCollector; c = EngagementCollector(); print(f'Metrics: {c.collect_tweet_metrics()} tweets'); print(f'Mentions: {len(c.collect_mentions())} new')"
	PYTHONPATH=. python -c "from system_e.mention_responder import MentionResponder; r = MentionResponder(); print(f'Replied: {len(r.run())}')"

system-e-check:
	python system_e/scripts/launch_check.py

system-e-seed:
	python system_e/scripts/seed_content.py --days 7

system-e-launch:
	@bash system_e/scripts/setup_launch.sh

# ─── crontab一括登録 ───
cron-install:
	@PROJECT_ROOT=$$(pwd); \
	(crontab -l 2>/dev/null | grep -v "hiroki-ai-empire\|inquiry_bot.scheduler\|system_a/\|system_c/\|system_d/"; \
	echo "# ═══ HIROKI AI Empire — 自動化タスク ═══"; \
	echo "# System A: X投稿パイプライン（毎日6時）"; \
	echo "0 6 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_a/daily_pipeline.py >> data/cron.log 2>&1"; \
	echo "# System A: パフォーマンス分析（毎日21時）"; \
	echo "0 21 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_a/analyze_performance.py >> data/cron.log 2>&1"; \
	echo "# System C: データ収集（毎日7時）"; \
	echo "0 7 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_c/scheduler.py --task daily_watch >> data/cron.log 2>&1"; \
	echo "# System C: 週次テックトレンド（月曜8時）"; \
	echo "0 8 * * 1 cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_c/scheduler.py --task weekly_tech >> data/cron.log 2>&1"; \
	echo "# System D: 実績コンテンツ生成（金曜20時）"; \
	echo "0 20 * * 5 cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_d/generate_results_content.py >> data/cron.log 2>&1"; \
	echo "# Bot: 日次レポート（毎日21時）"; \
	echo "0 21 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python -m inquiry_bot.scheduler daily_report >> data/cron.log 2>&1"; \
	echo "# Bot: ヘルスチェック（5分毎）"; \
	echo "*/5 * * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python -m inquiry_bot.scheduler health_check >> data/cron.log 2>&1"; \
	echo "# Bot: FAQ更新チェック（月曜9時）"; \
	echo "0 9 * * 1 cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python -m inquiry_bot.scheduler faq_update_check >> data/cron.log 2>&1"; \
	echo "# Bot: X投稿案生成（金曜19時、System D前）"; \
	echo "0 19 * * 5 cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python -m inquiry_bot.scheduler results_to_x >> data/cron.log 2>&1"; \
	echo "# System E: コンテンツ生成（毎日21時）"; \
	echo "0 21 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_e/daily_pipeline.py --mode generate >> data/cron.log 2>&1"; \
	echo "# System E: 投稿ウィンドウ（07/12/19/23時JST）"; \
	echo "0 7 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_e/daily_pipeline.py --mode post >> data/cron.log 2>&1"; \
	echo "0 12 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_e/daily_pipeline.py --mode post >> data/cron.log 2>&1"; \
	echo "0 19 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_e/daily_pipeline.py --mode post >> data/cron.log 2>&1"; \
	echo "0 23 * * * cd $$PROJECT_ROOT && PYTHONPATH=$$PROJECT_ROOT python system_e/daily_pipeline.py --mode post >> data/cron.log 2>&1"; \
	) | crontab -
	@echo "✅ crontab 登録完了"
	@crontab -l | grep -A1 "AI Empire"

# ─── クリーンアップ ───
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "✅ クリーンアップ完了"

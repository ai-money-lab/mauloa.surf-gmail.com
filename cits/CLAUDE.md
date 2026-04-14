# CITS - Claude Intelligence Trading System

## 概要
TradingAgentsフレームワークをベースに、日本株特化のマルチエージェント取引システム。
LLMエージェントが実際のトレーディングファームの組織構造を再現し、
5段階パイプラインで売買判断を行う。

## アーキテクチャ
```
5段階パイプライン:
I.   アナリストチーム（4人並行）: ファンダメンタル、センチメント、ニュース、テクニカル
II.  リサーチチーム: Bull vs Bear ディベート（2ラウンド）
III. トレーダー: ディベート結果から売買判断
IV.  リスク管理: ポートフォリオリスク・ボラティリティ評価
V.   ファンドマネージャー: 最終承認・執行
```

## LLM設定
- deep_think_llm: claude-opus-4-6（判断・分析用）
- quick_think_llm: claude-sonnet-4-20250514（データ取得用）
- ディベート: 2ラウンド固定

## 日本株特化要素
- データソース: yfinance（^N225、個別銘柄）、J-Quants API
- ニュース: 日経、ロイター日本語版
- 発注: kabuステーションAPI → 立花証券API（Stage 2）
- 市場時間: TSE（前場9:00-11:30、後場12:30-15:00）
- 独自レイヤー: 発言者トラッカー、投資部門別売買動向、空売り残高、信用残高、EDINET

## 開発コマンド
```bash
# テスト実行
pytest cits/tests/ -v

# Lint
ruff check cits/

# ペーパートレード実行
python -m cits.core.graph.trading_graph --paper --ticker 7203

# 全パイプライン実行（ペーパー）
python -m cits.main --mode paper --ticker 7203

# ライブトレード（朝スキャン）
python -m cits.scripts.live_trader --mode morning --capital 300000

# ポジション監視
python -m cits.scripts.position_monitor

# 全銘柄スキャン（dry-run）
python -m cits.scripts.live_trader --mode full_scan --capital 300000 --dry-run

# バックテスト
python -c "from cits.backtest.engine import BacktestEngine; eng = BacktestEngine(initial_capital=100_000); print(eng.run(['7203','8306','6758','9984'], '2025-09-01', '2026-03-21', strategies=['cis_momentum','keikun']).summary())"

# ペーパートレード
python -m cits.scripts.paper_sim --days 5 --capital 100000

# ダッシュボード
python -m cits.scripts.dashboard --full

# 取引日レポート
python -m cits.scripts.daily_report --dry-run
```

## 環境変数
- `ANTHROPIC_API_KEY`: Claude API
- `JQUANTS_API_KEY`: J-Quants API
- `KABU_API_PASSWORD`: kabuステーションAPIパスワード
- `KABU_ORDER_PASSWORD`: kabuステーション注文パスワード
- `EDINET_API_KEY`: EDINET API
- `TACHIBANA_USER_ID`: 立花証券ユーザーID（Stage 2）
- `TACHIBANA_PASSWORD`: 立花証券パスワード（Stage 2）

## 口座・稼働状況
- 三菱UFJ eスマート証券（kabuステーション）
- 口座番号: 02210320
- APIユーザID: 10074931
- APIパスワード(本番): `hiroki0380` / 注文パスワード: `hiroki0380HM`

## 実装完了済み
- 5段階パイプライン（Stage I〜V）: 完全動作
- Stage I アナリスト並列化（ThreadPoolExecutor 4workers）
- kabuステーションAPI: 完全実装・テスト済み
- 立花証券API（Stage 2）: 完全実装・テスト済み
- Software OCO（TP/SL管理）: 完全実装
- バックテストエンジン（5戦略: intraday_momentum, overnight_reversal, premarket_trio, cis_momentum, keikun）
- ペーパートレードシミュレーター（APIキー不要）
- ポートフォリオダッシュボード（CLI）
- 日本市場リスクパラメータ（値幅制限、SQ日、権利付最終日、TSE時間）
- CircuitBreaker / CrashDetector / PositionSizer / WinRateEngine
- SignalTracker（シグナル単位勝率追跡）
- Voice Tracker（BOJ / FOMC / Trump）
- データソース: yfinance, J-Quants, JPX(空売り/信用/フロー), EDINET
- 全銘柄CISスキャン: morning/afternoon/full_scanで全TSE銘柄スキャン
- Kei-kun戦略統合: BacktestEngine + live_traderに完全統合
- チャートベース出口戦略: `cits/core/chart_exit.py`
- 取引日メールレポート: `cits/scripts/daily_report.py`
- config.yml駆動パラメータ: CIS/KEI paramsをconfig.ymlから読み込み
- 6リスクガード: ギャップダウン/日次損失上限/実残高管理/排他制御/BOJ-SQ削減/祝日判定

## 絶対遵守ルール
1. 損をするような発注は絶対禁止。購入根拠を明確にしてから発注
2. **時刻は日本時間（JST, UTC+9）で把握・報告。** `TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S %Z'` で確認。市場時間（9:00-15:30）との関係を常に意識
3. 「問題ない」と嘘をつくな。実行結果のみが事実
4. 自立しろ。毎回確認するな
5. PLAN B/C必須。CIS式だけに依存しない
6. 取引した日は mauloa.surf@gmail.com にレポートをメール送信

---

## 検証ルール（絶対遵守）

### 原則
- **「読んで確認した」は検証ではない。実行結果だけが事実。**
- **編集前にコードベースを調査せよ。読んでいないコードは決して変更するな。**

### 変更後の必須検証チェックリスト
```bash
# 1. Lint
ruff check cits/

# 2. Import検証
python -c "from cits.モジュール名 import クラス名"

# 3. スモークテスト
python cits/tests/smoke_test.py

# 4. ユニットテスト
pytest cits/tests/ -v --tb=short
```

### 完成の定義
- [ ] `ruff check cits/` がエラー0
- [ ] `python cits/tests/smoke_test.py` が全パス
- [ ] `pytest cits/tests/ -v` が全パス
- [ ] `python -m cits.main --help` が起動する

### 禁止事項
- 存在しないモジュール・クラス・メソッドをimportするコードを書くこと
- テストを実行せずに「テストは通るはず」と報告すること

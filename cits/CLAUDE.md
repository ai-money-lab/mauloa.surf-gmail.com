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
```

## 環境変数
- `ANTHROPIC_API_KEY`: Claude API
- `JQUANTS_API_KEY`: J-Quants API
- `KABU_API_PASSWORD`: kabuステーションAPIパスワード
- `EDINET_API_KEY`: EDINET API
- `TACHIBANA_USER_ID`: 立花証券ユーザーID（Stage 2）
- `TACHIBANA_PASSWORD`: 立花証券パスワード（Stage 2）

## 現在のステータス（2026-03-23更新）

### 口座開設
- 三菱UFJ eスマート証券: 申請済み、審査待ち（株式信用取引、特定口座源泉徴収あり）
- 選択内容: NISA無し、FX口座あり

### 実装完了済み
- 5段階パイプライン（Stage I〜V）: 完全動作
- Stage I アナリスト並列化（ThreadPoolExecutor 4workers）
- kabuステーションAPI: 完全実装・テスト済み
- 立花証券API（Stage 2）: 完全実装・テスト済み
- Software OCO（TP/SL管理）: 完全実装
- バックテストエンジン（3戦略: intraday_momentum, overnight_reversal, premarket_trio）
- ペーパートレードシミュレーター（APIキー不要）
- ポートフォリオダッシュボード（CLI）
- 日本市場リスクパラメータ（値幅制限、SQ日、権利付最終日、TSE時間）
- CircuitBreaker / CrashDetector / PositionSizer / WinRateEngine
- SignalTracker（シグナル単位勝率追跡）
- Voice Tracker（BOJ / FOMC / Trump）
- データソース: yfinance, J-Quants, JPX(空売り/信用/フロー), EDINET
- テスト: 157件全パス、smoke 84/84パス

### 口座開設後のTODO
1. kabuステーションをPCにインストール・起動
2. KABU_API_PASSWORD 環境変数を設定
3. ペーパーモードで動作確認: `python -m cits.main --mode paper --ticker 7203`
4. バックテスト実行（ローカルで）: `python -c "from cits.backtest.engine import BacktestEngine; ..."`
5. 少額（¥10万）でライブ移行: config.yml の mode: paper → mode: live

### 追加コマンド
```bash
# バックテスト（ローカルのみ、yfinanceネットワーク必要）
python -c "from cits.backtest.engine import BacktestEngine; eng = BacktestEngine(initial_capital=100_000); print(eng.run(['7203','8306','6758','9984'], '2025-09-01', '2026-03-21').summary())"

# ペーパートレード
python -m cits.scripts.paper_sim --days 5 --capital 100000

# ダッシュボード
python -m cits.scripts.dashboard --full

# ウォッチリスト一括分析
python -m cits.scripts.run_watchlist
```

## 検証ルール（絶対遵守 — AIへの必須指示）

### 原則
- **「読んで確認した」は検証ではない。実行結果だけが事実。**
- 「正しいはず」「問題ないはず」という報告は禁止。実行して証拠を出すこと。
- コードを1行でも変更したら、必ず以下の検証を実行すること。

### 変更後の必須検証チェックリスト
```bash
# 1. Lint — 全ファイル構文チェック
ruff check cits/

# 2. Import検証 — 変更したモジュールを実際にimport
python -c "from cits.モジュール名 import クラス名"

# 3. シグネチャ検証 — 呼び出しているメソッドの引数が正しいか
python -c "import inspect; from cits.モジュール名 import クラス名; print(inspect.signature(クラス名.メソッド名))"

# 4. スモークテスト — 全モジュール一括検証
python cits/tests/smoke_test.py

# 5. ユニットテスト
pytest cits/tests/ -v --tb=short
```

### 完成の定義（これを全て満たさない限り「完成」と報告してはならない）
- [ ] `ruff check cits/` がエラー0
- [ ] 全モジュールが `python -c "import cits.xxx"` で読み込める
- [ ] `python cits/tests/smoke_test.py` が全パス
- [ ] `pytest cits/tests/ -v` が全パス
- [ ] エントリーポイント `python -m cits.main --help` が起動する

### 禁止事項
- 存在しないモジュール・クラス・メソッドをimportするコードを書くこと
- 呼び出し先のシグネチャを確認せずにメソッド呼び出しを書くこと
- テストを実行せずに「テストは通るはず」と報告すること
- エラーが出ているのに「軽微な問題」として無視すること

### AI作業完了時の報告フォーマット
```
## 検証結果
- ruff check: ✅ エラー0件
- import検証: ✅ 全モジュール読み込み成功
- smoke_test: ✅ 全XX件パス
- pytest: ✅ 全XX件パス（XXs）
- エントリーポイント: ✅ --help起動確認済み

※上記は全て実際の実行結果です（実行ログ添付）
```

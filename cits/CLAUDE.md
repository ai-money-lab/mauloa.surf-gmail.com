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

## 現在のステータス（2026-04-09 JST更新）

### 口座・稼働状況
- 三菱UFJ eスマート証券: **開設完了・入金完了・取引開始済み**
- 口座番号: 02210320
- APIユーザID: 10074931
- APIパスワード(本番): `hiroki0380` / 注文パスワード: `hiroki0380HM`
- ¥100,000で稼働中

### 本番VPS (CITS専用)
- IP: 150.66.3.162 (ABLENET 3VOBDHFE, Win1 SSD, 2GB RAM)
- SSH: `ssh -i ~/.ssh/id_ed25519 Administrator@150.66.3.162`（鍵認証のみ）
- CITSコード: `C:\cits\repo\cits\`
- kabuStation: インストール済み・自動ログイン構築済み（5/5テスト成功）
- 自動ログイン方式: Chrome MCP→noVNC→スタートメニュー→ログイン→Gmail 2FA自動取得
- TightVNC: ポート5900稼働（パスワード: cits2026）
- check_readiness: ALL PASS (21/21)

### VPSタスクスケジューラ
| タスク | 時間 | 内容 |
|--------|------|------|
| CITS_KabuStation_Start | 08:25 | kabuStation起動 |
| CITS_LiveTrader | 08:30 | 朝CIS+全銘柄スキャン → **買い発注** |
| CITS_PositionMonitor | 09:30-15:00 (30分毎) | ポジション監視 → **売り決済** |
| CITS_Prefetch | 14:00 | 全銘柄データ収集 |
| CITS_Afternoon | 15:20 | ポジション監視→**売り決済** → CIS+KEI→**買い発注** + レポート |

### Claude Code scheduled-task
| タスク | スケジュール | 内容 |
|--------|------------|------|
| cits-kabu-login | 平日08:27 | kabuStation自動ログイン+2FA |

### 絶対遵守ルール
1. 損をするような発注は絶対禁止。購入根拠を明確にしてから発注
2. **時刻は日本時間（JST, UTC+9）で把握・報告。** システムはUTCなので `TZ=Asia/Tokyo date` で確認。全報告に現在JST時刻明記。市場時間（9:00-15:30）との関係を常に意識
3. 「問題ない」と嘘をつくな。実行結果のみが事実
4. 自立しろ。毎回HIROKIに確認するな
5. PLAN B/C必須。CIS式だけに依存しない
6. 取引した日は mauloa.surf@gmail.com にレポートをメール送信

### 時刻確認コマンド（毎回実行）
```bash
TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S %Z (%A)'
```

### 実装完了済み
- 5段階パイプライン（Stage I〜V）: 完全動作
- Stage I アナリスト並列化（ThreadPoolExecutor 4workers）
- kabuステーションAPI: 完全実装・テスト済み
- 立花証券API（Stage 2）: 完全実装・テスト済み
- Software OCO（TP/SL管理）: 完全実装
- バックテストエンジン（5戦略: intraday_momentum, overnight_reversal, premarket_trio, **cis_momentum, keikun**）
- ペーパートレードシミュレーター（APIキー不要）
- ポートフォリオダッシュボード（CLI）
- 日本市場リスクパラメータ（値幅制限、SQ日、権利付最終日、TSE時間）
- CircuitBreaker / CrashDetector / PositionSizer / WinRateEngine
- SignalTracker（シグナル単位勝率追跡）
- Voice Tracker（BOJ / FOMC / Trump）
- データソース: yfinance, J-Quants, JPX(空売り/信用/フロー), EDINET
- テスト: 172件全パス、smoke 88/88パス

### 2026-04-09セッションで実装（VPSデプロイ済み）
- **全銘柄CISスキャン**: morning/afternoon/full_scanで全TSE銘柄スキャン
- **Kei-kun戦略統合**: BacktestEngine + live_traderに完全統合
- **チャートベース出口戦略**: `cits/core/chart_exit.py`（ローソク足・モメンタム・ATRトレイリング・ステージ分析）
- **取引日メールレポート**: `cits/scripts/daily_report.py`（afternoon後自動送信）
- **VPSフェイルオーバー**: `cits/scripts/vps_failover.py`
- **config.yml駆動パラメータ**: CIS/KEI paramsをconfig.ymlから読み込み
- **position_monitor chart_exit統合**: 重複ロジック解消
- **全bat自動git pull**: VPSコード自動更新
- **6リスクガード**:
  1. ギャップダウンフィルター（前日比-2%で買い停止）
  2. 日次損失上限（累計-3%でトレード停止）
  3. 実残高ベース資金管理（オープンポジション差引）
  4. positions.json排他制御（ロックファイル方式）
  5. BOJ会合/SQ週リスク削減（ポジション半減）
  6. 祝日判定（土日+2026年祝日）
- **タスクスケジューラ自動設定**: afternoon 15:20変更 + position_monitor 30分毎登録（初回bat実行時自動）

### 残作業（次セッション）
- `.env`に`GMAIL_APP_PASSWORD`設定 → メールレポート送信有効化
- 2027年の祝日リスト追加（`_JP_HOLIDAYS_2026`を更新）
- 実弾トレード実績の検証・パラメータ調整

### 追加コマンド
```bash
# バックテスト -- CIS+Kei-kun（ローカルのみ、yfinanceネットワーク必要）
python -c "from cits.backtest.engine import BacktestEngine; eng = BacktestEngine(initial_capital=100_000); print(eng.run(['7203','8306','6758','9984'], '2025-09-01', '2026-03-21', strategies=['cis_momentum','keikun']).summary())"

# ペーパートレード
python -m cits.scripts.paper_sim --days 5 --capital 100000

# ダッシュボード
python -m cits.scripts.dashboard --full

# ウォッチリスト一括分析
python -m cits.scripts.run_watchlist

# 全銘柄スキャン（CIS+KEI on all TSE tickers）
python -m cits.scripts.live_trader --mode full_scan --capital 300000 --dry-run

# 取引日レポート
python -m cits.scripts.daily_report --dry-run

# VPS障害モニター
python -m cits.scripts.vps_failover --check
python -m cits.scripts.vps_failover --monitor --dry-run
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

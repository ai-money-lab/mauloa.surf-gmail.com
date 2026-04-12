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
- IP: 203.183.9.252 (chrishell, Win2 SSD, 3.5GB RAM, 3コア, UUID: JZQJ5GDA)
- SSH: `ssh -i ~/.ssh/id_ed25519 Administrator@203.183.9.252`（鍵認証のみ）
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

### 2026-04-12セッション（continue-kabusute）で実施
- **ブランチ移行**: `claude/japanese-stock-trading-agent-kJBwp` → `claude/continue-kabusute-DmFKB`
  - vps_agent.py / bootstrap.py / diagnose_kabu.py の BRANCH 定数更新
  - run_*.bat / report_status.bat の git pull/push 先を新ブランチに変更
- **kabuStation診断結果 (02:04 JST)**:
  - ポート18080: OPEN ✅
  - kabuStation プロセス: Running ✅
  - Token API: 200 OK (`hiroki0380`) ✅
- **bootstrap結果 (02:23 JST)**: CITS_Afternoon/PositionMonitor タスク修正コマンド送信済み
- **完全自立型システム構築 (前セッション)**:
  - `.github/workflows/cits-kabu-login.yml`: 平日08:27 JST GitHub Actions → commands.json injection
  - `cits/scripts/watchdog.py`: VPS自己修復 (5分毎: kabu API / vps_agent / 全タスク確認 / GitHub push)
  - `cits/run_watchdog.bat`: CITS_Watchdog タスク用 bat
  - `cits/scripts/bootstrap.py`: CITS_Watchdog + CITS_KabuStart_IT タスク追加
  - `cits/tests/smoke_test.py`: watchdog モジュール追加

### 2026-04-12 セッション2（11:06 JST）で修正した重要バグ
- **vps_agent `git add -f` 修正**: `git add cits/data/vps_status.json` → `git add -f ...`
  - `data/` が .gitignore にあるため `-f` なしでは silent fail → 結果が一度も GitHubに届いていなかった
- **VNCDO パス修正 (2ファイル)**: `C:\cits\repo\venv\Scripts\vncdo.exe` → `C:\cits\venv\Scripts\vncdo.exe`
  - `kabu_auto_login_vps.py` / `kabu_vnc_login.py` の誤パス → VNC GUI操作が全て失敗していた
- **report_status.bat `git add -f` 修正**: vps_status.json が .gitignore で弾かれていた
- **VPS移行バグ修正**: マーカーファイル方式 (`if not exist .migrated_...`) の問題
  - git checkout が失敗してもマーカーが書かれる → 以降の全実行でマーカーが存在 → 移行スキップ
  - 修正: `git branch --show-current` で実際のブランチを確認 + 古いマーカーを削除
  - 旧ブランチ `run_monitor.bat` を byte-alignment 設計で更新（git pull 後の cmd.exe ファイル読み取り問題に対処）
- **GMAIL_APP_PASSWORD 設定**: VPS `.env` に `agdcsxloedxlstor` を追加 → Gmail IMAP: OK ✅

### VPS 移行状況（2026-04-12 16:00 JST確認済み）
- VPS: **`claude/continue-kabusute-DmFKB`で稼働中** ✅
- vps_agent: pythonw.exeで稼働中、GitHubへpush確認済み ✅
- kabu API: 200 OK (token取得成功) ✅
- IP: 203.183.9.252 (newvps_diag確認済み) ✅
- 懸念: CITS_*タスクが未登録の可能性 → commands.jsonの`register_all_tasks_20260412_1700`で解消予定

### ブランチ構成（2026-04-12以降）
- **コード開発・VPS**: `claude/continue-kabusute-DmFKB`（唯一のブランチ）

### 残作業（次セッション）
- vps_status.jsonで`register_all_tasks`/`verify_tasks`の実行結果確認
- 2170株ポジション確認・解消（sell_2170.pyで処理済みのはずだが要確認）

---

## トラブルシューティング・プレイブック（月曜本番前必読）

### 月曜朝シーケンス（正常フロー）
```
07:58 JST  vps_agent稼働中（毎60秒ポーリング）
08:00 JST  CITS_Watchdog: kabu APIヘルスチェック開始
08:25 JST  CITS_KabuStation_Start: kabuStation.exe起動（GUI表示）
08:27 JST  GitHub Actions (cits-kabu-login): ログイン+2FA自動実行
08:30 JST  CITS_LiveTrader: run_morning.bat → live_trader morning
             → git pull → sell_2170(未売なら) → CIS全銘柄スキャン → 買い発注
09:00〜    kabuStation: 前場取引
09:30 JST  CITS_PositionMonitor: 30分毎 → position_monitor実行 → 売り判断
11:30 JST  前場クローズ
12:30 JST  後場開始
14:00 JST  CITS_Prefetch: 全銘柄データ収集
15:00 JST  後場クローズ
15:20 JST  CITS_Afternoon: 売り決済 + CIS+KEI全銘柄スキャン + 買い発注 + メールレポート
```

### 障害別対応手順

#### ❌ kabuStation起動失敗（08:25に起動しない）
1. `CITS_Watchdog`が5分後に検出 → `CITS_KabuStart_IT`タスクで再起動を試みる
2. それも失敗 → `kabu_auto_login_vps.py`でVNC経由ログイン
3. **手動対応**: VPS RDP接続 → `C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe`を直接起動
4. **確認**: `curl http://localhost:18080/kabusapi/token` でAPI応答確認

#### ❌ kabu API接続失敗（token取得エラー）
1. kabuStationが起動しているか確認
2. タスクマネージャーで`KabuS.exe`プロセス確認
3. kabuStation画面でログイン状態確認（2FA要確認）
4. **VPSコマンドで診断**:
   ```json
   {"id": "diag_api_YYYYMMDD", "type": "python",
    "code": "import requests; r=requests.post('http://localhost:18080/kabusapi/token',json={'APIPassword':'hiroki0380'},timeout=5); print(r.status_code,r.text[:200])"}
   ```

#### ❌ タスクが登録されていない
1. `cits/data/commands.json`に`register_all_tasks_*`コマンドを追加
2. vps_agentが60秒以内に実行
3. その後`verify_tasks_*`コマンドで確認
4. **緊急**: CITS_Watchdogが5分毎に欠損タスクを自動再登録（watchdog.py `_verify_tasks()`）

#### ❌ vps_agentが停止
1. CITS_Watchdogが検出 → 自動再起動
2. **手動VPSコマンド**（vps_agentが停止中の場合はRDP接続が必要）:
   ```bat
   cd C:\cits\repo
   set PYTHONPATH=C:\cits\repo
   start /b C:\cits\venv\Scripts\pythonw.exe -m cits.scripts.vps_agent
   ```
3. CITS_VPSAgentタスク（起動時自動起動）が機能しているか確認

#### ❌ Git pull失敗（コードが更新されない）
- bat filesは `git pull --quiet 2>nul` → 失敗しても実行継続
- **確認**: VPSコマンドで `git log --oneline -3` を実行してHEADコミットを確認
- **対処**: git remote URLにtokenが含まれているか確認（`git remote -v`）

#### ❌ 発注失敗（orders not placed）
1. ログ確認: `C:\cits\logs\morning_YYYYMMDD.log`
2. `CITS_SCHEDULED_RUN`環境変数が`TASKSCHEDULER`か確認（live_traderの安全ゲート）
3. `KABU_ORDER_PASSWORD`が設定されているか確認
4. kabu API残高確認: 発注ログで`AvailableEquity`を確認

#### ❌ ポジションが売れない（position_monitorが動かない）
1. CITS_PositionMonitorタスクが登録済みか確認
2. `C:\cits\logs\monitor_YYYYMMDD.log` を確認
3. **手動実行VPSコマンド**:
   ```json
   {"id": "manual_monitor_YYYYMMDD", "type": "module",
    "module": "cits.scripts.position_monitor", "args": []}
   ```

#### ❌ VPS自体が応答しない（ネットワーク障害）
1. ローカルPCでVPSフェイルオーバー:
   ```bash
   python -m cits.scripts.vps_failover --check
   python -m cits.scripts.vps_failover --force-local --live
   ```
2. chrishellコントロールパネルからVPS再起動
3. VPS再起動後: CITS_VPSAgentタスクが2分後にvps_agentを自動起動

### VPS状態の遠隔確認方法
```json
// commands.jsonに追加 → vps_agentが60秒以内に実行 → vps_status.jsonに結果
{"id": "check_YYYYMMDD_HHMM", "type": "shell",
 "command": "git branch --show-current && schtasks /Query /FO CSV /NH 2>&1 | findstr CITS && tasklist | findstr python",
 "timeout": 30}
```

### 緊急停止手順
```json
// 全Python処理を即座に停止（vps_agentも停止する）
{"id": "emergency_stop_YYYYMMDD", "type": "shell",
 "command": "taskkill /f /im pythonw.exe & taskkill /f /im python.exe & echo STOPPED",
 "timeout": 10}
```

### セキュリティ注意事項
- **GitHubリポジトリは必ずPrivateに保つ**（クレデンシャルが含まれるため）
- `.env`ファイルは絶対にコミットしない（`.gitignore`で除外済み）
- `commands.json`は`data/`が`.gitignore`対象のため通常コミットされない（`git add -f`必須）
- VPS gitリモートURLにOAuthトークンが埋め込まれている（VPS側ローカルのみ）
- APIパスワード変更時は以下を更新:
  - VPS `C:\cits\repo\cits\.env`: `KABU_API_PASSWORD=新パスワード`
  - VPS `C:\cits\repo\cits\.env`: `KABU_ORDER_PASSWORD=新パスワード`
  - `cits/scripts/vps_agent.py` line 98（フォールバック）
  - `cits/run_*.bat`（フォールバック）

### ログ場所（VPS）
| ログ | パス |
|------|------|
| 朝LiveTrader | `C:\cits\logs\morning_YYYYMMDD.log` |
| 午後LiveTrader | `C:\cits\logs\afternoon_YYYYMMDD.log` |
| PositionMonitor | `C:\cits\logs\monitor_YYYYMMDD.log` |
| vps_agent | `C:\cits\logs\vps_agent.log` |
| Watchdog | `C:\cits\logs\watchdog.log` |
| kabu自動ログイン | `C:\cits\logs\kabu_auto_login.log` |
| フェイルオーバー | `C:\cits\logs\failover\failover.log` |

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
- **編集前にコードベースを調査せよ。読んでいないコードは決して変更するな。**
- **マージ後にファイルが全部揃っているか確認せよ。消失は許さない。**
- **VPS（Windows）での動作を常に意識。パス、エンコーディング、改行コード。**
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

# CITS - Claude Intelligence Trading System

日本株（日経225マイクロ先物）の自動売買システム。
初期資金10万円。証拠金約26,000円/枚、最大2枚運用。手数料11円/枚。

## 核心コンセプト
「チャートを読む」のではなく「チャートを動かす人間の発言を読む」。
世界のエコノミスト・政策決定者の発言をClaudeがリアルタイム解析し、
HFT（単語反応）と機関投資家（意味理解・5-30分遅延）の間の時間差で利益を取る。

## 確定した事実
- テクニカルパターン（RSI、ギャップ逆張り等6種）は全滅。価格パターンだけでは優位性ゼロ。
- 外国人が日本株の32%保有、売買代金の60-70%。日経チャートの「原因」は海外発言と資金フロー。
- パウエル/植田/トランプとも「初動の約30%を日中で戻す」クセが一貫。
- 2日ドリフト継続率：全員ほぼ100%。

## 技術スタック
- Python 3.12+, yfinance, pandas, scipy
- Claude API: claude-sonnet-4-20250514（分析用）/ claude-opus-4-6（最終判断用）
- 証券API: kabuステーションAPI（三菱UFJ eスマート証券）
- DB: SQLite → PostgreSQL

## ディレクトリ構成
```
cits/
├── CLAUDE.md
├── data/
│   ├── events.json          # 発言-反応データベース
│   ├── fomc_statements/     # FOMC声明文
│   └── boj_statements/      # 日銀声明文
├── analysis/
│   ├── fetch_data.py        # yfinanceデータ取得
│   ├── event_reaction.py    # イベント反応分析
│   ├── claude_scorer.py     # Claude APIスコアリング
│   ├── backtest_5min.py     # 5分足バックテスト
│   └── correlation_test.py  # スコア-反応の相関検証
├── trading/
├── monitor/
└── logs/
```

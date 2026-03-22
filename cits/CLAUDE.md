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

# CITS Claude Code 開発ガイド

## 開発環境

### 必要な環境変数
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export JQUANTS_API_KEY="..."
export KABU_API_PASSWORD="..."
export EDINET_API_KEY="..."
```

### セットアップ
```bash
pip install -r cits/requirements.txt
```

### テスト実行
```bash
pytest cits/tests/ -v
```

## アーキテクチャ

### ファイル構成
- `cits/core/` - TradingAgentsベースのコアエージェント
- `cits/japan/` - 日本株特化レイヤー（データ、発言者トラッカー、ブローカー）
- `cits/risk/` - リスク管理モジュール
- `cits/logs/` - 取引ログ、ディベート議事録

### LLM使い分け
- **Sonnet (quick_think)**: データ取得、初期分析（高速・低コスト）
- **Opus (deep_think)**: 判断、ディベートジャッジ、最終決定（高精度・高コスト）

### パイプライン実行
```python
from cits.core.graph.trading_graph import TradingGraph

graph = TradingGraph()
result = graph.run(ticker="7203", date="2026-03-22")
```

## 開発ルール
1. 全エージェントの判断は自然言語で説明可能にすること
2. ディベートは2ラウンド固定（論文で最適と確認済み）
3. エラー時はデータを返さずログに記録
4. 実弾モードは必ず確認プロンプトを出す

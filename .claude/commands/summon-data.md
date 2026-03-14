# データ収集エージェント召喚

System Cの全データ収集エージェントを指揮し、最新データを一括収集する。

## 引数
- `$ARGUMENTS`: 対象エージェント指定（例: "realestate", "market", "regulation", "tech"）
- 引数なしで全エージェント実行

## 実行手順

1. **現在のデータ鮮度チェック**:
   - `data/` 配下の各データソースの最終更新日を確認
   - 古いデータを特定（24h以上経過 = 要更新）

2. **エージェント設定確認**:
   - `system_c/crew_config.yaml` からエージェント設定を読み取り
   - `system_c/data_sources.yaml` からデータソース一覧を確認

3. **収集実行**:
   - 指定エージェントまたは全エージェントの収集スクリプトを実行:
     - `system_c/agents/realestate_data_agent.py` — 不動産データ
     - `system_c/agents/market_analysis_agent.py` — 市場分析
     - `system_c/agents/regulation_watch_agent.py` — 法規制ウォッチ
     - `system_c/agents/tech_trend_agent.py` — テックトレンド
   - 各エージェントの実行結果とエラーを監視

4. **品質検証**:
   - 収集データを `core/quality_checker.py` の `data_collection` プロファイルで検証
   - 70点/100点未満のデータはフラグ付き報告

5. **出力**:
   ```
   ═══════════════════════════════════════════════
    SUMMON DATA — 収集結果サマリー
   ═══════════════════════════════════════════════

   [realestate]  {OK/NG} | {件数}件 | 品質: {score}/100
   [market]      {OK/NG} | {件数}件 | 品質: {score}/100
   [regulation]  {OK/NG} | {件数}件 | 品質: {score}/100
   [tech_trend]  {OK/NG} | {件数}件 | 品質: {score}/100

   総収集: {合計}件 | 所要時間: {time}
   ═══════════════════════════════════════════════
   ```

# Empire全体ステータス確認

HIROKI AI Empireの全システム状態を一括確認せよ。

## 実行手順

1. **System A（X投稿パイプライン）** の状態確認:
   - `data/` 配下の最新投稿データを確認
   - `data/quality_logs/` の直近の品質スコアを確認
   - pipeline比率（buzz/data-driven/original）の現在値を `config/config.yaml` から読み取り

2. **System B（案件処理）** の状態確認:
   - `system_b/products.yaml` の登録プロダクト数を確認

3. **System C（データ収集）** の状態確認:
   - `data/` 配下の収集データの鮮度（最終更新日）を確認
   - 各エージェント（realestate, market, regulation, tech_trend）のデータ有無

4. **System D（実績配信）** の状態確認:
   - 実績コンテンツの最新生成日を確認

5. **Inquiry Bot** の状態確認:
   - `inquiry_bot/config.yaml` の設定確認
   - `inquiry_bot/faq_data.yaml` のFAQ数を確認

6. **コード品質**:
   - `ruff check` を実行してlintエラー数を報告

## 出力フォーマット

以下の形式でダッシュボードを表示:

```
═══════════════════════════════════════════════
 HIROKI AI Empire — STATUS DASHBOARD
═══════════════════════════════════════════════

 System A [X投稿]     : {状態} | 直近品質: {スコア}/120
 System B [案件処理]   : {状態} | プロダクト: {数}件
 System C [データ収集] : {状態} | 最終更新: {日付}
 System D [実績配信]   : {状態} | 最終生成: {日付}
 Inquiry Bot          : {状態} | FAQ: {数}件

 コード品質: lintエラー {数}件
 Pipeline比率: buzz {n}% / data {n}% / original {n}%
═══════════════════════════════════════════════
```

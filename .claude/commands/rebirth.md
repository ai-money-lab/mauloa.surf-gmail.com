# システム再生（リビルド）

開発環境を完全にクリーン化し、ゼロから再構築する。

## 注意
破壊的操作を含むため、必ずユーザーに確認してから実行すること。

## 実行手順

1. **現状バックアップ確認**:
   - `git status` で未コミットの変更がないか確認
   - 未コミットがあれば「先にコミットしますか？」と確認
   - `data/` 配下の重要データの有無を確認

2. **クリーンアップ**（ユーザー確認後）:
   ```bash
   # Pythonキャッシュ削除
   find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
   find . -name "*.pyc" -delete 2>/dev/null || true
   rm -rf .pytest_cache 2>/dev/null || true

   # Node.jsキャッシュ削除
   rm -rf node_modules 2>/dev/null || true
   ```

3. **再構築**:
   ```bash
   # Python依存パッケージ再インストール
   pip install -r requirements.txt

   # ruff再インストール
   pip install ruff

   # Node.js再インストール
   npm install
   ```

4. **検証**:
   - `ruff check` で全モジュールのlintチェック
   - `pytest` で全テスト実行
   - `python -c "import core; import system_a; import inquiry_bot"` でインポート確認

5. **出力**:
   ```
   ═══════════════════════════════════════════════
    REBIRTH — システム再生完了
   ═══════════════════════════════════════════════

   クリーンアップ: 完了
   Python依存:    {n}パッケージ インストール済
   Node.js依存:   {n}パッケージ インストール済
   Lint:          エラー{n}件
   テスト:        {n}/{n} パス

   システムは生まれ変わった。
   ═══════════════════════════════════════════════
   ```

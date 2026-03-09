#!/usr/bin/env python3
"""
Dropbox フォルダ構造エクスプローラー
ローカルPCで実行して、Dropbox内のフォルダ構造をツリー表示する。

使い方:
  pip install dropbox
  python dropbox_explorer.py YOUR_ACCESS_TOKEN

出力をクリップボードにコピーしてClaude Codeに貼り付ければ、整理方針を提案できます。
"""

import sys
import json
from collections import defaultdict

try:
    import dropbox
except ImportError:
    print("dropbox パッケージが必要です: pip install dropbox")
    sys.exit(1)


def get_all_entries(dbx, path=""):
    """指定パス以下のすべてのエントリを再帰的に取得"""
    entries = []
    try:
        result = dbx.files_list_folder(path, recursive=True)
        while True:
            entries.extend(result.entries)
            if not result.has_more:
                break
            result = dbx.files_list_folder_continue(result.cursor)
    except dropbox.exceptions.ApiError as e:
        print(f"APIエラー: {e}", file=sys.stderr)
    return entries


def format_size(size_bytes):
    """バイト数を読みやすい形式に変換"""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.1f}GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f}MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f}KB"
    return f"{size_bytes}B"


def build_tree(entries):
    """エントリリストからツリー構造を構築"""
    tree = {}
    folder_sizes = defaultdict(int)
    folder_counts = defaultdict(int)

    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            # 各親フォルダのサイズを加算
            parts = entry.path_display.split("/")
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i]) or "/"
                folder_sizes[parent] += entry.size
                folder_counts[parent] += 1

    return folder_sizes, folder_counts


def print_tree(dbx, path="", depth=0, max_depth=3):
    """ツリー形式でフォルダ構造を表示"""
    try:
        result = dbx.files_list_folder(path)
        entries = []
        while True:
            entries.extend(result.entries)
            if not result.has_more:
                break
            result = dbx.files_list_folder_continue(result.cursor)
    except dropbox.exceptions.ApiError as e:
        print(f"{'  ' * depth}エラー: {e}")
        return

    # フォルダとファイルに分離
    folders = sorted(
        [e for e in entries if isinstance(e, dropbox.files.FolderMetadata)],
        key=lambda x: x.name,
    )
    files = sorted(
        [e for e in entries if isinstance(e, dropbox.files.FileMetadata)],
        key=lambda x: x.name,
    )

    indent = "  " * depth

    for folder in folders:
        print(f"{indent}📁 {folder.name}/")
        if depth < max_depth:
            print_tree(dbx, folder.path_lower, depth + 1, max_depth)

    # ファイルが多すぎる場合はサマリー表示
    if len(files) > 20:
        # 拡張子ごとに集計
        ext_stats = defaultdict(lambda: {"count": 0, "size": 0})
        for f in files:
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else "(拡張子なし)"
            ext_stats[ext]["count"] += 1
            ext_stats[ext]["size"] += f.size

        total_size = sum(f.size for f in files)
        print(f"{indent}  [{len(files)}ファイル, 合計 {format_size(total_size)}]")
        for ext, stats in sorted(ext_stats.items(), key=lambda x: -x[1]["size"]):
            print(
                f"{indent}    .{ext}: {stats['count']}件 ({format_size(stats['size'])})"
            )
    else:
        for f in files:
            mod = f.client_modified.strftime("%Y-%m-%d") if f.client_modified else "?"
            print(f"{indent}  📄 {f.name} ({format_size(f.size)}, {mod})")


def print_summary(dbx):
    """ストレージ使用状況のサマリーを表示"""
    usage = dbx.users_get_space_usage()
    used = usage.used
    if hasattr(usage.allocation, "individual"):
        allocated = usage.allocation.get_individual().allocated
    else:
        allocated = usage.allocation.get_team().allocated

    print(f"使用量: {format_size(used)} / {format_size(allocated)}")
    print(f"使用率: {used / allocated * 100:.1f}%")
    print()


def main():
    if len(sys.argv) < 2:
        print("使い方: python dropbox_explorer.py YOUR_ACCESS_TOKEN [max_depth]")
        print()
        print("  max_depth: ツリー表示の最大深度 (デフォルト: 3)")
        sys.exit(1)

    token = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    dbx = dropbox.Dropbox(token)

    # アカウント確認
    account = dbx.users_get_current_account()
    print(f"=== Dropbox: {account.name.display_name} ({account.email}) ===")
    print()

    # ストレージサマリー
    print_summary(dbx)

    # ツリー表示
    print(f"=== フォルダ構造 (深度 {max_depth} まで) ===")
    print()
    print_tree(dbx, "", 0, max_depth)
    print()
    print("--- ここまでの出力をClaude Codeに貼り付けてください ---")


if __name__ == "__main__":
    main()

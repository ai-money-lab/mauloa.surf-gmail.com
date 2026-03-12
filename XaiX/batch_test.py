#!/usr/bin/env python3
"""
全エンジン × 全シーンの比較テスト
同じシードで各エンジンの出力を比較できる
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCENES_DIR = Path(__file__).parent / "scenes"
ENGINES = ["flux2-pro", "realistic-vision", "lora-realism"]

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    scene = sys.argv[2] if len(sys.argv) > 2 else "night_1"

    print(f"=== 比較テスト: シーン={scene}, シード={seed} ===\n")

    for engine in ENGINES:
        print(f"--- {engine} ---")
        cmd = [
            sys.executable, "generate_beauty_v8.py",
            "--engine", engine,
            "--scene", scene,
            "--seed", str(seed),
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"  {engine} は失敗しました（エンドポイントが利用不可の可能性）")
        print()

    print("=== 比較テスト完了 ===")
    print(f"~/Pictures/AILAB/ を確認してください")


if __name__ == "__main__":
    main()

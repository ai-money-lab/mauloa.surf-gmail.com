#!/usr/bin/env python3
"""RunPod Serverless セットアップ & テストスクリプト.

エンドポイントの状態確認、GPU設定変更、テスト画像生成を自動実行。
Usage:
    python3 system_e/scripts/runpod_setup.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# .envファイルがUTF-16の場合に対応
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
env_path = os.path.normpath(env_path)
try:
    load_dotenv(env_path)
except UnicodeDecodeError:
    # UTF-16 BOM付きファイルの場合
    with open(env_path, "r", encoding="utf-16") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()

API_KEY = os.getenv("RUNPOD_API_KEY", "")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "")
BASE_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"
GRAPHQL_URL = "https://api.runpod.io/graphql"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def graphql(query: str, variables: dict = None) -> dict:
    """RunPod GraphQL API call."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def check_endpoint() -> dict | None:
    """エンドポイント情報を取得."""
    query = """
    query Endpoints {
        myself {
            serverlessDiscount
            endpoints {
                id
                name
                gpuIds
                templateId
                networkVolumeId
                idleTimeout
                scalerType
                scalerValue
                workersMin
                workersMax
                executionTimeoutMs
            }
        }
    }
    """
    try:
        result = graphql(query)
        endpoints = result.get("data", {}).get("myself", {}).get("endpoints", [])
        for ep in endpoints:
            if ep["id"] == ENDPOINT_ID:
                return ep
        print(f"[ERROR] Endpoint {ENDPOINT_ID} not found")
        print(f"Available endpoints: {[e['id'] for e in endpoints]}")
        return None
    except Exception as e:
        print(f"[ERROR] GraphQL failed: {e}")
        return None


def check_health() -> dict | None:
    """エンドポイントのヘルス状態を確認."""
    try:
        resp = requests.get(f"{BASE_URL}/health", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Health check failed: {e}")
        return None


def update_gpu_types(gpu_ids: list[str]) -> bool:
    """GPU タイプを変更."""
    query = """
    mutation UpdateEndpoint($input: UpdateEndpointInput!) {
        updateEndpoint(input: $input) {
            id
            gpuIds
        }
    }
    """
    variables = {
        "input": {
            "id": ENDPOINT_ID,
            "gpuIds": gpu_ids,
        }
    }
    try:
        result = graphql(query, variables)
        updated = result.get("data", {}).get("updateEndpoint", {})
        print(f"[OK] GPU types updated: {updated.get('gpuIds')}")
        return True
    except Exception as e:
        print(f"[ERROR] GPU update failed: {e}")
        return False


def test_generation() -> bool:
    """テスト画像生成 (シンプルなFlux.1 Devワークフロー)."""
    workflow = {
        "4": {
            "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
            "class_type": "CheckpointLoaderSimple",
        },
        "5": {
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "class_type": "EmptyLatentImage",
        },
        "6": {
            "inputs": {"text": "a cute orange tabby cat sitting on a kitchen counter, morning light, cozy apartment", "clip": ["4", 1]},
            "class_type": "CLIPTextEncode",
        },
        "7": {
            "inputs": {"text": "", "clip": ["4", 1]},
            "class_type": "CLIPTextEncode",
        },
        "3": {
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
            "class_type": "KSampler",
        },
        "8": {
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            "class_type": "VAEDecode",
        },
        "9": {
            "inputs": {"filename_prefix": "test", "images": ["8", 0]},
            "class_type": "SaveImage",
        },
    }

    payload = {"input": {"workflow": workflow}}

    print("[...] Submitting test job...")
    try:
        resp = requests.post(
            f"{BASE_URL}/run", headers=HEADERS, json=payload, timeout=30
        )
        resp.raise_for_status()
        job = resp.json()
        job_id = job.get("id")
        status = job.get("status")
        print(f"[OK] Job submitted: {job_id} (status: {status})")

        if status == "COMPLETED":
            print("[OK] Instant completion!")
            return _handle_output(job.get("output", {}))

        # Poll
        print("[...] Waiting for completion (max 3 min)...")
        return _poll(job_id)

    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"[ERROR] Submit failed: {e}")
        return False


def _poll(job_id: str, max_wait: int = 180) -> bool:
    """ジョブ完了をポーリング."""
    url = f"{BASE_URL}/status/{job_id}"
    start = time.time()
    last_status = ""

    while time.time() - start < max_wait:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "UNKNOWN")

            if status != last_status:
                elapsed = int(time.time() - start)
                print(f"  [{elapsed}s] Status: {status}")
                last_status = status

            if status == "COMPLETED":
                return _handle_output(data.get("output", {}))
            elif status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                print(f"[FAIL] Job {status}: {data.get('error', 'unknown')}")
                return False

            time.sleep(3)
        except Exception as e:
            print(f"  [WARN] Poll error: {e}")
            time.sleep(5)

    print(f"[FAIL] Timed out after {max_wait}s")
    return False


def _handle_output(output: dict) -> bool:
    """出力結果を処理."""
    images = output.get("images", [])
    if images:
        first = images[0]
        img_type = first.get("type", "unknown") if isinstance(first, dict) else "raw"
        if isinstance(first, dict):
            data_preview = str(first.get("data", ""))[:50]
        else:
            data_preview = str(first)[:50]
        print(f"[OK] Image received! type={img_type}, data={data_preview}...")
        print(f"[OK] Total images: {len(images)}")
        return True

    # Other output formats
    if output:
        print(f"[OK] Output keys: {list(output.keys())}")
        for k, v in output.items():
            print(f"  {k}: {str(v)[:100]}")
        return True

    print("[WARN] Empty output")
    return False


def main():
    print("=" * 60)
    print(" RunPod Serverless セットアップ & テスト")
    print("=" * 60)

    if not API_KEY or not ENDPOINT_ID:
        print("[ERROR] RUNPOD_API_KEY or RUNPOD_ENDPOINT_ID not set in .env")
        sys.exit(1)

    print(f"\nEndpoint ID: {ENDPOINT_ID}")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")

    # Step 1: エンドポイント情報
    print("\n--- Step 1: エンドポイント情報 ---")
    ep = check_endpoint()
    if ep:
        print(f"  Name: {ep.get('name')}")
        print(f"  GPU IDs: {ep.get('gpuIds')}")
        print(f"  Workers: min={ep.get('workersMin')} max={ep.get('workersMax')}")
        print(f"  Idle Timeout: {ep.get('idleTimeout')}s")
        print(f"  Execution Timeout: {ep.get('executionTimeoutMs')}ms")

    # Step 2: ヘルスチェック
    print("\n--- Step 2: ヘルスチェック ---")
    health = check_health()
    if health:
        workers = health.get("workers", {})
        print(f"  Workers: idle={workers.get('idle', 0)}, "
              f"running={workers.get('running', 0)}, "
              f"ready={workers.get('ready', 0)}, "
              f"throttled={workers.get('throttled', 0)}")
        jobs = health.get("jobs", {})
        print(f"  Jobs: completed={jobs.get('completed', 0)}, "
              f"failed={jobs.get('failed', 0)}, "
              f"inProgress={jobs.get('inProgress', 0)}, "
              f"inQueue={jobs.get('inQueue', 0)}, "
              f"retried={jobs.get('retried', 0)}")

    # Step 3: GPU在庫が少ない場合、追加GPUタイプを設定
    if ep:
        current_gpus = ep.get("gpuIds", "")
        print(f"\n--- Step 3: GPU設定 ---")
        print(f"  Current: {current_gpus}")

        # 複数のGPUタイプをフォールバックとして設定
        # AMPERE_16: RTX A4000 (16GB) — 安い
        # AMPERE_24: RTX 3090/A5000 (24GB) — バランス
        # AMPERE_48: A6000/RTX A6000 (48GB) — 余裕
        # ADA_24: RTX 4090 (24GB) — 最速
        desired_gpus = "AMPERE_24,ADA_24,AMPERE_48"
        if current_gpus != desired_gpus:
            print(f"  → Updating to: {desired_gpus}")
            update_gpu_types(desired_gpus.split(","))
        else:
            print("  [OK] GPU types already optimal")

    # Step 4: テスト生成
    print("\n--- Step 4: テスト画像生成 ---")
    success = test_generation()

    print("\n" + "=" * 60)
    if success:
        print(" [OK] セットアップ完了！RunPod画像生成が正常に動作しています")
    else:
        print(" [!] テスト生成に問題があります。Requestsタブで確認してください")
        print(f"     https://www.runpod.io/console/serverless/{ENDPOINT_ID}")
    print("=" * 60)


if __name__ == "__main__":
    main()

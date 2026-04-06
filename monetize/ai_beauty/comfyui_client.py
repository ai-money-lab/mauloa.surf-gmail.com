"""ComfyUI API クライアント — ワークフロー実行・画像取得・バッチ処理."""

import io
import json
import logging
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """ComfyUI HTTP APIのクライアント."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.base_url = f"http://{host}:{port}"
        self.client_id = uuid.uuid4().hex[:8]

    def is_available(self) -> bool:
        """ComfyUIが起動しているかチェック."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False

    def get_system_stats(self) -> dict:
        """システム情報を取得（GPU VRAM等）."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read())
        except Exception as e:
            logger.error("ComfyUI system_stats取得失敗: %s", e)
            return {}

    def queue_prompt(self, workflow: dict) -> Optional[str]:
        """ワークフローをキューに投入.

        Returns:
            prompt_id (str) or None
        """
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            prompt_id = result.get("prompt_id")
            logger.info("ComfyUIキュー投入成功: prompt_id=%s", prompt_id)
            return prompt_id
        except Exception as e:
            logger.error("ComfyUIキュー投入失敗: %s", e)
            return None

    def wait_for_completion(self, prompt_id: str, timeout: int = 300, poll_interval: float = 1.0) -> bool:
        """ワークフローの完了を待機.

        Returns:
            True if completed, False if timeout/error
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                req = urllib.request.Request(f"{self.base_url}/history/{prompt_id}", method="GET")
                resp = urllib.request.urlopen(req, timeout=5)
                history = json.loads(resp.read())

                if prompt_id in history:
                    status = history[prompt_id].get("status", {})
                    if status.get("completed", False):
                        return True
                    if status.get("status_str") == "error":
                        logger.error("ComfyUI実行エラー: %s", status)
                        return False
            except Exception:
                pass

            time.sleep(poll_interval)

        logger.error("ComfyUI実行タイムアウト: %s秒", timeout)
        return False

    def get_outputs(self, prompt_id: str) -> dict:
        """実行結果（出力ファイル情報）を取得."""
        try:
            req = urllib.request.Request(f"{self.base_url}/history/{prompt_id}", method="GET")
            resp = urllib.request.urlopen(req, timeout=5)
            history = json.loads(resp.read())

            if prompt_id in history:
                return history[prompt_id].get("outputs", {})
        except Exception as e:
            logger.error("ComfyUI出力取得失敗: %s", e)
        return {}

    def download_image(self, filename: str, subfolder: str = "", output_type: str = "output") -> Optional[bytes]:
        """生成された画像をダウンロード."""
        params = f"filename={filename}&subfolder={subfolder}&type={output_type}"
        url = f"{self.base_url}/view?{params}"
        try:
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=30)
            return resp.read()
        except Exception as e:
            logger.error("ComfyUI画像ダウンロード失敗: %s", e)
            return None

    def generate_image(
        self,
        workflow: dict,
        output_dir: Path,
        filename_prefix: str = "img",
        timeout: int = 300,
    ) -> list[Path]:
        """ワークフローを実行して画像を保存.

        Returns:
            保存されたファイルパスのリスト
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return []

        if not self.wait_for_completion(prompt_id, timeout=timeout):
            return []

        outputs = self.get_outputs(prompt_id)
        saved_files = []

        for node_id, node_output in outputs.items():
            if "images" not in node_output:
                continue
            for i, image_info in enumerate(node_output["images"]):
                img_filename = image_info.get("filename", "")
                subfolder = image_info.get("subfolder", "")
                img_type = image_info.get("type", "output")

                image_data = self.download_image(img_filename, subfolder, img_type)
                if image_data:
                    ext = Path(img_filename).suffix or ".png"
                    save_path = output_dir / f"{filename_prefix}_{i+1:03d}{ext}"
                    save_path.write_bytes(image_data)
                    saved_files.append(save_path)
                    logger.info("画像保存: %s (%.1f KB)", save_path, len(image_data) / 1024)

        return saved_files

    def batch_generate(
        self,
        workflows: list[dict],
        output_dir: Path,
        filename_prefix: str = "img",
        timeout_per_image: int = 120,
    ) -> list[Path]:
        """複数ワークフローを順次実行して全画像を保存."""
        all_files = []
        for i, workflow in enumerate(workflows):
            logger.info("バッチ生成 %d/%d...", i + 1, len(workflows))
            files = self.generate_image(
                workflow=workflow,
                output_dir=output_dir,
                filename_prefix=f"{filename_prefix}_{i+1:03d}",
                timeout=timeout_per_image,
            )
            all_files.extend(files)
        logger.info("バッチ生成完了: %d/%d 成功", len(all_files), len(workflows))
        return all_files


def build_sdxl_workflow(
    positive_prompt: str,
    negative_prompt: str,
    checkpoint: str = "juggernaut_xl_ragnarok.safetensors",
    width: int = 832,
    height: int = 1216,
    steps: int = 25,
    cfg: float = 7.0,
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    seed: int = -1,
    lora_name: str = "",
    lora_weight: float = 0.7,
) -> dict:
    """SDXL用のComfyUIワークフローJSONを構築."""
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": "beauty",
            },
        },
    }

    # LoRAが指定されている場合、モデルにLoRAを適用
    if lora_name:
        workflow["10"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": lora_name,
                "strength_model": lora_weight,
                "strength_clip": lora_weight,
            },
        }
        # KSamplerのモデル入力をLoRA出力に切り替え
        workflow["5"]["inputs"]["model"] = ["10", 0]
        workflow["2"]["inputs"]["clip"] = ["10", 1]
        workflow["3"]["inputs"]["clip"] = ["10", 1]

    return workflow


def build_flux_workflow(
    positive_prompt: str,
    model: str = "flux2-dev.safetensors",
    width: int = 832,
    height: int = 1216,
    steps: int = 20,
    guidance: float = 2.0,
    seed: int = -1,
) -> dict:
    """FLUX用のComfyUIワークフローJSONを構築."""
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": model,
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp16.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 0],
            },
        },
        "5": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "6": {
            "class_type": "FluxGuidance",
            "inputs": {
                "conditioning": ["4", 0],
                "guidance": guidance,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["6", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "beauty_flux",
            },
        },
    }
    return workflow


# アスペクト比 → ピクセルサイズ変換テーブル（SDXL推奨解像度）
ASPECT_RATIO_MAP = {
    "1:1": (1024, 1024),
    "3:4": (832, 1216),
    "4:3": (1216, 832),
    "9:16": (768, 1344),
    "16:9": (1344, 768),
    "2:3": (832, 1216),
    "3:2": (1216, 832),
}


def aspect_to_size(aspect_ratio: str) -> tuple[int, int]:
    """アスペクト比を SDXL推奨ピクセルサイズに変換."""
    return ASPECT_RATIO_MAP.get(aspect_ratio, (832, 1216))

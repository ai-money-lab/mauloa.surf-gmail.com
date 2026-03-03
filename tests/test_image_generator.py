"""Tests for core.image_generator — Gemini Imagen (Nano Banana 2) client."""

import base64
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.image_generator import ImageGenerator, build_image_prompt, PILLAR_VISUAL_HINTS


# ===========================================================================
# build_image_prompt tests
# ===========================================================================

class TestBuildImagePrompt:
    """Test the image prompt builder."""

    def test_includes_post_text(self):
        prompt = build_image_prompt("退去費用って意外と高いですよね", pillar=1)
        assert "退去費用って意外と高いですよね" in prompt

    def test_includes_pillar_visual_hint(self):
        prompt = build_image_prompt("テスト", pillar=2)
        assert "apartment building" in prompt or "property management" in prompt

    def test_includes_style_directive(self):
        prompt = build_image_prompt("テスト", pillar=3)
        assert "16:9" in prompt
        assert "no text overlay" in prompt

    def test_unknown_pillar_uses_default_hint(self):
        prompt = build_image_prompt("テスト", pillar=99)
        assert "lifestyle" in prompt

    def test_truncates_long_post_text(self):
        long_text = "あ" * 500
        prompt = build_image_prompt(long_text, pillar=1)
        # Should only include first 200 chars of post text
        assert len(prompt) < len(long_text) + 500

    def test_all_pillars_have_hints(self):
        for pillar_num in range(1, 6):
            assert pillar_num in PILLAR_VISUAL_HINTS


# ===========================================================================
# ImageGenerator tests
# ===========================================================================

class TestImageGeneratorEnabled:
    """Test the enabled property."""

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_enabled_when_key_set(self):
        gen = ImageGenerator()
        assert gen.enabled is True

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_disabled_when_key_empty(self):
        gen = ImageGenerator()
        assert gen.enabled is False

    @patch.dict("os.environ", {}, clear=True)
    def test_disabled_when_key_missing(self):
        gen = ImageGenerator()
        assert gen.enabled is False


class TestImageGeneratorGenerate:
    """Test image generation with mocked API."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp_path = tmp_path

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_generate_image_returns_none_when_disabled(self):
        gen = ImageGenerator()
        result = gen.generate_image("test prompt")
        assert result is None

    @patch("core.image_generator.IMAGE_DIR")
    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_success(self, mock_post, mock_dir):
        mock_dir.__truediv__ = lambda self, name: self.tmp_path / name if hasattr(self, 'tmp_path') else Path("/tmp") / name
        # Use real tmp_path for image storage
        with patch("core.image_generator.IMAGE_DIR", self.tmp_path):
            fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(fake_image).decode(),
                            }
                        }]
                    }
                }]
            }
            mock_post.return_value = mock_resp

            gen = ImageGenerator()
            result = gen.generate_image("test prompt")

            assert result is not None
            assert Path(result).exists()
            assert Path(result).suffix == ".png"

    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_no_candidates(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"candidates": []}
        mock_post.return_value = mock_resp

        gen = ImageGenerator()
        result = gen.generate_image("test prompt")
        assert result is None

    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_http_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.HTTPError("403 Forbidden")

        gen = ImageGenerator()
        result = gen.generate_image("test prompt")
        assert result is None

    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_timeout(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout("timeout")

        gen = ImageGenerator()
        result = gen.generate_image("test prompt")
        assert result is None

    @patch("core.image_generator.IMAGE_DIR")
    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_jpeg(self, mock_post, mock_dir):
        with patch("core.image_generator.IMAGE_DIR", self.tmp_path):
            fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64.b64encode(fake_image).decode(),
                            }
                        }]
                    }
                }]
            }
            mock_post.return_value = mock_resp

            gen = ImageGenerator()
            result = gen.generate_image("test prompt")
            assert result is not None
            assert Path(result).suffix == ".jpg"

    @patch("core.image_generator.requests.post")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_generate_image_no_image_in_parts(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "I cannot generate that image."}]
                }
            }]
        }
        mock_post.return_value = mock_resp

        gen = ImageGenerator()
        result = gen.generate_image("test prompt")
        assert result is None


class TestGenerateForPost:
    """Test the generate_for_post convenience method."""

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_returns_none_when_disabled(self):
        gen = ImageGenerator()
        result = gen.generate_for_post("テスト投稿", pillar=1)
        assert result is None

    @patch.object(ImageGenerator, "generate_image")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_calls_generate_image_with_prompt(self, mock_gen):
        mock_gen.return_value = "/tmp/test.png"
        gen = ImageGenerator()
        result = gen.generate_for_post("退去費用の話", pillar=1)
        assert result == "/tmp/test.png"
        # Verify the prompt was built correctly
        call_args = mock_gen.call_args[0][0]
        assert "退去費用の話" in call_args
        assert "real estate" in call_args or "house" in call_args


# ===========================================================================
# AutoPoster media upload tests
# ===========================================================================

class TestAutoPosterMediaUpload:
    """Test AutoPoster image upload and image-attached posting."""

    @patch("system_a.auto_post.Notifier")
    @patch("system_a.auto_post.SheetsClient")
    def test_upload_media_returns_none_for_missing_file(self, mock_sheets, mock_notif):
        from system_a.auto_post import AutoPoster
        poster = AutoPoster()
        result = poster._upload_media("/nonexistent/file.png")
        assert result is None

    @patch("system_a.auto_post.Notifier")
    @patch("system_a.auto_post.SheetsClient")
    @patch("system_a.auto_post.requests.post")
    def test_upload_media_success(self, mock_post, mock_sheets, mock_notif, tmp_path):
        from system_a.auto_post import AutoPoster

        # Create a fake image file
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n" + b"\x00" * 100)

        # Mock INIT response
        init_resp = MagicMock()
        init_resp.raise_for_status.return_value = None
        init_resp.json.return_value = {"media_id_string": "12345"}

        # Mock APPEND response
        append_resp = MagicMock()
        append_resp.raise_for_status.return_value = None

        # Mock FINALIZE response
        finalize_resp = MagicMock()
        finalize_resp.raise_for_status.return_value = None
        finalize_resp.json.return_value = {"media_id_string": "12345"}

        mock_post.side_effect = [init_resp, append_resp, finalize_resp]

        poster = AutoPoster()
        result = poster._upload_media(str(img_path))
        assert result == "12345"

    @patch("system_a.auto_post.Notifier")
    @patch("system_a.auto_post.SheetsClient")
    @patch("system_a.auto_post.requests.post")
    def test_post_tweet_with_media_id(self, mock_post, mock_sheets, mock_notif):
        from system_a.auto_post import AutoPoster

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {"id": "999"}}
        mock_post.return_value = mock_resp

        poster = AutoPoster()
        result = poster.post_tweet("テスト", media_id="12345")

        # Verify the payload included media
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["media"] == {"media_ids": ["12345"]}

    @patch("system_a.auto_post.Notifier")
    @patch("system_a.auto_post.SheetsClient")
    @patch("system_a.auto_post.requests.post")
    def test_post_tweet_without_media_id(self, mock_post, mock_sheets, mock_notif):
        from system_a.auto_post import AutoPoster

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {"id": "999"}}
        mock_post.return_value = mock_resp

        poster = AutoPoster()
        result = poster.post_tweet("テスト")

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "media" not in payload

"""
deAPI provider for photo-to-illustration conversion.

Uses https://deapi.ai - $5 free credits, no credit card required.
Get API key and Client ID at: https://deapi.ai/dashboard
Docs: https://docs.deapi.ai/api/transformation/image-to-image
WebSockets: https://docs.deapi.ai/execution-modes-and-integrations/websockets
"""

import io
import logging
from PIL import Image

from utils.http_client import get_http_session
from plugins.image_album.illustration_providers.base import BaseIllustrationProvider
from plugins.image_album.illustration_providers.prompts import get_illustration_prompt
from plugins.image_album.illustration_providers.deapi_websocket import wait_for_result

logger = logging.getLogger(__name__)

API_BASE = "https://api.deapi.ai"
IMG2IMG_ENDPOINT = f"{API_BASE}/api/v1/client/img2img"
STATUS_ENDPOINT = f"{API_BASE}/api/v1/client/request-status"
DEFAULT_MODEL = "Flux_2_Klein_4B_BF16"
MAX_WAIT_TIME = 300


class DeAPIIllustrationProvider(BaseIllustrationProvider):
    """Convert photos to illustrations via deAPI (https://deapi.ai)."""

    provider_id = "deapi"
    display_name = "deAPI (Free $5 credits)"
    requires_api_key = True
    expected_key = "DEAPI_TOKEN"

    def __init__(
        self,
        api_key: str | None = None,
        client_id: str | None = None,
        model: str = DEFAULT_MODEL,
        **kwargs,
    ):
        self.api_key = (api_key or "").strip()
        self.client_id = (client_id or "").strip()
        self.model = model
        self.session = get_http_session()

    def to_illustration(
        self,
        image: Image.Image,
        prompt: str | None = None,
        is_person: bool = True,
        guidance_scale: float = 7.5,
        **kwargs,
    ) -> Image.Image | None:
        """
        Convert photo to illustration using deAPI img2img.

        Args:
            image: Input PIL Image
            prompt: Override prompt (uses default if None)
            is_person: Use person-optimized prompt
            guidance_scale: CFG scale for generation
        """
        if not self.api_key:
            logger.error("deAPI API key not configured")
            return None

        prompt = prompt or get_illustration_prompt(is_person=is_person)

        try:
            img_rgb = image.convert("RGB") if image.mode != "RGB" else image
            buffer = io.BytesIO()
            img_rgb.save(buffer, format="PNG")
            buffer.seek(0)

            headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

            # Submit img2img request (multipart/form-data)
            files = {"image": ("image.png", buffer, "image/png")}
            data = {
                "prompt": prompt,
                "model": self.model,
                "steps": 4,
                "seed": 42,
                "guidance": guidance_scale,
            }

            logger.info("Sending image to deAPI for illustration conversion...")
            resp = self.session.post(
                IMG2IMG_ENDPOINT,
                data=data,
                files=files,
                headers=headers,
                timeout=30,
            )

            if resp.status_code != 200:
                err_msg = resp.text or resp.reason
                logger.error(f"deAPI error {resp.status_code}: {err_msg}")
                return None

            result = resp.json()
            request_id = result.get("data", {}).get("request_id")
            if not request_id:
                logger.error("deAPI did not return request_id")
                return None

            # Wait for result via WebSocket (real-time) or fallback to polling
            out_img = None
            if self.client_id:
                logger.info(f"Waiting for result via WebSocket (request {request_id})")
                ws_result = wait_for_result(
                    request_id=request_id,
                    api_token=self.api_key,
                    client_id=self.client_id,
                    session=self.session,
                    timeout=MAX_WAIT_TIME,
                )
                if ws_result and ws_result.get("result_url"):
                    img_resp = self.session.get(ws_result["result_url"], timeout=60)
                    if img_resp.status_code == 200:
                        out_img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                    else:
                        logger.warning("Failed to fetch WebSocket result URL, falling back to polling")
                else:
                    logger.warning("WebSocket did not return result, falling back to polling")

            if out_img is None:
                out_img = self._poll_for_result(request_id, headers)

            if out_img:
                logger.info(f"Illustration generated: {out_img.size[0]}x{out_img.size[1]}")
            return out_img

        except Exception as e:
            logger.error(f"Illustration conversion failed: {e}")
            return None

    def _poll_for_result(self, request_id: str, headers: dict) -> Image.Image | None:
        """Fallback: poll request-status until done."""
        import time

        url = f"{STATUS_ENDPOINT}/{request_id}"
        POLL_INTERVAL = 2
        start = time.monotonic()

        logger.info(f"Polling status for request {request_id}")

        while (time.monotonic() - start) < MAX_WAIT_TIME:
            resp = self.session.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.error(f"deAPI status error {resp.status_code}: {resp.text}")
                return None

            data = resp.json().get("data", {})
            status = data.get("status")

            if status == "done":
                result_url = data.get("result_url")
                if not result_url:
                    logger.error("deAPI done but no result_url")
                    return None
                img_resp = self.session.get(result_url, timeout=60)
                if img_resp.status_code != 200:
                    logger.error(f"Failed to fetch result image: {img_resp.status_code}")
                    return None
                return Image.open(io.BytesIO(img_resp.content)).convert("RGB")

            if status == "error":
                logger.error(f"deAPI job failed: {data}")
                return None

            time.sleep(POLL_INTERVAL)

        logger.error("deAPI job timed out waiting for result")
        return None

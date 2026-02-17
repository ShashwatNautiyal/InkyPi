import logging
import re
from pathlib import Path
from random import choice

from PIL import Image, ImageColor, ImageOps
from utils.http_client import get_http_session
from plugins.base_plugin.base_plugin import BasePlugin
from utils.image_utils import pad_image_blur
from plugins.image_album.illustration_providers import get_illustration_provider

logger = logging.getLogger(__name__)

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ILLUSTRATIONS_DIR = PROJECT_ROOT / "Illustrations"


def _sanitize_filename(name: str) -> str:
    """Sanitize string for use as filesystem path component."""
    s = (name or "unknown").strip()
    s = re.sub(r'[/\\:*?"<>|]', "", s)
    return s or "unknown"


def _save_illustration(
    img: Image.Image,
    *,
    person_name: str | None,
    album: str | None,
    asset: dict,
) -> None:
    """Save illustrated image to Illustrations/{personName|album}/{originalFileName}.EXT"""
    original_filename = asset.get("originalFileName") or asset.get("id", "illustration")
    # Preserve extension from original, default to png
    ext = ".jpeg"
    base_name = Path(original_filename).stem or "illustration"
    safe_filename = _sanitize_filename(base_name) + ext

    folder = _sanitize_filename(person_name) if person_name else _sanitize_filename(album) or "album"
    out_dir = ILLUSTRATIONS_DIR / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / safe_filename
    save_kwargs = {"quality": 95} if ext.lower() in (".jpg", ".jpeg") else {}
    img.save(out_path, **save_kwargs)
    logger.info(f"Saved illustration to {out_path}")


class ImmichProvider:
    def __init__(self, base_url: str, key: str, image_loader):
        self.base_url = base_url
        self.key = key
        self.headers = {"x-api-key": self.key}
        self.image_loader = image_loader
        self.session = get_http_session()

    def get_album_id(self, album: str) -> str:
        logger.debug(f"Fetching albums from {self.base_url}")
        r = self.session.get(f"{self.base_url}/api/albums", headers=self.headers)
        r.raise_for_status()
        albums = r.json()

        matching_albums = [a for a in albums if a["albumName"] == album]
        if not matching_albums:
            raise RuntimeError(f"Album '{album}' not found.")

        return matching_albums[0]["id"]

    def get_person_id(self, person_name: str) -> str:
        logger.debug(f"Fetching persons from {self.base_url}")
        r = self.session.get(f"{self.base_url}/api/search/person?name={person_name}", headers=self.headers)
        r.raise_for_status()
        persons = r.json()
        logger.info(f"Found {persons}")
        if not persons:
            raise RuntimeError(f"Person '{person_name}' not found.")
        return persons[0]["id"]

    def get_assets_by_person(self, person_id: str) -> list[dict]:
        """Fetch random assets from person via /api/search/random."""
        logger.debug(f"Fetching random assets from person {person_id}")
        body = {
            "personIds": [person_id],
            "type": "IMAGE"
            }
        r = self.session.post(f"{self.base_url}/api/search/random", json=body, headers=self.headers)
        r.raise_for_status()
        items = r.json()
        logger.info(f"Found {len(items)} total assets in person")
        return items

    def get_assets_by_album(self, album_id: str) -> list[dict]:
        """Fetch all assets from album."""
        all_items = []
        page_items = [1]
        page = 1

        logger.debug(f"Fetching assets from album {album_id}")
        while page_items:
            body = {
                "albumIds": [album_id],
                "size": 1000,
                "page": page
            }
            r2 = self.session.post(f"{self.base_url}/api/search/metadata", json=body, headers=self.headers)
            r2.raise_for_status()
            assets_data = r2.json()

            page_items = assets_data.get("assets", {}).get("items", [])
            all_items.extend(page_items)
            page += 1

        logger.debug(f"Found {len(all_items)} total assets in album")
        return all_items

    def get_image_by_album(self, album: str, dimensions: tuple[int, int], resize: bool = True) -> tuple[Image.Image | None, dict | None]:
        """
        Get a random image from the album.

        Returns:
            (PIL Image or None, selected_asset dict or None)
        """
        try:
            logger.info(f"Getting id for album '{album}'")
            album_id = self.get_album_id(album)
            logger.info(f"Getting assets from album id {album_id}")
            assets = self.get_assets_by_album(album_id)

            if not assets:
                logger.error(f"No assets found in album '{album}'")
                return None, None

        except Exception as e:
            logger.error(f"Error retrieving album data from {self.base_url}: {e}")
            return None, None

        selected_asset = choice(assets)
        asset_id = selected_asset["id"]
        asset_url = f"{self.base_url}/api/assets/{asset_id}/thumbnail?size=preview"

        logger.info(f"Selected random asset: {asset_id}")
        logger.debug(f"Downloading from: {asset_url}")

        img = self.image_loader.from_url(
            asset_url,
            dimensions,
            timeout_ms=40000,
            resize=resize,
            headers=self.headers
        )

        if not img:
            logger.error(f"Failed to load image {asset_id} from Immich")
            return None, None

        logger.info(f"Successfully loaded image: {img.size[0]}x{img.size[1]}")
        return img, selected_asset

    def get_image_by_person(self, person_name: str, dimensions: tuple[int, int], resize: bool = True) -> tuple[Image.Image | None, dict | None]:
        """
        Get a random image from the person.

        Returns:
            (PIL Image or None, selected_asset dict or None)
        """
        try:
            logger.info(f"Getting id for person '{person_name}'")
            person_id = self.get_person_id(person_name)
            logger.info(f"Getting assets from person id {person_id}")
            assets = self.get_assets_by_person(person_id)
        except Exception as e:
            logger.error(f"Error retrieving person data from {self.base_url}: {e}")
            return None, None

        selected_asset = choice(assets)
        asset_id = selected_asset["id"]
        asset_url = f"{self.base_url}/api/assets/{asset_id}/thumbnail?size=preview"

        logger.info(f"Selected random asset: {asset_id}")
        logger.debug(f"Downloading from: {asset_url}")

        img = self.image_loader.from_url(asset_url, dimensions, timeout_ms=40000, resize=resize, headers=self.headers)

        if not img:
            logger.error(f"Failed to load image {asset_id} from Immich")
            return None, None

        logger.info(f"Successfully loaded image: {img.size[0]}x{img.size[1]}")
        return img, selected_asset

class ImageAlbum(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "Immich",
            "expected_key": "IMMICH_KEY"
        }
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Image Album Plugin: Starting image generation ===")

        orientation = device_config.get_config("orientation")
        dimensions = device_config.get_resolution()

        if orientation == "vertical":
            dimensions = dimensions[::-1]
            logger.debug(f"Vertical orientation detected, dimensions: {dimensions[0]}x{dimensions[1]}")

        img = None
        illustration_resized = False
        album_provider = settings.get("albumProvider")
        logger.info(f"Album provider: {album_provider}")

        # Check padding options to determine resize strategy
        use_padding = settings.get('padImage') == "true"
        background_option = settings.get('backgroundOption', 'blur')
        logger.debug(f"Settings: pad_image={use_padding}, background_option={background_option}")

        match album_provider:
            case "Immich":
                key = device_config.load_env_key("IMMICH_KEY")
                if not key:
                    logger.error("Immich API Key not configured")
                    raise RuntimeError("Immich API Key not configured.")

                url = settings.get('url')
                if not url:
                    logger.error("Immich URL not provided")
                    raise RuntimeError("Immich URL is required.")

                album = settings.get('album')
                person_name = settings.get('personName')
                if not album and not person_name:
                    logger.error("Neither album name nor person name provided")
                    raise RuntimeError("Either album name or person name is required.")

                logger.info(f"Immich URL: {url}")
                logger.info(f"Album: {album}")
                logger.info(f"Person name: {person_name}")

                provider = ImmichProvider(url, key, self.image_loader)
                convert_to_illustration = settings.get("convertToIllustration") == "true"
                # Load without resize when illustrating (AI needs full-size); else resize when no padding
                load_resize = False if convert_to_illustration else not use_padding

                if person_name:
                    img, selected_asset = provider.get_image_by_person(person_name, dimensions, resize=load_resize)
                else:
                    img, selected_asset = provider.get_image_by_album(album, dimensions, resize=load_resize)

                # Optional: convert to illustration via AI (modular provider)
                if img and convert_to_illustration:
                    illustration_provider_id = settings.get("illustrationProvider", "deapi")
                    api_key = device_config.load_env_key("DEAPI_TOKEN")
                    illustration_provider = get_illustration_provider(
                        illustration_provider_id,
                        api_key=api_key,
                    )
                    if illustration_provider and illustration_provider.is_configured(api_key):
                        illustrated = illustration_provider.to_illustration(img, is_person=bool(person_name))
                        if illustrated:
                            img = illustrated
                            logger.info("Image converted to illustration successfully")
                            # Resize illustration to dimensions (done after illustration)
                            if use_padding:
                                img = pad_image_blur(img, dimensions)
                            else:
                                img = ImageOps.fit(img, dimensions, method=Image.Resampling.LANCZOS)
                            illustration_resized = True
                            # Save illustration to Illustrations/{folder}/{originalFileName}.EXT
                            if selected_asset:
                                _save_illustration(
                                    illustrated,
                                    person_name=person_name,
                                    album=album,
                                    asset=selected_asset,
                                )
                        else:
                            logger.warning("Illustration conversion failed, using original image")
                    else:
                        logger.warning("Illustration provider not configured, using original image")

                if not img:
                    logger.error("Failed to retrieve image from Immich")
                    raise RuntimeError("Failed to load image, please check logs.")
            case _:
                logger.error(f"Unknown album provider: {album_provider}")
                raise RuntimeError(f"Unsupported album provider: {album_provider}")

        if img is None:
            logger.error("Image is None after provider processing")
            raise RuntimeError("Failed to load image, please check logs.")

        # Apply padding if requested (image was loaded at full size); skip if already resized by illustration
        if not illustration_resized:
            if use_padding:
                logger.debug(f"Applying padding with {background_option} background")
                if background_option == "blur":
                    img = pad_image_blur(img, dimensions)
                else:
                    background_color = ImageColor.getcolor(
                        settings.get('backgroundColor') or "white",
                        img.mode
                    )
                    img = ImageOps.pad(img, dimensions, color=background_color, method=Image.Resampling.LANCZOS)
            # else: loader already resized to fit with proper aspect ratio

        logger.info("=== Image Album Plugin: Image generation complete ===")
        return img

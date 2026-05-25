from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests

from .config import SETTINGS


# ---------------------------------------------------------------------------
# Image hosting helpers
# ---------------------------------------------------------------------------

def upload_image_to_imgbb(png_path: Path) -> str | None:
    """Upload PNG to ImgBB and return a public image URL."""
    api_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not api_key:
        print("[ImgBB] ERROR: IMGBB_API_KEY is empty")
        return None

    if not png_path.exists():
        print(f"[ImgBB] ERROR: image file not found: {png_path}")
        return None

    url = "https://api.imgbb.com/1/upload"

    try:
        # ImgBB expects base64 as a text string, not raw bytes.
        encoded_image = base64.b64encode(png_path.read_bytes()).decode("ascii")
        response = requests.post(
            url,
            data={
                "key": api_key,
                "image": encoded_image,
                "name": png_path.stem,
            },
            timeout=SETTINGS.request_timeout_s,
        )

        if response.status_code >= 400:
            print(f"[ImgBB] ERROR HTTP {response.status_code}: {response.text[:500]}")
            return None

        data = response.json()
        if not data.get("success"):
            print(f"[ImgBB] ERROR response: {data}")
            return None

        image_url = (
            data.get("data", {}).get("url")
            or data.get("data", {}).get("display_url")
            or data.get("data", {}).get("image", {}).get("url")
        )

        if not image_url:
            print(f"[ImgBB] ERROR: no URL returned: {data}")
            return None

        print(f"[ImgBB] OK image_url={image_url}")
        return image_url

    except Exception as exc:
        print(f"[ImgBB] ERROR upload failed: {exc}")
        return None


def upload_image_to_cloudinary(png_path: Path) -> str | None:
    """Upload PNG to Cloudinary and return a secure public URL."""
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("[Cloudinary] package not installed; skipping")
        return None

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "").strip(),
        api_key=os.getenv("CLOUDINARY_API_KEY", "").strip(),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", "").strip(),
    )

    try:
        result = cloudinary.uploader.upload(str(png_path), resource_type="image")
        image_url = result.get("secure_url")
        if image_url:
            print(f"[Cloudinary] OK image_url={image_url}")
            return image_url
        print(f"[Cloudinary] ERROR: no secure_url returned: {result}")
        return None
    except Exception as exc:
        print(f"[Cloudinary] ERROR upload failed: {exc}")
        return None


def get_image_public_url(png_path: Path) -> str | None:
    """Return a public URL for a PNG using IMAGE_HOST."""
    host = os.getenv("IMAGE_HOST", "imgbb").lower().strip()

    if host == "cloudinary":
        return upload_image_to_cloudinary(png_path)

    # Default: ImgBB
    return upload_image_to_imgbb(png_path)


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_make_payload(caption: str, report: dict[str, Any], image_path: Path) -> dict[str, Any]:
    """Build Make.com payload.

    IMPORTANT:
    Facebook Pages > Create a Photo Post needs a public URL.
    Therefore this function sends top-level image_url only after successful upload.
    It no longer falls back to image_base64, because that creates text-only posts in Make.
    """
    base_fields: dict[str, Any] = {
        "caption": caption,
        "page_name": SETTINGS.facebook_page_name,
        "risk_level": report.get("risk", {}).get("level"),
        "confidence": report.get("validation", {}).get("confidence"),
        "safe_mode_blocked": report.get("safe_mode_blocked", False),
        "report": report,
    }

    png_path_str = report.get("image_png_path")
    if not png_path_str:
        return {
            **base_fields,
            "image_url": "",
            "image_upload_error": "report.image_png_path is missing",
        }

    png_path = Path(png_path_str)
    if not png_path.exists():
        return {
            **base_fields,
            "image_url": "",
            "image_upload_error": f"PNG file not found: {png_path}",
        }

    image_url = get_image_public_url(png_path)
    if not image_url:
        return {
            **base_fields,
            "image_url": "",
            "image_filename": png_path.name,
            "image_mime": "image/png",
            "image_upload_error": "Public image upload failed. Check IMGBB_API_KEY / IMAGE_HOST in GitHub Secrets.",
        }

    return {
        **base_fields,
        "image_url": image_url,
        "image_filename": png_path.name,
        "image_mime": "image/png",
    }


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def post_to_make(payload: dict[str, Any]) -> tuple[bool, str]:
    if not SETTINGS.make_webhook_url:
        return False, "MAKE_WEBHOOK_URL is empty"

    # Do not send text-only Facebook posts when image upload failed.
    if not payload.get("image_url"):
        return False, f"image_url is empty: {payload.get('image_upload_error', 'unknown upload error')}"

    try:
        response = requests.post(
            SETTINGS.make_webhook_url,
            json=payload,
            timeout=SETTINGS.request_timeout_s,
        )
        response.raise_for_status()
        return True, f"posted: HTTP {response.status_code}"
    except Exception as exc:
        return False, f"post failed: {exc}"

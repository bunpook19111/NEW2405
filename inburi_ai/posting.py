from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests

from .config import SETTINGS
from .graphics import file_to_base64


# ---------------------------------------------------------------------------
# Image hosting helpers
# ---------------------------------------------------------------------------

def upload_image_to_imgbb(png_path: Path) -> str | None:
    """อัปโหลดไฟล์ PNG ไปที่ ImgBB แล้วคืน Public URL
    
    ต้องตั้งค่า IMGBB_API_KEY ใน .env
    สมัคร API Key ได้ที่ https://api.imgbb.com/
    """
    api_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not api_key:
        print("[ImgBB] IMGBB_API_KEY ไม่ได้ตั้งค่า — ข้าม upload")
        return None

    url = "https://api.imgbb.com/1/upload"
    with open(png_path, "rb") as f:
        payload = {
            "key": api_key,
            "image": base64.b64encode(f.read()),
        }
    try:
        response = requests.post(url, data=payload, timeout=SETTINGS.request_timeout_s)
        response.raise_for_status()
        data = response.json()
        public_url = data["data"]["url"]
        print(f"[ImgBB] อัปโหลดสำเร็จ: {public_url}")
        return public_url
    except Exception as e:
        print(f"[ImgBB] อัปโหลดล้มเหลว: {e}")
        return None


def upload_image_to_cloudinary(png_path: Path) -> str | None:
    """อัปโหลดไฟล์ PNG ไปที่ Cloudinary แล้วคืน Secure URL
    
    ต้องตั้งค่า CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET ใน .env
    และ pip install cloudinary
    """
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("[Cloudinary] ไม่พบ package — รัน: pip install cloudinary")
        return None

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
        api_key=os.getenv("CLOUDINARY_API_KEY", ""),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    )
    try:
        result = cloudinary.uploader.upload(str(png_path))
        public_url = result.get("secure_url")
        print(f"[Cloudinary] อัปโหลดสำเร็จ: {public_url}")
        return public_url
    except Exception as e:
        print(f"[Cloudinary] อัปโหลดล้มเหลว: {e}")
        return None


def get_image_public_url(png_path: Path) -> str | None:
    """ลองอัปโหลดรูปตามลำดับ: ImgBB → Cloudinary → None
    
    เลือก provider จาก IMAGE_HOST env var ("imgbb" | "cloudinary")
    ถ้าไม่ตั้งค่าจะลอง ImgBB ก่อน แล้ว fallback ไป Cloudinary
    """
    host = os.getenv("IMAGE_HOST", "imgbb").lower().strip()
    if host == "cloudinary":
        return upload_image_to_cloudinary(png_path)
    # default: imgbb
    url = upload_image_to_imgbb(png_path)
    if url is None:
        print("[posting] ImgBB ล้มเหลว — ลอง Cloudinary...")
        url = upload_image_to_cloudinary(png_path)
    return url


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_make_payload(caption: str, report: dict[str, Any], image_path: Path) -> dict[str, Any]:
    """สร้าง payload สำหรับส่งไปที่ Make.com webhook
    
    ลำดับความสำคัญของรูป:
    1. PNG → อัปโหลดขึ้น ImgBB/Cloudinary → ส่ง image_url (Public URL)
    2. ถ้าอัปโหลดไม่สำเร็จ → fallback ส่ง base64 แทน (Make อาจรองรับหรือไม่ก็ได้)
    3. ถ้าไม่มี PNG เลย → ส่ง SVG base64 พร้อม warning
    """
    base_fields = {
        "caption": caption,
        "page_name": SETTINGS.facebook_page_name,
        "risk_level": report.get("risk", {}).get("level"),
        "confidence": report.get("validation", {}).get("confidence"),
        "safe_mode_blocked": report.get("safe_mode_blocked", False),
        "report": report,
    }

    # --- ลองใช้ PNG ก่อน ---
    png_path_str = report.get("image_png_path")
    if png_path_str:
        img_path = Path(png_path_str)
        if img_path.exists():
            image_url = get_image_public_url(img_path)
            if image_url:
                # ✅ วิธีที่ดีที่สุด: ส่ง URL ตรงๆ — Make → Facebook รองรับเต็มรูปแบบ
                return {
                    **base_fields,
                    "image_url": image_url,
                    "image_filename": img_path.name,
                    "image_mime": "image/png",
                }
            else:
                # ⚠️ อัปโหลดไม่ได้ — fallback base64 (Make อาจต้องการ HTTP module เพิ่มเติม)
                print("[posting] ไม่ได้ URL สาธารณะ — fallback ใช้ base64")
                return {
                    **base_fields,
                    "image_filename": img_path.name,
                    "image_mime": "image/png",
                    "image_base64": file_to_base64(img_path),
                    "image_warning": "URL upload failed; base64 fallback used",
                }

    # --- Fallback SVG ---
    print("[posting] ไม่พบ PNG — ส่ง SVG (Facebook/LINE อาจแสดงผลไม่ถูกต้อง)")
    return {
        **base_fields,
        "image_filename": image_path.name,
        "image_mime": "image/svg+xml",
        "image_base64": file_to_base64(image_path),
        "image_warning": "PNG unavailable; SVG sent — Facebook/LINE may not display this correctly",
    }


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def post_to_make(payload: dict[str, Any]) -> tuple[bool, str]:
    if not SETTINGS.make_webhook_url:
        return False, "MAKE_WEBHOOK_URL is empty"
    try:
        r = requests.post(SETTINGS.make_webhook_url, json=payload, timeout=SETTINGS.request_timeout_s)
        r.raise_for_status()
        return True, f"posted: HTTP {r.status_code}"
    except Exception as exc:
        return False, f"post failed: {exc}"

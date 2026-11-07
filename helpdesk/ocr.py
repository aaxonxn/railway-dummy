"""OCR processing module using Tesseract."""

import io
import os
import shutil
from pathlib import Path
from typing import Optional
from PIL import Image, ImageEnhance, ImageOps

from helpdesk.config import config
from helpdesk.logging_config import logger

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract is not installed; OCR capabilities will be disabled.")


def get_tesseract_cmd() -> Optional[str]:
    """Find and return valid Tesseract executable path."""
    if not PYTESSERACT_AVAILABLE:
        return None

    # Check configured path first
    configured = config.tesseract_cmd
    if configured and Path(configured).is_file():
        return str(configured)

    # Check system PATH
    which_path = shutil.which("tesseract")
    if which_path:
        return which_path

    # Common Windows installation locations
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        Path.home() / "AppData" / "Local" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for p in common_paths:
        if Path(p).is_file():
            return str(p)

    return None


def init_ocr() -> bool:
    """Initialize Tesseract configuration."""
    if not PYTESSERACT_AVAILABLE:
        return False

    cmd = get_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            ver = pytesseract.get_tesseract_version()
            logger.info("Tesseract initialized at '%s' (version %s)", cmd, ver)
            return True
        except Exception as e:
            logger.warning("Tesseract binary found at '%s' but failed execution: %s", cmd, e)
            return False
    else:
        logger.warning("Tesseract executable not found. Scanned pages will not have OCR text.")
        return False


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """Apply grayscale and contrast enhancement to improve OCR accuracy."""
    # Convert to grayscale
    gray = image.convert("L")
    # Increase contrast
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.8)
    return enhanced


def ocr_image(image: Image.Image, lang: str = "eng") -> str:
    """Perform OCR on a PIL Image and return extracted text."""
    if not PYTESSERACT_AVAILABLE:
        logger.warning("pytesseract unavailable, skipping OCR.")
        return ""

    cmd = get_tesseract_cmd()
    if not cmd:
        logger.warning("Tesseract binary not found, skipping OCR.")
        return ""

    pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        processed = preprocess_image_for_ocr(image)
        # Check if requested language is available in Tesseract
        try:
            available_langs = pytesseract.get_languages()
        except Exception:
            available_langs = ["eng"]

        selected_lang = lang if lang in available_langs else "eng"
        text = pytesseract.image_to_string(processed, lang=selected_lang)
        return text.strip()
    except Exception as e:
        logger.error("OCR execution error: %s", e)
        return ""


def ocr_pixmap(pixmap, lang: str = "eng") -> str:
    """Perform OCR on a PyMuPDF pixmap."""
    try:
        img_bytes = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))
        return ocr_image(image, lang=lang)
    except Exception as e:
        logger.error("Failed to convert pixmap to image for OCR: %s", e)
        return ""


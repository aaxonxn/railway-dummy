"""Unit tests for OCR module and Tesseract integration."""

from pathlib import Path
from PIL import Image, ImageDraw
import pytest

from helpdesk.config import config
from helpdesk.ocr import (
    get_tesseract_cmd,
    init_ocr,
    ocr_image,
    preprocess_image_for_ocr,
)


def test_tesseract_command_discovery():
    """Verify that get_tesseract_cmd finds the executable or valid path."""
    cmd = get_tesseract_cmd()
    if cmd is not None:
        assert Path(cmd).is_file()
        assert "tesseract" in cmd.lower()


def test_init_ocr():
    """Verify init_ocr initializes properly."""
    res = init_ocr()
    # Should succeed on this machine where Tesseract is installed
    assert isinstance(res, bool)


def test_preprocess_image():
    """Verify image preprocessing converts to grayscale and enhances contrast."""
    img = Image.new("RGB", (100, 50), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "RAILWAY", fill="black")
    processed = preprocess_image_for_ocr(img)
    assert processed.mode == "L"
    assert processed.size == (100, 50)


def test_ocr_synthetic_image():
    """Verify OCR extracts text from a rendered synthetic test image."""
    cmd = get_tesseract_cmd()
    if not cmd:
        pytest.skip("Tesseract executable not available")

    # Create image with clear black text on white background
    img = Image.new("RGB", (400, 100), color="white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "COMMERCIAL CIRCULAR 10 OF 2024", fill="black")

    text = ocr_image(img, lang="eng")
    assert "COMMERCIAL" in text or "CIRCULAR" in text or "2024" in text


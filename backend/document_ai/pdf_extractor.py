"""
NWIS Phase 4 — PDF Extractor
============================
Extracts text and page structure from PDF and TXT documents.
Employs direct PDF text stream extraction first, automatically falling back
to OCR processing when scanned or image-only pages are detected.
Preserves page numbers, paragraph bounds, and line locations.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pypdf

from .ocr_processor import ocr_processor

logger = logging.getLogger("nwis.pdf_extractor")


class PDFExtractorError(Exception):
    """Raised when PDF extraction encounters unrecoverable corruption."""
    pass


class PDFExtractor:
    """
    Unified text extraction engine for engineering documents (PDF & TXT).
    """

    def __init__(self, min_page_chars_for_text: int = 35):
        self.min_page_chars_for_text = min_page_chars_for_text

    def extract_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extracts document pages and paragraphs.
        Returns a list of page dicts:
        [
            {
                "page_number": int,
                "text": str,
                "lines": List[Dict[str, Any]],  # {"line_no": int, "text": str}
                "ocr_applied": bool,
                "confidence": float
            },
            ...
        ]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file does not exist: {path}")

        suffix = path.suffix.lower()

        if suffix == ".txt":
            return self._extract_txt(path)
        elif suffix == ".pdf":
            return self._extract_pdf(path)
        else:
            raise ValueError(f"Unsupported document format: {suffix}. Supported formats: .pdf, .txt")

    def _extract_txt(self, path: Path) -> List[Dict[str, Any]]:
        """Extracts plain text documents, chunking into simulated pages of 60 lines."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise PDFExtractorError(f"Failed to read TXT document: {e}")

        raw_lines = content.split("\n")
        page_size = 60
        pages: List[Dict[str, Any]] = []

        total_pages = max(1, (len(raw_lines) + page_size - 1) // page_size)
        for p_idx in range(total_pages):
            chunk_lines = raw_lines[p_idx * page_size : (p_idx + 1) * page_size]
            line_dicts = [
                {"line_no": idx + 1, "text": l.strip()}
                for idx, l in enumerate(chunk_lines)
                if l.strip()
            ]
            page_text = "\n".join(chunk_lines).strip()
            pages.append({
                "page_number": p_idx + 1,
                "text": page_text,
                "lines": line_dicts,
                "ocr_applied": False,
                "confidence": 1.0,
            })

        return pages

    def _extract_pdf(self, path: Path) -> List[Dict[str, Any]]:
        """
        Extracts PDF document using high-fidelity native extractors (PyMuPDF / pdfplumber),
        falling back to pypdf and Tesseract OCR when scanned or image-only pages are detected.
        """
        # Try PyMuPDF (fitz) first
        try:
            import pymupdf
            doc = pymupdf.open(str(path))
            if len(doc) == 0:
                raise PDFExtractorError("PDF file contains 0 pages.")

            pages: List[Dict[str, Any]] = []
            for p_idx in range(len(doc)):
                page_num = p_idx + 1
                page = doc[p_idx]
                page_text = page.get_text() or ""
                ocr_applied = False
                confidence = 0.99

                clean_text = page_text.strip()
                if len(clean_text) < self.min_page_chars_for_text:
                    logger.info(f"Page {page_num} has sparse text ({len(clean_text)} chars). Triggering OCR.")
                    ocr_result = ocr_processor.process_image(path, page_number=page_num)
                    page_text = ocr_result.get("text", "")
                    ocr_applied = True
                    confidence = ocr_result.get("confidence", 0.75)

                lines_raw = page_text.split("\n")
                lines_structured = [
                    {"line_no": idx + 1, "text": l.strip()}
                    for idx, l in enumerate(lines_raw)
                    if l.strip()
                ]

                pages.append({
                    "page_number": page_num,
                    "text": page_text.strip(),
                    "lines": lines_structured,
                    "ocr_applied": ocr_applied,
                    "confidence": confidence,
                    "extractor": "pymupdf" if not ocr_applied else "ocr",
                })
            doc.close()
            return pages
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed or encountered error: {e}. Falling back.")

        # Try pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                if len(pdf.pages) == 0:
                    raise PDFExtractorError("PDF file contains 0 pages.")
                pages = []
                for p_idx, page in enumerate(pdf.pages):
                    page_num = p_idx + 1
                    page_text = page.extract_text() or ""
                    ocr_applied = False
                    confidence = 0.98

                    clean_text = page_text.strip()
                    if len(clean_text) < self.min_page_chars_for_text:
                        ocr_result = ocr_processor.process_image(path, page_number=page_num)
                        page_text = ocr_result.get("text", "")
                        ocr_applied = True
                        confidence = ocr_result.get("confidence", 0.75)

                    lines_raw = page_text.split("\n")
                    lines_structured = [
                        {"line_no": idx + 1, "text": l.strip()}
                        for idx, l in enumerate(lines_raw)
                        if l.strip()
                    ]
                    pages.append({
                        "page_number": page_num,
                        "text": page_text.strip(),
                        "lines": lines_structured,
                        "ocr_applied": ocr_applied,
                        "confidence": confidence,
                        "extractor": "pdfplumber" if not ocr_applied else "ocr",
                    })
                return pages
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}. Falling back to pypdf.")

        # Standard pypdf fallback
        try:
            reader = pypdf.PdfReader(str(path))
        except Exception as e:
            raise PDFExtractorError(f"Corrupted or invalid PDF file: {e}")

        if len(reader.pages) == 0:
            raise PDFExtractorError("PDF file contains 0 pages.")

        pages = []
        for p_idx, page in enumerate(reader.pages):
            page_num = p_idx + 1
            page_text = ""
            ocr_applied = False
            confidence = 0.95

            try:
                page_text = page.extract_text() or ""
            except Exception as e:
                logger.warning(f"Direct pypdf text extraction failed on page {page_num}: {e}")
                page_text = ""

            clean_text = page_text.strip()
            if len(clean_text) < self.min_page_chars_for_text:
                logger.info(f"Page {page_num} has sparse text ({len(clean_text)} chars). Triggering OCR.")
                ocr_result = ocr_processor.process_image(path, page_number=page_num)
                page_text = ocr_result.get("text", "")
                ocr_applied = True
                confidence = ocr_result.get("confidence", 0.75)

            lines_raw = page_text.split("\n")
            lines_structured = [
                {"line_no": idx + 1, "text": l.strip()}
                for idx, l in enumerate(lines_raw)
                if l.strip()
            ]

            pages.append({
                "page_number": page_num,
                "text": page_text.strip(),
                "lines": lines_structured,
                "ocr_applied": ocr_applied,
                "confidence": confidence,
                "extractor": "pypdf" if not ocr_applied else "ocr",
            })

        return pages


pdf_extractor = PDFExtractor()


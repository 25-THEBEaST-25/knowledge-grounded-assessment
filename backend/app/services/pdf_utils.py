import io
from typing import List


def render_pdf_pages(content: bytes, scale: float = 2.0, max_pages: int = 30) -> List[bytes]:
    """Rasterise PDF pages to PNG bytes (for OCR). Raises ValueError on unreadable PDFs."""
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(content)
        n = len(pdf)
        if n == 0 or n > max_pages:
            raise ValueError(f"PDF must have between 1 and {max_pages} pages (has {n}).")
        out = []
        for i in range(n):
            buf = io.BytesIO()
            pdf[i].render(scale=scale).to_pil().save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this PDF.") from exc

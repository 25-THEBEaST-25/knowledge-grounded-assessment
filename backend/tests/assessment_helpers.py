"""Shared fakes for assessment-workflow tests. EVERYTHING here is a test double:
fake OCR, fake LLM, fake embedder (hashed bag-of-words) with in-memory Qdrant.
Nothing here proves real Gemini/PaddleOCR/Qdrant-server integration."""
import hashlib
import io
import json
import re

from PIL import Image

from backend.app.services.ocr_service import OCRLine, OCRResult

QUESTION_PAPER = b"Q1(a) Explain the TCP three-way handshake. [4 marks]\nQ1(b) State the purpose of the sliding window. [2 marks]\n"
MODEL_ANSWERS = (b"Q1(a) The client sends SYN, the server replies with SYN-ACK and the client answers with ACK, "
                 b"establishing a reliable connection.\nQ1(b) The sliding window controls how much data may be in flight "
                 b"before an acknowledgement, giving flow control.\n")
RUBRIC = (b"Q1(a)\n- Client sends SYN (1 mark)\n- Server replies SYN-ACK (2 marks) (partial credit)\n- Client sends ACK (1 mark)\n"
          b"Q1(b)\n- Explains flow control (2 marks)\n")
REFERENCE = b"Reference notes: TCP uses sequence numbers and acknowledgements. Window size advertises receiver buffer space.\n"


def png(seed: int = 0) -> bytes:
    img = Image.new("RGB", (80, 60), (255, 255, 255))
    img.putpixel((seed % 80, seed % 60), (0, 0, 0))
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


class FakeOCR:
    """Returns scripted text lines with a given confidence."""
    def __init__(self, text: str, conf: float = 0.95):
        self.text, self.conf = text, conf

    def extract(self, image_bytes: bytes) -> OCRResult:
        lines = [OCRLine(t, self.conf, [0, i * 20, 100, i * 20 + 18]) for i, t in enumerate(self.text.split("\n"))]
        return OCRResult(text="\n".join(l.text for l in lines), lines=lines, mean_confidence=self.conf, engine="fake")


GOOD_SHEET = ("Q1(a) The client sends SYN to the server. The server replies with SYN-ACK. Then the client sends ACK.\n"
              "Q1(b) The sliding window limits unacknowledged data in flight, which gives flow control.")


def fake_llm_factory(statuses=None, confidence=0.95, calls=None):
    """Behaves like a well-formed evaluator: marks every criterion in the prompt with `statuses[code]` (default SATISFIED)."""
    statuses = statuses or {}

    def llm(prompt: str) -> str:
        if calls is not None:
            calls.append(prompt)
        codes = re.findall(r'"code":\s*"(C\d+)"', prompt)
        refs = re.findall(r"^\[(S\d+)\]", prompt, re.M)
        return json.dumps({"criteria": [
            {"code": c, "status": statuses.get(c, "SATISFIED"), "evidence": f"evidence for {c}",
             "confidence": confidence, "source_refs": refs[:1]} for c in codes]})
    return llm


class HashEmbedder:
    DIM = 64

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.DIM
            for w in re.findall(r"[a-z]+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.DIM] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out

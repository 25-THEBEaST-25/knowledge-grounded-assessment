"""DEMONSTRATION DATA ONLY. Creates a clearly-labelled demo assessment (is_demo=True) from sample
documents, approves it, and writes a SYNTHETIC PRINTED-TEXT answer sheet PNG for the demo upload.
The sheet is printed text, not handwriting: it demonstrates the pipeline, not handwriting accuracy.

Run from the repo root:  python -m backend.scripts.demo_seed [--out demo_assets]
Safe to re-run: it reuses an existing demo assessment with the same title."""
import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw

from backend.app.db import models as m
from backend.app.db.session import get_engine, session_scope
from backend.app.services import materials_service as mat

TITLE = "[DEMO] Computer Networks Quiz 1"
DOCS = {
    "question_paper": ("demo_question_paper.txt",
                       "Q1(a) Explain the TCP three-way handshake. [4 marks]\nQ1(b) State the purpose of the sliding window. [2 marks]\n"),
    "model_answer": ("demo_model_answers.txt",
                     "Q1(a) The client sends SYN, the server replies with SYN-ACK and the client answers with ACK, establishing a reliable connection.\n"
                     "Q1(b) The sliding window controls how much data may be in flight before an acknowledgement, giving flow control.\n"),
    "rubric": ("demo_rubric.txt",
               "Q1(a)\n- Client sends SYN (1 mark)\n- Server replies SYN-ACK (2 marks) (partial credit)\n- Client sends ACK (1 mark)\n"
               "Q1(b)\n- Explains flow control (2 marks)\n"),
    "reference": ("demo_reference_notes.txt",
                  "TCP uses sequence numbers and acknowledgements. The window size advertises receiver buffer space.\n"),
}
SHEET = ["Q1(a) The client sends SYN to the server.", "The server replies with SYN-ACK. Then the client sends ACK.",
         "Q1(b) The sliding window limits unacknowledged data", "in flight, which gives flow control."]


def make_sheet(path: Path) -> None:
    img = Image.new("RGB", (1200, 500), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(SHEET):
        d.text((40, 40 + i * 60), line, fill="black")  # default bitmap font; synthetic, printed
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo_assets")
    out = Path(ap.parse_args().out)
    from backend.app.db.models import Base
    if os.getenv("DATABASE_URL", "").startswith("sqlite") or not os.getenv("DATABASE_URL"):
        Base.metadata.create_all(get_engine())  # dev convenience only; Postgres uses `alembic upgrade head`
    with session_scope() as db:
        a = db.query(m.Assessment).filter_by(title=TITLE, is_demo=True).first()
        if a is None:
            a = mat.create_assessment(db, subject_code="DEMO-CN", subject_name="Computer Networks (demo)", title=TITLE,
                                      actor="demo_seed", is_demo=True)
            for kind, (name, text) in DOCS.items():
                mat.add_document(db, a, kind, name, text.encode(), "demo_seed")
        print(f"Demo assessment id: {a.id}  (status {a.status})")
        print("Approve it in the UI (or POST /assessments/<id>/approve), then upload the sheet below.")
    make_sheet(out / "demo_answer_sheet.png")
    print(f"Synthetic printed-text answer sheet: {out / 'demo_answer_sheet.png'}")


if __name__ == "__main__":
    main()

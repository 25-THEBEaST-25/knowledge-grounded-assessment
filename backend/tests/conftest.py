import sys
from pathlib import Path

# repo root so `backend.app...` imports resolve when running `pytest backend/tests`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

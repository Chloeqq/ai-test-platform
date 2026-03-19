import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

PYTHONPATH_ENTRIES = [
    ROOT / "apps" / "ai-orchestrator" / "src",
    ROOT / "runners" / "web-playwright-python",
    ROOT / "agents" / "test-design-agent",
]


for entry in PYTHONPATH_ENTRIES:
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

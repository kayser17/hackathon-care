from __future__ import annotations

import json
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from preprocessing.pipeline import preprocess_conversation_file


def main() -> int:
    conversation_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else BACKEND_DIR / "preprocessing" / "conversation_draft.json"
    )

    result = preprocess_conversation_file(str(conversation_path))
    print(json.dumps(result.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Regenerate the committed REST contract from the application (SPEC.md 5.6).

Run from `server/`:  .venv\\Scripts\\python.exe scripts\\export_contract.py
The contract is a reviewed artifact, so the change shows up as a file diff.
"""

import json
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from core.config import Settings  # noqa: E402
from main import create_app  # noqa: E402

CONTRACTS_DIR = SERVER_ROOT.parent / "contracts"


def main() -> None:
    contract = create_app(Settings()).openapi()
    target = CONTRACTS_DIR / "openapi.json"
    target.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",  # tracked as LF (see .gitattributes); keeps the diff clean
    )
    print(f"wrote {target}")


if __name__ == "__main__":
    main()

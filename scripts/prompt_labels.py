"""Quản lý label prompt day13-chat trên Langfuse — promote/rollback production.

Mỗi label chỉ trỏ tới MỘT version; dời label = promote (v2) hoặc rollback (v1).
App lấy prompt theo LANGFUSE_PROMPT_LABEL trong .env và cache ~60 giây,
nên SAU MỖI LẦN đổi label phải restart API rồi mới gửi request kiểm tra:

    python scripts/prompt_labels.py status          # xem label đang trỏ đâu
    python scripts/prompt_labels.py promote         # production -> version 2
    python scripts/prompt_labels.py rollback        # production -> version 1

Sau khi đổi label, restart API và gửi 1 request, rồi mở trace của request đó
xem Metadata của lab-agent-run phải có prompt_version khớp (2 sau promote,
1 sau rollback).
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from langfuse import get_client  # noqa: E402  (cần load .env trước)

PROMPT_NAME = "day13-chat"
LABELS = ("baseline", "candidate", "production", "latest")


def show_status(client) -> None:
    print(f"prompt {PROMPT_NAME!r} label state:")
    for label in LABELS:
        prompt = client.get_prompt(PROMPT_NAME, label=label, type="text")
        print(f"  {label!r:14s} -> version {prompt.version}")


def main() -> int:
    op = sys.argv[1] if len(sys.argv) > 1 else "status"
    client = get_client()

    if op == "promote":
        # production dời từ version 1 -> version 2 (candidate vẫn ở v2)
        client.update_prompt(
            name=PROMPT_NAME, version=2, new_labels=["candidate", "production"]
        )
        print("promoted: production -> version 2")
    elif op == "rollback":
        # production dời về version 1 (baseline vẫn ở v1)
        client.update_prompt(
            name=PROMPT_NAME, version=1, new_labels=["baseline", "production"]
        )
        print("rolled back: production -> version 1")
    elif op != "status":
        print(f"unknown op {op!r} - use: status | promote | rollback")
        return 2

    show_status(client)
    print("\nRemember: restart the API before checking (prompt cache ~60s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

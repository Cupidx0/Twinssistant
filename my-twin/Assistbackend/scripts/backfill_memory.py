"""One-off: index existing Firestore history into long-term memory (README1 section 11.7).

Usage (from Assistbackend/):
    venv312/bin/python scripts/backfill_memory.py <firebase_uid> [conversation_id ...]

With no conversation ids it backfills user_<uid> and imported_conv_1 (the history
migrated from chat_history.txt). Costs a few pence of Haiku + embeddings per
hundred exchanges.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    user_id = sys.argv[1]
    conv_ids = sys.argv[2:] or [f"user_{user_id}", "imported_conv_1"]
    for conv_id in conv_ids:
        memory.backfill(user_id, conv_id)
    print("Backfill complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Ankivert minimal main.py

- Reads Markdown from an Obsidian vault (anywhere on disk).
- Extracts Q:: / A:: cards.
- Sends to Anki via AnkiConnect (http://127.0.0.1:8765).
- Creates decks automatically.
- Avoids duplicates by tagging each note with a stable ID and updating if it already exists.

Usage:
  python main.py scan
  python main.py sync
  python main.py sync --dry-run
  python main.py sync --classes math250 phys202
  python main.py sync --vault ~/Documents/Obsidian_vault/obsidian/101_CerritosCollege/03_sp26
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests


ANKI_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_VERSION = 6

DEFAULT_VAULT = Path(
    "~/Documents/Obsidian_vault/Obsidian/101_CerritosCollege/03_sp26"
).expanduser()

DEFAULT_CLASSES = ["math250", "cis292", "phys202", "hist103"]


@dataclass(frozen=True)
class Card:
    deck: str
    front: str
    back: str
    tags: list[str]
    stable_tag: str  # used for dedupe/update


def ankiconnect(action: str, params: dict | None = None):
    payload = {
        "action": action,
        "version": ANKI_CONNECT_VERSION,
        "params": params or {},
    }
    r = requests.post(ANKI_URL, json=payload, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error for {action}: {data['error']}")
    return data.get("result")


def ensure_deck(deck_name: str) -> None:
    # createDeck is safe to call even if it already exists
    ankiconnect("createDeck", {"deck": deck_name})


def stable_id_tag(vault_root: Path, md_path: Path, question: str, ordinal: int) -> str:
    """
    Create a stable tag for a card so re-running updates instead of duplicating.

    We use:
      - path relative to vault root (stable even if your absolute path changes)
      - question text
      - ordinal within file (handles multiple Q:: in same file)
    """
    rel = md_path.relative_to(vault_root).as_posix()
    raw = f"{rel}||{ordinal}||{question}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()  # stable, short enough
    return f"ankivert_id_{digest[:12]}"


def extract_cards_from_markdown(
    vault_root: Path,
    md_path: Path,
    deck: str,
    base_tags: list[str],
) -> list[Card]:
    """
    Card syntax supported:
      Q:: <question>
      A:: <answer begins>  (answer may continue on subsequent lines)
    """
    text = md_path.read_text(encoding="utf-8", errors="replace")

    cards: list[Card] = []
    q: str | None = None
    a_lines: list[str] = []
    in_answer = False
    ordinal = 0

    for raw in text.splitlines():
        line = raw.rstrip("\n")

        if line.startswith("Q::"):
            # flush previous complete card
            if q is not None and a_lines:
                tag = stable_id_tag(vault_root, md_path, q, ordinal)
                cards.append(
                    Card(
                        deck=deck,
                        front=q,
                        back="\n".join(a_lines).strip(),
                        tags=base_tags + [tag],
                        stable_tag=tag,
                    )
                )

            ordinal += 1
            q = line[len("Q::") :].strip()
            a_lines = []
            in_answer = False
            continue

        if line.startswith("A::") and q is not None:
            in_answer = True
            rest = line[len("A::") :].lstrip()
            if rest:
                a_lines.append(rest)
            continue

        if in_answer and q is not None:
            a_lines.append(line)

    # flush at EOF
    if q is not None and a_lines:
        tag = stable_id_tag(vault_root, md_path, q, ordinal)
        cards.append(
            Card(
                deck=deck,
                front=q,
                back="\n".join(a_lines).strip(),
                tags=base_tags + [tag],
                stable_tag=tag,
            )
        )

    return cards


def iter_md_files(vault: Path, class_names: list[str]) -> Iterable[tuple[str, Path]]:
    for cls in class_names:
        cls_dir = vault / cls
        if not cls_dir.exists():
            print(f"[warn] Missing class dir: {cls_dir}", file=sys.stderr)
            continue
        for p in sorted(cls_dir.rglob("*.md")):
            yield cls, p


def find_note_id_by_tag(tag: str) -> int | None:
    # Find notes with that tag. If multiple, we just use the first.
    note_ids = ankiconnect("findNotes", {"query": f"tag:{tag}"}) or []
    if not note_ids:
        return None
    return int(note_ids[0])


def add_or_update_basic_note(card: Card, dry_run: bool = False) -> None:
    """
    Uses the built-in 'Basic' note type (Front/Back).
    Update if tag already exists; otherwise add.
    """
    existing_id = None if dry_run else find_note_id_by_tag(card.stable_tag)

    if existing_id is None:
        if dry_run:
            print(f"[dry-run] addNote -> {card.deck} [{card.stable_tag}] {card.front[:60]!r}")
            return

        result = ankiconnect(
            "addNote",
            {
                "note": {
                    "deckName": card.deck,
                    "modelName": "Basic",
                    "fields": {"Front": card.front, "Back": card.back},
                    "tags": card.tags,
                }
            },
        )
        print(f"[add] note_id={result} deck={card.deck} tag={card.stable_tag}")
    else:
        if dry_run:
            print(f"[dry-run] updateNoteFields -> note_id={existing_id} [{card.stable_tag}]")
            return

        ankiconnect(
            "updateNoteFields",
            {
                "note": {
                    "id": existing_id,
                    "fields": {"Front": card.front, "Back": card.back},
                }
            },
        )
        # Ensure tag exists (in case tags changed)
        ankiconnect("addTags", {"notes": [existing_id], "tags": " ".join(card.tags)})
        print(f"[upd] note_id={existing_id} deck={card.deck} tag={card.stable_tag}")


def build_deck_name(vault: Path, class_name: str) -> str:
    # term folder name becomes the parent deck (e.g., "03_sp26")
    term = vault.name
    return f"{term}::{class_name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["scan", "sync"])
    ap.add_argument("--vault", type=str, default=str(DEFAULT_VAULT))
    ap.add_argument("--classes", nargs="*", default=DEFAULT_CLASSES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.exists():
        print(f"[error] Vault path not found: {vault}", file=sys.stderr)
        return 2

    # Collect cards
    all_cards: list[Card] = []

    for cls, md_path in iter_md_files(vault, list(args.classes)):
        deck = build_deck_name(vault, cls)
        base_tags = [cls, vault.name]  # simple defaults: "math250", "03_sp26"
        cards = extract_cards_from_markdown(vault, md_path, deck, base_tags)
        if args.command == "scan":
            if cards:
                rel = md_path.relative_to(vault).as_posix()
                print(f"\n{deck} :: {rel}  -> {len(cards)} card(s)")
                for c in cards:
                    print(f"  - {c.front[:70]!r}  [{c.stable_tag}]")
        all_cards.extend(cards)

    print(f"\nTotal cards found: {len(all_cards)}")

    if args.command == "scan":
        return 0

    # sync
    # Create decks first (one call per unique deck)
    decks = sorted({c.deck for c in all_cards})
    if not args.dry_run:
        for d in decks:
            ensure_deck(d)

    for c in all_cards:
        add_or_update_basic_note(c, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

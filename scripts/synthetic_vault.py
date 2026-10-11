from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def generate_vault(target: Path, notes: int = 500, seed: int = 7) -> None:
    """Generate deterministic Markdown files in a new or empty directory."""
    if notes < 0:
        raise ValueError("notes must be nonnegative")
    target = target.resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("target must be a new or empty directory")
    target.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    for index in range(notes):
        name = f"note-{index:05d}"
        # A ring keeps every note available in the default connected-only graph.
        links = {(index + 1) % notes} if notes > 1 else set()
        for _ in range(rng.randint(1, 4)):
            candidate = rng.randrange(notes)
            if candidate != index:
                links.add(candidate)
        meta = {"title": f"Synthetic note {index:05d}", "kind": "fact" if index % 4 == 0 else "note",
                "project": f"project-{index % 5}", "visibility": "public"}
        body = "\n".join(f"[[note-{other:05d}]]" for other in sorted(links))
        text = f"---\n{json.dumps(meta, ensure_ascii=False, sort_keys=True)}\n---\n\n# {meta['title']}\n\n{body}\n"
        # Exclusive creation also refuses to overwrite a file introduced during generation.
        with (target / f"{name}.md").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic synthetic Markdown vault.")
    parser.add_argument("target", type=Path)
    parser.add_argument("--notes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    try:
        generate_vault(args.target, args.notes, args.seed)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

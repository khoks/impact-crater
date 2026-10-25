"""Regenerate project/BOARD.md from the work-item frontmatter under project/.

The board is a mirror of the files; the files win. This script keeps the
hand-written narrative header (everything above the first "## " heading) and
rewrites every table below it from frontmatter + activity logs, then appends
a status tally so drift is checkable.

    python scripts/tracker_board.py            # rewrite project/BOARD.md
    python scripts/tracker_board.py --check    # exit 1 if BOARD.md is stale
    python scripts/tracker_board.py --tally    # print the status tally only

Placement rules (see project/README.md):
  In Progress   status in-progress
  Up Next       status todo and (phase in {mvp, mvp-hardening} or tag plan-phase-0/1)
  Backlog       status backlog/deferred/blocked, or todo tagged plan-phase-2/3
  Future        everything else still open, summarised per epic
  Recently Done status done with a done date on/after RECENT_CUTOFF
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
BOARD = PROJECT / "BOARD.md"
LEVELS = ("initiatives", "epics", "stories", "tasks")
TYPE_LABEL = {"initiative": "Initiative", "epic": "Epic", "story": "Story", "task": "Task"}
TYPE_ORDER = {"initiative": 0, "epic": 1, "story": 2, "task": 3}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
RECENT_CUTOFF = "2026-06-11"
CURRENT_PHASES = {"mvp", "mvp-hardening"}
DATE_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) — (.*)$")
DONE_WORD = re.compile(r"(^|[^a-z-])(done|shipped|closed|passed|merged)([^a-z-]|$)", re.I)
NOT_DONE = re.compile(r"(not done|reopen|code-done →|→ in-progress|→ todo|status → todo)", re.I)


@dataclass
class Item:
    id: str
    title: str
    type: str
    status: str
    priority: str
    phase: str
    parent: str | None
    tags: list[str]
    updated: str
    path: Path
    log: list[tuple[str, str]] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return "./" + self.path.relative_to(PROJECT).as_posix()

    @property
    def link(self) -> str:
        return f"[{self.id}]({self.rel})"

    @property
    def plan_phases(self) -> set[int]:
        out: set[int] = set()
        for t in self.tags:
            m = re.fullmatch(r"plan-phase-(\d)", t)
            if m:
                out.add(int(m.group(1)))
        return out

    @property
    def done_date(self) -> str:
        for date, text in self.log:
            if DONE_WORD.search(text) and not NOT_DONE.search(text):
                return date
        return self.updated

    def sort_key(self) -> tuple[int, int, tuple[int, ...]]:
        return (PRIORITY_ORDER.get(self.priority, 9), TYPE_ORDER.get(self.type, 9), id_key(self.id))


def id_key(item_id: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", item_id))


def parse_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("missing frontmatter")
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.split(" #", 1)[0].strip()
    return fm


def parse_tags(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]


def load_items() -> dict[str, Item]:
    items: dict[str, Item] = {}
    for level in LEVELS:
        for path in sorted((PROJECT / level).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            log: list[tuple[str, str]] = []
            in_log = False
            for line in text.splitlines():
                if line.startswith("## "):
                    in_log = line.strip().lower() == "## activity log"
                    continue
                if in_log:
                    m = DATE_LINE.match(line)
                    if m:
                        log.append((m.group(1), m.group(2)))
            item = Item(
                id=fm["id"], title=fm.get("title", "").strip(), type=fm.get("type", level[:-1]),
                status=fm.get("status", "?"), priority=fm.get("priority", "P3"), phase=fm.get("phase", "?"),
                parent=fm.get("parent") or None, tags=parse_tags(fm.get("tags", "")),
                updated=fm.get("updated", ""), path=path, log=log,
            )
            if item.id in items:
                raise ValueError(f"duplicate id {item.id}: {path} and {items[item.id].path}")
            items[item.id] = item
    return items


def table(rows: list[list[str]], header: list[str]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def plan_tag(item: Item) -> str:
    return ", ".join(f"plan-phase-{n}" for n in sorted(item.plan_phases))


def open_row(i: Item) -> list[str]:
    extra = plan_tag(i)
    title = i.title + (f" ({extra})" if extra else "")
    return [i.link, title, TYPE_LABEL.get(i.type, i.type), i.priority, i.phase, i.status]


def done_row(i: Item) -> list[str]:
    return [i.link, i.title, TYPE_LABEL.get(i.type, i.type), i.done_date]


def render_sections(items: dict[str, Item]) -> str:
    by_id = items
    in_progress = sorted((i for i in items.values() if i.status == "in-progress"), key=Item.sort_key)
    up_next = sorted(
        (i for i in items.values() if i.status == "todo"
         and (i.phase in CURRENT_PHASES or i.plan_phases & {0, 1})),
        key=Item.sort_key,
    )
    backlog = sorted(
        (i for i in items.values() if i.type != "initiative" and (
            i.status in {"backlog", "deferred", "blocked"}
            or (i.status == "todo" and i.plan_phases & {2, 3} and i not in up_next))),
        key=Item.sort_key,
    )
    surfaced = {i.id for i in in_progress} | {i.id for i in up_next} | {i.id for i in backlog}
    future_open = [i for i in items.values() if i.status in {"todo", "backlog", "deferred", "blocked"}
                   and i.id not in surfaced and i.type in {"story", "task"}]
    future_by_epic: dict[str, list[Item]] = defaultdict(list)
    for i in future_open:
        future_by_epic[i.parent or "?"].append(i)

    recent_done = sorted((i for i in items.values() if i.status == "done" and i.done_date >= RECENT_CUTOFF),
                         key=lambda i: (i.done_date, TYPE_ORDER.get(i.type, 9), id_key(i.id)), reverse=True)
    older_done_epics = sorted((i for i in items.values() if i.status == "done" and i.type == "epic"
                               and i.done_date < RECENT_CUTOFF), key=lambda i: (i.done_date, id_key(i.id)), reverse=True)
    canceled = sorted((i for i in items.values() if i.status == "canceled"), key=lambda i: id_key(i.id))

    parts: list[str] = []
    parts.append("## In Progress\n\n" + table([open_row(i) for i in in_progress],
                 ["ID", "Title", "Type", "Priority", "Phase", "Status"]))
    parts.append("## Up Next (Ready)\n\n" + table([open_row(i) for i in up_next],
                 ["ID", "Title", "Type", "Priority", "Phase", "Status"]))
    parts.append("## Backlog (queued)\n\n" + table([open_row(i) for i in backlog],
                 ["ID", "Title", "Type", "Priority", "Phase", "Status"]))

    future_rows = []
    for epic_id in sorted(future_by_epic, key=id_key):
        children = future_by_epic[epic_id]
        epic = by_id.get(epic_id)
        counts = Counter(c.status for c in children)
        ids = ", ".join(c.id for c in sorted(children, key=lambda c: id_key(c.id)))
        future_rows.append([
            epic.link if epic else epic_id, epic.title if epic else "?", epic.phase if epic else "?",
            epic.status if epic else "?", ", ".join(f"{n} {s}" for s, n in sorted(counts.items())), ids,
        ])
    parts.append("## Future phases (open, not yet scheduled)\n\n"
                 "Placeholder stories backfilled on 2026-06-14 plus later filings whose restart-plan phase is 4 or later. "
                 "They open when their epic opens.\n\n"
                 + table(future_rows, ["Epic", "Title", "Phase", "Epic status", "Open children", "IDs"]))

    parts.append(f"## Recently Done (since {RECENT_CUTOFF})\n\n" + table([done_row(i) for i in recent_done],
                 ["ID", "Title", "Type", "Done"]))

    older_rows = []
    for e in older_done_epics:
        kids = sorted((i for i in items.values() if i.parent == e.id and i.status == "done"), key=lambda i: id_key(i.id))
        span = f"{kids[0].id}..{kids[-1].id.split('.')[-1]} ({len(kids)} stories)" if kids else "delivered epic-level, no stories"
        older_rows.append([e.link, e.title, span, e.done_date])
    parts.append("## Previously Done\n\n" + table(older_rows, ["Epic", "Title", "Stories", "Done"]))

    if canceled:
        parts.append("## Canceled\n\n" + table([[i.link, i.title, TYPE_LABEL.get(i.type, i.type), i.updated] for i in canceled],
                     ["ID", "Title", "Type", "Canceled"]))

    init_rows = []
    for init in sorted((i for i in items.values() if i.type == "initiative"), key=lambda i: id_key(i.id)):
        epics = sorted((i for i in items.values() if i.parent == init.id), key=lambda i: id_key(i.id))
        counts = Counter(e.status for e in epics)
        init_rows.append([init.link, init.title, init.status, init.phase,
                          f"{len(epics)} epics: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))])
    parts.append("## Initiative index\n\n" + table(init_rows, ["ID", "Title", "Status", "Phase", "Epics"]))

    tally = Counter((i.type, i.status) for i in items.values())
    statuses = sorted({s for _, s in tally})
    tally_rows = []
    for t in ("initiative", "epic", "story", "task"):
        row = [TYPE_LABEL[t]] + [str(tally.get((t, s), 0)) for s in statuses]
        row.append(str(sum(tally.get((t, s), 0) for s in statuses)))
        tally_rows.append(row)
    tally_rows.append(["**All**"] + [str(sum(tally.get((t, s), 0) for t in TYPE_ORDER)) for s in statuses] + [str(len(items))])
    parts.append("## Status tally (from frontmatter)\n\nRegenerate with `python scripts/tracker_board.py`; "
                 "`--check` fails when this file drifts from the item files.\n\n"
                 + table(tally_rows, ["Type", *statuses, "Total"]))
    return "\n\n".join(parts) + "\n"


def render_board(items: dict[str, Item]) -> str:
    current = BOARD.read_text(encoding="utf-8")
    head, sep, _ = current.partition("\n## ")
    if not sep:
        raise ValueError("BOARD.md has no '## ' section to anchor the generated part")
    return head.rstrip() + "\n\n" + render_sections(items)


def main(argv: list[str]) -> int:
    items = load_items()
    if "--tally" in argv:
        tally = Counter(i.status for i in items.values())
        for status, n in sorted(tally.items()):
            print(f"{n:4d} {status}")
        print(f"{len(items):4d} total")
        return 0
    new = render_board(items)
    if "--check" in argv:
        if BOARD.read_text(encoding="utf-8") == new:
            print("BOARD.md is up to date")
            return 0
        print("BOARD.md is stale; run scripts/tracker_board.py")
        return 1
    BOARD.write_text(new, encoding="utf-8", newline="\n")
    print(f"BOARD.md regenerated from {len(items)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Storage layer per ADR-0006.

Modules:
  - paths      — filesystem path resolution (~/.impact-crater/ or override)
  - db         — aiosqlite connection helpers
  - migrations — schema-migration runner
  - settings   — typed read/write of the SQLite settings table

Full implementations land in S-2.1.3.
"""

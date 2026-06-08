# Schema Folder for Web-Scraper-v1 / scrapehound

Generated: 2026-06-08

This folder contains simple schema files for the `scrapehound` repository. The goal is to document the major data contracts without making the project heavier than it needs to be.

## Files

| File | Purpose |
| --- | --- |
| `database.schema.sql` | SQLite schema copied into a standalone schema file. |
| `database.schema.md` | Human-readable explanation of the SQLite tables and relationships. |
| `export.schema.json` | JSON Schema for `scrapehound export --format json`. |
| `stats.schema.json` | JSON Schema for `scrapehound stats`. |
| `crawl-summary.schema.json` | Structured schema for the crawl/resume summary object. |
| `fetch-result.schema.json` | JSON-safe schema for a fetch result. |
| `timing-breakdown.schema.json` | Timing object used by fetch/export outputs. |
| `robots-result.schema.json` | JSON Schema for `scrapehound robots`. |
| `crawl-options.schema.json` | Normalized configuration/options schema. |
| `cli-contract.schema.json` | Schema for documenting the CLI command surface. |
| `cli-contract.example.json` | Concrete CLI command metadata that conforms to `cli-contract.schema.json`. |
| `schema-manifest.json` | Machine-readable index of the schema package. |

## Notes

- These schemas are intentionally simple and capstone-friendly.
- The database schema mirrors the repository's SQLite persistence model.
- JSON schemas use JSON Schema Draft 2020-12.
- `fetch-result.schema.json` stores response bytes as `body_base64` because raw Python `bytes` are not directly JSON serializable.
- SQLite timestamps are documented as strings because the app uses SQLite `datetime('now')`, which does not include an explicit timezone suffix.

## Suggested Repository Placement

Copy this folder into the repository root:

```text
Web-Scraper-v1/
  Schema/
    README.md
    database.schema.sql
    database.schema.md
    export.schema.json
    stats.schema.json
    crawl-summary.schema.json
    fetch-result.schema.json
    timing-breakdown.schema.json
    robots-result.schema.json
    crawl-options.schema.json
    cli-contract.schema.json
    cli-contract.example.json
    schema-manifest.json
```

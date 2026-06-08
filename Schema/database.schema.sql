PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crawl_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seed_url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  max_pages INTEGER NOT NULL,
  max_depth INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS frontier (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  normalized_url TEXT NOT NULL,
  depth INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'fetched', 'skipped', 'failed', 'retry_scheduled')),
  discovered_from TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  next_fetch_at REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(job_id, normalized_url)
);

CREATE INDEX IF NOT EXISTS idx_frontier_job_status_next
ON frontier(job_id, status, next_fetch_at, depth, id);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  final_url TEXT NOT NULL,
  normalized_url TEXT NOT NULL,
  status_code INTEGER NOT NULL,
  content_type TEXT,
  title TEXT,
  description TEXT,
  headings_json TEXT NOT NULL DEFAULT '[]',
  links_json TEXT NOT NULL DEFAULT '[]',
  body_sha256 TEXT NOT NULL,
  body_text TEXT,
  text_encoding TEXT,
  timing_json TEXT NOT NULL DEFAULT '{}',
  transport TEXT NOT NULL,
  depth INTEGER NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(job_id, normalized_url)
);

CREATE TABLE IF NOT EXISTS failures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  normalized_url TEXT,
  category TEXT NOT NULL,
  message TEXT,
  status_code INTEGER,
  retry_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_failures_job ON failures(job_id);

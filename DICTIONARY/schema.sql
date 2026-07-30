-- Simlish lyric dictionary schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS songs (
  song_id TEXT PRIMARY KEY,
  artist TEXT NOT NULL,
  title TEXT NOT NULL,
  game_section TEXT,
  pack TEXT,
  station TEXT,
  notes TEXT,
  has_real_world_original INTEGER NOT NULL DEFAULT 1,
  skip_reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lyric_documents (
  doc_id INTEGER PRIMARY KEY,
  song_id TEXT NOT NULL REFERENCES songs(song_id),
  side TEXT NOT NULL CHECK(side IN ('original','simlish')),
  source_kind TEXT NOT NULL,
  language TEXT,
  text TEXT NOT NULL,
  source_url TEXT,
  confidence REAL,
  retrieved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS line_pairs (
  pair_id INTEGER PRIMARY KEY,
  song_id TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  original_line TEXT NOT NULL,
  simlish_line TEXT NOT NULL,
  align_method TEXT NOT NULL,
  UNIQUE(song_id, line_index)
);

CREATE TABLE IF NOT EXISTS word_alignments (
  alignment_id INTEGER PRIMARY KEY,
  song_id TEXT NOT NULL,
  pair_id INTEGER REFERENCES line_pairs(pair_id),
  original_word TEXT NOT NULL,
  original_norm TEXT NOT NULL,
  simlish_word TEXT NOT NULL,
  simlish_norm TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS dictionary (
  original_word TEXT NOT NULL,
  simlish_1 TEXT NOT NULL,
  simlish_2 TEXT,
  simlish_3 TEXT,
  simlish_4 TEXT,
  simlish_5 TEXT,
  simlish_6 TEXT,
  simlish_7 TEXT,
  simlish_8 TEXT,
  simlish_9 TEXT,
  simlish_10 TEXT,
  simlish_extra TEXT,
  occurrence_count INTEGER NOT NULL,
  PRIMARY KEY (original_word)
);

CREATE INDEX IF NOT EXISTS idx_align_orig ON word_alignments(original_norm);
CREATE INDEX IF NOT EXISTS idx_align_sim ON word_alignments(simlish_norm);
CREATE INDEX IF NOT EXISTS idx_docs_song ON lyric_documents(song_id, side);

CREATE VIEW IF NOT EXISTS v_dictionary_stats AS
  SELECT COUNT(*) AS entries,
         SUM(CASE WHEN simlish_2 IS NOT NULL THEN 1 ELSE 0 END) AS multi_form_entries
  FROM dictionary;

"""Local knowledge: documents chunked and indexed for lexical retrieval (spec §45).

Retrieval is BM25 over SQLite FTS5. It is fast, private and works offline, and it is
*lexical*: it finds passages that share words with the question. Semantic (embedding)
retrieval is a planned upgrade and will be presented as such, not silently assumed.
"""

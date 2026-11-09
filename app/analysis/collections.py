"""Chroma collection names.

Kept free of chromadb imports so the web service can name collections (admin
status) without loading the vector store client at startup.
"""

TAXONOMY_COLLECTION_NAME = "hate_speech_taxonomy"
AUTHORITATIVE_COLLECTION_NAME = "hate_speech_authoritative"
EXAMPLE_COLLECTION_NAME = "hate_speech_examples"

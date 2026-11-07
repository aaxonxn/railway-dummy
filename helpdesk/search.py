"""Hybrid search engine combining BM25, dense semantic retrieval (FAISS), and reciprocal rank fusion."""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from helpdesk.chunking import Chunk
from helpdesk.config import config
from helpdesk.logging_config import logger
from helpdesk.reranker import PrecisionReranker
from helpdesk.utils import CustomJSONEncoder

# Lazy loader for SentenceTransformer to optimize startup time
_EMBEDDING_MODEL = None


def get_embedding_model():
    """Retrieve or initialize SentenceTransformer model."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        # Check if local model snapshot path exists
        model_path = config.local_model_path
        if model_path and Path(model_path).exists():
            logger.info("Loading SentenceTransformer from local path: %s", model_path)
            _EMBEDDING_MODEL = SentenceTransformer(model_path)
        else:
            logger.info("Loading SentenceTransformer: %s", config.embedding_model_name)
            _EMBEDDING_MODEL = SentenceTransformer(config.embedding_model_name)
    return _EMBEDDING_MODEL


def tokenize_for_bm25(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    import re
    tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
    return tokens


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file for change detection."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class HybridSearcher:
    """Hybrid search system combining FAISS dense vector search and BM25Okapi keyword search."""

    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = index_dir or config.index_dir
        self.chunks: List[Chunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.faiss_index: Optional[faiss.IndexFlatIP] = None
        self.embeddings: Optional[np.ndarray] = None
        self.reranker = PrecisionReranker()

    def build_index(self, chunks: List[Chunk], force: bool = False) -> None:
        """Build and persist BM25, vector embeddings, FAISS index, and manifest."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.chunks = chunks

        logger.info("Building hybrid index for %d chunks...", len(chunks))

        # 1. Build BM25 index
        tokenized_corpus = [tokenize_for_bm25(f"{c.title} {c.text}") for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 2. Build dense embeddings
        model = get_embedding_model()
        texts_to_embed = [
            f"Title: {c.title}. Document: {c.doc_name}. Content: {c.text}"
            for c in chunks
        ]
        logger.info("Computing dense embeddings for %d chunks...", len(texts_to_embed))
        embeddings = model.encode(texts_to_embed, show_progress_bar=False, convert_to_numpy=True)
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        self.embeddings = embeddings

        # 3. Build FAISS index (Inner Product on L2-normalized vectors is Cosine Similarity)
        dimension = embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(dimension)
        self.faiss_index.add(embeddings)

        # 4. Save index files to disk
        self.save_index()
        logger.info("Hybrid index successfully built and saved to %s", self.index_dir)

    def save_index(self) -> None:
        """Persist chunks, FAISS index, embeddings, and manifest to disk."""
        # Save chunks
        chunks_file = self.index_dir / "chunks.json"
        with open(chunks_file, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in self.chunks], f, cls=CustomJSONEncoder, indent=2)

        # Save embeddings
        embeddings_file = self.index_dir / "embeddings.npy"
        np.save(str(embeddings_file), self.embeddings)

        # Save FAISS index
        faiss_file = self.index_dir / "faiss.index"
        faiss.write_index(self.faiss_index, str(faiss_file))

        # Save metadata
        metadata = {
            "chunk_count": len(self.chunks),
            "doc_names": sorted(list({c.doc_name for c in self.chunks})),
            "embedding_dimension": int(self.embeddings.shape[1]),
            "model_name": config.embedding_model_name,
        }
        with open(self.index_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Save manifest of document hashes
        manifest = {}
        if config.documents_dir.exists():
            for f in sorted(config.documents_dir.iterdir()):
                if f.is_file():
                    manifest[f.name] = {
                        "size": f.stat().st_size,
                        "sha256": compute_file_hash(f),
                    }
        with open(self.index_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def load_index(self) -> bool:
        """Load persisted index files into memory."""
        chunks_file = self.index_dir / "chunks.json"
        embeddings_file = self.index_dir / "embeddings.npy"
        faiss_file = self.index_dir / "faiss.index"

        if not (chunks_file.exists() and embeddings_file.exists() and faiss_file.exists()):
            logger.warning("Index files missing in %s", self.index_dir)
            return False

        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                raw_chunks = json.load(f)
            self.chunks = [Chunk(**d) for d in raw_chunks]

            # Reconstruct BM25
            tokenized_corpus = [tokenize_for_bm25(f"{c.title} {c.text}") for c in self.chunks]
            self.bm25 = BM25Okapi(tokenized_corpus)

            # Load embeddings and FAISS
            self.embeddings = np.load(str(embeddings_file))
            self.faiss_index = faiss.read_index(str(faiss_file))

            logger.info("Successfully loaded hybrid index with %d chunks.", len(self.chunks))
            return True
        except Exception as e:
            logger.error("Failed to load hybrid index: %s", e)
            return False

    def is_index_valid(self) -> bool:
        """Check whether the persisted index is valid and up to date with source documents."""
        manifest_file = self.index_dir / "manifest.json"
        chunks_file = self.index_dir / "chunks.json"
        if not (manifest_file.exists() and chunks_file.exists()):
            return False

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                saved_manifest = json.load(f)

            if not config.documents_dir.exists():
                return True

            current_files = {f.name for f in config.documents_dir.iterdir() if f.is_file()}
            if set(saved_manifest.keys()) != current_files:
                return False

            for f_name, f_info in saved_manifest.items():
                f_path = config.documents_dir / f_name
                if not f_path.exists():
                    return False
                if f_path.stat().st_size != f_info["size"]:
                    return False
                if compute_file_hash(f_path) != f_info["sha256"]:
                    return False

            return True
        except Exception:
            return False

    def search(self, query: str, top_k: int = 5, use_reranker: bool = True) -> List[Tuple[Chunk, float]]:
        """
        Execute hybrid search using Reciprocal Rank Fusion (RRF) between Dense and BM25 retrieval.
        Optionally applies precision reranking.
        """
        if not self.chunks or self.bm25 is None or self.faiss_index is None:
            if not self.load_index():
                raise RuntimeError("Hybrid index is not loaded and could not be found.")

        k_candidates = max(top_k * 3, 20)

        # 1. Dense retrieval
        model = get_embedding_model()
        query_emb = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
        faiss.normalize_L2(query_emb)
        dense_distances, dense_indices = self.faiss_index.search(query_emb, k_candidates)

        dense_ranks: Dict[int, int] = {}
        for rank, idx in enumerate(dense_indices[0]):
            if idx >= 0:
                dense_ranks[idx] = rank

        # 2. BM25 retrieval
        q_tokens = tokenize_for_bm25(query)
        bm25_scores = self.bm25.get_scores(q_tokens)
        bm25_indices = np.argsort(bm25_scores)[::-1][:k_candidates]

        bm25_ranks: Dict[int, int] = {}
        for rank, idx in enumerate(bm25_indices):
            bm25_ranks[idx] = rank

        # 3. Reciprocal Rank Fusion (RRF)
        all_candidate_indices = set(dense_ranks.keys()).union(set(bm25_ranks.keys()))
        rrf_k = config.rrf_k
        w_dense = config.dense_weight
        w_bm25 = config.bm25_weight

        scored_candidates: List[Tuple[Chunk, float]] = []
        for idx in all_candidate_indices:
            score = 0.0
            if idx in dense_ranks:
                score += w_dense * (1.0 / (rrf_k + dense_ranks[idx]))
            if idx in bm25_ranks:
                score += w_bm25 * (1.0 / (rrf_k + bm25_ranks[idx]))

            scored_candidates.append((self.chunks[idx], score))

        # Sort by initial RRF score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 4. Optional Precision Reranking
        if use_reranker:
            return self.reranker.rerank(query, scored_candidates[:k_candidates], top_k=top_k)
        else:
            return scored_candidates[:top_k]


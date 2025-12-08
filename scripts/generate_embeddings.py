#!/usr/bin/env python3
"""
Generate and store document embeddings for paper abstracts.

This script:
1. Checks for/downloads required models to data/models/
2. Loads papers without embeddings (incremental by default)
3. Generates embeddings in batches using PubMedBERT
4. Stores embeddings in SQLite paper_embeddings table
5. Builds FAISS index and saves .npy files for fast access

Usage:
    python scripts/generate_embeddings.py           # Incremental (only new papers)
    python scripts/generate_embeddings.py --force   # Regenerate all embeddings

Model:
    pritamdeka/S-PubMedBert-MS-MARCO (768-dim)
    - PubMedBERT fine-tuned on MS-MARCO retrieval task
    - Optimized for biomedical semantic search
    - Deterministic: same input always produces same embedding

Outputs:
    - SQLite: paper_embeddings table (source of truth)
    - data/embeddings/embeddings.npy (N, 768) full embedding matrix
    - data/embeddings/pmids.npy (N,) PMID index mapping
    - data/embeddings/faiss_index.bin FAISS index for similarity search
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data/raw/subiculum_literature.db"
MODEL_DIR = PROJECT_ROOT / "data/models/sentence-transformers"
EMBEDDING_DIR = PROJECT_ROOT / "data/embeddings"

# Model configuration
MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"
BATCH_SIZE = 32


def ensure_model_downloaded():
    """
    Download model to local cache if not present.

    Returns local path if cached, model name otherwise.
    sentence-transformers will auto-download to cache_folder if not found.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Check if already cached
    model_cache_name = MODEL_NAME.replace("/", "_")
    model_path = MODEL_DIR / model_cache_name

    if model_path.exists():
        print(f"✓ Model found in cache: {model_path}")
        return str(model_path)

    print(f"Model not found in cache. Downloading {MODEL_NAME}...")
    print(f"This is a one-time download (~420 MB)")

    # Download to our cache directory
    model = SentenceTransformer(MODEL_NAME, cache_folder=str(MODEL_DIR))
    print(f"✓ Model downloaded and cached at: {MODEL_DIR}")

    return MODEL_NAME


def get_papers_without_embeddings(conn, force=False):
    """
    Get papers that need embeddings.
    Returns:
        List of (pmid, abstract) tuples
    """
    if force:
        print("Force mode: regenerating all embeddings")
        query = """
            SELECT pmid, abstract
            FROM papers
            WHERE abstract IS NOT NULL AND abstract != ''
        """
    else:
        query = """
            SELECT p.pmid, p.abstract
            FROM papers p
            LEFT JOIN paper_embeddings pe ON p.pmid = pe.pmid
            WHERE pe.pmid IS NULL
              AND p.abstract IS NOT NULL
              AND p.abstract != ''
        """

    cursor = conn.execute(query)
    papers = cursor.fetchall()
    return papers


def generate_embeddings(model, papers, batch_size=32):
    """
    Generate embeddings in batches.

    The model is deterministic - same abstract always produces same embedding.
    No random seed needed as there's no stochasticity in inference.

    Args:
        model: SentenceTransformer model
        papers: List of (pmid, abstract) tuples
        batch_size: Batch size for encoding

    Returns:
        pmids: List of PMIDs
        embeddings: NumPy array of embeddings (N, embedding_dim)
    """
    pmids = [p[0] for p in papers]
    abstracts = [p[1] for p in papers]

    print(f"Generating embeddings for {len(papers):,} papers...")
    print(f"Model: {MODEL_NAME}")
    print(f"Batch size: {batch_size}")

    # Generate embeddings with progress bar
    # normalize_embeddings=True ensures L2 norm = 1 (required for cosine similarity)
    embeddings = model.encode(
        abstracts,
        show_progress_bar=True,
        batch_size=batch_size,
        normalize_embeddings=True,  # L2 normalization for cosine similarity
        convert_to_numpy=True,
    )

    print(f"✓ Generated {len(embeddings):,} embeddings")
    print(f"  Shape: {embeddings.shape}")
    print(f"  Dtype: {embeddings.dtype}")

    return pmids, embeddings


def store_embeddings(conn, pmids, embeddings, model_name):
    """
    Store embeddings in database.

    Args:
        conn: SQLite connection
        pmids: List of PMIDs
        embeddings: NumPy array of embeddings
        model_name: Name of the model used
    """
    print("Storing embeddings in database...")

    embedding_dim = embeddings.shape[1]

    for pmid, emb in tqdm(zip(pmids, embeddings), total=len(pmids), desc="Inserting"):
        # Convert to float32 for storage efficiency
        emb_blob = emb.astype(np.float32).tobytes()

        conn.execute(
            """
            INSERT OR REPLACE INTO paper_embeddings
            (pmid, embedding, model_name, embedding_dim)
            VALUES (?, ?, ?, ?)
        """,
            (int(pmid), emb_blob, model_name, embedding_dim),
        )

    conn.commit()
    print(f"✓ Stored {len(pmids):,} embeddings in database")

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM paper_embeddings").fetchone()[0]
    print(f"✓ Total embeddings in database: {count:,}")


def build_faiss_index(conn):
    """
    Build FAISS index from all embeddings in database.

    This rebuilds the index from scratch using ALL embeddings in the DB.
    Called after adding new embeddings to include them in the index.

    Outputs:
        - data/embeddings/embeddings.npy: (N, 768) matrix
        - data/embeddings/pmids.npy: (N,) PMID index
        - data/embeddings/faiss_index.bin: FAISS index for similarity search
    """
    print("\nBuilding FAISS index from all embeddings in database...")

    cursor = conn.execute(
        """
        SELECT pmid, embedding, embedding_dim
        FROM paper_embeddings
        ORDER BY pmid
    """
    )

    pmids = []
    embeddings_list = []

    for pmid, emb_blob, dim in tqdm(cursor, desc="Loading embeddings"):
        pmids.append(pmid)
        # Reconstruct embedding from blob
        emb = np.frombuffer(emb_blob, dtype=np.float32).reshape(dim)
        embeddings_list.append(emb)

    if not embeddings_list:
        print("⚠ No embeddings found in database. Nothing to index.")
        return

    embeddings = np.vstack(embeddings_list)
    pmids = np.array(pmids, dtype=np.int64)

    print(f"✓ Loaded {len(embeddings):,} embeddings from database")
    print(f"  Shape: {embeddings.shape}")

    # Create FAISS index for cosine similarity
    # IndexFlatIP uses inner product, which equals cosine sim for normalized vectors
    embedding_dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(embedding_dim)

    # Add vectors to index
    index.add(embeddings)

    # Save outputs
    EMBEDDING_DIR.mkdir(parents=True, exist_ok=True)

    embeddings_path = EMBEDDING_DIR / "embeddings.npy"
    pmids_path = EMBEDDING_DIR / "pmids.npy"
    index_path = EMBEDDING_DIR / "faiss_index.bin"

    np.save(embeddings_path, embeddings)
    np.save(pmids_path, pmids)
    faiss.write_index(index, str(index_path))

    print(f"✓ FAISS index built with {len(pmids):,} vectors")
    print(f"✓ Saved outputs to: {EMBEDDING_DIR}")
    print(f"  - embeddings.npy ({embeddings.nbytes / 1024 / 1024:.1f} MB)")
    print(f"  - pmids.npy ({pmids.nbytes / 1024:.1f} KB)")
    print(f"  - faiss_index.bin")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--force", action="store_true", help="Regenerate all embeddings (not just new papers)"
    )
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size for encoding")
    args = parser.parse_args()

    print("=" * 80)
    print("Embedding Generation Pipeline")
    print("=" * 80)
    print()

    model_path = ensure_model_downloaded() # avail?
    print()

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(model_path if Path(model_path).exists() else MODEL_NAME)
    print(f"✓ Model loaded (embedding dimension: {model.get_sentence_embedding_dimension()})")
    print()

    conn = sqlite3.connect(DB_PATH)

    papers = get_papers_without_embeddings(conn, force=args.force)

    if not papers:
        print("✓ All papers already have embeddings")
        print()
    else:
        print(f"Found {len(papers):,} papers needing embeddings")
        print()

        pmids, embeddings = generate_embeddings(model, papers, args.batch_size)
        print()

        store_embeddings(conn, pmids, embeddings, MODEL_NAME)
        print()

    # Build/rebuild FAISS index from ALL embeddings in DB
    build_faiss_index(conn)

    conn.close()

    print()
    print("=" * 80)
    print("✓ Embedding pipeline complete")
    print("=" * 80)


if __name__ == "__main__":
    main()

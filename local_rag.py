# local_rag.py

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from math import isfinite

import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# Replace these imports with your project's implementations
from pdf_processor import PDFProcessor, get_pdf_files_recursive, get_organization_structure

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _safe_get_first(lst):
    """Chroma often returns nested lists for single-query responses."""
    if not lst:
        return []
    # if returned as [[...]] -> take first; if it's already flat -> return as-is
    return lst[0] if isinstance(lst[0], (list, tuple)) else lst


class MergedLocalRAG:
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        model_name: str = "all-MiniLM-L6-v2",
        embed_batch_size: int = 32,
        enable_bm25: bool = True,
    ):
        self.persist_directory = persist_directory
        self.model_name = model_name
        self.embed_batch_size = max(1, embed_batch_size)
        self.enable_bm25 = enable_bm25

        # Components
        self._initialize_chroma()
        self._initialize_embedder()
        self.pdf_processor = PDFProcessor()

        # BM25 structures
        self.bm25 = None
        self.bm25_corpus: List[str] = []
        self.bm25_metadata: List[Dict[str, Any]] = []

        logger.info(f"🚀 MergedLocalRAG initialized (model={model_name}, bm25={enable_bm25})")

    def _initialize_chroma(self):
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.client.get_or_create_collection(
                name="engineering_documents",
                metadata={"description": "Athena Knowledge Base"}
            )
            logger.info("✅ ChromaDB initialized")
        except Exception as e:
            logger.exception("❌ Failed to initialize ChromaDB")
            raise

    def _initialize_embedder(self):
        try:
            self.embedder = SentenceTransformer(self.model_name)
            logger.info(f"✅ Embedding model loaded: {self.model_name}")
        except Exception as e:
            logger.exception("❌ Failed to load embedding model")
            raise

    def _chunk_id(self, file_info: Dict[str, str], chunk: Dict[str, Any]) -> str:
        # deterministic id that avoids path separators
        base = f"{file_info.get('subject','unknown')}|{file_info.get('module','unknown')}|{os.path.basename(file_info.get('full_path','file'))}"
        return f"{base}|p{chunk.get('page_number',0)}|c{chunk.get('chunk_number',0)}"

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch embeddings to avoid memory spikes."""
        embeddings = []
        for i in range(0, len(texts), self.embed_batch_size):
            batch = texts[i:i + self.embed_batch_size]
            emb = self.embedder.encode(batch, show_progress_bar=False)
            # ensure list-of-lists
            emb_list = emb.tolist() if hasattr(emb, "tolist") else [list(e) for e in emb]
            embeddings.extend(emb_list)
        return embeddings

    def ingest_pdf(self, file_info: Dict[str, str], rebuild_bm25: bool = True) -> int:
        """Ingest one PDF (file_info must contain 'full_path', 'subject', 'module')."""
        try:
            file_path = file_info['full_path']
            chunks = self.pdf_processor.process_pdf(file_path)
            if not chunks:
                logger.warning(f"⚠️ No text extracted from {file_path}")
                return 0

            ids, documents, metadatas = [], [], []
            for chunk in chunks:
                ids.append(self._chunk_id(file_info, chunk))
                documents.append(chunk['text'])
                # normalize metadata keys
                md = {
                    'file_name': chunk.get('file_name', os.path.basename(file_path)),
                    'file_path': chunk.get('file_path', file_path),
                    'subject': file_info.get('subject'),
                    'module': file_info.get('module'),
                    'page_number': chunk.get('page_number'),
                    'chunk_number': chunk.get('chunk_number'),
                    'total_pages': chunk.get('total_pages', None)
                }
                metadatas.append(md)

            embeddings = self._embed_texts(documents)

            # add to collection
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )

            logger.info(f"✅ Added {len(chunks)} chunks from {file_info.get('full_path')}")
            if self.enable_bm25 and rebuild_bm25:
                self._rebuild_bm25_index()
            return len(chunks)

        except Exception as e:
            logger.exception(f"❌ Failed to ingest {file_info.get('full_path')}: {e}")
            return 0

    def ingest_directory(self, data_dir: str = "./data", rebuild_bm25: bool = True) -> Dict[str, Any]:
        pdf_files = get_pdf_files_recursive(data_dir)
        results = {'total_files': 0, 'total_chunks': 0, 'by_subject': {}, 'by_module': {}}

        if not pdf_files:
            logger.warning(f"📭 No PDFs found in {data_dir}")
            return results

        logger.info(f"📚 Processing {len(pdf_files)} PDF files from {data_dir}")
        for file_info in pdf_files:
            chunk_count = self.ingest_pdf(file_info, rebuild_bm25=False)
            results['total_files'] += 1
            results['total_chunks'] += chunk_count

            subject = file_info.get('subject', 'unknown')
            results['by_subject'].setdefault(subject, {'files': 0, 'chunks': 0})
            results['by_subject'][subject]['files'] += 1
            results['by_subject'][subject]['chunks'] += chunk_count

            module_key = f"{subject}/{file_info.get('module','unknown')}"
            results['by_module'].setdefault(module_key, {'files': 0, 'chunks': 0})
            results['by_module'][module_key]['files'] += 1
            results['by_module'][module_key]['chunks'] += chunk_count

        # rebuild BM25 once after directory ingestion
        if self.enable_bm25 and rebuild_bm25:
            self._rebuild_bm25_index()

        logger.info(f"🎉 Ingested {results['total_chunks']} chunks from {results['total_files']} files")
        return results

    def _rebuild_bm25_index(self):
        """Rebuild BM25 index from Chroma collection documents."""
        try:
            all_docs = self.collection.get(include=['documents', 'metadatas'])
            documents = _safe_get_first(all_docs.get('documents', []))
            metadatas = _safe_get_first(all_docs.get('metadatas', []))

            if not documents:
                logger.warning("No documents found for BM25 indexing")
                self.bm25 = None
                self.bm25_corpus = []
                self.bm25_metadata = []
                return

            tokenized = [doc.lower().split() for doc in documents]
            self.bm25 = BM25Okapi(tokenized)
            self.bm25_corpus = documents
            self.bm25_metadata = metadatas
            logger.info(f"✅ BM25 index built with {len(documents)} documents")
        except Exception as e:
            logger.exception(f"Failed to build BM25 index: {e}")
            self.bm25 = None

    def _normalize_similarity(self, distances: List[float]) -> List[float]:
        """Convert distances -> similarity (0..1) robustly."""
        sims = []
        # if distances are not finite, fallback to 0
        # We also handle case where smaller distance = more similar.
        max_d = max([d for d in distances if isfinite(d)] or [1.0])
        min_d = min([d for d in distances if isfinite(d)] or [0.0])
        denom = (max_d - min_d) if max_d != min_d else 1.0
        for d in distances:
            if not isfinite(d):
                sims.append(0.0)
            else:
                # similarity = 1 - (d - min)/(max-min) ; clipped to [0,1]
                val = 1.0 - ((d - min_d) / denom)
                sims.append(min(1.0, max(0.0, val)))
        return sims

    def hybrid_search(
        self,
        query: str,
        n_results: int = 10,
        subject_filter: Optional[str] = None,
        module_filter: Optional[str] = None,
        semantic_weight: float = 0.7
    ) -> Dict[str, Any]:
        """
        Hybrid search: combine semantic (vector) + keyword (BM25).
        Returns top n_results ranked by hybrid score.
        """
        try:
            # Semantic search
            query_emb = self._embed_texts([query])
            where_filter = {}
            if subject_filter: where_filter['subject'] = subject_filter
            if module_filter: where_filter['module'] = module_filter

            semantic_raw = self.collection.query(
                query_embeddings=query_emb,
                n_results=n_results * 3,
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"]
            )

            sem_docs = _safe_get_first(semantic_raw.get('documents', []))
            sem_mds = _safe_get_first(semantic_raw.get('metadatas', []))
            sem_dists = _safe_get_first(semantic_raw.get('distances', []))

            semantic_scores = self._normalize_similarity(sem_dists if sem_dists else [0.0] * len(sem_docs))

            combined = {}
            # add semantic candidates
            for doc, md, sscore in zip(sem_docs, sem_mds, semantic_scores):
                # build predictable id
                fid = f"{md.get('file_name','unk')}_p{md.get('page_number','0')}_c{md.get('chunk_number','0')}"
                combined[fid] = {
                    'document': doc,
                    'metadata': md,
                    'semantic_score': sscore,
                    'bm25_score': 0.0
                }

            # BM25 search
            if self.enable_bm25:
                if self.bm25 is None:
                    self._rebuild_bm25_index()
                if self.bm25:
                    tokenized_q = query.lower().split()
                    bm25_scores_raw = self.bm25.get_scores(tokenized_q)
                    # pair with metadata and apply filters
                    bm25_candidates = []
                    for idx, score in enumerate(bm25_scores_raw):
                        md = self.bm25_metadata[idx] if idx < len(self.bm25_metadata) else {}
                        if subject_filter and md.get('subject') != subject_filter:
                            continue
                        if module_filter and md.get('module') != module_filter:
                            continue
                        bm25_candidates.append({'idx': idx, 'score': score, 'meta': md, 'doc': self.bm25_corpus[idx]})
                    bm25_candidates.sort(key=lambda x: x['score'], reverse=True)
                    top_bm25 = bm25_candidates[:n_results * 3]

                    max_b = max([c['score'] for c in top_bm25], default=1.0)
                    for c in top_bm25:
                        md = c['meta']
                        doc_id = f"{md.get('file_name','unk')}_p{md.get('page_number','0')}_c{md.get('chunk_number','0')}"
                        normalized = (c['score'] / max_b) if max_b > 0 else 0.0
                        if doc_id in combined:
                            combined[doc_id]['bm25_score'] = normalized
                        else:
                            combined[doc_id] = {
                                'document': c['doc'],
                                'metadata': md,
                                'semantic_score': 0.0,
                                'bm25_score': normalized
                            }

            # compute hybrid score & sort
            for k, v in combined.items():
                v['hybrid_score'] = semantic_weight * v.get('semantic_score', 0.0) + (1 - semantic_weight) * v.get('bm25_score', 0.0)

            ranked = sorted(combined.values(), key=lambda x: x['hybrid_score'], reverse=True)[:n_results]

            return {
                'documents': [r['document'] for r in ranked],
                'metadatas': [r['metadata'] for r in ranked],
                'scores': [r['hybrid_score'] for r in ranked],
                'semantic_scores': [r.get('semantic_score', 0.0) for r in ranked],
                'bm25_scores': [r.get('bm25_score', 0.0) for r in ranked],
                'query': query,
                'total_results': len(ranked)
            }

        except Exception as e:
            logger.exception(f"❌ Hybrid search failed: {e}")
            return {'documents': [], 'metadatas': [], 'scores': [], 'query': query, 'total_results': 0}

    def search(self, query: str, n_results: int = 5, subject_filter: Optional[str] = None, module_filter: Optional[str] = None) -> Dict[str, Any]:
        """Default: use hybrid search if enabled, otherwise semantic only."""
        if self.enable_bm25:
            return self.hybrid_search(query, n_results, subject_filter, module_filter)
        # else fallback to semantic-only query
        try:
            emb = self._embed_texts([query])
            results = self.collection.query(query_embeddings=emb, n_results=n_results,
                                            where={'subject': subject_filter, 'module': module_filter} if (subject_filter or module_filter) else None,
                                            include=["documents", "metadatas", "distances"])
            docs = _safe_get_first(results.get('documents', []))
            mds = _safe_get_first(results.get('metadatas', []))
            dists = _safe_get_first(results.get('distances', []))
            sims = self._normalize_similarity(dists if dists else [0.0] * len(docs))
            return {'documents': docs, 'metadatas': mds, 'distances': dists, 'similarities': sims, 'query': query, 'total_results': len(docs)}
        except Exception as e:
            logger.exception(f"❌ Search failed: {e}")
            return {'documents': [], 'metadatas': [], 'distances': [], 'query': query, 'total_results': 0}

    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            count = 0
            try:
                count = self.collection.count()
                if isinstance(count, dict) and 'count' in count:
                    count = int(count['count'])
                else:
                    count = int(count)
            except Exception:
                # fallback: get all metadatas length
                all_md = self.collection.get(include=['metadatas'])
                md_list = _safe_get_first(all_md.get('metadatas', []))
                count = len(md_list)

            all_metadatas = self.collection.get(include=['metadatas'])
            md_list = _safe_get_first(all_metadatas.get('metadatas', []))
            subjects = set()
            modules = set()
            for md in md_list:
                if not md: continue
                if 'subject' in md and md['subject'] is not None:
                    subjects.add(md['subject'])
                if 'module' in md and md['module'] is not None:
                    modules.add(md['module'])

            return {'total_chunks': count, 'subjects': list(subjects), 'modules': list(modules), 'persist_directory': self.persist_directory, 'embedding_model': self.model_name}
        except Exception as e:
            logger.exception("❌ Failed to get collection stats")
            return {'total_chunks': 0, 'subjects': [], 'modules': []}

    def get_organization_info(self) -> Dict[str, Any]:
        stats = self.get_collection_stats()
        file_structure = {}
        try:
            file_structure = get_organization_structure()
        except Exception:
            logger.debug("Could not fetch organization structure")
        return {'database_stats': stats, 'file_structure': file_structure}

    def clear_database(self):
        try:
            self.client.delete_collection("engineering_documents")
            self.collection = self.client.get_or_create_collection("engineering_documents")
            logger.info("🗑️ Database cleared successfully")
            # clear BM25
            self.bm25 = None
            self.bm25_corpus = []
            self.bm25_metadata = []
        except Exception as e:
            logger.exception("❌ Failed to clear database")

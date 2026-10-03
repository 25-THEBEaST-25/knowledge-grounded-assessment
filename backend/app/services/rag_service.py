"""Approved-material RAG: extraction -> chunking -> embeddings -> Qdrant ->
metadata-filtered retrieval. Only faculty-approved material of the same
assessment is ever retrieved. If Qdrant/embeddings are unavailable we say so
(status UNAVAILABLE) -- RAG is never pretended."""
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Sequence

from backend.app.db import models as m

logger = logging.getLogger(__name__)

GLOBAL_SCOPE = "*"
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
_NS = uuid.UUID("6f1b7c0e-3b1d-4c55-9a77-0d5b6f7a1e11")


class RAGUnavailableError(RuntimeError):
    pass


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> List[List[float]]: ...


class GeminiEmbedder:
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        from backend.app.services import evaluation_service
        try:
            resp = evaluation_service.get_client().models.embed_content(model=EMBED_MODEL, contents=list(texts))
            return [list(e.values) for e in resp.embeddings]
        except Exception as exc:  # provider/key/network: surface as unavailable, never fake vectors
            raise RAGUnavailableError(f"Embedding service unavailable: {type(exc).__name__}") from exc


@dataclass
class RAG:
    client: object  # qdrant_client.QdrantClient
    embedder: Embedder
    collection: str = field(default_factory=lambda: os.getenv("QDRANT_COLLECTION", "snaptix_approved_material"))


_rag_override: Optional[RAG] = None


def set_rag(rag: Optional[RAG]) -> None:
    """Test/DI hook."""
    global _rag_override
    _rag_override = rag


def get_rag() -> Optional[RAG]:
    """None => retrieval unavailable (QDRANT_URL unset or client creation failed)."""
    if _rag_override is not None:
        return _rag_override
    url = os.getenv("QDRANT_URL")
    if not url:
        return None
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(":memory:") if url == ":memory:" else QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
        return RAG(client=client, embedder=GeminiEmbedder())
    except Exception:
        logger.exception("Qdrant client init failed")
        return None


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> List[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + size])
        if i + size >= len(text):
            break
        i += size - overlap
    return chunks


@dataclass
class ChunkRecord:
    text: str
    doc_type: str
    scope: str
    document_id: Optional[str]
    source: str
    version: int = 1


def _ensure_collection(rag: RAG, dim: int) -> None:
    from qdrant_client.models import Distance, VectorParams
    try:
        if not rag.client.collection_exists(rag.collection):
            rag.client.create_collection(rag.collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    except Exception as exc:
        raise RAGUnavailableError(f"Vector store unavailable: {type(exc).__name__}") from exc


def _assessment_filter(assessment_id: str, scopes: Optional[Sequence[str]] = None):
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
    must = [FieldCondition(key="assessment_id", match=MatchValue(value=assessment_id))]
    if scopes is not None:
        must.append(FieldCondition(key="approved", match=MatchValue(value=True)))
        must.append(FieldCondition(key="scope", match=MatchAny(any=list(scopes))))
    return Filter(must=must)


def collect_chunks(db, assessment: m.Assessment, read_text: Callable[[m.Document], str]) -> List[ChunkRecord]:
    """Only APPROVED items become chunks."""
    out: List[ChunkRecord] = []
    for q in db.query(m.Question).filter_by(assessment_id=assessment.id):
        for sq in q.subquestions:
            if not sq.approved:
                continue
            if sq.text:
                out.append(ChunkRecord(f"Question {sq.full_id}: {sq.text}", "question", sq.full_id, None, "question_paper"))
            ma = sq.model_answer
            if ma and ma.approved:
                for c in chunk_text(ma.text):
                    out.append(ChunkRecord(c, "model_answer", sq.full_id,
                                           str(ma.source_document_id) if ma.source_document_id else None,
                                           f"model_answer {sq.full_id}", ma.version))
            if sq.rubric and sq.rubric.approved:
                text = "; ".join(f"{c.code}: {c.description} ({c.max_marks:g})" for c in sq.rubric.criteria)
                out.append(ChunkRecord(f"Rubric {sq.full_id}: {text}", "rubric", sq.full_id, None, f"rubric {sq.full_id}"))
    for doc in db.query(m.Document).filter_by(assessment_id=assessment.id, kind="reference", approved=True):
        for c in chunk_text(read_text(doc)):
            out.append(ChunkRecord(c, "reference", GLOBAL_SCOPE, str(doc.id), doc.filename, doc.version))
    return out


def index_assessment(db, assessment: m.Assessment, rag: Optional[RAG], read_text: Callable[[m.Document], str]) -> Dict:
    """Idempotent: replaces all points of this assessment. Returns {status, chunks}."""
    if rag is None:
        return {"status": "UNAVAILABLE", "chunks": 0, "detail": "Vector store not configured (QDRANT_URL)."}
    chunks = collect_chunks(db, assessment, read_text)
    try:
        from qdrant_client.models import FilterSelector, PointStruct
        if not chunks:
            return {"status": "EMPTY", "chunks": 0, "detail": "No approved material to index."}
        vectors = rag.embedder.embed([c.text for c in chunks])
        _ensure_collection(rag, len(vectors[0]))
        rag.client.delete(rag.collection, points_selector=FilterSelector(filter=_assessment_filter(str(assessment.id))))
        points = [
            PointStruct(
                id=str(uuid.uuid5(_NS, f"{assessment.id}:{i}:{c.doc_type}:{c.scope}:{c.text[:64]}")),
                vector=v,
                payload={"assessment_id": str(assessment.id), "subject_id": str(assessment.subject_id),
                         "document_id": c.document_id, "doc_type": c.doc_type, "scope": c.scope,
                         "approved": True, "version": c.version, "source": c.source, "text": c.text},
            )
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ]
        rag.client.upsert(rag.collection, points=points)
        return {"status": "INDEXED", "chunks": len(points)}
    except RAGUnavailableError as exc:
        return {"status": "UNAVAILABLE", "chunks": 0, "detail": str(exc)}
    except Exception as exc:
        logger.exception("Indexing failed")
        return {"status": "UNAVAILABLE", "chunks": 0, "detail": f"Indexing failed: {type(exc).__name__}"}


@dataclass
class Retrieval:
    status: str  # USED | NO_MATCH | UNAVAILABLE
    chunks: List[Dict] = field(default_factory=list)  # {ref, point_id, source, doc_type, scope, document_id, score, text}
    detail: str = ""


def retrieve(rag: Optional[RAG], assessment_id: str, subquestion_full_id: str, query: str, k: int = 4) -> Retrieval:
    if rag is None:
        return Retrieval("UNAVAILABLE", detail="Vector store not configured.")
    try:
        vec = rag.embedder.embed([query])[0]
        if not rag.client.collection_exists(rag.collection):
            return Retrieval("NO_MATCH", detail="Nothing indexed for this assessment.")
        res = rag.client.query_points(rag.collection, query=vec, limit=k, with_payload=True,
                                      query_filter=_assessment_filter(assessment_id, [subquestion_full_id, GLOBAL_SCOPE]))
        pts = res.points
    except RAGUnavailableError as exc:
        return Retrieval("UNAVAILABLE", detail=str(exc))
    except Exception as exc:
        logger.warning("Retrieval failed: %s", exc)
        return Retrieval("UNAVAILABLE", detail=f"Retrieval failed: {type(exc).__name__}")
    if not pts:
        return Retrieval("NO_MATCH", detail="No approved material matched.")
    chunks = [{"ref": f"S{i + 1}", "point_id": str(p.id), "source": p.payload.get("source", ""),
               "doc_type": p.payload.get("doc_type", ""), "scope": p.payload.get("scope", ""),
               "document_id": p.payload.get("document_id"), "score": round(float(p.score), 4),
               "text": p.payload.get("text", "")} for i, p in enumerate(pts)]
    return Retrieval("USED", chunks)

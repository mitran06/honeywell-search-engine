# PDF Search Engine Pipeline

## Architecture Overview

```mermaid
flowchart TB
    subgraph INPUT["INPUT LAYER"]
        direction TB
        PDF[PDF Upload]
        TC[Text Cleaning]
        CH[Chunking]
        OCR[OCR Engine]
        PDF --> TC
        PDF --> OCR
        OCR --> TC
        TC --> CH
    end

    subgraph EMBED["EMBEDDINGS LAYER"]
        direction TB
        WE[Word Embeddings]
        SE[Sentence Embeddings<br/>BGE-M3]
        OIE[OpenIE Triple<br/>Extraction]
        CH --> WE
        CH --> SE
        CH --> OIE
    end

    subgraph INDEX["HYBRID INDEXING"]
        direction TB
        FAISS[(FAISS Index<br/>Sentences)]
        QDRANT[(Qdrant<br/>Vector DB)]
        BM25[(BM25/Lucene<br/>Lexical Index)]
        TRIPLE[(Triple Index<br/>Subject-Predicate-Object)]
        WORD[(Word Index<br/>Inverted Index)]
        SE --> FAISS
        SE --> QDRANT
        WE --> BM25
        WE --> WORD
        OIE --> TRIPLE
    end

    subgraph QUERY["QUERY PROCESSING"]
        direction TB
        QI[User Query]
        QSE[Query Sentence<br/>Embedding]
        QTE[Query Token<br/>Embedding]
        QOIE[OIE Triple<br/>Pattern Matching]
        QI --> QSE
        QI --> QTE
        QI --> QOIE
    end

    subgraph RETRIEVAL["PARALLEL RETRIEVAL"]
        direction TB
        FS[FAISS/Qdrant<br/>Semantic Search]
        TS[Triple Index<br/>Relation Search]
        TKS[BM25/Token<br/>Lexical Search]
        QSE --> FS
        QOIE --> TS
        QTE --> TKS
        FAISS -.-> FS
        QDRANT -.-> FS
        TRIPLE -.-> TS
        BM25 -.-> TKS
        WORD -.-> TKS
    end

    subgraph FUSION["FUSION & RANKING"]
        direction TB
        RRF[Reciprocal Rank<br/>Fusion]
        RERANK[Cross-Encoder<br/>Reranking]
        FS --> RRF
        TS --> RRF
        TKS --> RRF
        RRF --> RERANK
    end

    subgraph OUTPUT["OUTPUT"]
        direction TB
        UI[Web Interface]
        RES[Results:<br/>Page + Snippet +<br/>Highlight + Score]
        RERANK --> RES
        RES --> UI
    end

    style INPUT fill:#e3f2fd,stroke:#1976d2
    style EMBED fill:#fff3e0,stroke:#f57c00
    style INDEX fill:#f3e5f5,stroke:#7b1fa2
    style QUERY fill:#e8f5e9,stroke:#388e3c
    style RETRIEVAL fill:#fce4ec,stroke:#c2185b
    style FUSION fill:#fff8e1,stroke:#fbc02d
    style OUTPUT fill:#e0f2f1,stroke:#00796b
```

---

## Detailed Pipeline Stages

### 1. Input Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **PDF Parsing** | `PyMuPDF (fitz)` | Fast, accurate text extraction with layout preservation |
| **OCR Engine** | `Tesseract` + `pdf2image` | Handle scanned PDFs and images within PDFs |
| **Text Cleaning** | `ftfy` + `regex` | Fix encoding issues, normalize whitespace, remove artifacts |
| **Chunking** | `LangChain TextSplitter` | Split documents into semantic chunks (512-1024 tokens) |

**Why these choices:**
- **PyMuPDF**: 10x faster than PyPDF2, better text extraction quality, handles complex layouts
- **Tesseract**: Industry standard OCR, good accuracy for printed text, free and open-source
- **Chunking Strategy**: Sentence-aware splitting preserves context; overlap (128 tokens) prevents boundary information loss

---

### 2. Embeddings Layer

| Component | Technology | Model | Purpose |
|-----------|------------|-------|---------|
| **Sentence Embeddings** | `sentence-transformers` | `BAAI/bge-m3` | Dense vector representations for semantic search |
| **Word Embeddings** | `FastText` or `BM25 Tokenizer` | - | Sparse representations for lexical matching |
| **OpenIE Triples** | `Stanford OpenIE` or `OpenIE6` | - | Extract (subject, predicate, object) relations |

**Why BGE-M3:**
- Multi-lingual support (100+ languages)
- Multi-granularity (dense + sparse + ColBERT in one model)
- State-of-the-art retrieval performance
- 8192 token context length
- Optimized for retrieval tasks

**Why OpenIE:**
- Captures relational knowledge ("Einstein developed relativity")
- Enables structured queries ("Who developed X?", "What did Y do?")
- Complements semantic search with factual retrieval

---

### 3. Hybrid Indexing

| Index Type | Technology | Data Stored | Use Case |
|------------|------------|-------------|----------|
| **Vector Index** | `Qdrant` | Dense embeddings (768-1024d) | Semantic similarity search |
| **FAISS Index** | `faiss-cpu/gpu` | Dense embeddings (optional) | Fast in-memory search, filtering |
| **Lexical Index** | `Elasticsearch` or `Tantivy` | BM25 inverted index | Exact keyword matching |
| **Triple Index** | `PostgreSQL` + `pg_trgm` | (subject, predicate, object, chunk_id) | Relation-based queries |

**Why Qdrant over Pinecone/Weaviate:**
- Self-hosted (data stays on-premise) ✓
- Built-in filtering and payload storage
- Supports hybrid search natively
- Lower latency for production workloads
- Free and open-source

**Why Hybrid Indexing:**
- Semantic search alone misses exact matches ("Error code E-5021")
- Lexical search alone misses paraphrases ("car" vs "automobile")
- Hybrid combines best of both worlds

---

### 4. Query Processing

```mermaid
flowchart LR
    Q[User Query] --> PREP[Preprocessing]
    PREP --> SE[Sentence Embedding<br/>BGE-M3]
    PREP --> TE[Token Extraction<br/>BM25]
    PREP --> OIE[Triple Pattern<br/>Detection]
    
    SE --> VS[Vector Search]
    TE --> LS[Lexical Search]
    OIE --> TS[Triple Search]
```

| Step | Technology | Description |
|------|------------|-------------|
| **Query Preprocessing** | Custom | Spell correction, query expansion, stopword handling |
| **Query Embedding** | `BGE-M3` | Same model as indexing for consistency |
| **Query Tokenization** | `BM25Encoder` | Extract keywords for lexical search |
| **Triple Pattern Detection** | `SpaCy` + rules | Identify relation patterns in queries |

---

### 5. Parallel Retrieval

| Search Type | Method | Returns |
|-------------|--------|---------|
| **Semantic Search** | Qdrant ANN search (HNSW) | Top-k chunks by cosine similarity |
| **Lexical Search** | BM25 scoring | Top-k chunks by term frequency |
| **Triple Search** | SQL pattern matching | Chunks containing matching relations |

**Retrieval Parameters:**
- `top_k = 100` per search type (before fusion)
- `ef_search = 128` for HNSW (accuracy vs speed tradeoff)
- Parallel execution using `asyncio.gather()`

---

### 6. Fusion & Ranking

```mermaid
flowchart LR
    SEM[Semantic Results<br/>score: 0.0-1.0]
    LEX[Lexical Results<br/>score: BM25]
    TRI[Triple Results<br/>score: match %]
    
    SEM --> NORM[Score<br/>Normalization]
    LEX --> NORM
    TRI --> NORM
    
    NORM --> RRF[Reciprocal Rank<br/>Fusion]
    RRF --> RERANK[Cross-Encoder<br/>Reranking]
    RERANK --> TOP[Top-k Results]
```

| Stage | Technology | Formula/Method |
|-------|------------|----------------|
| **Score Normalization** | Min-Max scaling | `(score - min) / (max - min)` |
| **Reciprocal Rank Fusion** | Custom implementation | `RRF(d) = Σ 1/(k + rank(d))` where k=60 |
| **Cross-Encoder Reranking** | `cross-encoder/ms-marco-MiniLM-L-12-v2` | Pairwise relevance scoring |

**Why RRF:**
- Robust to different score scales
- No hyperparameter tuning needed
- Proven effectiveness in hybrid search
- Simple and fast

**Why Cross-Encoder Reranking:**
- More accurate than bi-encoder similarity
- Considers query-document interaction
- Only applied to top-50 candidates (manageable latency)

---

### 7. Output Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Result Formatting** | Custom | Structure results with metadata |
| **Snippet Extraction** | `regex` + sliding window | Extract relevant text around matches |
| **Highlighting** | Frontend `mark.js` | Highlight matched terms in UI |
| **PDF Viewer** | `react-pdf` / `pdf.js` | Display PDF with highlighted regions |

**Result Schema:**
```json
{
  "results": [
    {
      "document_id": "uuid",
      "document_name": "research_paper.pdf",
      "page_number": 5,
      "chunk_text": "...",
      "snippet": "...relevant excerpt with <mark>highlights</mark>...",
      "score": 0.89,
      "score_breakdown": {
        "semantic": 0.85,
        "lexical": 0.72,
        "triple": 0.95
      },
      "matched_triples": [
        {"subject": "Einstein", "predicate": "developed", "object": "relativity"}
      ],
      "bounding_box": {"x": 100, "y": 200, "width": 400, "height": 50}
    }
  ]
}
```

---

## Technology Stack Summary

### Backend
| Layer | Technology | Reason |
|-------|------------|--------|
| API Framework | **FastAPI** | Async support, auto-docs, type hints |
| Task Queue | **Celery + Redis** | Background PDF processing, scalable workers |
| Vector DB | **Qdrant** | Self-hosted, hybrid search, filtering |
| Relational DB | **PostgreSQL** | Metadata, users, triples, ACID compliance |
| Object Storage | **MinIO** | S3-compatible, self-hosted PDF storage |
| Embedding Model | **BGE-M3** | SOTA retrieval, multi-lingual |
| Reranker | **cross-encoder/ms-marco** | Accuracy boost for top results |
| PDF Parsing | **PyMuPDF** | Speed and accuracy |
| OCR | **Tesseract** | Open-source, good accuracy |
| OpenIE | **OpenIE6** or **Stanford OpenIE** | Relation extraction |

### Frontend
| Layer | Technology | Reason |
|-------|------------|--------|
| Framework | **React + TypeScript** | Type safety, component reuse |
| PDF Viewer | **react-pdf** | Native PDF.js integration |
| State | **React Query** | Server state management, caching |
| Styling | **CSS Modules** | Scoped styles, no runtime overhead |

### Infrastructure
| Layer | Technology | Reason |
|-------|------------|--------|
| Containerization | **Docker Compose** | Easy local development |
| Reverse Proxy | **Nginx** (production) | Load balancing, SSL termination |
| Monitoring | **Prometheus + Grafana** | Metrics and alerting |

---

## Processing Pipeline Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant Q as Celery Queue
    participant W as Worker
    participant S3 as MinIO
    participant PG as PostgreSQL
    participant QD as Qdrant

    U->>API: Upload PDF
    API->>S3: Store PDF
    API->>PG: Create metadata (status: pending)
    API->>Q: Queue processing job
    API-->>U: 202 Accepted (job_id)

    Q->>W: Dispatch job
    W->>S3: Fetch PDF
    W->>W: Extract text (PyMuPDF/OCR)
    W->>W: Clean & chunk text
    W->>W: Generate embeddings (BGE-M3)
    W->>W: Extract triples (OpenIE)
    W->>QD: Store vectors
    W->>PG: Store chunks, triples
    W->>PG: Update status (completed)
    
    U->>API: Search query
    API->>API: Generate query embedding
    API->>QD: Semantic search
    API->>PG: Lexical search (BM25)
    API->>PG: Triple search
    API->>API: RRF Fusion
    API->>API: Cross-encoder rerank
    API-->>U: Search results
```

---

## Performance Targets

| Metric | Target | Method |
|--------|--------|--------|
| PDF Processing | < 30s per 100 pages | Parallel chunking, batch embedding |
| Search Latency (p95) | < 500ms | HNSW index, result caching |
| Throughput | 100 queries/sec | Async API, connection pooling |
| Index Size | ~1KB per page | Quantized embeddings (int8) |

---

## Future Enhancements

1. **ColBERT Integration**: Late interaction for better accuracy
2. **Query Understanding**: Intent classification, entity recognition
3. **Feedback Loop**: Learn from user clicks to improve ranking
4. **Multi-modal Search**: Search within images/diagrams in PDFs
5. **Clustering**: Group similar documents, topic modeling

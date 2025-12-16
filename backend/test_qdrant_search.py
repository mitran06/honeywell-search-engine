import asyncio
from app.services.embeddings.embedder import embed_query
from app.services.qdrant.qdrant_search import semantic_search

async def test():
    query_vec = await embed_query("integration of NVIDIA NeMo, FAISS")
    results = semantic_search(query_vec, top_k=3)

    for r in results:
     print("Score:", r["score"])
     print("FULL RESULT:", r)
     print("-" * 40)


asyncio.run(test())

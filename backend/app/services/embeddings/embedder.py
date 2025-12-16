from sentence_transformers import SentenceTransformer
import asyncio

_model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    return _model.encode(texts, convert_to_numpy=True).tolist()


async def embed_text_async(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: generate_embeddings([text])[0])


async def embed_query(query: str) -> list[float]:
    """
    Embed a user search query into a vector (384-dim)
    """
    return await embed_text_async(query)


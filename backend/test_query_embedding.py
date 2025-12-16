import asyncio
from app.services.embeddings.embedder import embed_query

vec = asyncio.run(embed_query("working principle of zirconia oxygen sensor"))
print(len(vec))

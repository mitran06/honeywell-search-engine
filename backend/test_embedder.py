from app.services.embeddings.embedder import get_embedder

embedder = get_embedder()
vec = embedder.embed_query("what is AI?")

print("Vector shape:", vec.shape)
print("Vector preview:", vec[:5])

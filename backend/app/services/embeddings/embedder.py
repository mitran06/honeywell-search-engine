from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    return _model.encode(texts, convert_to_numpy=True).tolist()

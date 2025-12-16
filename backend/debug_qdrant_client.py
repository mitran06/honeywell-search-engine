from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

print("Client type:", type(client))
print("\nAvailable methods:\n")

methods = [m for m in dir(client) if "search" in m.lower()]
for m in methods:
    print(m)

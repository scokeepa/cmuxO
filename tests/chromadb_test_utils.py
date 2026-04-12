"""ChromaDB helpers for tests.

Tests that seed collections directly must use the same CPU-only embedding
policy as the production palace helpers.
"""

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2


def cpu_embedding():
    return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])


def get_collection(client, name):
    return client.get_collection(name, embedding_function=cpu_embedding())


def create_collection(client, name):
    return client.create_collection(name, embedding_function=cpu_embedding())


def get_or_create_collection(client, name):
    return client.get_or_create_collection(name, embedding_function=cpu_embedding())

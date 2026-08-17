#!/usr/bin/env python3
"""
Creates the MongoDB Vector Search index on the past_issues collection, using the
current vectorSearch index type (not the older Search index with a knnVector
field mapping). Run this once, after create_issue_embeddings.py has inserted
at least one document with an `embedding` field -- creating a vector index on
a collection before it exists raises NamespaceNotFound.

Safe to run again: skips creation if an index with this name already exists.

Usage:
    python create_vector_index.py

Ensure the following environment variables are set:
    - MONGO_URI: Your MongoDB Atlas connection string.
    - DATABASE: The database containing past_issues.
    - VECTOR_SEARCH_INDEX: The index name (matches main.py's vector_search_tool).
"""

import os
import time

import pymongo
from pymongo.operations import SearchIndexModel

from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIMENSIONS = 1024  # voyage-3-large's default output dimensionality


def main():
    mongo_uri = os.environ.get("MONGO_URI")
    database = os.environ.get("DATABASE")
    index_name = os.environ.get("VECTOR_SEARCH_INDEX")

    if not mongo_uri or not database or not index_name:
        raise SystemExit("MONGO_URI, DATABASE, and VECTOR_SEARCH_INDEX must be set (see .env)")

    client = pymongo.MongoClient(mongo_uri)
    collection = client[database]["past_issues"]

    existing = {idx["name"] for idx in collection.list_search_indexes()}
    if index_name in existing:
        print(f"Index '{index_name}' already exists on past_issues, skipping.")
        client.close()
        return

    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMENSIONS,
                    "similarity": "cosine",
                }
            ]
        },
        name=index_name,
        type="vectorSearch",
    )
    collection.create_search_index(model=model)
    print(f"Requested creation of '{index_name}'. Waiting for it to become queryable...")

    for _ in range(60):
        indexes = list(collection.list_search_indexes(index_name))
        if indexes and indexes[0].get("queryable"):
            print(f"'{index_name}' is READY and queryable.")
            break
        time.sleep(5)
    else:
        print(f"'{index_name}' was created but did not become queryable within 5 minutes. Check the Atlas UI.")

    client.close()


if __name__ == "__main__":
    main()

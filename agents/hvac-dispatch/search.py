import os
import sys

import chromadb
import voyageai
from dotenv import load_dotenv

load_dotenv()

VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "hvac_company_docs"
EMBED_MODEL = "voyage-3.5"
N_RESULTS = 2


def main():
    if len(sys.argv) < 2:
        print("Usage: python search.py \"<question>\"")
        sys.exit(1)

    question = sys.argv[1]

    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    query_embedding = voyage_client.embed(
        [question], model=EMBED_MODEL, input_type="query"
    ).embeddings[0]

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    results = collection.query(query_embeddings=[query_embedding], n_results=N_RESULTS)
    documents = results["documents"][0]

    print(f"Question: {question}\n")
    print("Retrieved context:")
    for i, doc in enumerate(documents, start=1):
        print(f"  {i}. {doc}")


if __name__ == "__main__":
    main()

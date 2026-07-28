import os

import chromadb
import voyageai
from dotenv import load_dotenv

from company_docs import COMPANY_DOCS

load_dotenv()

VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "hvac_company_docs"
EMBED_MODEL = "voyage-3.5"


def main():
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    result = voyage_client.embed(COMPANY_DOCS, model=EMBED_MODEL, input_type="document")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    collection.upsert(
        ids=[str(i) for i in range(len(COMPANY_DOCS))],
        embeddings=result.embeddings,
        documents=COMPANY_DOCS,
    )

    print(f"Ingested {len(COMPANY_DOCS)} documents into '{COLLECTION_NAME}' at {CHROMA_PATH}")


if __name__ == "__main__":
    main()

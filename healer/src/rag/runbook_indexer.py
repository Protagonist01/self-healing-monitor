import os
import hashlib
import json
import math
from typing import List, Dict, Any
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from openai import OpenAI

from healer.src.config import settings

class OpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        # Call OpenAI Embeddings API
        response = self.client.embeddings.create(
            input=input,
            model=self.model_name
        )
        return [data.embedding for data in response.data]

class LocalHashEmbeddingFunction(EmbeddingFunction):
    """
    Deterministic local embedding fallback for demo and test runs.

    It avoids network calls and API-key requirements while still giving ChromaDB
    a stable vector space that rewards shared technical vocabulary.
    """
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(document) for document in input]

    def _embed(self, document: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = [
            token.strip(".,:;!?()[]{}<>\"'").lower()
            for token in document.split()
            if token.strip(".,:;!?()[]{}<>\"'")
        ]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

class RunbookIndexer:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)

        if settings.OPENAI_API_KEY:
            self.embedding_fn = OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.EMBEDDING_MODEL
            )
        else:
            print("OPENAI_API_KEY not set. Using local hash embeddings for runbook retrieval.")
            self.embedding_fn = LocalHashEmbeddingFunction()
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="runbooks",
            embedding_function=self.embedding_fn
        )
        
        # State tracking file to record file hashes
        self.hash_file_path = os.path.join(settings.CHROMA_DB_DIR, "runbooks_hashes.json")

    def _get_file_hash(self, filepath: str) -> str:
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def _load_stored_hashes(self) -> Dict[str, str]:
        if os.path.exists(self.hash_file_path):
            try:
                with open(self.hash_file_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_hashes(self, hashes: Dict[str, str]):
        os.makedirs(os.path.dirname(self.hash_file_path), exist_ok=True)
        with open(self.hash_file_path, "w") as f:
            json.dump(hashes, f, indent=2)

    def _chunk_markdown(self, content: str) -> List[Dict[str, str]]:
        """
        Simple markdown chunker that splits by header (h1 or h2)
        and returns list of dicts with 'header' and 'content' keys.
        """
        lines = content.split("\n")
        chunks = []
        current_header = "General"
        current_lines = []

        for line in lines:
            if line.startswith("# ") or line.startswith("## "):
                if current_lines:
                    chunks.append({
                        "header": current_header,
                        "content": "\n".join(current_lines).strip()
                    })
                    current_lines = []
                current_header = line.replace("#", "").strip()
            else:
                current_lines.append(line)

        if current_lines:
            chunks.append({
                "header": current_header,
                "content": "\n".join(current_lines).strip()
            })

        return [c for c in chunks if c["content"]]

    def index_runbooks(self, force: bool = False):
        """
        Scan RUNBOOKS_DIR and index runbooks into ChromaDB.
        Re-indexes files only if their MD5 hash has changed (unless force=True).
        """
        if not os.path.exists(settings.RUNBOOKS_DIR):
            print(f"Runbooks directory {settings.RUNBOOKS_DIR} does not exist. Skipping indexing.")
            return

        stored_hashes = self._load_stored_hashes()
        current_hashes = {}
        files_to_index = []

        for filename in os.listdir(settings.RUNBOOKS_DIR):
            if filename.endswith(".md"):
                filepath = os.path.join(settings.RUNBOOKS_DIR, filename)
                file_hash = self._get_file_hash(filepath)
                current_hashes[filename] = file_hash

                if force or stored_hashes.get(filename) != file_hash:
                    files_to_index.append((filename, filepath))

        if not files_to_index:
            print("All runbooks are up to date in the index.")
            return

        print(f"Indexing {len(files_to_index)} modified/new runbook(s)...")

        for filename, filepath in files_to_index:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Split markdown into sections
            sections = self._chunk_markdown(content)
            
            # Delete old entries for this file to prevent duplicates
            self.collection.delete(where={"source": filename})

            # Add chunks
            documents = []
            metadatas = []
            ids = []

            for idx, section in enumerate(sections):
                chunk_id = f"{filename}#chunk-{idx}"
                doc_text = f"Runbook: {filename}\nSection: {section['header']}\nContent:\n{section['content']}"
                
                documents.append(doc_text)
                metadatas.append({
                    "source": filename,
                    "header": section["header"],
                    "filepath": filepath
                })
                ids.append(chunk_id)

            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )

        self._save_hashes(current_hashes)
        print("Runbook indexing completed successfully.")

    def search(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Semantic query to retrieve the top runbook sections.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )

        output = []
        if results and results["documents"] and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0]*len(docs)
            ids = results["ids"][0]

            for i in range(len(docs)):
                output.append({
                    "id": ids[i],
                    "document": docs[i],
                    "metadata": metas[i],
                    "distance": distances[i]
                })

        return output

# Singleton instance
indexer = RunbookIndexer()

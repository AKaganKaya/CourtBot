import faiss
import pickle
import json
import numpy as np
from tqdm import tqdm
from FlagEmbedding import BGEM3FlagModel
from typing import Iterable, Tuple



# DENSE embedding
def get_embedding(texts, model, batch_size=16):
    dense_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        encoded = model.encode_corpus(batch, max_length=512)
        dense_vecs = encoded["dense_vecs"]
        dense_embeddings.append(dense_vecs)
    return np.vstack(dense_embeddings).astype("float32")

# JSONL okuyucu
def sentence_generator(jsonl_path: str) -> Iterable[Tuple[str, str]]:
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                yield obj["sentence"], obj["file"]
            except Exception:
                continue

# FAISS indexleme
def build_faiss_in_batches(
    jsonl_path: str,
    batch_size: int = 10000,
    faiss_path: str = "database/faiss.index",
    metadata_path: str = "database/metadata.pkl"
):
    dim = None
    index = None
    metadata = []

    batch_sentences = []
    batch_meta = []

    gen = sentence_generator(jsonl_path)
    count = 0
# MODEL — FlagEmbedding ile
    model = BGEM3FlagModel('mirzabey/bge-m3-law', devices="mps", use_fp16=True)
    print("✅ BGE-M3 model yüklendi.")
    for sentence, filename in tqdm(gen, desc="🔄 Processing"):
        batch_sentences.append(sentence)
        batch_meta.append((sentence, filename))
        count += 1

        if len(batch_sentences) >= batch_size:
            embeddings = get_embedding(batch_sentences, model)
            if index is None:
                dim = embeddings.shape[1]
                index = faiss.IndexFlatL2(dim)
            index.add(embeddings)
            metadata.extend(batch_meta)
            batch_sentences.clear()
            batch_meta.clear()

    if batch_sentences:
        embeddings = get_embedding(batch_sentences, model)
        if index is None:
            dim = embeddings.shape[1]
            index = faiss.IndexFlatL2(dim)
        index.add(embeddings)
        metadata.extend(batch_meta)

    faiss.write_index(index, faiss_path)
    with open(metadata_path, "wb") as f:
        pickle.dump(metadata, f)

    print(f"\n✅ Toplam {count} cümle işlendi.")
    print(f"📁 FAISS index: {faiss_path}")
    print(f"📁 Metadata: {metadata_path}")



import requests

def get_remote_embedding(query: str, api_url="https://mirzabey-bge-m3-api.hf.space/embed") -> list:
    try:
        response = requests.post(api_url, json={"text": query})
        response.raise_for_status()
        data = response.json()
        return [data["embedding"]]
    except Exception as e:
        print(f"❌ Embedding API error: {e}")
        return []

def search_faiss(
    query,
    index,
    metadata,
    top_k: int = 10,
    embedding_api_url: str = "https://mirzabey-bge-m3-api.hf.space/embed"
):
    # FAISS index ve metadata yükle


    # Embed sorgusu
    query_vec = get_remote_embedding(query, api_url=embedding_api_url)
    if not query_vec:
        print("❌ Query için embedding alınamadı.")
        return []

    import numpy as np
    query_vec = np.array(query_vec).astype("float32")

    # FAISS arama
    distances, indices = index.search(query_vec, top_k)

    results = []
    for i, dist in zip(indices[0], distances[0]):
        sentence, file = metadata[i]
        results.append({
            "sentence": sentence,
            "file": file,
            "distance": float(dist)
        })

    return results




from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import torch
from weaviate_db import Database

def load_model() -> SentenceTransformer :
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = model.to(device)
    return model


if __name__ == "__main__":
    load_dotenv(dotenv_path=".env")

    print("Loading model and Database...")
    model = load_model()
    with Database() as db:
        db.create_or_get_collections("Embeddings_new_preprocess")
        
        while True:
            query = input("Input sth you want to search: ").lower().strip()
            if query == "quit":
                break

            try:
                query_embedding = model.encode(query).tolist()
                property = {"language": "en", "file_type": "pdf"}

                results = db.search(query = query, query_embedding=query_embedding, 
                                     property=property)
                for o in results.objects[:5]:
                    print(f"File name: {o.properties['name']}, File language: {o.properties['language']}, File type: {o.properties['file_type']} Score: {o.metadata.score}, Reranker_score: {o.metadata.rerank_score}")
            except ValueError as e:
                print(f"Error: {e}")
        


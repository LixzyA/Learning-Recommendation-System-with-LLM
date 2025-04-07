from weaviate_db import Database
from dotenv import load_dotenv
import pandas as pd

if __name__ == '__main__':
    load_dotenv(dotenv_path=".env")
    dataset = pd.read_parquet("embeddings.parquet")
    with Database() as db:
        db.create_or_get_collections("Embeddings_new_preprocess")
        db.ingest_data(dataset)
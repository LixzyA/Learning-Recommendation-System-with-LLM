from weaviate_db import Database
from dotenv import load_dotenv
import pandas as pd
from os import getenv

if __name__ == '__main__':
    load_dotenv(dotenv_path=".env")
    dataset = pd.read_parquet("Embeddings.parquet")
    with Database() as db:
        db.create_or_get_collections(getenv('WEAVIATE_DB'))
        db.ingest_data(dataset)
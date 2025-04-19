from weaviate_db import Database
from dotenv import load_dotenv
import pandas as pd

if __name__ == '__main__':
    load_dotenv(dotenv_path=".env") # To access Weaviate Database
    dataset = pd.read_parquet("Embeddings.parquet")
    with Database() as db:
        db.ingest_data(dataset)
    print("Success ingesting data")
    
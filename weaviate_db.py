import weaviate
from weaviate.classes.query import Rerank, MetadataQuery
from weaviate.classes.config import Configure
from weaviate.util import generate_uuid5
import weaviate.classes as wvc
from os import getenv
import pandas as pd
from dotenv import load_dotenv
# import numpy as np



class Database:
    def __init__(self):
        """Initialize the Database with API key and null client/collection."""
        self.api_key = getenv("COHERE_APIKEY")
        self.client = None
        self.collection = None

    def __enter__(self):
        """Establish connection to Weaviate when entering the context."""
        self.client = weaviate.connect_to_local(
            headers={'X-Cohere-Api-Key': self.api_key}
        )
        if not self.client.is_ready():
            raise Exception("Error connecting to the database")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the Weaviate client connection when exiting the context."""
        self.client.close()

    def create_or_get_collections(self, collection: str):
        """Create or retrieve a collection in Weaviate."""
        if not self.client.collections.exists(collection):
            self.collection = self.client.collections.create(
                collection,
                reranker_config=Configure.Reranker.cohere()
            )
        else:
            self.collection = self.client.collections.get(collection)

    def delete_auth(self, collection):
        auth = input(f"Are you sure you want to delete {collection}? Y or N")
        if auth.lower == 'y':
            return True  
        return False
    
    def delete_collection(self, collection:str):
        if self.delete_auth(collection):
            self.client.collections.delete(collection)

    def ingest_data(self, Dataframe: pd.DataFrame):
        """Ingest data into the current collection."""
        with self.collection.batch.dynamic() as batch:
            for idx, row in Dataframe.iterrows():
                batch.add_object(
                    properties={
                        "name": row["title"],
                        "content": row["content"],
                        "language": row["lang"],
                        "file_type": row['file_type'],
                        "url": row.get("url", ""),
                        "upvote": 0,
                        "downvote": 0,
                        "obj_uuid": generate_uuid5(row["content"]),
                    },
                    vector=row['embeddings']
                )
        print("Success ingesting data")

    def search(self, query: str, query_embedding: list, property: dict | None):
        """Search the current collection with a hybrid query."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty or whitespace.")
        
        result = self.collection.query.hybrid(
            query= query, vector=query_embedding, limit=10
            # query_properties = ["name^2"]
            # , filters = wvc.query.Filter.by_property("file_type").equal(property["file_type"])
            # , rerank = Rerank(prop='content', query=query)
            , alpha=0.5
            , return_metadata=MetadataQuery(score=True)
            )
        
        # result = self.collection.query.hybrid(
        #     query=query,
        #     vector=query_embedding,
        #     limit=10,
        #     rerank=Rerank(prop='content', query=query),
        #     return_metadata=MetadataQuery(score=True)
        # )
        return result

    def close(self):
        """Manually close the client (optional with context manager)."""
        self.client.close()


if __name__ == "__main__":
    
    load_dotenv(dotenv_path=".env")
    with Database() as db:
        collection_name = getenv("WEAVIATE_DB")
        db.create_or_get_collections(collection_name)

        print("""Menu:
              1. Check number of object in a collection
              2. Delete collection
""")
        user_input = int(input("Option: "))
        if user_input == 1:
            agg_result = db.collection.aggregate.over_all(total_count=True)

            # Check if the collection is filled or empty
            if agg_result.total_count > 0:
                print(f"The collection '{collection_name}' is filled with {agg_result.total_count} objects.")
            else:
                print(f"The collection '{collection_name}' is empty.")

        if user_input == 2:
            db.delete_collection(collection_name)




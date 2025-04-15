import weaviate
from weaviate.classes.query import Rerank, MetadataQuery
from weaviate.classes.config import Configure
from weaviate.classes.config import Property, DataType
from weaviate.util import generate_uuid5
import weaviate.classes as wvc
from os import getenv
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from pytz import timezone

class Database:
    def __init__(self):
        """Initialize the Database with API key and null client/collection."""
        self.api_key = getenv("COHERE_APIKEY")
        self.client = None
        self.collections = {} # Name-to-collection mapping
        self.embeddings = getenv("WEAVIATE_EMBEDDINGS")
        self.vote = getenv("WEAVIATE_VOTE")

    def __enter__(self):
        """Establish connection to Weaviate when entering the context."""
        self.client = weaviate.connect_to_local(
            headers={'X-Cohere-Api-Key': self.api_key}
        )
        if not self.client.is_ready():
            raise Exception("Error connecting to the database")
        
        self.collections[self.embeddings] = self._create_or_get_embedding_collections(getenv("WEAVIATE_EMBEDDINGS"))
        self.collections[self.vote] = self._create_or_get_vote_collections(getenv("WEAVIATE_VOTE"))

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the Weaviate client connection when exiting the context."""
        self.client.close()

    def _create_or_get_embedding_collections(self, collection_name: str):
        """Create or retrieve embedding collection in Weaviate."""
        if not self.client.collections.exists(collection_name):
            collection = self.client.collections.create(collection_name, reranker_config=Configure.Reranker.cohere())
        else:
            collection = self.client.collections.get(collection_name)
        return collection
    
    def _create_or_get_vote_collections(self, collection_name: str):
        """Create or retrieve vote collection in Weaviate."""
        if not self.client.collections.exists(collection_name):
            collection = self.client.collections.create(
                collection_name,
                properties=[
                        Property(name='obj_uuid', data_type=DataType.UUID),
                        Property(name='user_id', data_type=DataType.INT),
                        Property(name='vote_type', data_type=DataType.TEXT),
                        Property(name="vote_time", data_type=DataType.DATE)
                ])
            
        else:
            collection = self.client.collections.get(collection_name)
        return collection

    def _delete_auth(self, collection):
        auth = input(f"Are you sure you want to delete {collection}? (Y or N)")
        if auth.lower() == 'y':
            return True  
        return False
    
    def delete_collection(self, collection:str):
        if self._delete_auth(collection):
            self.client.collections.delete(collection)
            print(f"{collection} deleted.")

    def ingest_data(self, Dataframe: pd.DataFrame):
        """Ingest data into the current collection."""
        with self.collections.get(self.embeddings).batch.dynamic() as batch:
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
                        "last_interaction": datetime.now(timezone("Asia/Chongqing")),
                        "obj_uuid": generate_uuid5(row['content']), # to ensure no duplicates
                    },
                    vector=row['embeddings']
                )
        print("Success ingesting data")

    def update_vote(self, obj_uuid, user_id, vote:str):
        """Update the number of vote and last_interaction"""

        """
        1. Check if object exist in embeddings collection
        2. Check if user already voted for that object
        2.1 if already check if it is a diffrent vote, if it is then update in the vote collection and the count in the embeddings collection
        2.2 if the user haven't voted yet, create a new vote object in the vote collection and update the count in embeddings collection
        """
        # Check if object exist
        response = self.collections.get(self.embeddings).query.fetch_objects(filters = wvc.query.Filter.by_property("obj_uuid").equal(obj_uuid))
        if not response:
            raise LookupError(f"No object found with UUID {obj_uuid}")
        
        vote_response = self.collections.get(self.vote).query.fetch_objects(filters = (
            wvc.query.Filter.all_of([
                wvc.query.Filter.by_property("obj_uuid").equal((obj_uuid)),
                wvc.query.Filter.by_property("user_id").equal(user_id)
                ])
            ))
        # print(vote_response)
        if vote_response.objects:
            # Update vote type
            existing_vote = vote_response.objects[0]
            old_vote_type = existing_vote.properties['vote_type']
            if old_vote_type == vote:
                return (-1, -1)
            self.collections.get(self.vote).data.update(uuid = existing_vote.uuid, properties = {"vote_type": vote, "vote_time": datetime.now("Asia/Chongqing")})
        else:
            self.collections.get(self.vote).data.insert({"obj_uuid": obj_uuid, "user_id": user_id, "vote_type": vote, "vote_time": datetime.now("Asia/Chongqing")})

        response = response.objects[0]
        upvote = response.properties['upvote']
        downvote = response.properties['downvote']
        if vote == 'up':
            upvote += 1
            downvote -= 1
        else:
            upvote -=1
            downvote += 1
        # Ensure counts don't go negative
        upvote = max(upvote, 0)
        downvote = max(downvote, 0)
        self.collections.get(self.embeddings).data.update(uuid = response.uuid, properties = {"upvote": upvote, "downvote": downvote, "last_interaction": datetime.now("Asia/Chongqing")})
        return (upvote, downvote)
            

    def search(self, query: str, query_embedding: list, property: dict | None, rerank: bool = False):
        """Search the current collection with a hybrid query."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty or whitespace.")
        
        if rerank:
            result = self.collections.get(self.embeddings).query.hybrid(
                query= query, vector=query_embedding, limit=5
                # , filters = (
                #     wvc.query.Filter.all_of([
                #         wvc.query.Filter.by_property("file_type").equal(property["file_type"]),
                #         wvc.query.Filter.by_property("language").equal(property['language'])
                #         ]))
                , rerank = Rerank(prop='content', query=query)
                , alpha=0.5
                , return_metadata=MetadataQuery(score=True)
                )
        else:
            result = self.collections.get(self.embeddings).query.hybrid(
                query= query, vector=query_embedding, limit=5
                # , filters = (
                #     wvc.query.Filter.all_of([
                #         wvc.query.Filter.by_property("file_type").equal(property["file_type"]),
                #         wvc.query.Filter.by_property("language").equal(property['language'])
                #         ]))
                , alpha=0.5
                , return_metadata=MetadataQuery(score=True)
                )
        return result

    def close(self):
        """Manually close the client (optional with context manager)."""
        self.client.close()


if __name__ == "__main__":
    
    load_dotenv(dotenv_path=".env")
    embedding_collection = getenv("WEAVIATE_EMBEDDINGS")
    vote_collection = getenv("WEAVIATE_VOTE")
    with Database() as db:
        print(f"""Menu:
              1. Check number of object in {embedding_collection} collection
              2. Check number of object in {vote_collection} collection
              3. Delete collection
              4. Add vote to vote collection
""")
        user_input = int(input("Option: "))
        # user_input = 5
        
        if user_input == 1:
            agg_result = db.collections.get(embedding_collection).aggregate.over_all(total_count=True)

            # Check if the collection is filled or empty
            if agg_result.total_count > 0:
                print(f"The collection '{embedding_collection}' is filled with {agg_result.total_count} objects.")
            else:
                print(f"The collection '{embedding_collection}' is empty.")

        elif user_input == 2:
            
            agg_result = db.collections.get(vote_collection).aggregate.over_all(total_count=True)

            # Check if the collection is filled or empty
            if agg_result.total_count > 0:
                print(f"The collection '{vote_collection}' is filled with {agg_result.total_count} objects.")
            else:
                print(f"The collection '{vote_collection}' is empty.")

        elif user_input == 3:
            option = input(f"Input the collection name to delete: 1. {embedding_collection}\n2.{vote_collection}")
            if option == 1:
                delete = embedding_collection
            else:
                delete = vote_collection
            db.delete_collection(delete)
        
        elif user_input == 4:
            db.update_vote("34aecf05-01ff-5ab8-a0bc-d1c8e6795d64", 2, "up")
import weaviate
from weaviate.classes.query import Rerank, MetadataQuery
from weaviate.classes.config import Configure, Property, DataType
from weaviate.util import generate_uuid5
import weaviate.classes as wvc
from os import getenv
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from pytz import timezone
import math
from collections import defaultdict

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
        counter = 0
        interval = 1000  # print progress every this many records; should be bigger than the batch_size
        with self.collections.get(self.embeddings).batch.fixed_size(batch_size=100) as batch:
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
                    },
                    uuid = generate_uuid5(row), # Deterministic UUIDs to prevent duplicate entries
                    vector=row['embeddings']
                )
                # Calculate and display progress
                counter += 1
                if counter % interval == 0:
                    print(f"Imported {counter} articles...")

    def update_vote(self, obj_uuid, user_id, vote:str):
        """Update the number of vote and last_interaction"""

        """
        1. Check if object exist in embeddings collection
        2. Check if user already voted for that object
        2.1 if already check if it is a diffrent vote, if it is then update in the vote collection and the count in the embeddings collection
        2.2 if the user haven't voted yet, create a new vote object in the vote collection and update the count in embeddings collection
        """
        # Check if object exist
        response = self.collections.get(self.embeddings).query.fetch_object_by_id(obj_uuid)
        if not response:
            raise LookupError(f"No object found with UUID {obj_uuid}")
        
        vote_collection = self.collections.get(self.vote)
        filters = (
            wvc.query.Filter.by_property("obj_uuid").equal(obj_uuid) &
            wvc.query.Filter.by_property("user_id").equal(user_id)
        )
        vote_response = vote_collection.query.fetch_objects(filters=filters, limit=1)
        existing_vote = vote_response.objects[0] if vote_response.objects else None

        if existing_vote:
            old_vote = existing_vote.properties['vote_type']
            if old_vote == vote:
                return (-1, -1)  # No change needed
            # Update existing vote
            vote_collection.data.update(
                uuid=existing_vote.uuid,
                properties={
                    "vote_type": vote,
                    "vote_time": datetime.now(timezone("Asia/Chongqing"))
                }
            )
            upvote = response.properties['upvote']
            downvote = response.properties['downvote']
            if old_vote == 'up':
                upvote -= 1
            else:
                downvote -= 1

        # if vote_response.objects:
        #     # Update vote type
        #     existing_vote = vote_response.objects[0]
        #     old_vote_type = existing_vote.properties['vote_type']
        #     if old_vote_type == vote:
        #         return (-1, -1)
        #     self.collections.get(self.vote).data.update(uuid = existing_vote.uuid, properties = {"vote_type": vote, "vote_time": datetime.now(timezone("Asia/Chongqing"))})
        else:
            vote_collection.data.insert(
            properties={
                "obj_uuid": obj_uuid,
                "user_id": user_id,
                "vote_type": vote,
                "vote_time": datetime.now(timezone("Asia/Chongqing"))
            }
            )
            upvote = response.properties['upvote']
            downvote = response.properties['downvote']
        
        if vote == 'up':
            upvote += 1
        else:
            downvote += 1
        # Ensure counts don't go negative
        upvote = max(upvote, 0)
        downvote = max(downvote, 0)
        self.collections.get(self.embeddings).data.update(
            uuid=obj_uuid,
            properties={
                "upvote": upvote,
                "downvote": downvote,
                "last_interaction": datetime.now(timezone("Asia/Chongqing"))
            }
        )
        return (upvote, downvote)
            

    def search(self, query: str, query_embedding: list, property: dict | None, alpha: int = 0.7):
        """Search the current collection with a hybrid query."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty or whitespace.")
        result = self.collections.get(self.embeddings).query.hybrid(
            query= query, vector=query_embedding, limit=10
            # , filters = (
            #     wvc.query.Filter.all_of([
            #         wvc.query.Filter.by_property("file_type").equal(property["file_type"]),
            #         wvc.query.Filter.by_property("language").equal(property['language'])
            #         ]))
            , rerank = Rerank(prop='content', query=query)
            , alpha=alpha
            , return_metadata=MetadataQuery(score=True)
            )
            
        # 2. Identify objects needing decay processing
        threshold = 5
        decay_candidates = [
            obj.uuid for obj in result.objects
            if (obj.properties["upvote"] + obj.properties["downvote"]) > threshold
        ]

        # 3. Batch fetch decayed scores for qualifying objects
        decayed_scores = self._batch_get_decayed_scores(decay_candidates) if decay_candidates else {}

        # 4. Calculate final scores
        ranked_results = []
        for obj in result.objects:
            total_votes = obj.properties["upvote"] + obj.properties["downvote"]
            
            # Only consider votes if they pass threshold
            if total_votes > threshold:
                vote_score = decayed_scores.get(obj.uuid, {"up": 0, "down": 0})
                net_votes = vote_score["up"] - vote_score["down"]
            else:
                net_votes = 0  # Ignore votes below threshold

            if total_votes > 5:
                combined_score = 0.7 * obj.metadata.rerank_score + 0.3 * net_votes
            else:
                combined_score = obj.metadata.rerank_score  # Full weight to search relevance
            
            ranked_results.append({
                "object": obj,
                "combined_score": combined_score,
                "vote_used": total_votes > threshold
            })

        # 5. Return top 5 results
        return sorted(ranked_results, key=lambda x: x["combined_score"], reverse=True)[:5]

    def _batch_get_decayed_scores(self, uuids: list) -> dict:
        """Batch process decayed scores for multiple objects"""
        if not uuids:
            return {}

        HALF_LIFE_DAYS = 7  # Adjust this value to control decay speed
        LAMBDA = math.log(2) / (HALF_LIFE_DAYS * 24)  # Hourly decay rate
        now = datetime.now(timezone("Asia/Chongqing"))

        # Fetch all votes for target objects
        votes = self.collections.get(self.vote).query.fetch_objects(
            filters=wvc.query.Filter.by_property("obj_uuid").contains_any(uuids),
            return_properties=["obj_uuid", "vote_type", "vote_time"],
            limit=10000
        ).objects

        # Calculate decayed scores
        scores = defaultdict(lambda: {"up": 0.0, "down": 0.0})
        for vote in votes:
            obj_uuid = vote.properties["obj_uuid"]
            age_hours = (now - vote.properties["vote_time"]).total_seconds() / 3600
            decay = math.exp(-LAMBDA * age_hours)
            
            if vote.properties["vote_type"] == "up":
                scores[obj_uuid]["up"] += decay
            else:
                scores[obj_uuid]["down"] += decay

        return dict(scores)

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
            option = int(input(f"Input the collection name to delete: 1. {embedding_collection}\n2.{vote_collection}"))
            if option == 1:
                delete = embedding_collection
            else:
                delete = vote_collection
            db.delete_collection(delete)
        
        elif user_input == 4:
            db.update_vote("34aecf05-01ff-5ab8-a0bc-d1c8e6795d64", 2, "up")
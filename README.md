# AI-Based Learning System

This project is an AI-based learning system that provides personalized content recommendations to users. It uses a FastAPI backend, a Weaviate vector database for storing and searching content, and a sentence transformer model for generating embeddings.

## Features

- **User Authentication:** Secure user login and registration.
- **Personalized Recommendations:** Content recommendations based on user queries and preferences (language, file type).
- **Hybrid Search:** Combines keyword-based search with semantic vector search for more relevant results.
- **Reranking:** Improves search result ranking using Cohere's reranker.
- **Voting System:** Allows users to upvote or downvote content, influencing future recommendations.
- **Score Decay:** Implements a time-based decay for vote scores to keep recommendations fresh.
- **Profile Management:** Users can set and update their content preferences.
- **Data Ingestion:** Scripts for preprocessing and ingesting data from various sources (JSON, CSV) into the Weaviate database.


## Project Structure

```
.
├── app.py                  # Main FastAPI application
├── weaviate_db.py          # Weaviate database interaction logic
├── models.py               # SQLAlchemy data models (User, Session, Preference)
├── Preprocess.py           # Data preprocessing and embedding generation
├── data_ingestion.py       # Script for ingesting preprocessed data into Weaviate
├── security.py             # Password hashing and session validation
├── recommendation.db       # SQLite database for user and session data
├── static/                 # Frontend static files (HTML, CSS, JS)
├── web_scraper/            # Scripts for web scraping data
├── testing/                # Test scripts
    ├── results/                # Output from test scripts
├── weaviate_data/          # Weaviate local data storage
├── values.yaml             # Configuration file for weaviate kubernetes deployment
```

## Core Components

### 1. FastAPI Application (`app.py`)
- Handles HTTP requests for user authentication (signup, login, logout).
- Serves static frontend files.
- Provides API endpoints for:
    - Getting and updating user preferences.
    - Fetching content recommendations based on user input and preferences.
    - Recording user votes on content.
- Loads the sentence transformer model for encoding user queries.
- Interacts with `weaviate_db.py` for search and `models.py` for user data.

### 2. Weaviate Database (`weaviate_db.py`)
- Manages connection to the Weaviate vector database.
- Creates and manages two Weaviate collections:
    - `embeddings`: Stores content data (title, content, language, file type, URL, upvotes, downvotes, last interaction timestamp) and their vector embeddings.
    - `vote`: Stores individual user votes (object UUID, user ID, vote type, timestamp).
- **Data Ingestion (`ingest_data`):**
    - Takes a Pandas DataFrame with precomputed embeddings.
    - Adds data to the `embeddings` collection with deterministic UUIDs to prevent duplicates.
- **Search Functionality (`search`):**
    - Performs a hybrid search using both the query string and its vector embedding.
    - Filters results based on user's language and file type preferences.
    - Uses Cohere's reranker (`Rerank(prop='content', query=query)`) to improve relevance.
    - Implements a scoring mechanism that combines the reranker score with a net vote score (upvotes - downvotes).
    - **Score Decay (`_batch_get_decayed_scores`):** Vote scores decay over time (half-life of 7 days by default) to prioritize more recently interacted-with content. A vote's influence diminishes exponentially based on its age. Votes for items with few interactions (below a threshold of 5 total votes) are not heavily weighted in the combined score.
- **Vote Update (`update_vote`):**
    - Records a user's upvote or downvote for a specific content item.
    - Updates the vote counts in the `embeddings` collection and records the individual vote in the `vote` collection.
    - Handles cases where a user changes their vote.

### 3. Data Models (`models.py`)
- Defines SQLAlchemy models for:
    - `User`: Stores user ID, username, and hashed password.
    - `UserSession`: Stores session tokens, linking them to user IDs with a creation timestamp.
    - `Preference`: Stores user-specific preferences like preferred file type and language.
- Uses SQLite (`recommendation.db`) as the database for these models.

### 4. Data Preprocessing (`Preprocess.py`)
- Loads datasets from various JSON and CSV files.
- **Preprocessing Steps:**
    - Normalizes language codes (e.g., 'en', 'zh-cn').
    - Renames columns for consistency.
    - Removes rows with empty content.
    - **Deduplication:** Generates SHA256 hashes of content to remove duplicate entries.
    - Adds 'lang' and 'file_type' columns.
- **Embedding Generation (`get_embeddings`):**
    - Uses the `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` model.
    - Tokenizes content and splits it into chunks (max 126 tokens).
    - Generates embeddings for each chunk.
    - Averages chunk embeddings to get a single embedding for each content item.
- The main script loads data, preprocesses it, generates embeddings, and saves the result to `Embeddings.parquet`.

### 5. Data Ingestion (`data_ingestion.py`)
- Loads the preprocessed data and embeddings from `Embeddings.parquet`.
- Uses `weaviate_db.Database` to ingest this data into the Weaviate `embeddings` collection.

### 6. Security (`security.py`)
- Provides functions for:
    - Hashing passwords (`get_password_hash`).
    - Verifying passwords (`verify_password`).
    - Creating secure session tokens (`create_session_token`).
    - Validating session tokens and retrieving user IDs (`validate_session`).

## Setup and Running

(Instructions would typically go here - e.g., how to install dependencies, set up environment variables, run the FastAPI server, and ingest data. This would depend on your specific project setup like `requirements.txt` or `Pipfile`, and how environment variables are managed, e.g., via a `.env` file.)

### Prerequisites:
- Python 3.x
- Weaviate instance (local or cloud)
- Cohere API Key (for reranking)

### Environment Variables:
Create a `.env` file in the root directory with the following (example values):
```
COHERE_APIKEY=your_cohere_api_key
WEAVIATE_EMBEDDINGS=EmbeddingsCollectionName  # e.g., MyEmbeddings
WEAVIATE_VOTE=VoteCollectionName              # e.g., MyVotes
```

### Installation:
(Assuming you have a `requirements.txt`)
```bash
pip install -r requirements.txt
```

### Running the Application:
1.  **Ensure Weaviate is running and accessible.**
2.  **Ingest Data (if not already done):**
    ```bash
    python Preprocess.py  # This will generate Embeddings.parquet
    python data_ingestion.py
    ```
3.  **Start the FastAPI server:**
    ```bash
    uvicorn app:app --host 0.0.0.0 --port 1234 --reload
    ```
    The application will be accessible at `http://localhost:1234`.

## Future Improvements / Considerations
- Add more comprehensive error handling and logging.
- Implement unit and integration tests.
- Frontend development for a richer user interface.
- Explore different embedding models or fine-tuning.
- More sophisticated cold-start problem handling for new users or content.
- Scalability considerations for a larger user base and dataset.
- CI/CD pipeline for automated testing and deployment.
- Detailed API documentation (e.g., using Swagger/OpenAPI).

---

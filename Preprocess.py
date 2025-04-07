from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import torch
import pandas as pd
from weaviate_db import Database
import pyarrow.parquet as pq
import asyncio
import linecache
import numpy as np
import tracemalloc
_model = None


def display_top(snapshot, key_type='lineno', limit=10): #for debugging, remove in production
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        print("#%s: %s:%s: %.1f KiB"
              % (index, frame.filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))

def load_dataset() -> pd.DataFrame:
    try:
        dir = 'dataset'
        data1 = pd.read_csv(f'{dir}/supervisor-dataset-new.csv')
        data2 = pd.read_json(f'{dir}/w3schools.json')
        data3 = pd.read_json(f'{dir}/geeksforgeeks.json')
        data4 = pd.read_json(f'{dir}/w3cschools.json')

    except Exception as e:
        print(e)

    return data1, data2, data3, data4

tracemalloc.start()

async def preprocess_spv_dataset(df) -> pd.DataFrame:
    for index in [3,37,38,46,55,56,71,79,80,81,83,85,87,89,94,95,96]:
        df.at[index, 'lang'] = 'zh-cn'
    df =df.rename(columns={"name":"title"})
    return df

async def preprocess_w3schools(df) -> pd.DataFrame:
    df= df.drop(['timestamp', "Source"], axis =1)
    df = df[~df['url'].str.contains('geeksforgeeks', na=False)]
    df["lang"] = "en"
    df['file_type'] = 'html'
    return df
    
async def preprocess_geeksforgeeks(df: pd.DataFrame) -> pd.DataFrame:
    df= df.drop(['timestamp', "Source"], axis =1)
    # drop empty rows
    df = df.dropna()
    df= df[df['content'] != ""] # drop empty content rows
    df["lang"] = "en"
    df['file_type'] = 'html'
    return df

async def preprocess_w3cschools(df: pd.DataFrame) -> pd.DataFrame:
    df= df.dropna()
    df= df[df['content'] != ""] # drop empty content rows
    df["lang"] = "zh-cn"
    df['file_type'] = 'html'
    df = df.drop(['timestamp', 'section_titles'], axis=1)
    return df

def load_model_once()-> SentenceTransformer:
    global _model
    if _model is None:
        _model = load_model()  # Initialize only once
    return _model

def load_model() -> SentenceTransformer:
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = model.to(device)
    return model


def get_embeddings(df):
    """Generate embeddings for text chunks with batching"""
    # Collect all chunks and track their content indices
    model = load_model_once()
    tokenizer = model.tokenizer
    all_chunk_texts = []
    content_indices = []
    for idx, content in enumerate(df['content']):
        token_ids = tokenizer.encode(content, add_special_tokens=False)
        chunks = [token_ids[i:i + 126] for i in range(0, len(token_ids), 126)]
        chunk_texts = [tokenizer.decode(chunk) for chunk in chunks]
        all_chunk_texts.extend(chunk_texts)
        content_indices.extend([idx] * len(chunk_texts))

    # Encode all chunks in one batch
    all_embeddings = model.encode(all_chunk_texts, convert_to_tensor=False, truncation=True)  # Returns numpy array

    # Compute average embedding per content
    content_embeddings = []
    for idx in range(len(df)):
        idx_mask = np.array(content_indices) == idx
        if idx_mask.any():
            content_embedding = np.mean(all_embeddings[idx_mask], axis=0)
        else:
            content_embedding = np.zeros(model.get_sentence_embedding_dimension())
        content_embeddings.append(content_embedding)
    return content_embeddings


async def load_and_preprocess():
    spv_dataset, w3schools, geeksforgeeks, w3cschools = load_dataset()
    results = await asyncio.gather(preprocess_spv_dataset(spv_dataset), 
                                   preprocess_w3schools(w3schools), 
                                   preprocess_geeksforgeeks(geeksforgeeks),
                                   preprocess_w3cschools(w3cschools)
                                   )    
    return results
    
if __name__ == "__main__":
    load_dotenv(dotenv_path=".env")
    
    print("Preprocessing dataset...")
    supervisor_dataset, w3schools, geeksforgeeks, w3cschools = asyncio.run(load_and_preprocess())
    Dataframe = pd.concat([supervisor_dataset,w3schools, geeksforgeeks, w3cschools])
    print("Creating embeddings for dataset..")

    Dataframe['embeddings'] = get_embeddings(Dataframe)
    # Convert embeddings to lists for Parquet compatibility
    Dataframe['embeddings'] = Dataframe['embeddings'].apply(lambda x: x.tolist())
    
    with Database() as db:
        db.create_or_get_collections("Embeddings_new_preprocess")
        db.ingest_data(Dataframe, Dataframe['embeddings'])
    
    snapshot = tracemalloc.take_snapshot()
    display_top(snapshot)

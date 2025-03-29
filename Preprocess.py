from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import torch
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from io import StringIO
from weaviate_db import Database
import asyncio
import linecache
import numpy as np
import tracemalloc
MAX_TOKEN = 512
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


def auth():
    gauth = GoogleAuth()
    scope = ["https://www.googleapis.com/auth/drive"]
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name('service-account-credentials.json', scope)
    drive = GoogleDrive(gauth)
    return drive

def load_dataset() -> pd.DataFrame:
    # connect to google drive
    drive = auth()

    try:
        # Dataset 1
        file_id = "1nBVPsULN_2gN_UbplA6AfVCNfyiilafG"
        csv_file = drive.CreateFile({"id": file_id})
        csv_content = csv_file.GetContentString()
        data1 = pd.read_csv(StringIO(csv_content))

        # w3schools
        file_id = "1qLFb_vxWYE_G2GPggqeiOwpbq5HqEjNt"
        json_file = drive.CreateFile({'id': file_id})
        json_content = json_file.GetContentString()  # Fetch content as a string
        data2 = pd.read_json(StringIO(json_content))

        # geeksforgeeks
        file_id = "1Gw-ZDNl4kZZ9v0iX8bYJ8_nfPhpOncYF"
        json_file = drive.CreateFile({'id': file_id})
        json_content = json_file.GetContentString()  # Fetch content as a string
        data3 = pd.read_json(StringIO(json_content))

        file_id = "1NfYyEU6Z7c08kDE7t9aXNThX4zErCFAZ"
        json_file = drive.CreateFile({'id': file_id})
        json_content = json_file.GetContentString()  # Fetch content as a string
        data4 = pd.read_json(StringIO(json_content))

    finally:
        del csv_file
        del json_file
        del drive  # Remove reference to GoogleDrive object

    return data1, data2, data3, data4

tracemalloc.start()

async def preprocess_spv_dataset(df) -> pd.DataFrame:
    for index in [3,37,38,46,55,56,71,79,80,81,83,85,87,89,94,95,96]:
        df.at[index, 'lang'] = 'zh-cn'
    df =df.rename(columns={"name":"title"})

    model = load_model_once()
    df['weighted_content'] = df['title'] + ' .' + df['content']
    # Tokenize all content in one go using list comprehension
    contents = df['weighted_content'].tolist()
    tokenized = [model.tokenize(c) for c in contents]

    # Create truncation mask and process truncations
    truncate_mask = [len(t) > MAX_TOKEN for t in tokenized]
    truncated_strings = [model.convert_tokens_to_string(t[:MAX_TOKEN]) for i, t in enumerate(tokenized) if truncate_mask[i]]

    # Update dataframe using mask
    df.loc[truncate_mask, 'weighted_content'] = truncated_strings

    return df

async def preprocess_w3schools(df) -> pd.DataFrame:
    df= df.drop(['timestamp', "Source"], axis =1)
    df = df[~df['url'].str.contains('geeksforgeeks', na=False)]
    df["lang"] = "en"
    df['file_type'] = 'html'

    model = load_model_once()
    df['weighted_content'] = df['title'] + ' .' + df['content']
    # Tokenize all content in one go using list comprehension
    contents = df['weighted_content'].tolist()
    tokenized = [model.tokenize(c) for c in contents]

    # Create truncation mask and process truncations
    truncate_mask = [len(t) > MAX_TOKEN for t in tokenized]
    truncated_strings = [model.convert_tokens_to_string(t[:MAX_TOKEN]) for i, t in enumerate(tokenized) if truncate_mask[i]]

    # Update dataframe using mask
    df.loc[truncate_mask, 'weighted_content'] = truncated_strings

    return df
    
async def preprocess_geeksforgeeks(df: pd.DataFrame) -> pd.DataFrame:
    df= df.drop(['timestamp', "Source"], axis =1)
    # drop empty rows
    df = df.dropna()
    df= df[df['content'] != ""] # drop empty content rows
    df["lang"] = "en"
    df['file_type'] = 'html'

    model = load_model_once()
    df['weighted_content'] = df['title'] + ' .' + df['content']
    # Tokenize all content in one go using list comprehension
    contents = df['weighted_content'].tolist()
    tokenized = [model.tokenize(c) for c in contents]

    # Create truncation mask and process truncations
    truncate_mask = [len(t) > MAX_TOKEN for t in tokenized]
    truncated_strings = [model.convert_tokens_to_string(t[:MAX_TOKEN]) for i, t in enumerate(tokenized) if truncate_mask[i]]

    # Update dataframe using mask
    df.loc[truncate_mask, 'weighted_content'] = truncated_strings
    return df

async def preprocess_w3cschools(df: pd.DataFrame) -> pd.DataFrame:
    df= df.dropna()
    df= df[df['content'] != ""] # drop empty content rows
    df["lang"] = "zh-cn"
    df['file_type'] = 'html'

    df['weighted_content'] = (df['title'] + ' . ' + df['section_titles'].apply(", ".join) + ' . ' + df['content'])
    
    df = df.drop(['timestamp', 'section_titles'], axis=1)

    model = load_model_once()
    contents = df['weighted_content'].tolist()
    tokenized = [model.tokenize(c) for c in contents]

    # Create truncation mask and process truncations
    truncate_mask = [len(t) > MAX_TOKEN for t in tokenized]
    truncated_strings = [model.convert_tokens_to_string(t[:MAX_TOKEN]) for i, t in enumerate(tokenized) if truncate_mask[i]]

    # Update dataframe using mask
    df.loc[truncate_mask, 'weighted_content'] = truncated_strings
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

def embed_dataset(model: SentenceTransformer, df: pd.DataFrame) -> np.ndarray:
    batch_size = 32
    num_sentences = len(df)
    embedding_dim = model.get_sentence_embedding_dimension()  # Model-specific method
    embeddings_np = np.zeros((num_sentences, embedding_dim), dtype=np.float32)

    for i in range(0, num_sentences, batch_size):
        batch_sentences = df['weighted_content'].iloc[i:i + batch_size].tolist()
        batch_embeddings = model.encode(batch_sentences, convert_to_tensor=True, normalize_embeddings=True)
        embeddings_np[i:i + batch_size] = batch_embeddings.cpu().numpy()
    
    return embeddings_np

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
    with Database() as db:
        db.create_or_get_collections("Embeddings")
    
        model = load_model_once()
        supervisor_dataset, w3schools, geeksforgeeks, w3cschools = asyncio.run(load_and_preprocess())
        Dataframe = pd.concat([supervisor_dataset,w3schools, geeksforgeeks, w3cschools])

        embedding_list = embed_dataset(model, Dataframe)
        db.ingest_data(Dataframe, embedding_list)
    
    snapshot = tracemalloc.take_snapshot()
    display_top(snapshot)

from sentence_transformers import SentenceTransformer
import torch
import pandas as pd
import asyncio
import numpy as np
from tqdm.auto import tqdm
import hashlib
_model = None

def load_dataset():
    try:
        geeksforgeeks = pd.read_json("dataset/geeksforgeeks.json")
        pytorch_cn = pd.read_json("dataset/pytorch-cn-merged.json")
        pytorch = pd.read_json("dataset/pytorch.json")
        scikit = pd.read_json("dataset/scikit-learn.json")
        spv_dataset = pd.read_csv("dataset/supervisor-dataset-new.csv")
        tensorflow = pd.read_json("dataset/tensorflow_merged-en.json")
        tensorflow_cn = pd.read_json("dataset/tensorflow-zh-cn.json")
        w3cschools = pd.read_json("dataset/w3cschools.json")
        w3schools = pd.read_json("dataset/w3schools.json")
            
    except Exception as e:
        print(e)

    return geeksforgeeks, pytorch_cn, pytorch, scikit, spv_dataset, tensorflow, tensorflow_cn, w3cschools, w3schools

# Generate a hash for each content string
def generate_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

async def preprocess_spv_dataset(df) -> pd.DataFrame:
    df['lang'] = df['lang'].str.lower()  # Normalize to lowercase
    df.loc[~df['lang'].isin(['en', 'zh-cn']), 'lang'] = 'zh-cn'
    df =df.rename(columns={"name":"title"})
    return df

async def preprocess_dataframe(df:pd.DataFrame, column_to_drop: list, lang:str = 'en', file_type:str='html'):
    """
    Args:
        df(pd.Dataframe): Dataframe to be preprocessed
        column_to_drop(list): List of columns to be dropped
        lang(str): Language of the dataframe, Either en or zh-cn
        file_type(str): Type of the source of the dataframe

    Return:
        df(pd.Dataframe): The cleaned dataframe
    """
    df= df.dropna()
    df= df[df['content'] != ""] # drop empty content rows
    df['hash'] = df['content'].apply(generate_hash)
    df = df.drop_duplicates(subset='hash', keep='first').drop(columns='hash')
    df = df.drop(column_to_drop, axis=1)
    df['lang']= lang
    df['file_type'] = file_type
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
    """Generate embeddings for text chunks with batching and progress tracking"""
    model = load_model_once()
    tokenizer = model.tokenizer
    all_chunk_texts = []
    content_indices = []
    
    # Tokenize and chunk all content
    print("Preprocessing content...")
    for idx, content in tqdm(enumerate(df['content']), total=len(df), desc="Tokenizing"):
        token_ids = tokenizer.encode(content, add_special_tokens=False)
        chunks = [token_ids[i:i + 126] for i in range(0, len(token_ids), 126)]
        chunk_texts = [tokenizer.decode(chunk) for chunk in chunks]
        all_chunk_texts.extend(chunk_texts)
        content_indices.extend([idx] * len(chunk_texts))

    batch_size = 32  # Adjust based on your GPU memory
    all_embeddings = []
    
    print("Generating embeddings...")
    for i in tqdm(range(0, len(all_chunk_texts), batch_size), desc="Embedding"):
        batch_texts = all_chunk_texts[i:i+batch_size]
        batch_embeddings = model.encode(
            batch_texts,
            convert_to_tensor=False,
            truncation=True,
            show_progress_bar=False  # Disable internal progress bar
        )
        all_embeddings.append(batch_embeddings)
    
    all_embeddings = np.concatenate(all_embeddings)

    # Compute average embeddings with progress
    content_embeddings = []
    print("Aggregating results...")
    for idx in tqdm(range(len(df)), desc="Averaging"):
        idx_mask = np.array(content_indices) == idx
        if idx_mask.any():
            content_embedding = np.mean(all_embeddings[idx_mask], axis=0)
        else:
            content_embedding = np.zeros(model.get_sentence_embedding_dimension())
        content_embeddings.append(content_embedding)
        
    return content_embeddings


async def load_and_preprocess():
    geeksforgeeks, pytorch_cn, pytorch, scikit, spv_dataset, tensorflow, tensorflow_cn, w3cschools, w3schools = load_dataset()
    results = await asyncio.gather(
        preprocess_dataframe(geeksforgeeks, ['timestamp', "Source"]),
        preprocess_dataframe(pytorch_cn, ['timestamp'], 'zh-cn'),
        preprocess_dataframe(pytorch, ['timestamp']),
        preprocess_dataframe(scikit, ['timestamp']),
        preprocess_spv_dataset(spv_dataset),
        preprocess_dataframe(tensorflow, ['timestamp']),
        preprocess_dataframe(tensorflow_cn, ['timestamp'], 'zh-cn'),
        preprocess_dataframe(w3cschools, ['timestamp', 'section_titles'], 'zh-cn'),
        preprocess_dataframe(w3schools, ['timestamp', 'Source']),
                                   )    
    return pd.concat(results)
    
if __name__ == "__main__":
    print("Preprocessing dataset...")
    Dataframe = asyncio.run(load_and_preprocess())
    print("Creating embeddings for dataset..")
    Dataframe['embeddings'] = get_embeddings(Dataframe)
    # Convert embeddings to lists for Parquet compatibility
    Dataframe['embeddings'] = Dataframe['embeddings'].apply(lambda x: x.tolist())
    Dataframe.to_parquet("Embeddings.parquet", engine="pyarrow")

    
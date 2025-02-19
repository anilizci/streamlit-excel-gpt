# chunked_embeddings.py

import openai
import numpy as np

def split_text(text, chunk_size=300, overlap=50):
    """
    Splits 'text' into chunks of roughly 'chunk_size' words,
    with 'overlap' words carried over between consecutive chunks.
    Increased chunk_size from 200 -> 300 for more context.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        # Move start forward by chunk_size - overlap
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

def get_embedding(text, model="text-embedding-ada-002"):
    """
    Returns the embedding vector for the given text using OpenAI's Embedding API.
    """
    response = openai.Embedding.create(input=[text], model=model)
    embedding = response['data'][0]['embedding']
    return embedding

def cosine_similarity(vec1, vec2):
    """
    Computes the cosine similarity between two vectors.
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def create_embeddings_for_chunks(chunks):
    """
    For each text chunk, compute its embedding and store both in a list.
    Returns a list of dicts: [{ "chunk": chunk_text, "embedding": [...] }, ...]
    """
    embeddings = []
    for chunk in chunks:
        emb = get_embedding(chunk)
        embeddings.append({
            "chunk": chunk,
            "embedding": emb
        })
    return embeddings

def find_top_n_chunks(query, embeddings, n=2):
    """
    Computes the embedding of 'query' and finds the top 'n' most similar chunks.
    Returns a list of (similarity_score, chunk_text) sorted descending by score.
    """
    query_embedding = get_embedding(query)
    scored = []
    for item in embeddings:
        similarity = cosine_similarity(query_embedding, item["embedding"])
        scored.append((similarity, item["chunk"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:n]

def ask_gpt(query, combined_chunks):
    """
    Calls GPT using a prompt that instructs it to answer ONLY with the provided chunks.
    combined_chunks is a string that merges the top N chunks.
    """
    if not combined_chunks.strip():
        return "I don't have information on that."

    # More direct instructions for GPT
    system_msg = (
        "You are an AI assistant. Your answers must be factual, concise, and well-structured. "
        "Use bullet points or short paragraphs where appropriate. If you cannot find relevant info "
        "in the snippet, reply with 'I don't have information on that.' "
        "Always include the disclaimer at the end of your answer."
    )

    user_prompt = (
        f"You have the following relevant excerpts from the knowledge base. "
        f"Use only these excerpts to answer the user's question. If the excerpts "
        f"do not answer the question, say: 'I don't have information on that.'\n\n"
        f"Excerpts:\n{combined_chunks}\n\n"
        f"User's question: {query}\n\n"
        "Answer in short, structured paragraphs or bullet points:\n"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",  # If you have GPT-4 access; else "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,  # Adjust for more or less creativity
        max_tokens=500
    )
    answer = response['choices'][0]['message']['content']
    return answer

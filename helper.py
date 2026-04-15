from sklearn.metrics.pairwise import cosine_similarity
from model.embedding import get_embedding
import numpy as np

def find_best_match(user_input, questions):
    user_vec = get_embedding(user_input).numpy()

    scores = []

    for q in questions:
        q_vec = get_embedding(q).numpy()
        score = cosine_similarity(user_vec, q_vec)[0][0]
        scores.append(score)

    best_index = np.argmax(scores)
    best_score = scores[best_index]

    return best_index, best_score
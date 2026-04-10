from __future__ import annotations

from functools import lru_cache

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from sentence_transformers import SentenceTransformer


TOXICITY_MODEL_NAME = "cooperleong00/deberta-v3-large_toxicity-scorer"
EMOTION_MODEL_NAME = "j-hartmann/emotion-english-distilroberta-base"
SIMILARITY_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_toxicity_components() -> tuple[AutoTokenizer, AutoModelForSequenceClassification, torch.device]:
    tokenizer = AutoTokenizer.from_pretrained(TOXICITY_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(TOXICITY_MODEL_NAME)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return tokenizer, model, device


@lru_cache(maxsize=1)
def get_emotion_components() -> tuple[AutoTokenizer, AutoModelForSequenceClassification, torch.device]:
    tokenizer = AutoTokenizer.from_pretrained(EMOTION_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(EMOTION_MODEL_NAME)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return tokenizer, model, device


@lru_cache(maxsize=1)
def get_similarity_model() -> SentenceTransformer:
    return SentenceTransformer(SIMILARITY_MODEL_NAME)

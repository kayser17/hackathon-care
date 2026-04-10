from __future__ import annotations

import json

# import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


MODEL_NAME = "cooperleong00/deberta-v3-large_toxicity-scorer"

SAMPLE_TEXTS = [
    "You are an idiot and nobody likes you.",
    "Let's meet after class and finish the homework together.",
    "Leave me alone. You keep humiliating me in the group chat.",
    "Nobody wants you here. Just disappear.",
    "I disagree with you, but we can talk about it calmly.",
    "You are worthless and everyone is laughing at you.",
]


tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()


def get_toxicity_score(text: str) -> float:
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)

    return float(probs.cpu().numpy()[0][0])


def run_examples() -> list[dict[str, float | str]]:
    results = []
    for text in SAMPLE_TEXTS:
        results.append(
            {
                "text": text,
                "toxicity_score": round(get_toxicity_score(text), 4),
            }
        )
    return results


if __name__ == "__main__":
    output = {
        "model_name": MODEL_NAME,
        "device": str(device),
        "results": run_examples(),
    }
    print(json.dumps(output, indent=2))

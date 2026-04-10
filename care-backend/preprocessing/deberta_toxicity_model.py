from __future__ import annotations

import json

try:
    from .model_registry import TOXICITY_MODEL_NAME, get_toxicity_components
except ImportError:
    from model_registry import TOXICITY_MODEL_NAME, get_toxicity_components


MODEL_NAME = TOXICITY_MODEL_NAME

SAMPLE_TEXTS = [
    "You are an idiot and nobody likes you.",
    "Let's meet after class and finish the homework together.",
    "Leave me alone. You keep humiliating me in the group chat.",
    "Nobody wants you here. Just disappear.",
    "I disagree with you, but we can talk about it calmly.",
    "You are worthless and everyone is laughing at you.",
]

def get_toxicity_score(text: str) -> float:
    tokenizer, model, device = get_toxicity_components()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    ).to(device)

    import torch

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
    _, _, device = get_toxicity_components()
    output = {
        "model_name": MODEL_NAME,
        "device": str(device),
        "results": run_examples(),
    }
    print(json.dumps(output, indent=2))

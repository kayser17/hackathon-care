from __future__ import annotations

import torch

try:
    from .model_registry import EMOTION_MODEL_NAME, get_emotion_components
except ImportError:
    from model_registry import EMOTION_MODEL_NAME, get_emotion_components


MODEL_NAME = EMOTION_MODEL_NAME


def predict_emotions(text: str, threshold: float = 0.3) -> list[tuple[str, float]]:
    scores_by_label = predict_emotion_scores(text)
    emotions = [
        (label, score)
        for label, score in scores_by_label.items()
        if score > threshold
    ]
    return sorted(emotions, key=lambda item: item[1], reverse=True)


def predict_emotion_scores(text: str) -> dict[str, float]:
    tokenizer, model, device = get_emotion_components()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    ).to(device)

    with torch.no_grad():
        logits = model(**inputs).logits
        probabilities = torch.sigmoid(logits)[0].detach().cpu().tolist()

    labels = {
        int(index): str(label).lower()
        for index, label in model.config.id2label.items()
    }
    return {
        labels[index]: float(score)
        for index, score in enumerate(probabilities)
        if index in labels
    }


if __name__ == "__main__":
    text = "I am so happy and excited about this, but also a bit nervous."

    results = predict_emotions(text)

    print(f"\nText: {text}\n")
    print("Detected emotions:")
    for emotion, score in results:
        print(f"{emotion}: {score:.4f}")

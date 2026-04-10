import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_NAME = "AnasAlokla/multilingual_go_emotions"

# Load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

# Device (GPU if available)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Get labels
labels = model.config.id2label

def predict_emotions(text, threshold=0.3):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512
    ).to(device)

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.sigmoid(logits)[0].cpu().numpy()

    # Filter by threshold (multi-label)
    emotions = [
        (labels[i], float(probs[i]))
        for i in range(len(probs))
        if probs[i] > threshold
    ]

    # Sort by confidence
    emotions = sorted(emotions, key=lambda x: x[1], reverse=True)

    return emotions


if __name__ == "__main__":
    text = "I am so happy and excited about this, but also a bit nervous."

    results = predict_emotions(text)

    print(f"\nText: {text}\n")
    print("Detected emotions:")
    for emotion, score in results:
        print(f"{emotion}: {score:.4f}")
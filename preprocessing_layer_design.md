# Pre-processing Layer Design for AI-Based Child Safety Conversation Analysis

## Overview

Our solution aims to detect potential risks to minors in digital conversations, such as cyberbullying, grooming/manipulation, and emotional distress. The system should not rely on a single model decision. Instead, before sending the conversation to the main LLM, we extract a compact set of structured metrics that summarize linguistic, emotional, behavioral, and temporal risk signals.

This **pre-processing layer** has three goals:

1. **Enrich the LLM context** with structured evidence.
2. **Reduce ambiguity** by transforming raw text into measurable signals.
3. **Improve explainability** so the final alert can be justified with concrete features.

The output of this layer is a JSON object like this:

```json
{
  "toxicity": 0.68,
  "insult_score": 0.72,
  "emotion": {
    "anger": 0.6,
    "sadness": 0.5,
    "fear": 0.3
  },
  "manipulation_similarity": 0.81,
  "targeting_intensity": 0.85,
  "dominance_ratio": 0.9,
  "risk_trend": "increasing",
  "activity_anomaly": 0.6,
  "distress_signal": 0.55,
  "confidence": 0.78
}
```

## General Architecture

The pre-processing layer receives a conversation as a list of timestamped messages with speaker information.

### Input format

```json
[
  {
    "speaker": "user_a",
    "timestamp": "2026-04-08T21:03:00Z",
    "text": "You're so annoying, nobody wants you here."
  },
  {
    "speaker": "user_b",
    "timestamp": "2026-04-08T21:03:10Z",
    "text": "Leave me alone."
  }
]
```

### Pipeline

```text
Raw conversation
    ↓
Normalization and conversation parsing
    ↓
Per-message analysis
    - toxicity
    - emotion
    - semantic embeddings
    ↓
Conversation-level aggregation
    - targeting
    - dominance
    - trends
    - anomalies
    ↓
Final metrics JSON
```

## Metric 1: `toxicity`

### What it measures

`toxicity` estimates the overall level of harmful or aggressive language in the conversation. It is a broad signal that captures hostility, harassment, or abuse.

### Why it matters

Cyberbullying and verbal aggression usually contain some level of toxic language, even if not every message is openly insulting.

### Recommended implementation

Use a lightweight toxicity classifier on each message, then aggregate the scores across the conversation.

### Tools

- **Recommended:** `Detoxify`
- Alternative: Hugging Face toxicity models such as `unitary/toxic-bert`

### Implementation idea

1. Run toxicity prediction for each message.
2. Compute the average conversation toxicity.

```python
toxicity = mean(toxicity_score(message_i) for message_i in conversation)
```

### Notes

- Average is better than max if you want conversation-level stability.
- Max can be kept internally as a debugging feature, but not necessarily passed to the LLM.

## Metric 2: `insult_score`

### What it measures

`insult_score` captures how directly offensive the conversation is, focusing more on targeted attacks than general toxicity.

### Why it matters

A conversation can be toxic without being clearly insulting, and vice versa. This helps distinguish direct bullying from general negativity.

### Recommended implementation

Use message-level toxicity/offensive classification and calculate the proportion of highly insulting messages.

### Tools

- **Recommended:** same toxicity model as above, with a threshold
- Alternative: offensive language classifier from Hugging Face

### Implementation idea

1. Score each message with the toxicity/offensive model.
2. Count how many messages exceed an insult threshold.
3. Normalize by total number of messages.

```python
insult_score = number_of_messages_with_score_above_0_7 / total_messages
```

### Notes

- This keeps the metric simple and robust.
- You can tune the threshold later based on validation data.

## Metric 3: `emotion`

### What it measures

This metric captures the dominant emotional signals present in the conversation. We decided to keep emotions detailed and include:

- `anger`
- `sadness`
- `fear`

### Why it matters

These emotions are especially relevant for the risks we want to detect:

- **Anger** can indicate aggression or escalation.
- **Sadness** can indicate distress, hopelessness, or victimization.
- **Fear** can indicate intimidation, coercion, or vulnerability.

### Recommended implementation

Use a multi-label emotion classifier on each message and aggregate scores across the conversation.

### Tools

- **Recommended:** `j-hartmann/emotion-english-distilroberta-base`
- Alternative: LLM-based emotion extraction, but this is slower and more expensive

### Implementation idea

1. Run the emotion model on each message.
2. Extract the scores for anger, sadness, and fear.
3. Average them across the conversation.

```python
anger = mean(anger_score(message_i) for message_i in conversation)
sadness = mean(sadness_score(message_i) for message_i in conversation)
fear = mean(fear_score(message_i) for message_i in conversation)
```

### Notes

- We keep only these three emotions to avoid feature overload.
- If needed later, emotions can also be computed separately per speaker.

## Metric 4: `manipulation_similarity`

### What it measures

`manipulation_similarity` estimates how similar parts of the conversation are to manipulation or grooming patterns, such as secrecy, coercion, emotional pressure, or trust exploitation.

### Why it matters

Manipulative behavior is often subtle and may not appear as toxic. This is especially important for grooming detection.

### Recommended implementation

Use semantic similarity between messages and a curated library of manipulation/grooming patterns.

### Tools

- **Recommended:** `SentenceTransformers`
- Model example: `all-MiniLM-L6-v2`

### Pattern examples

- “Don’t tell your parents.”
- “This is our secret.”
- “Only I understand you.”
- “You can trust me, don’t tell anyone.”
- “Let’s keep this between us.”

### Implementation idea

1. Create a small library of high-risk manipulation phrases.
2. Embed both conversation messages and reference phrases.
3. Compute cosine similarity between each message and each reference phrase.
4. Keep the maximum similarity found in the conversation.

```python
manipulation_similarity = max(
    cosine_similarity(embed(message), embed(pattern))
    for message in conversation
    for pattern in manipulation_patterns
)
```

### Notes

- This is more flexible than keyword rules.
- Rules can still be added as a backup layer, but embeddings should be the main method.

## Metric 5: `targeting_intensity`

### What it measures

`targeting_intensity` measures how strongly one participant appears to be focusing negative attention on another participant.

### Why it matters

Bullying is often characterized by repeated targeting of the same individual, not just isolated toxic messages.

### Recommended implementation

Use speaker metadata and message flow to estimate how concentrated the interaction is from one user toward another.

### Tools

- **Recommended:** custom Python logic with `pandas`

### Implementation idea

For a two-person conversation:

```python
targeting_intensity = messages_from_aggressor_to_target / total_messages
```

For group conversations, a better version is:

1. Identify the pair with the highest directed interaction concentration.
2. Weight this by negativity or insult presence.

Possible practical formula:

```python
targeting_intensity = harmful_messages_from_A_to_B / total_harmful_messages
```

### Notes

- This works best when speaker IDs are available.
- In early MVP versions, this can be approximated in 1-to-1 chats more easily than in large group chats.

## Metric 6: `dominance_ratio`

### What it measures

`dominance_ratio` captures how much one participant dominates the conversation.

### Why it matters

Dominance can indicate a power imbalance, which is relevant in both bullying and grooming scenarios.

### Recommended implementation

Count how many messages are sent by each participant and compute how dominant the most active speaker is.

### Tools

- **Recommended:** custom Python logic with `pandas`

### Implementation idea

```python
dominance_ratio = max(messages_by_user) / total_messages
```

### Notes

- High dominance alone is not dangerous.
- It becomes more meaningful when combined with toxicity or manipulation signals.

## Metric 7: `risk_trend`

### What it measures

`risk_trend` summarizes whether the risk signals in the conversation are increasing, stable, or decreasing over time.

### Why it matters

A single harmful message may not justify an alert, but an escalating pattern is much more concerning.

### Recommended implementation

Use message-level toxicity over time as the main proxy for trend.

### Tools

- **Recommended:** `pandas`, `numpy`

### Implementation idea

1. Sort messages by timestamp.
2. Compute toxicity per message.
3. Fit a simple slope over the toxicity sequence.

```python
slope = linear_regression_index_vs_toxicity(message_indices, toxicity_scores)
```

Then map the slope into categories:

```python
if slope > positive_threshold:
    risk_trend = "increasing"
elif slope < negative_threshold:
    risk_trend = "decreasing"
else:
    risk_trend = "stable"
```

### Notes

- This metric is intentionally categorical to keep the final JSON simple.
- Later versions could combine toxicity trend and distress trend, but for now one trend metric is enough.

## Metric 8: `activity_anomaly`

### What it measures

`activity_anomaly` measures whether the conversation pattern is unusual compared to expected behavior. Examples include sudden message spikes or activity at unusual hours.

### Why it matters

Anomalous activity can strengthen suspicion in risky cases, especially for grooming or crisis-related conversations.

### Recommended implementation

Use a simple weighted anomaly score based on:

- message frequency spike
- late-night activity
- abrupt change in response patterns

### Tools

- **Recommended:** `pandas`, rule-based logic

### Implementation idea

Compute binary or normalized sub-signals such as:

- `frequency_spike`: whether message count exceeds expected short-term baseline
- `late_night_flag`: whether a significant number of messages occur during late-night hours
- `response_change`: whether response timing changes abruptly

Then combine them:

```python
activity_anomaly = 0.5 * frequency_spike + 0.3 * late_night_flag + 0.2 * response_change
```

### Notes

- For the hackathon, frequency spike + late-night activity is enough.
- More advanced anomaly detection can come later.

## Metric 9: `distress_signal`

### What it measures

`distress_signal` estimates how much the conversation resembles emotional distress, hopelessness, self-harm ideation, or psychological vulnerability.

### Why it matters

This metric is essential for the mental-health side of the project. Toxicity alone is not enough to detect risk to wellbeing.

### Recommended implementation

Use semantic similarity against a curated set of distress-related phrases.

### Tools

- **Recommended:** `SentenceTransformers`
- Model example: `all-MiniLM-L6-v2`

### Pattern examples

- “I want to disappear.”
- “I can’t do this anymore.”
- “Nobody cares about me.”
- “I feel empty.”
- “I’m tired of everything.”

### Implementation idea

1. Create a small distress phrase library.
2. Embed messages and distress phrases.
3. Compute similarity.
4. Keep the maximum or top-k average similarity.

```python
distress_signal = max(
    cosine_similarity(embed(message), embed(pattern))
    for message in conversation
    for pattern in distress_patterns
)
```

### Notes

- This should be interpreted as a signal, not a diagnosis.
- It is especially useful when sadness and fear are also elevated.

## Metric 10: `confidence`

### What it measures

`confidence` estimates how reliable the extracted metrics are overall.

### Why it matters

The system should not treat all conversations equally. A very short conversation or weakly aligned signals should produce lower confidence.

### Recommended implementation

Use a heuristic based on:

- number of messages
- consistency of extracted signals
- availability of speaker/timestamp metadata

### Tools

- **Recommended:** custom Python logic

### Implementation idea

Start with a base confidence from conversation size:

```python
base_confidence = min(1.0, log(num_messages + 1) / 5)
```

Then adjust it slightly:

- increase if several signals are high together
- decrease if the conversation is too short
- decrease if metadata is missing

Example:

```python
confidence = base_confidence

if num_messages < 5:
    confidence -= 0.15

if toxicity > 0.6 and insult_score > 0.5 and targeting_intensity > 0.6:
    confidence += 0.1

confidence = max(0.0, min(1.0, confidence))
```

### Notes

- This is not model confidence in a strict ML sense.
- It is an operational confidence score for downstream decision-making.

## Recommended MVP Stack

For the hackathon, the most practical stack is:

### Core libraries

- **Python**
- **pandas**
- **numpy**
- **scikit-learn**

### NLP / ML

- **Detoxify** for toxicity
- **Hugging Face Transformers** for emotion classification
- **SentenceTransformers** for semantic similarity

### Why this stack

- Fast to implement
- Easy to explain
- Good balance between performance and complexity
- Mostly local, which supports your privacy-first narrative

## Example End-to-End Implementation Flow

```text
1. Receive conversation
2. Normalize text and parse timestamps/speakers
3. Run toxicity model per message
4. Run emotion model per message
5. Compute embeddings for each message
6. Compare embeddings against manipulation and distress phrase libraries
7. Aggregate conversation-level behavioral metrics
8. Compute trend and anomaly metrics
9. Estimate overall confidence
10. Build final metrics JSON
11. Send conversation + metrics to the main LLM
```

## Why This Pre-processing Layer Is Strong

This design is intentionally compact. It does not overload the LLM with too many raw features, but it still captures the main dimensions needed to assess risk:

- **Content harm** through toxicity and insults
- **Emotional state** through anger, sadness, and fear
- **Manipulation intent** through semantic similarity
- **Interaction dynamics** through targeting and dominance
- **Temporal evolution** through trend and anomaly
- **Mental health risk** through distress signals
- **Reliability** through confidence

This makes the system both more explainable and more robust than relying on a single raw LLM call.

## Final Output Example

```json
{
  "toxicity": 0.68,
  "insult_score": 0.72,
  "emotion": {
    "anger": 0.60,
    "sadness": 0.50,
    "fear": 0.30
  },
  "manipulation_similarity": 0.81,
  "targeting_intensity": 0.85,
  "dominance_ratio": 0.90,
  "risk_trend": "increasing",
  "activity_anomaly": 0.60,
  "distress_signal": 0.55,
  "confidence": 0.78
}
```

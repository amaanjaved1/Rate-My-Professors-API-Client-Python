from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

try:
    from textblob import TextBlob  # type: ignore[import]
except Exception:  # noqa: BLE001
    TextBlob = None  # type: ignore[assignment]


SentimentLabel = Literal["very positive", "positive", "neutral", "negative", "very negative"]


@dataclass(slots=True)
class SentimentResult:
    score: float
    label: SentimentLabel


def analyze_sentiment(text: str) -> SentimentResult:
    """Return a simple sentiment score/label for the given text."""
    if TextBlob is None:
        raise RuntimeError(
            "textblob is not installed. Install with: pip install textblob",
        )

    blob = TextBlob(text)
    score = float(blob.sentiment.polarity)
    if score > 0.5:
        label: SentimentLabel = "very positive"
    elif score > 0.2:
        label = "positive"
    elif score < -0.5:
        label = "very negative"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(score=score, label=label)


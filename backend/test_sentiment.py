"""Test sentiment analyzer."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.sentiment_analyzer import get_sentiment_analyzer


async def main():
    """Test sentiment detection."""
    analyzer = get_sentiment_analyzer()

    test_texts = [
        "biraz hastayım ne önerebilirsin",
        "çok üzgünüm bir şey içebilir miyim",
        "stresli bir gün geçirdim",
        "mutluyum bugün",
    ]

    for text in test_texts:
        print(f"\n[+] Testing: '{text}'")
        result = await analyzer.analyze(text, use_llm=True)
        print(f"  Mood: {result.mood}")
        print(f"  Confidence: {result.confidence:.2f}")
        if result.response_template:
            print(f"  Template: {result.response_template}")


if __name__ == "__main__":
    asyncio.run(main())

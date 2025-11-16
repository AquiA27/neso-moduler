import pytest

from app.services.intent_detector import detect_intent, extract_quantity, load_triggers, normalize


@pytest.fixture(scope="module")
def triggers():
    return load_triggers()


def test_normalize_basic():
    assert normalize(" Çay   Ver!! ") == "çay ver"


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("Çay ver", 1),
        ("Çay 2", 2),
        ("Üç çay istiyoruz", 3),
        ("Çok sıcak bir çay", 1),
    ],
)
def test_extract_quantity(sentence, expected):
    assert extract_quantity(sentence) == expected


def test_detect_intent_positive_sentences(triggers):
    positives = [
        "Çay ver",
        "Çay versene abi",
        "Bi çay alalım",
        "Çay varmı?",
        "Çay 2",
        "Bir çay atıver",
        "Çok sıcak bir çay",
        "Çay istiyoruz",
    ]
    for sentence in positives:
        result = detect_intent(sentence, triggers=triggers)
        assert result["intent"] == "siparis_cay"
        assert result["confidence_band"] in {"high", "ambiguous"}


def test_detect_intent_negative_sentence(triggers):
    result = detect_intent("Pastan var mı?", triggers=triggers)
    assert result["intent"] in {None, "siparis_cay"}
    assert result["confidence"] < 0.4
    assert result["confidence_band"] == "unknown"


def test_detect_intent_ambiguous_asr(triggers):
    result = detect_intent("çaaay vrsn", triggers=triggers)
    assert result["confidence_band"] == "ambiguous"


def test_detect_intent_confidence_requirement(triggers):
    result = detect_intent("Çay versene", triggers=triggers)
    assert result["confidence"] >= 0.85


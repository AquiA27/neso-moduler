from __future__ import annotations

from typing import Dict, List, Optional


VOICE_PRESETS: List[Dict[str, object]] = [
    {
        "id": "google_tr_nehir",
        "provider": "google",
        "label": "Nehir · Google Neural2",
        "tone": "Sıcak ve samimi",
        "description": "Misafir karşılama ve önerilerde yumuşak, empati kuran bir ton kullanır.",
        "language": "tr-TR",
        "voice": {
            "name": "tr-TR-Standard-A",
            "ssmlGender": "FEMALE",
            "fallback": ["tr-TR-Neural2-A"],
        },
    },
    {
        "id": "google_tr_mert",
        "provider": "google",
        "label": "Mert · Google Neural2",
        "tone": "Dengeli ve güven veren",
        "description": "Sipariş özetleri ve kampanya duyuruları için dengeli, güven veren bir ton.",
        "language": "tr-TR",
        "voice": {
            "name": "tr-TR-Standard-B",
            "ssmlGender": "MALE",
            "fallback": ["tr-TR-Neural2-B", "tr-TR-Standard-C"],
        },
    },
    {
        "id": "google_tr_elif",
        "provider": "google",
        "label": "Elif · Google Neural2",
        "tone": "Neşeli ve canlı",
        "description": "Gün içinde promosyon anonsları ve kampanya duyurularında enerjik bir izlenim yaratır.",
        "language": "tr-TR",
        "voice": {
            "name": "tr-TR-Standard-D",
            "ssmlGender": "FEMALE",
            "fallback": ["tr-TR-Neural2-C"],
        },
    },
    {
        "id": "google_en_ava",
        "provider": "google",
        "label": "Ava · Google Neural2",
        "tone": "Canlı ve enerjik",
        "description": "İngilizce karşılamalarda enerjik ve neşeli bir ses tonu tercih eden işletmeler için.",
        "language": "en-US",
        "voice": {
            "name": "en-US-Neural2-F",
            "ssmlGender": "FEMALE",
        },
    },
    {
        "id": "azure_tr_serra",
        "provider": "azure",
        "label": "Serra · Azure Neural",
        "tone": "Ferah ve profesyonel",
        "description": "Azure Cognitive Speech ile Türkçe müşterilere profesyonel bir karşılama tonu sunar.",
        "language": "tr-TR",
        "voice": {
            "name": "tr-TR-SedaNeural",
            "style": "friendly",
        },
    },
    {
        "id": "azure_tr_kaan",
        "provider": "azure",
        "label": "Kaan · Azure Neural",
        "tone": "Sakin ve net",
        "description": "Adisyon kapatma veya ödeme hatırlatma gibi kritik aksiyonlarda sakin ve net ton.",
        "language": "tr-TR",
        "voice": {
            "name": "tr-TR-AhmetNeural",
            "style": "calm",
        },
    },
    {
        "id": "openai_tr_alloy",
        "provider": "openai",
        "label": "Alloy · OpenAI",
        "tone": "Modern ve dengeli",
        "description": "OpenAI TTS ile hem Türkçe hem İngilizce mesajlarda doğal, dengeli bir ton.",
        "language": "tr-TR",
        "voice": {
            "name": "alloy",
            "model": "tts-1-hd",
        },
    },
    {
        "id": "openai_tr_shimmer",
        "provider": "openai",
        "label": "Shimmer · OpenAI",
        "tone": "Dinamik ve enerjik",
        "description": "Kampanya ve çapraz satış mesajlarında dikkat çeken enerjik bir ton.",
        "language": "tr-TR",
        "voice": {
            "name": "shimmer",
            "model": "tts-1-hd",
        },
    },
    {
        "id": "aws_tr_filiz",
        "provider": "aws",
        "label": "Filiz · AWS Polly",
        "tone": "Samimi ve oturmuş",
        "description": "AWS Polly Türkçe Filiz sesi ile sıcak, köklü işletme hissi verir.",
        "language": "tr-TR",
        "voice": {
            "name": "Filiz",
            "languageCode": "tr-TR",
        },
    },
    {
        "id": "system_tr_default",
        "provider": "system",
        "label": "Sistem · Varsayılan Ses",
        "tone": "Temel ve nötr",
        "description": "Test ortamlarında ek lisans gerektirmeyen temel Windows TTS sesi.",
        "language": "tr-TR",
        "voice": {
            "name": "default",
        },
    },
]


VOICE_PRESET_MAP: Dict[str, Dict[str, object]] = {preset["id"]: preset for preset in VOICE_PRESETS}

DEFAULT_VOICE_BY_PROVIDER: Dict[str, str] = {}
for preset in VOICE_PRESETS:
    provider = preset["provider"]
    if provider not in DEFAULT_VOICE_BY_PROVIDER:
        DEFAULT_VOICE_BY_PROVIDER[provider] = preset["id"]

DEFAULT_VOICE_ID = VOICE_PRESETS[0]["id"] if VOICE_PRESETS else "system_tr_default"


def get_voice_preset(voice_id: Optional[str]) -> Optional[Dict[str, object]]:
    if not voice_id:
        return None
    return VOICE_PRESET_MAP.get(voice_id)


def get_voice_presets_by_provider(provider: str) -> List[Dict[str, object]]:
    return [preset for preset in VOICE_PRESETS if preset["provider"] == provider]


def get_default_voice_for_provider(provider: Optional[str]) -> Dict[str, object]:
    if provider and provider in DEFAULT_VOICE_BY_PROVIDER:
        return VOICE_PRESET_MAP[DEFAULT_VOICE_BY_PROVIDER[provider]]
    return VOICE_PRESET_MAP.get(DEFAULT_VOICE_ID, VOICE_PRESETS[0])


def list_voice_presets() -> List[Dict[str, object]]:
    return VOICE_PRESETS[:]


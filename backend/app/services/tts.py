import asyncio
import base64
import logging
import os
import tempfile
from typing import Optional
import httpx
from httpx import HTTPStatusError

import pyttsx3

try:  # pragma: no cover - Windows specific dependency
    import pythoncom  # type: ignore
except ImportError:  # pragma: no cover - fallback when not available
    pythoncom = None  # type: ignore[misc]

from ..core.config import settings
from .tts_presets import (
    get_voice_preset,
    get_default_voice_for_provider,
    get_voice_presets_by_provider,
)

# Map language codes to hints that help us match available system voices.
_VOICE_HINTS = {
    "tr": ["tr", "turk"],
    "en": ["en", "eng", "us", "uk"],
    "fr": ["fr", "fra", "french"],
    "de": ["de", "ger", "german"],
    "ar": ["ar", "ara", "arab"],
    "es": ["es", "spa", "span"],
}

# Google Speech Recognition dil kodları -> TTS dil kodları mapping
_LANG_TO_GOOGLE_TTS = {
    "tr": "tr-TR",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "ar": "ar-XA",
    "es": "es-ES",
}

# Her dil için doğal kadın ve erkek sesleri (Neural2 veya Wavenet modelleri)
# Legacy gender-based maps were superseded by configurable voice presets.


async def _get_assistant_settings(tenant_id: Optional[int] = None, assistant_type: Optional[str] = None) -> tuple[str, float, str]:
    """Veritabanından asistan ayarlarını getir. Returns: (voice_id, rate, provider)
    
    Args:
        tenant_id: İşletme ID'si (opsiyonel). Varsa tenant-specific ayarları kullanır.
        assistant_type: Asistan tipi ('customer' veya 'business'). Varsa o asistan için özel ayarları kullanır.
    """
    try:
        from ..db.database import db
        
        voice_id = None
        rate = 1.0
        provider = "system"
        
        # Önce tenant-specific ayarları kontrol et
        if tenant_id and assistant_type:
            try:
                # Asistan tipine göre kolon seç
                voice_col = "customer_assistant_tts_voice_id"
                rate_col = "customer_assistant_tts_speech_rate"
                provider_col = "customer_assistant_tts_provider"
                if assistant_type == "business":
                    voice_col = "business_assistant_tts_voice_id"
                    rate_col = "business_assistant_tts_speech_rate"
                    provider_col = "business_assistant_tts_provider"
                
                # Kolonların varlığını kontrol et
                column_check = await db.fetch_one(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'tenant_customizations' 
                    AND column_name = :voice_col
                    """,
                    {"voice_col": voice_col}
                )
                
                if column_check:
                    # Yeni kolonlar varsa kullan
                    try:
                        row = await db.fetch_one(
                            f"""
                            SELECT {voice_col} as voice_id, {rate_col} as speech_rate, {provider_col} as tts_provider
                            FROM tenant_customizations
                            WHERE isletme_id = :id
                            """,
                            {"id": tenant_id}
                        )
                        if row:
                            row_dict = dict(row) if hasattr(row, 'keys') else row
                            voice_id = row_dict.get("voice_id")
                            rate = float(row_dict.get("speech_rate") or 1.0)
                            provider = row_dict.get("tts_provider") or "system"
                            if voice_id or provider != "system":
                                logging.info(f"[TTS_SETTINGS] Using tenant-specific settings for tenant_id={tenant_id}, assistant_type={assistant_type}")
                    except Exception as col_err:
                        logging.warning(f"[TTS_SETTINGS] Column {voice_col} not found or error: {col_err}")
            except Exception as e:
                logging.warning(f"[TTS_SETTINGS] Failed to fetch tenant-specific TTS settings: {e}")
        
        # Tenant-specific ayar yoksa global ayarları kontrol et
        if not voice_id and provider == "system":
            rows = await db.fetch_all(
                """
                SELECT key, value
                  FROM app_settings
                 WHERE key IN (
                     'assistant_tts_voice_id',
                     'assistant_tts_speech_rate',
                     'assistant_tts_provider',
                     'assistant_tts_voice_gender'
                 )
                """
            )
            settings_dict = {r["key"]: r["value"] for r in rows}

        def _coerce_str(value: Optional[object], default: Optional[str] = None) -> Optional[str]:
            if value is None:
                return default
            if isinstance(value, str):
                try:
                    if value.startswith('"') and value.endswith('"'):
                        import json as json_module
                        return json_module.loads(value)
                except Exception:
                    pass
                return value
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, dict):
                return str(value.get("value", default))
            return default

        def _coerce_float(value: Optional[object], default: float = 1.0) -> float:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    if value.startswith('"') and value.endswith('"'):
                        import json as json_module
                        return float(json_module.loads(value))
                    return float(value)
                except Exception:
                    return default
            if isinstance(value, dict):
                try:
                    return float(value.get("value", default))
                except Exception:
                    return default
            return default

            voice_id = voice_id or _coerce_str(settings_dict.get("assistant_tts_voice_id"))
            rate = rate if voice_id else _coerce_float(settings_dict.get("assistant_tts_speech_rate"), 1.0)
            provider = (provider if voice_id or provider != "system" else _coerce_str(settings_dict.get("assistant_tts_provider"), "system") or "system").lower()

        valid_providers = ["system", "google", "azure", "aws", "openai"]
        if provider not in valid_providers:
            provider = "system"

        if provider == "system":
            if settings.GOOGLE_TTS_API_KEY:
                provider = "google"
            elif settings.OPENAI_API_KEY:
                provider = "openai"
            elif settings.AZURE_SPEECH_KEY:
                provider = "azure"

        if not voice_id:
            legacy_gender = (_coerce_str(settings_dict.get("assistant_tts_voice_gender"), "female") or "female").lower()
            candidates = get_voice_presets_by_provider(provider) or []
            if candidates:
                gender_pref = "female" if legacy_gender == "female" else "male"
                for preset in candidates:
                    voice_params = preset.get("voice") or {}
                    ssml_gender = str(voice_params.get("ssmlGender", ""))
                    if ssml_gender and gender_pref in ssml_gender.lower():
                        voice_id = preset["id"]
                        break

        preset = get_voice_preset(voice_id)
        if not preset or preset["provider"] != provider:
            preset = get_default_voice_for_provider(provider)

        voice_id = preset["id"]
        provider = preset["provider"]

        logging.info(
            "[TTS_SETTINGS] Parsed values: voice=%s, rate=%.2f, provider=%s",
            voice_id,
            rate,
            provider,
        )
        return (voice_id, rate, provider)
    except Exception as e:
        logging.warning(f"[TTS_SETTINGS] Error loading assistant settings: {e}, using defaults", exc_info=True)
        preset = get_default_voice_for_provider(None)
        return (preset["id"], 1.0, preset["provider"])

_LANG_TO_AZURE_TTS = {
    "tr": "tr-TR",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "ar": "ar-SA",
    "es": "es-ES",
}

_LANG_TO_AWS_TTS = {
    "tr": "tr-TR",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "ar": "ar-AE",
    "es": "es-ES",
}


def _normalize(value: str) -> str:
    return (value or "").lower()


def _match_voice(engine: pyttsx3.Engine, language: str) -> bool:
    """Try to set a voice that matches the requested language."""
    if not language:
        return False

    hints = _VOICE_HINTS.get(language.lower(), [])
    if not hints:
        hints = [language.lower()]

    try:
        voices = engine.getProperty("voices") or []
    except Exception:  # pragma: no cover - defensive
        logging.exception("TTS: could not fetch voices from engine")
        return False

    for voice in voices:
        parts = []
        try:
            if getattr(voice, "languages", None):
                for lang in voice.languages:
                    if isinstance(lang, bytes):
                        try:
                            lang = lang.decode("utf-8", errors="ignore")
                        except Exception:  # pragma: no cover - defensive
                            lang = ""
                    parts.append(_normalize(lang))
        except Exception:  # pragma: no cover - defensive
            pass

        parts.append(_normalize(getattr(voice, "name", "")))
        parts.append(_normalize(getattr(voice, "id", "")))

        haystack = " ".join(parts)
        if any(h in haystack for h in hints):
            engine.setProperty("voice", voice.id)
            logging.debug("TTS: selected voice '%s' for language '%s'", voice.name, language)
            return True

    return False


def _synthesize_system_sync(text: str, language: Optional[str], rate: Optional[int]) -> bytes:
    """Blocking synthesis helper executed outside the event loop."""
    try:
        co_initialized = False
        if pythoncom is not None:
            try:
                pythoncom.CoInitialize()
                co_initialized = True
            except Exception:  # pragma: no cover - defensive
                logging.debug("TTS: pythoncom.CoInitialize failed", exc_info=True)

        engine = pyttsx3.init()
        try:
            if language:
                matched = _match_voice(engine, language)
                if not matched:
                    logging.debug("TTS: no dedicated voice for language '%s'; using default", language)

            if rate:
                try:
                    engine.setProperty("rate", rate)
                except Exception:  # pragma: no cover - defensive
                    logging.debug("TTS: unable to set rate=%s", rate, exc_info=True)

            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                engine.save_to_file(text, path)
                engine.runAndWait()
                with open(path, "rb") as handle:
                    return handle.read()
            finally:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            if co_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:  # pragma: no cover - defensive
                    logging.debug("TTS: pythoncom.CoUninitialize failed", exc_info=True)
    except OSError as e:
        # libespeak.so.1 veya benzer sistem kütüphanesi eksik
        logging.warning(f"TTS system library not available: {e}. Falling back to silent audio.")
        # Sessiz bir WAV dosyası döndür (44 bytes - minimal WAV header)
        silent_wav = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        return silent_wav
    except Exception as e:
        # Diğer hatalar için de sessiz audio döndür
        logging.warning(f"TTS synthesis failed: {e}. Falling back to silent audio.", exc_info=True)
        silent_wav = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        return silent_wav


async def _synthesize_google(text: str, language: Optional[str], voice_id: Optional[str], speech_rate: Optional[float] = None) -> bytes:
    """Google Cloud Text-to-Speech API - Ayarlara göre ses seçimi."""
    if not settings.GOOGLE_TTS_API_KEY:
        raise ValueError("GOOGLE_TTS_API_KEY not configured")

    preset = get_voice_preset(voice_id) or get_default_voice_for_provider("google")
    voice_params = preset.get("voice") or {}

    lang_code = voice_params.get("languageCode") or preset.get("language") or _LANG_TO_GOOGLE_TTS.get(language or "tr", "tr-TR")
    voice_name = voice_params.get("name")
    fallback_voices = [
        voice for voice in voice_params.get("fallback", [])
        if isinstance(voice, str) and voice
    ]
    fallback_voices.append("tr-TR-Standard-A")
    fallback_voices.append(lang_code.replace("Neural2", "Standard"))
    fallback_voices = [v for v in fallback_voices if isinstance(v, str) and v]

    voices_to_try = []
    if voice_name:
        voices_to_try.append(voice_name)
    voices_to_try.extend([v for v in fallback_voices if v not in voices_to_try])
    if not voices_to_try:
        voices_to_try.append("tr-TR-Standard-A")

    ssml_gender = str(voice_params.get("ssmlGender", "NEUTRAL")).upper()

    if speech_rate is None:
        _, db_rate, _ = await _get_assistant_settings()
        speech_rate = db_rate

    speaking_rate = max(0.25, min(4.0, float(speech_rate or 1.0)))

    last_error: Optional[Exception] = None

    async with httpx.AsyncClient() as client:
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={settings.GOOGLE_TTS_API_KEY}"
        headers = {"Content-Type": "application/json"}

        for candidate_voice in voices_to_try:
            logging.info(
                "[TTS_GOOGLE] Generating speech with: lang=%s, voice=%s, gender=%s, rate=%.2f",
                lang_code,
                candidate_voice,
                ssml_gender,
                speaking_rate,
            )
            data = {
                "input": {"text": text},
                "voice": {
                    "languageCode": lang_code,
                    "name": candidate_voice,
                    "ssmlGender": ssml_gender,
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "sampleRateHertz": 24000,
                    "speakingRate": speaking_rate,
                },
            }
            try:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return base64.b64decode(result["audioContent"])
            except HTTPStatusError as exc:
                error_body = exc.response.text
                logging.error(
                    "[TTS_GOOGLE] Voice '%s' failed (%s): %s",
                    candidate_voice,
                    exc.response.status_code,
                    error_body,
                )
                if (
                    exc.response.status_code == 400
                    and "does not exist" in error_body.lower()
                    and candidate_voice != voices_to_try[-1]
                ):
                    last_error = exc
                    continue
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logging.exception("[TTS_GOOGLE] Unexpected error for voice '%s'", candidate_voice)
                last_error = exc
                continue

    if last_error:
        raise last_error
    raise RuntimeError("Google TTS synthesis failed for all candidate voices")


async def _synthesize_azure(text: str, language: Optional[str], voice_id: Optional[str]) -> bytes:
    """Azure Speech Services TTS."""
    if not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION:
        raise ValueError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must be configured")

    preset = get_voice_preset(voice_id) or get_default_voice_for_provider("azure")
    voice_params = preset.get("voice") or {}

    lang_code = voice_params.get("languageCode") or preset.get("language") or _LANG_TO_AZURE_TTS.get(language or "tr", "tr-TR")
    voice_name = voice_params.get("name", f"{lang_code}-Standard-A")
    style = voice_params.get("style")
    style_degree = voice_params.get("styleDegree", 1.0)

    if style:
        ssml = (
            f"<speak version='1.0' xml:lang='{lang_code}' xmlns:mstts='http://www.w3.org/2001/mstts'>"
            f"<voice xml:lang='{lang_code}' name='{voice_name}'>"
            f"<mstts:express-as style='{style}' styledegree='{style_degree}'>"
            f"{text}"
            f"</mstts:express-as>"
            f"</voice>"
            f"</speak>"
        )
    else:
        ssml = (
            f"<speak version='1.0' xml:lang='{lang_code}'>"
            f"<voice xml:lang='{lang_code}' name='{voice_name}'>"
            f"{text}"
            f"</voice>"
            f"</speak>"
        )

    url = f"https://{settings.AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": settings.AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, content=ssml.encode("utf-8"))
        response.raise_for_status()
        return response.content


async def _synthesize_aws(text: str, language: Optional[str], voice_id: Optional[str]) -> bytes:
    """AWS Polly TTS."""
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY or not settings.AWS_REGION:
        raise ValueError("AWS credentials must be configured")

    preset = get_voice_preset(voice_id) or get_default_voice_for_provider("aws")
    voice_params = preset.get("voice") or {}

    lang_code = voice_params.get("languageCode") or preset.get("language") or _LANG_TO_AWS_TTS.get(language or "tr", "tr-TR")
    voice_name = voice_params.get("name", _get_aws_voice_id(lang_code))

    try:
        import boto3
    except ImportError:
        raise ValueError("boto3 is required for AWS Polly. Install with: pip install boto3")

    polly = boto3.client(
        "polly",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    def _polly_sync():
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat="pcm",
            SampleRate="16000",
            LanguageCode=lang_code,
            VoiceId=voice_name,
        )
        return response["AudioStream"].read()

    return await asyncio.to_thread(_polly_sync)


async def _synthesize_openai(text: str, language: Optional[str], voice_id: Optional[str], speech_rate: Optional[float] = None) -> bytes:
    """OpenAI TTS API - Yüksek kaliteli ses üretimi."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    preset = get_voice_preset(voice_id) or get_default_voice_for_provider("openai")
    voice_params = preset.get("voice") or {}

    voice = voice_params.get("name", "alloy")
    model = voice_params.get("model") or settings.OPENAI_TTS_MODEL or "tts-1-hd"

    logging.info(
        "[TTS_OPENAI] Generating speech with: model=%s, voice=%s, language=%s",
        model,
        voice,
        language,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "wav",
        }
        response = await client.post(url, headers=headers, json=data)
        if response.status_code != 200:
            error_body = response.text
            logging.error(f"[TTS_OPENAI] API error {response.status_code}: {error_body}")
        response.raise_for_status()
        return response.content


def _get_aws_voice_id(lang_code: str) -> str:
    """AWS Polly için uygun voice ID döndürür."""
    voice_map = {
        "tr-TR": "Filiz",
        "en-US": "Joanna",
        "fr-FR": "Celine",
        "de-DE": "Marlene",
        "ar-AE": "Zeina",
        "es-ES": "Conchita",
    }
    return voice_map.get(lang_code, "Joanna")


async def synthesize_speech(
    text: str,
    *,
    language: Optional[str] = None,
    rate: Optional[int] = None,
    voice_id: Optional[str] = None,
    speech_rate: Optional[float] = None,
    tenant_id: Optional[int] = None,
    assistant_type: Optional[str] = None,
) -> bytes:
    """
    Generate speech audio for the supplied text using the configured TTS provider.

    Args:
        text: Metin
        language: Dil kodu (opsiyonel)
        rate: Konuşma hızı (opsiyonel, eski format)
        voice_id: Ses ID (opsiyonel)
        speech_rate: Konuşma hızı (opsiyonel, yeni format)
        tenant_id: İşletme ID'si (opsiyonel)
        assistant_type: Asistan tipi ('customer' veya 'business') (opsiyonel)

    Returns raw WAV bytes.
    """
    if not text:
        return b""

    db_voice_id, db_rate, db_provider = await _get_assistant_settings(tenant_id=tenant_id, assistant_type=assistant_type)
    provider = (db_provider or settings.TTS_PROVIDER or "system").lower()

    if provider == "system":
        if settings.GOOGLE_TTS_API_KEY:
            provider = "google"
            db_voice_id = get_default_voice_for_provider("google")["id"]
        elif settings.OPENAI_API_KEY:
            provider = "openai"
            db_voice_id = get_default_voice_for_provider("openai")["id"]
        elif settings.AZURE_SPEECH_KEY:
            provider = "azure"
            db_voice_id = get_default_voice_for_provider("azure")["id"]

    voice_id = voice_id or db_voice_id
    speech_rate = speech_rate or db_rate

    preset = get_voice_preset(voice_id)
    if not preset or preset["provider"].lower() != provider:
        preset = get_default_voice_for_provider(provider)
        voice_id = preset["id"]

    try:
        if provider == "google":
            if not settings.GOOGLE_TTS_API_KEY:
                raise ValueError("Google TTS API key not configured. Please set GOOGLE_TTS_API_KEY in .env file.")
            return await _synthesize_google(text, language, voice_id, speech_rate)
        if provider == "azure":
            if not settings.AZURE_SPEECH_KEY:
                raise ValueError("Azure Speech key not configured. Please set AZURE_SPEECH_KEY in .env file.")
            return await _synthesize_azure(text, language, voice_id)
        if provider == "aws":
            if not settings.AWS_ACCESS_KEY_ID:
                raise ValueError("AWS credentials not configured. Please set AWS_ACCESS_KEY_ID in .env file.")
            return await _synthesize_aws(text, language, voice_id)
        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file.")
            return await _synthesize_openai(text, language, voice_id, speech_rate)

        logging.warning("[TTS] System TTS kullanılıyor - kalite düşük olabilir. Daha iyi kalite için Google/Azure/OpenAI API key'i ekleyin.")
        system_rate = int((speech_rate or 1.0) * 100) if speech_rate else rate
        return await asyncio.to_thread(_synthesize_system_sync, text, language, system_rate)
    except Exception as e:
        logging.error("[TTS] Provider %s synthesis failed: %s", provider, e, exc_info=True)
        raise
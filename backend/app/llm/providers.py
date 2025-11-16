from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict, Optional, List

from ..core.config import settings


class LLMProvider:
    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        raise NotImplementedError

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError


class RuleBasedProvider(LLMProvider):
    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        # Very small, safe fallback that explains capabilities and routes to parse/siparis flow
        text = (
            "Asistan aktif. Doğal dilde sipariş verebilirsiniz. Örn: 'iki latte bir americano'. "
            "Menüye göre eşleşen ürünleri ayıklar ve siparişe çeviririm. Sorularınıza da kısa cevap veririm. "
            "Devam etmek için bir sipariş metni söyleyin ya da sistemle ilgili soru sorun."
        )
        for chunk in text.split(" "):
            yield chunk + " "
            await asyncio.sleep(0.01)

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        # Simple rule-based responder for local/dev usage
        if not messages:
            return "Merhaba, size nasıl yardımcı olabilirim?"
        last = messages[-1]["content"].lower()
        if "süt" in last and "süz" in last:
            return "Süt içermeyen seçenekler listesine bakıyorum; örnek: Americano ve Cola sütsüzdür."
        if "kafeinsiz" in last:
            return "Menüde kafeinsiz içecek olarak şu an için Cola'yı önerebilirim."
        return "Elimdeki bilgilere göre yardımcı olmaya çalıştım. Daha fazla detay için ürün adı vererek sorabilirsiniz."


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        # Use httpx directly to avoid hard dep on openai package
        import json
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "stream": True,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "POST", "https://api.openai.com/v1/chat/completions", headers=headers, content=json.dumps(payload)
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except Exception:
                        # Ignore malformed chunks
                        continue

    async def chat(self, messages: List[Dict[str, str]], task_type: str = "general") -> str:
        import httpx
        import json

        # Task-specific parameters
        if task_type == "bi_analysis":
            # BI analizi için: daha tutarlı, fact-based, deterministik
            temperature = 0.3
            top_p = 0.85
            frequency_penalty = 0.2
            presence_penalty = 0.1
        else:
            # Genel chat için: daha yaratıcı
            temperature = 0.8
            top_p = 0.9
            frequency_penalty = 0.3
            presence_penalty = 0.3

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                content=json.dumps(payload),
            )
            resp.raise_for_status()
            data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            import logging
            logging.error(f"OpenAI API error: {e}, response: {data if 'data' in locals() else 'no data'}")
            return ""


def get_llm_provider() -> LLMProvider:
    import logging
    # API key kontrolü ve loglama
    has_api_key = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())
    is_llm_enabled = settings.ASSISTANT_ENABLE_LLM
    
    logging.info(f"[LLM_PROVIDER] ASSISTANT_ENABLE_LLM={is_llm_enabled}, HAS_API_KEY={has_api_key}")
    
    if is_llm_enabled and has_api_key:
        try:
            model = settings.OPENAI_MODEL or "gpt-4o-mini"
            provider = OpenAIProvider(settings.OPENAI_API_KEY, model)
            logging.info(f"[LLM_PROVIDER] Using OpenAI provider with model: {model}")
            return provider
        except Exception as e:
            logging.error(f"[LLM_PROVIDER] Failed to initialize OpenAI provider: {e}")
            pass
    else:
        if not is_llm_enabled:
            logging.warning("[LLM_PROVIDER] LLM disabled in settings")
        if not has_api_key:
            logging.warning("[LLM_PROVIDER] OpenAI API key not found in environment")
    
    logging.warning("[LLM_PROVIDER] Falling back to RuleBasedProvider")
    return RuleBasedProvider()

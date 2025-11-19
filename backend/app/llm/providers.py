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

    async def chat(self, messages: List[Dict[str, str]], task_type: str = "general") -> tuple[str, Optional[Dict[str, Any]]]:
        """
        OpenAI API'ye mesaj gönder ve yanıt al.
        
        Returns:
            tuple[str, Optional[Dict]]: (response_text, usage_info)
            usage_info: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "cost_usd": float}
        """
        import httpx
        import json
        import time
        from typing import Optional

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
        
        start_time = time.time()
        usage_info = None
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                content=json.dumps(payload),
            )
            resp.raise_for_status()
            data = resp.json()
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        try:
            response_text = data["choices"][0]["message"]["content"]
            
            # Usage bilgisini çıkar
            if "usage" in data:
                usage = data["usage"]
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                # Model bazında maliyet hesapla (USD)
                # gpt-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
                # gpt-4o: $2.50 / 1M input tokens, $10.00 / 1M output tokens
                cost_per_1m_input = 0.15 if "gpt-4o-mini" in self.model.lower() else 2.50
                cost_per_1m_output = 0.60 if "gpt-4o-mini" in self.model.lower() else 10.00
                cost_usd = (prompt_tokens / 1_000_000 * cost_per_1m_input) + (completion_tokens / 1_000_000 * cost_per_1m_output)
                
                usage_info = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": round(cost_usd, 6),
                    "response_time_ms": response_time_ms,
                }
            
            return response_text, usage_info
        except Exception as e:
            import logging
            logging.error(f"OpenAI API error: {e}, response: {data if 'data' in locals() else 'no data'}")
            return "", None


async def get_llm_provider(tenant_id: Optional[int] = None) -> LLMProvider:
    """
    Tenant-specific veya global API key ile LLM provider döndürür.
    
    Args:
        tenant_id: İşletme ID'si (opsiyonel). Varsa tenant-specific API key kullanılır.
    
    Returns:
        LLMProvider: OpenAIProvider veya RuleBasedProvider
    """
    import logging
    from ..db.database import db
    
    api_key = None
    model = settings.OPENAI_MODEL or "gpt-4o-mini"
    
    # Önce tenant-specific API key'i kontrol et
    if tenant_id:
        try:
            customization = await db.fetch_one(
                """
                SELECT openai_api_key, openai_model
                FROM tenant_customizations
                WHERE isletme_id = :id AND openai_api_key IS NOT NULL AND openai_api_key != ''
                """,
                {"id": tenant_id}
            )
            if customization:
                customization_dict = dict(customization) if hasattr(customization, 'keys') else customization
                tenant_api_key = customization_dict.get("openai_api_key")
                tenant_model = customization_dict.get("openai_model")
                if tenant_api_key and tenant_api_key.strip():
                    api_key = tenant_api_key.strip()
                    if tenant_model:
                        model = tenant_model
                    logging.info(f"[LLM_PROVIDER] Using tenant-specific API key for tenant_id={tenant_id}, model={model}")
        except Exception as e:
            logging.warning(f"[LLM_PROVIDER] Failed to fetch tenant API key for tenant_id={tenant_id}: {e}")
    
    # Tenant-specific key yoksa global key'i kontrol et
    if not api_key:
        api_key = settings.OPENAI_API_KEY
        if api_key:
            api_key = api_key.strip()
            logging.info(f"[LLM_PROVIDER] Using global API key, model={model}")
    
    has_api_key = bool(api_key)
    is_llm_enabled = settings.ASSISTANT_ENABLE_LLM
    
    logging.info(f"[LLM_PROVIDER] ASSISTANT_ENABLE_LLM={is_llm_enabled}, HAS_API_KEY={has_api_key}, tenant_id={tenant_id}")
    
    if is_llm_enabled and has_api_key:
        try:
            provider = OpenAIProvider(api_key, model)
            logging.info(f"[LLM_PROVIDER] Using OpenAI provider with model: {model}")
            return provider
        except Exception as e:
            logging.error(f"[LLM_PROVIDER] Failed to initialize OpenAI provider: {e}")
            pass
    else:
        if not is_llm_enabled:
            logging.warning("[LLM_PROVIDER] LLM disabled in settings")
        if not has_api_key:
            logging.warning(f"[LLM_PROVIDER] OpenAI API key not found (tenant_id={tenant_id})")
    
    logging.warning("[LLM_PROVIDER] Falling back to RuleBasedProvider")
    return RuleBasedProvider()

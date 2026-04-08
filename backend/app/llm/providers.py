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
    def __init__(self, assistant_type: str = "general"):
        self.assistant_type = assistant_type

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        # Fallback text based on assistant type
        if self.assistant_type == "business":
            text = (
                "Neso İşletme Zekası Asistanı devrede. Şu an sınırlı yeteneklerle çalışıyorum ancak "
                "bana ciro, giderler, profit marjı veya stok durumu hakkında sorular sorabilirsiniz. "
                "Örn: 'Bugünkü ciro ne kadar?' veya 'Kritik stokları listele'."
            )
        else:
            text = (
                "Asistan aktif. Doğal dilde sipariş verebilirsiniz. Örn: 'iki latte bir americano'. "
                "Menüye göre eşleşen ürünleri ayıklar ve siparişe çeviririm. Sorularınıza da kısa cevap veririm."
            )
        
        for chunk in text.split(" "):
            yield chunk + " "
            await asyncio.sleep(0.01)

    async def chat(self, messages: List[Dict[str, str]], task_type: Optional[str] = None) -> str:
        # Improved rule-based responder when no OpenAI API key is available
        if not messages:
            return "Merhaba, size nasıl yardımcı olabilirim?"
        
        last = messages[-1]["content"].lower().strip()
        assistant_mode = task_type or self.assistant_type
        
        # Greeting
        greeting_words = {"merhaba", "selam", "selamlar", "hey", "hello", "hi", "günaydın", "nasıl"}
        first_word = last.split()[0].strip(".,!?") if last else ""
        
        if assistant_mode == "business" or assistant_mode == "bi_analysis":
            if first_word in greeting_words or "nasılsın" in last:
                return "Merhaba! Neso İşletme Zekası asistanı olarak performans analizi, ciro raporları ve stok durumu hakkında size yardımcı olabilirim. Ne öğrenmek istersiniz?"
        else:
            if first_word in greeting_words:
                return "Merhaba! Hoş geldiniz. Size menümüzden bir şeyler önerebilirim veya sipariş alabilirim. Ne istersiniz?"
        
        # Math / calculation (only for general assistants to avoid accidental prompt matching in BI)
        if assistant_mode != "business" and assistant_mode != "bi_analysis" and len(last) < 150:
            import re
            math_match = re.search(r'(\d+)\s*([\+\-\*\/x])\s*(\d+)', last)
            if math_match or any(kw in last for kw in ["kaç eder", "kaç yapar", "toplam", "artı", "eksi", "çarpı"]):
                if math_match:
                    a, b = math_match.group(1), math_match.group(3)
                    op_char = math_match.group(2)
                    try:
                        if op_char in ('+',): result = int(a) + int(b)
                        elif op_char in ('-',): result = int(a) - int(b)
                        elif op_char in ('*', 'x'): result = int(a) * int(b)
                        elif op_char in ('/',): result = round(int(a) / int(b), 2) if int(b) != 0 else "tanımsız"
                        else: result = "hesaplayamadım"
                        return f"{a} {op_char} {b} = {result}. Başka bir şey sormak ister misiniz?"
                    except Exception:
                        pass
                return "Matematik sorunuza yanıt vermekte zorlanıyorum. Ama menümüzden sipariş almakta yardımcı olabilirim!"
        
        # Süt / dairy / General
        if assistant_mode == "business" or assistant_mode == "bi_analysis":
            if "ciro" in last or "gelir" in last or "kazanç" in last:
                return "Şu an LLM bağlantısı kurulamadığı için canlı veri analizi yapamıyorum, ancak raporlar sayfasından detaylı ciro grafiklerinize ulaşabilirsiniz."
            if "stok" in last or "envanter" in last:
                return "Stok durumunuzu analiz etmek için veritabanına erişimim kısıtlı. Lütfen Stok sayfasını kontrol edin veya API anahtarınızı güncelleyin."
            if "kar" in last or "marj" in last:
                return "Kar marjı analizi için gelişmiş AI modeline ihtiyaç duyuyorum. Lütfen sistem ayarlarına geçerli bir OpenAI anahtarı girildiğinden emin olun."
            
            if "?" in last or any(kw in last for kw in ["rapor", "analiz", "durum", "nabız"]):
                return "Ben bir İşletme Zekası (BI) asistanıyım. Görevim sipariş almak değil, size işletme verileriniz üzerinden analiz ve öneriler sunmaktır. Şu an servis dışıyım ama yakında tüm verilere hakim olacağım."
            
            return "İşletme sahibi asistanı olarak buradayım. Size analiz, kampanya önerileri ve finansal durum hakkında bilgi verebilirim."
        else:
            if "süt" in last and ("süz" in last or "içermeyen" in last):
                return "Süt içermeyen seçenekler listesine bakıyorum; örnek: Americano ve Cola sütsüzdür."
            if "kafeinsiz" in last:
                return "Menüde kafeinsiz içecek olarak şu an için Cola'yı önerebilirim."
            
            # General question
            if "?" in last or any(kw in last for kw in ["nedir", "nasıl", "ne var", "öneri", "tavsiye"]):
                return "Sorunuzu yanıtlamaya çalışıyorum. Menümüzdeki ürünler hakkında soru sorabilir veya sipariş verebilirsiniz."
            
            return "Size menümüzden sipariş almak veya önerilerde bulunmak için buradayım. Ne istersiniz?"


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
        import logging
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
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    content=json.dumps(payload),
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as http_err:
            logging.error(f"[OpenAI] HTTP error {http_err.response.status_code}: {http_err.response.text[:500]}")
            return f"OpenAI API hatası ({http_err.response.status_code}). Lütfen API anahtarınızı kontrol edin.", None
        except httpx.ConnectError as conn_err:
            logging.error(f"[OpenAI] Connection error: {conn_err}")
            return "OpenAI API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.", None
        except httpx.TimeoutException:
            logging.error("[OpenAI] Request timed out after 60s")
            return "OpenAI API zaman aşımına uğradı. Lütfen tekrar deneyin.", None
        except Exception as e:
            logging.error(f"[OpenAI] Unexpected error: {e}", exc_info=True)
            return f"Beklenmeyen bir hata oluştu: {str(e)[:100]}", None
        
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


async def get_llm_provider(tenant_id: Optional[int] = None, assistant_type: Optional[str] = None) -> LLMProvider:
    """
    Tenant-specific veya global API key ile LLM provider döndürür.
    """
    import logging
    from ..db.database import db
    
    api_key = None
    model = settings.OPENAI_MODEL or "gpt-4o-mini"
    key_source = "none"
    
    # 1. Tenant-specific key'i kontrol et
    if tenant_id:
        try:
            api_key_col = "openai_api_key"
            if assistant_type == "customer": api_key_col = "customer_assistant_openai_api_key"
            elif assistant_type == "business": api_key_col = "business_assistant_openai_api_key"
            
            # Asistan-specific key
            cust = await db.fetch_one(
                f"SELECT {api_key_col} as k FROM tenant_customizations WHERE isletme_id = :id", 
                {"id": tenant_id}
            )
            if cust and cust["k"]:
                api_key = cust["k"].strip()
                key_source = f"tenant_{assistant_type}"
            
            # Genel tenant key (asistan specific yoksa)
            if not api_key:
                cust_gen = await db.fetch_one(
                    "SELECT openai_api_key as k FROM tenant_customizations WHERE isletme_id = :id", 
                    {"id": tenant_id}
                )
                if cust_gen and cust_gen["k"]:
                    api_key = cust_gen["k"].strip()
                    key_source = "tenant_general"
        except Exception as e:
            logging.warning(f"[LLM_PROVIDER] Tenant key lookup failed for {tenant_id}: {e}")

    # 2. Platform settings (DB) kontrol et
    if not api_key:
        try:
            ps_key = "openai_api_key"
            if assistant_type == "customer": ps_key = "customer_assistant_openai_api_key"
            elif assistant_type == "business": ps_key = "business_assistant_openai_api_key"
            
            row = await db.fetch_one("SELECT value FROM platform_settings WHERE key = :k", {"k": ps_key})
            if row and row["value"]:
                api_key = row["value"].strip()
                key_source = f"platform_{ps_key}"
            else:
                row_gen = await db.fetch_one("SELECT value FROM platform_settings WHERE key = 'openai_api_key'")
                if row_gen and row_gen["value"]:
                    api_key = row_gen["value"].strip()
                    key_source = "platform_general"
        except Exception as e:
            logging.warning(f"[LLM_PROVIDER] Platform settings lookup failed: {e}")

    # 3. Global Env (.env / environments) kontrol et
    if not api_key:
        api_key_env = settings.OPENAI_API_KEY
        if api_key_env and api_key_env.strip():
            api_key = api_key_env.strip()
            key_source = "global_env"

    # Karar ve Provider oluşturma
    is_llm_enabled = settings.ASSISTANT_ENABLE_LLM
    
    if is_llm_enabled and api_key:
        logging.info(f"[LLM_PROVIDER] ✅ Using {key_source} key for {assistant_type}")
        return OpenAIProvider(api_key, model)
    
    logging.warning(f"[LLM_PROVIDER] ⚠️ Fallback to RuleBasedProvider (Source: {key_source}, LLM_Enabled: {is_llm_enabled})")
    return RuleBasedProvider(assistant_type=assistant_type or "general")


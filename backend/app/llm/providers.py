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
        # Improved rule-based responder when no OpenAI API key is available
        if not messages:
            return "Merhaba, size nasıl yardımcı olabilirim?"
        last = messages[-1]["content"].lower().strip()
        
        # Greeting
        greeting_words = {"merhaba", "selam", "selamlar", "hey", "hello", "hi", "günaydın"}
        first_word = last.split()[0].strip(".,!?") if last else ""
        if first_word in greeting_words:
            return "Merhaba! Hoş geldiniz. Size menümüzden bir şeyler önerebilirim veya sipariş alabilrim. Ne istersiniz?"
        
        # Math / calculation
        import re
        math_match = re.search(r'(\d+)\s*[\+\-\*\/x]\s*(\d+)', last)
        if math_match or any(kw in last for kw in ["kaç eder", "kaç yapar", "toplam", "artı", "eksi", "çarpı"]):
            if math_match:
                a, b = math_match.group(1), math_match.group(2)
                op_char = re.search(r'[\+\-\*\/x]', last[math_match.start():math_match.end()]).group()
                try:
                    if op_char in ('+',):
                        result = int(a) + int(b)
                    elif op_char in ('-',):
                        result = int(a) - int(b)
                    elif op_char in ('*', 'x'):
                        result = int(a) * int(b)
                    elif op_char in ('/',):
                        result = round(int(a) / int(b), 2) if int(b) != 0 else "tanımsız"
                    else:
                        result = "hesaplayamadım"
                    return f"{a} {op_char} {b} = {result}. Başka bir şey sormak ister misiniz?"
                except Exception:
                    pass
            return "Matematik sorunuza yanıt vermekte zorlanıyorum. Ama menümüzden sipariş almakta yardımcı olabilirim!"
        
        # Süt / dairy
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
    
    Öncelik sırası:
    1. customer/business_assistant_openai_api_key (tenant-specific, asistan-specific)
    2. openai_api_key (tenant-specific, genel)
    3. settings.OPENAI_API_KEY (global/ortam değişkeni)
    4. RuleBasedProvider (hiçbir key yoksa)
    """
    import logging
    from ..db.database import db
    
    api_key = None
    model = settings.OPENAI_MODEL or "gpt-4o-mini"
    key_source = "none"
    
    # Önce tenant-specific API key'i kontrol et
    if tenant_id:
        try:
            # Asistan tipine göre kolon seç
            api_key_col = "openai_api_key"
            model_col = "openai_model"
            if assistant_type == "customer":
                api_key_col = "customer_assistant_openai_api_key"
                model_col = "customer_assistant_openai_model"
            elif assistant_type == "business":
                api_key_col = "business_assistant_openai_api_key"
                model_col = "business_assistant_openai_model"
            
            logging.info(f"[LLM_PROVIDER] Looking for key in column '{api_key_col}' for tenant_id={tenant_id}")
            
            # Önce tüm key kolonlarını tek sorguda çek
            try:
                all_keys_query = """
                    SELECT 
                        openai_api_key,
                        openai_model
                    FROM tenant_customizations
                    WHERE isletme_id = :id
                """
                base_row = await db.fetch_one(all_keys_query, {"id": tenant_id})
                
                if base_row:
                    base_dict = dict(base_row) if hasattr(base_row, 'keys') else base_row
                    logging.info(f"[LLM_PROVIDER] Found tenant_customizations row for tenant_id={tenant_id}, openai_api_key={'SET' if base_dict.get('openai_api_key') else 'EMPTY'}")
                else:
                    logging.warning(f"[LLM_PROVIDER] No tenant_customizations row found for tenant_id={tenant_id}")
            except Exception as base_err:
                logging.warning(f"[LLM_PROVIDER] Error checking base row: {base_err}")
                base_row = None
            
            # Asistan-specific kolonları kontrol et
            if assistant_type and api_key_col != "openai_api_key":
                try:
                    # Kolon varlığını kontrol et
                    column_check = await db.fetch_one(
                        """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'tenant_customizations' 
                        AND column_name = :api_key_col
                        """,
                        {"api_key_col": api_key_col}
                    )
                    
                    if column_check:
                        logging.info(f"[LLM_PROVIDER] Column '{api_key_col}' exists in DB")
                        customization = await db.fetch_one(
                            f"""
                            SELECT {api_key_col} as api_key, {model_col} as model
                            FROM tenant_customizations
                            WHERE isletme_id = :id AND {api_key_col} IS NOT NULL AND {api_key_col} != ''
                            """,
                            {"id": tenant_id}
                        )
                        if customization:
                            cust_dict = dict(customization) if hasattr(customization, 'keys') else customization
                            tenant_key = cust_dict.get("api_key")
                            tenant_model = cust_dict.get("model")
                            if tenant_key and tenant_key.strip():
                                api_key = tenant_key.strip()
                                if tenant_model:
                                    model = tenant_model
                                key_source = f"tenant_{assistant_type}_specific"
                                logging.info(f"[LLM_PROVIDER] ✅ Using {assistant_type}-specific API key for tenant_id={tenant_id}, model={model}, key=sk-...{api_key[-4:]}")
                            else:
                                logging.info(f"[LLM_PROVIDER] {assistant_type}-specific key exists but is empty/null for tenant_id={tenant_id}")
                        else:
                            logging.info(f"[LLM_PROVIDER] No {assistant_type}-specific key row found for tenant_id={tenant_id}")
                    else:
                        logging.warning(f"[LLM_PROVIDER] Column '{api_key_col}' does NOT exist in DB - schema migration may be needed")
                except Exception as col_err:
                    logging.warning(f"[LLM_PROVIDER] Error checking {api_key_col}: {col_err}")
            
            # Asistan-specific key bulunamadıysa, genel key'e bak
            if not api_key and base_row:
                base_dict = dict(base_row) if hasattr(base_row, 'keys') else base_row
                general_key = base_dict.get("openai_api_key")
                general_model = base_dict.get("openai_model")
                if general_key and general_key.strip():
                    api_key = general_key.strip()
                    if general_model:
                        model = general_model
                    key_source = "tenant_general"
                    logging.info(f"[LLM_PROVIDER] ✅ Using tenant general API key for tenant_id={tenant_id}, model={model}, key=sk-...{api_key[-4:]}")
                else:
                    logging.info(f"[LLM_PROVIDER] Tenant general openai_api_key is empty for tenant_id={tenant_id}")
                    
        except Exception as e:
            logging.error(f"[LLM_PROVIDER] ❌ Failed to fetch tenant API key for tenant_id={tenant_id}, assistant_type={assistant_type}: {e}", exc_info=True)
    else:
        logging.info(f"[LLM_PROVIDER] No tenant_id provided, skipping tenant-specific key lookup")
    
    # Tenant-specific key yoksa global key'i kontrol et
    if not api_key:
        # 1) Önce ortam değişkeninden
        api_key = settings.OPENAI_API_KEY
        if api_key:
            api_key = api_key.strip()
            key_source = "global_env"
            logging.info(f"[LLM_PROVIDER] ✅ Using global API key from env, model={model}, key=sk-...{api_key[-4:]}")
        else:
            # 2) Ortam değişkeni yoksa, platform_settings tablosundan
            try:
                ps_row = await db.fetch_one(
                    "SELECT value FROM platform_settings WHERE key = 'openai_api_key'",
                )
                if ps_row:
                    ps_dict = dict(ps_row) if hasattr(ps_row, 'keys') else ps_row
                    ps_key = ps_dict.get("value")
                    if ps_key and ps_key.strip():
                        api_key = ps_key.strip()
                        key_source = "platform_settings_db"
                        logging.info(f"[LLM_PROVIDER] ✅ Using global API key from platform_settings DB, model={model}, key=sk-...{api_key[-4:]}")
                
                # Model de platform_settings'den alınabilir
                if not api_key:
                    pass  # Key bulunamadı
                else:
                    ps_model_row = await db.fetch_one(
                        "SELECT value FROM platform_settings WHERE key = 'openai_model'",
                    )
                    if ps_model_row:
                        ps_model_dict = dict(ps_model_row) if hasattr(ps_model_row, 'keys') else ps_model_row
                        ps_model = ps_model_dict.get("value")
                        if ps_model and ps_model.strip():
                            model = ps_model.strip()
                            logging.info(f"[LLM_PROVIDER] Using model from platform_settings: {model}")
            except Exception as ps_err:
                logging.warning(f"[LLM_PROVIDER] platform_settings lookup failed (table may not exist): {ps_err}")
            
            if not api_key:
                logging.warning(f"[LLM_PROVIDER] ❌ No global OPENAI_API_KEY in env or platform_settings")
    
    has_api_key = bool(api_key)
    is_llm_enabled = settings.ASSISTANT_ENABLE_LLM
    
    logging.info(f"[LLM_PROVIDER] FINAL: ASSISTANT_ENABLE_LLM={is_llm_enabled}, HAS_API_KEY={has_api_key}, key_source={key_source}, tenant_id={tenant_id}, assistant_type={assistant_type}")
    
    if is_llm_enabled and has_api_key:
        try:
            provider = OpenAIProvider(api_key, model)
            logging.info(f"[LLM_PROVIDER] ✅ OpenAI provider created with model: {model}")
            return provider
        except Exception as e:
            logging.error(f"[LLM_PROVIDER] ❌ Failed to initialize OpenAI provider: {e}")
            pass
    else:
        if not is_llm_enabled:
            logging.warning("[LLM_PROVIDER] ❌ LLM disabled in settings (ASSISTANT_ENABLE_LLM=False)")
        if not has_api_key:
            logging.warning(f"[LLM_PROVIDER] ❌ No API key found from any source (tenant_id={tenant_id})")
    
    logging.warning("[LLM_PROVIDER] ⚠️ Falling back to RuleBasedProvider - responses will be limited")
    return RuleBasedProvider()


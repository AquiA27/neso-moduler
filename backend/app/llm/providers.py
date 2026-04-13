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
        self.model = model or "gpt-4o"

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
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
                        continue

    async def chat(self, messages: List[Dict[str, str]], task_type: str = "general") -> tuple[str, Optional[Dict[str, Any]]]:
        import httpx
        import json
        import time
        import logging

        # Task-specific parameters
        if task_type == "bi_analysis":
            temperature = 0.3
            top_p = 0.85
        else:
            temperature = 0.8
            top_p = 0.9

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    content=json.dumps(payload),
                )
                # Model bulunamazsa (404/400) daha basit modele düş
                if resp.status_code in (400, 404) and self.model != "gpt-4o-mini":
                    logging.warning(f"[OpenAI] Model {self.model} not available ({resp.status_code}), falling back to gpt-4o-mini")
                    self.model = "gpt-4o-mini"
                    payload["model"] = self.model
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        content=json.dumps(payload),
                    )
                resp.raise_for_status()
                data = resp.json()

            response_text = data["choices"][0]["message"]["content"]
            response_time_ms = int((time.time() - start_time) * 1000)
            
            usage_info = None
            if "usage" in data:
                usage = data["usage"]
                _MODEL_COSTS = {
                    "gpt-4o-mini": (0.15, 0.60),
                    "gpt-4.1-mini": (0.40, 1.60),
                    "gpt-4.1-nano": (0.10, 0.40),
                    "gpt-4.1": (2.00, 8.00),
                    "gpt-4o": (2.50, 10.00),
                }
                model_lower = self.model.lower()
                cost_per_1m_input, cost_per_1m_output = next(
                    (v for k, v in _MODEL_COSTS.items() if k in model_lower),
                    (2.50, 10.00)
                )
                cost_usd = (usage.get("prompt_tokens", 0) / 1_000_000 * cost_per_1m_input) + (usage.get("completion_tokens", 0) / 1_000_000 * cost_per_1m_output)
                
                usage_info = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "cost_usd": round(cost_usd, 6),
                    "response_time_ms": response_time_ms,
                }
            
            return response_text, usage_info
        except Exception as e:
            safe_err = str(e).replace(self.api_key, "***") if self.api_key in str(e) else str(e)
            logging.error(f"[OpenAI] Error: {safe_err}")
            return f"OpenAI hatası: {safe_err[:120]}", None


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "gemini-2.0-flash"

    async def stream(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2048) -> AsyncIterator[str]:
        import json
        import httpx
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}"
        
        # System instruction extraction
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
                break

        contents = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "topP": 0.95,
                "topK": 40,
        }
        
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("POST", url, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.strip(): continue
                    line = line.strip()
                    # Gemini stream returns a JSON array of candidates
                    if line.startswith('[') or line.startswith(','): line = line.lstrip('[, ')
                    if line.endswith(']'): line = line.rstrip(']')
                    
                    try:
                        obj = json.loads(line)
                        chunk = obj["candidates"][0]["content"]["parts"][0].get("text")
                        if chunk:
                            yield chunk
                    except Exception:
                        continue

    async def chat(self, messages: List[Dict[str, str]], task_type: str = "general") -> tuple[str, Optional[Dict[str, Any]]]:
        import httpx
        import json
        import time
        import logging

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        # Convert OpenAI-style messages to Gemini format
        gemini_history = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                
                # Gemini STRICT RULE: Roles must alternate between 'user' and 'model'.
                if gemini_history and gemini_history[-1]["role"] == role:
                    # If consecutive same-role messages occur, merege them.
                    gemini_history[-1]["parts"][0]["text"] += f"\n\n{msg['content']}"
                else:
                    gemini_history.append({
                        "role": role,
                        "parts": [{"text": msg["content"]}]
                    })

        payload = {
            "contents": gemini_history,
            "generationConfig": {
                "temperature": 0.4 if task_type == "bi_analysis" else 0.8,
                "topP": 0.95,
                "maxOutputTokens": 4096,
            }
        }
        
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        start_time = time.time()
        # Her model için hem v1beta hem v1 API versiyonunu dene
        candidates = []
        for m in ([self.model] + (["gemini-1.5-flash"] if self.model != "gemini-1.5-flash" else [])):
            candidates.append((m, "v1beta"))
            candidates.append((m, "v1"))

        last_error = None
        for attempt_model, api_ver in candidates:
            attempt_url = f"https://generativelanguage.googleapis.com/v1beta/models/{attempt_model}:generateContent?key={self.api_key}"
            if api_ver == "v1":
                attempt_url = f"https://generativelanguage.googleapis.com/v1/models/{attempt_model}:generateContent?key={self.api_key}"
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(attempt_url, json=payload)
                    if resp.status_code in (404, 400):
                        err_body = ""
                        try:
                            err_body = resp.json().get("error", {}).get("message", "")
                        except Exception:
                            pass
                        logging.warning(f"[Gemini] {attempt_model} ({api_ver}) → {resp.status_code}: {err_body[:100]}")
                        last_error = Exception(f"{resp.status_code} {err_body[:80]}")
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                if attempt_model != self.model:
                    logging.info(f"[Gemini] Using fallback model: {attempt_model} ({api_ver})")
                    self.model = attempt_model

                response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                response_time_ms = int((time.time() - start_time) * 1000)

                usage = data.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount", 0)
                completion_tokens = usage.get("candidatesTokenCount", 0)
                total_tokens = usage.get("totalTokenCount", 0)

                _GEMINI_COSTS = {
                    "gemini-2.5-pro": (1.25, 10.00),
                    "gemini-2.0-flash": (0.10, 0.40),
                    "gemini-1.5-pro": (1.25, 5.00),
                    "gemini-1.5-flash": (0.075, 0.30),
                }
                g_cost_input, g_cost_output = next(
                    (v for k, v in _GEMINI_COSTS.items() if k in self.model.lower()),
                    (0.10, 0.40)
                )
                cost_usd = (prompt_tokens / 1_000_000 * g_cost_input) + (completion_tokens / 1_000_000 * g_cost_output)

                return response_text, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": round(cost_usd, 7),
                    "response_time_ms": response_time_ms,
                }
            except Exception as e:
                last_error = e
                if not any(code in str(e) for code in ("404", "400")):
                    break  # Ağ/timeout hatası → retry etme

        # Tüm denemeler başarısız — key'i logda GIZLE
        safe_err = str(last_error).replace(self.api_key, "***") if last_error else "bilinmeyen hata"
        logging.error(f"[Gemini] All attempts failed: {safe_err}")
        return (
            "Gemini API bağlantısı kurulamadı. Lütfen Google AI Studio'dan yeni bir API key alın "
            "ve SuperAdmin panelinde güncelleyin. (aistudio.google.com/apikey)",
            None,
        )


async def get_llm_provider(tenant_id: Optional[int] = None, assistant_type: Optional[str] = None) -> LLMProvider:
    """
    Tenant-specific veya global API key ile LLM provider döndürür.
    Hem OpenAI hem de Gemini (Google) desteği sağlar.
    """
    import logging
    from ..db.database import db
    
    api_key = None
    model = None
    key_source = "none"
    provider_type = "openai" # default
    
    # 1. Tenant-specific key'i kontrol et
    if tenant_id:
        try:
            # Önce asistan-spesifik kolonlara bak
            cols = ["openai_api_key", "openai_model"]
            if assistant_type == "customer":
                cols = ["customer_assistant_openai_api_key", "customer_assistant_openai_model"]
            elif assistant_type == "business":
                cols = ["business_assistant_openai_api_key", "business_assistant_openai_model"]
            
            row = await db.fetch_one(
                f"SELECT {cols[0]} as k, {cols[1]} as m FROM tenant_customizations WHERE isletme_id = :id", 
                {"id": tenant_id}
            )
            
            if row and row["k"]:
                api_key = row["k"].strip()
                model = row["m"]
                key_source = f"tenant_{assistant_type}"
            else:
                # Genel tenant key'ine bak
                row_gen = await db.fetch_one(
                    "SELECT openai_api_key as k, openai_model as m FROM tenant_customizations WHERE isletme_id = :id", 
                    {"id": tenant_id}
                )
                if row_gen and row_gen["k"]:
                    api_key = row_gen["k"].strip()
                    model = row_gen["m"]
                    key_source = "tenant_general"
        except Exception as e:
            logging.warning(f"[LLM_PROVIDER] Tenant key lookup failed: {e}")

    # 2. Global Ayarlar (DB) kontrol et - platform_settings ve app_settings tabloları
    if not api_key:
        try:
            # Aranan anahtarlar
            ps_key = "openai_api_key"
            ps_model = "openai_model"
            if assistant_type == "customer":
                ps_key = "customer_assistant_openai_api_key"
                ps_model = "customer_assistant_openai_model"
            elif assistant_type == "business":
                ps_key = "business_assistant_openai_api_key"
                ps_model = "business_assistant_openai_model"



            # Önce platform_settings, sonra app_settings kontrol et
            for table in ["platform_settings", "app_settings"]:
                try:
                    # Spesifik anahtarı ara
                    row = await db.fetch_one(f"SELECT value FROM {table} WHERE key = :k", {"k": ps_key})
                    if row and row["value"]:
                        val = row["value"]
                        # app_settings JSONB ise ve string olarak kaydedilmişse temizle
                        if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                            import json
                            try: val = json.loads(val)
                            except: pass
                        
                        api_key = str(val).strip()
                        key_source = f"{table}_{ps_key}"
                        
                        # Modeli de al
                        m_row = await db.fetch_one(f"SELECT value FROM {table} WHERE key = :k", {"k": ps_model})
                        if m_row and m_row["value"]:
                            m_val = m_row["value"]
                            if isinstance(m_val, str) and m_val.startswith('"') and m_val.endswith('"'):
                                try: m_val = json.loads(m_val)
                                except: pass
                            model = str(m_val)
                        break
                except Exception as table_err:
                    logging.debug(f"[LLM_PROVIDER] Table {table} lookup error: {table_err}")
                    continue
            
            # Eğer hala bulunamadıysa genel 'openai_api_key' anahtarına bak
            if not api_key:
                for table in ["platform_settings", "app_settings"]:
                    try:
                        row_gen = await db.fetch_one(f"SELECT value FROM {table} WHERE key = 'openai_api_key'")
                        if row_gen and row_gen["value"]:
                            val = row_gen["value"]
                            if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                                try: val = json.loads(val)
                                except: pass
                            
                            api_key = str(val).strip()
                            key_source = f"{table}_general"
                            
                            m_gen = await db.fetch_one(f"SELECT value FROM {table} WHERE key = 'openai_model'")
                            if m_gen and m_gen["value"]:
                                m_val = m_gen["value"]
                                if isinstance(m_val, str) and m_val.startswith('"') and m_val.endswith('"'):
                                    try: m_val = json.loads(m_val)
                                    except: pass
                                model = str(m_val)
                            break
                    except: continue

        except Exception as e:
            logging.warning(f"[LLM_PROVIDER] Settings DB lookup failed: {e}")

    # 3. Global Env
    if not api_key:
        if settings.GOOGLE_API_KEY:
            api_key = settings.GOOGLE_API_KEY.strip()
            model = settings.GEMINI_MODEL
            key_source = "global_env_google"
            provider_type = "gemini"
        elif settings.OPENAI_API_KEY:
            api_key = settings.OPENAI_API_KEY.strip()
            model = settings.OPENAI_MODEL
            key_source = "global_env_openai"

    # Karar: Hangi provider?
    if api_key:
        # Gemini Kontrolü: Key AIza ile başlıyorsa veya modelde gemini geçiyorsa
        if provider_type == "gemini" or api_key.startswith("AIza") or (model and "gemini" in model.lower()):
            provider_type = "gemini"
            if not model or "gpt" in model.lower():  # Model ismi hatalıysa düzelt
                model = "gemini-2.0-flash"
        
        if provider_type == "gemini":
            logging.info(f"[LLM_PROVIDER] ♊ Using Gemini ({model}) via {key_source}")
            return GeminiProvider(api_key, model)
        else:
            logging.info(f"[LLM_PROVIDER] 🤖 Using OpenAI ({model or 'gpt-4o'}) via {key_source}")
            return OpenAIProvider(api_key, model or "gpt-4o")

    return RuleBasedProvider(assistant_type=assistant_type or "general")


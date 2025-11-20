from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple, AsyncIterator, Iterable, Set
import base64
import logging
import difflib
import re
import unicodedata
from uuid import uuid4
from collections import defaultdict
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError as e:
    # Python 3.13+ doesn't have 'aifc' module which speech_recognition depends on
    logging.warning(f"speech_recognition not available: {e}. STT features will be disabled.")
    sr = None
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False

import io

from ..core.config import settings
from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..llm import get_llm_provider
from ..services.tts import synthesize_speech
from ..services.tts_presets import (
    list_voice_presets,
    get_voice_preset,
    get_voice_presets_by_provider,
    get_default_voice_for_provider,
)
from .siparis import normalize_name  # mevcut yardımcıları kullan
import json

from ..services.data_access import resolve_data_query, DataQueryRequest
from ..services.data_access.exceptions import DataAccessError
from ..services.context_manager import context_manager
from ..services.nlp.intents import intent_classifier, IntentResult
from ..rules.engine import evaluate_rules
from ..utils.text_matching import closest_match

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["Assistant"])


def _provider_enabled(provider: Optional[str]) -> bool:
    provider = (provider or "").lower()
    if provider == "google":
        return bool(settings.GOOGLE_TTS_API_KEY)
    if provider == "azure":
        return bool(settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION)
    if provider == "aws":
        return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.AWS_REGION)
    if provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    return True  # system veya tanımsız sağlayıcılar için


class ParseIn(BaseModel):
    text: str = Field(min_length=1)


class ParsedItem(BaseModel):
    urun: str
    adet: int
    fiyat: Optional[float] = None


class ParseOut(BaseModel):
    items: List[ParsedItem]
    not_matched: List[str] = []


def _extract_candidates(text: str) -> List[Tuple[str, int]]:
    # Basit kural tabanlı çıkarım: "2 latte", "latte 2 tane", "bir americano"
    t = text.casefold()
    t = re.sub(r"[,.;\n]", " ", t)
    tokens = t.split()
    # Selamlama kelimeleri ve yardımcı kelimeleri atla
    skip_words = {
        "tane", "adet", "ve",
        "merhaba", "selam", "selamlar", "hey", "hello", "hi", 
        "hosgeldin", "hos geldin", "günaydın", "gunaydin",
        "iyi günler", "iyi gunler", "iyi akşamlar", "iyi aksamlar",
        "teşekkürler", "tesekkurler", "sağol", "sagol", "teşekkür", "tesekkur"
    }
    variation_keywords = {
        "orta", "sade", "sekerli", "şekerli", "sekersiz", "şekersiz",
        "az", "bol", "double", "duble", "single", "shotlu", "shotsuz",
    "küçük", "kucuk", "buyuk", "büyük", "beyaz", "sicak", "soğuk", "soguk",
    "ketcapli", "ketçaplı", "ketcapsiz", "ketçapsız", "mayonezli", "mayonezsiz",
    "acisiz", "acılı", "acili", "acili", "zeytinsiz", "zeytinli"
    }

    pairs: List[Tuple[str, int]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in skip_words:
            i += 1
            continue
        adet: Optional[int] = None
        # sayısal
        if tok.isdigit():
            adet = int(tok)
        elif tok in NUMBER_WORDS:
            adet = NUMBER_WORDS[tok]

        if adet is not None:
            # Sayıdan önce gelen kelimeyi kontrol et (eğer varsa)
            # Eğer sayıdan önce gelen kelime skip_words'de ise, onu atla
            if i > 0 and tokens[i - 1] in skip_words:
                # Önceki kelime skip_words'de, bu normal (zaten atlandı)
                pass
            # Sonraki kelimeleri birleştir (bir sonraki sayıya veya skip_word'e kadar)
            # ÖNEMLİ: Varyasyon isimleri genelde kısa (1-4 karakter: orta, sade, şekerli) ve ürün adlarından sonra gelir
            # Bu yüzden maksimum 3 kelime birleştir (çoğu ürün adı 1-3 kelime)
            product_words = []
            j = i + 1
            max_product_words = 3  # Maksimum ürün adı uzunluğu
            
            # İlk kelimeyi kontrol et: Eğer çok kısa ise (<=4 karakter) ve sonraki kelime uzunsa, muhtemelen varyasyon
            # Örnek: "1 orta türk kahvesi" -> "orta" varyasyon (4 karakter, kısa), "türk" ürün adı (uzun)
            # Ama "1 çay" -> "çay" ürün adı (3 karakter, kısa ama geçerli, sonraki kelime yok)
            if j < len(tokens):
                first_tok = tokens[j]
                # Bir sonraki sayı veya skip_word ise dur
                if first_tok in skip_words or first_tok.isdigit() or first_tok in NUMBER_WORDS:
                    # Sonraki kelime yok veya sayı/skip_word, bu durumda ürün adı eksik
                    i += 1
                    continue
                # Eğer ilk kelime çok kısa ise (<=4 karakter), sonraki kelimeleri kontrol et
                # "1 orta türk kahvesi" gibi: "orta" varyasyon (kısa), "türk kahvesi" ürün adı (uzun birleşik)
                if len(first_tok) <= 4 and first_tok in variation_keywords and j + 1 < len(tokens):
                    # Sonraki kelimeleri birleştirerek uzunluk kontrolü yap
                    potential_product_words = []
                    k = j + 1
                    while k < len(tokens) and len(potential_product_words) < max_product_words:
                        next_tok = tokens[k]
                        if next_tok in skip_words or next_tok.isdigit() or next_tok in NUMBER_WORDS:
                            break
                        potential_product_words.append(next_tok)
                        k += 1
                    # Birleştirilmiş kelimelerin toplam uzunluğu 6'dan fazlaysa muhtemelen ürün adı
                    if potential_product_words:
                        combined_length = sum(len(w) for w in potential_product_words) + len(potential_product_words) - 1  # + boşluklar
                        if combined_length >= 6:
                            # İlk kelime ("orta") muhtemelen varyasyon, sonraki kelimeler ürün adı
                            # "türk kahvesi"ni parse et (adet'i koruyarak)
                            product_name = " ".join(potential_product_words)
                            pairs.append((product_name, adet))
                            i = k  # "türk kahvesi"nin sonuna atla
                            continue
            
            inline_variations: List[str] = []
            # ÖNEMLİ: İlk kelimeyi al ve sonraki kelimeleri de kontrol et
            # Eğer ilk kelime tek başına bir ürün değilse, sonraki kelimeleri de dahil et
            first_word = tokens[j] if j < len(tokens) else None
            if first_word:
                product_words.append(first_word)
                j += 1
            
            # Sonraki kelimeleri birleştir (maksimum 3 kelime toplam)
            while j < len(tokens) and len(product_words) < max_product_words:
                next_tok = tokens[j]
                # Bir sonraki sayı veya skip_word bulunursa dur
                if next_tok in skip_words or next_tok.isdigit() or next_tok in NUMBER_WORDS:
                    break
                if next_tok in variation_keywords:
                    inline_variations.append(next_tok)
                    j += 1
                    continue
                # Eğer çok kısa bir kelime ise (1-4 karakter, muhtemelen varyasyon ismi) ve zaten 2+ kelime birleştirdiysek, dur
                # Örnek: "türk kahvesi orta" -> "türk kahvesi" (orta dahil etme)
                # ANCAK: "menengiç kahvesi" gibi durumlarda "kahvesi" de dahil edilmeli
                if len(product_words) >= 1 and len(next_tok) <= 7:
                    # Ürün adı ekleri listesi (Türkçe'de yaygın ekler)
                    product_suffixes = [
                        "kahvesi", "kahve", "cayı", "çayı", "çay", "suyu", "suyu", 
                        "sütü", "sutu", "süt", "suyu", "suyu", "limonatası", "limonata",
                        "çorbası", "corbası", "çorba", "corbası", "tatlısı", "tatlısı",
                        "tatlı", "tatlısı", "böreği", "boregi", "börek", "borek"
                    ]
                    # Eğer sonraki kelime bir ürün adı eki ise, dahil et
                    if next_tok.lower() in product_suffixes:
                        # Bu bir ürün adı eki, dahil et
                        product_words.append(next_tok)
                        j += 1
                        continue
                    # Eğer zaten 2+ kelime birleştirdiysek ve sonraki kelime kısa ise, muhtemelen varyasyon
                    if len(product_words) >= 2 and len(next_tok) <= 4:
                        # Muhtemelen bir varyasyon ismi, dur
                        break
                product_words.append(next_tok)
                j += 1
            if product_words:
                # Tüm kelimeleri birleştir: "menengiç kahvesi" -> "menengiç kahvesi"
                product_name = " ".join(product_words)
                pairs.append((product_name, adet))
                if inline_variations:
                    for var_token in inline_variations:
                        pairs.append((var_token, adet))
                i = j  # İşlenen kelimelerin sonuna atla
                continue
            else:
                i += 1
                continue

        # "urun 2" formu - ama önce selamlama kelimesi olup olmadığını kontrol et
        if i + 1 < len(tokens) and tokens[i + 1].isdigit():
            # Eğer bu kelime skip_words'de ise, parse etme (zaten yukarıda atlandı)
            # Buraya gelmemeli ama yine de kontrol edelim
            if tok not in skip_words:
                pairs.append((tok, int(tokens[i + 1])))
            i += 2
        else:
            # Sayı olmayan kelime - zaten skip_words kontrolü yukarıda yapıldı
            i += 1

    # Parse edilmemiş kelimeleri kontrol et (varyasyon isimleri vb. için)
    # ÖNEMLİ: Sadece pairs boşsa değil, parse edilmemiş kelimeler varsa da kontrol et
    greeting_skip = {"merhaba", "selam", "selamlar", "hey", "hello", "hi", "hosgeldin", "hos", "geldin", "günaydın", "iyi", "akşamlar", "günler", "lutfen", "please", "tesekkurler", "tesekkur", "thanks"}
    skip_words_all = skip_words | greeting_skip
    
    # Parse edilmiş ürün adlarının tüm kelimelerini topla (alt string kontrolü için)
    parsed_product_words = set()
    for name, _ in pairs:
        # Ürün adındaki tüm kelimeleri normalize edip ekle
        # Örnek: "türk kahvesi" -> {"turk", "kahvesi", "turk kahvesi"}
        words = name.split()
        for word in words:
            parsed_product_words.add(normalize_name(word))
        # Tam adı da ekle
        parsed_product_words.add(normalize_name(name))
    
    # Parse edilmemiş token'ları bul (sayı olmayan, skip_words'de olmayan)
    for i, tok in enumerate(tokens):
        if tok.isdigit() or tok in skip_words_all or tok in NUMBER_WORDS:
            continue
        # Bu token bir pair'de kullanılmış mı kontrol et
        tok_norm = normalize_name(tok)
        # Kontrol 1: Token'ın normalize edilmiş hali bir pair isminde geçiyor mu?
        # Kontrol 2: Token'ın normalize edilmiş hali parse edilmiş ürün adlarının kelimelerinde var mı?
        tok_in_pairs = False
        for name, _ in pairs:
            name_norm = normalize_name(name)
            # Tam eşleşme veya alt string kontrolü
            if tok_norm == name_norm or tok_norm in name_norm or name_norm in tok_norm:
                tok_in_pairs = True
                break
        # Eğer token parse edilmiş ürün adlarının kelimelerinden biri ise, ekleme
        if tok_norm in parsed_product_words:
            tok_in_pairs = True
        
        if not tok_in_pairs:
            # Parse edilmemiş bir kelime, varyasyon ismi olabilir
            pairs.append((tok, 1))
            logging.info(f"[EXTRACT] Added unparsed token as potential variation: '{tok}'")
    
    # Eğer hiç pair yoksa (sadece greeting vb. varsa), tüm parse edilmemiş kelimeleri ekle
    if not pairs and tokens:
        for tok in tokens:
            if tok.isdigit():
                continue
            if tok not in skip_words_all:
                pairs.append((tok, 1))

    return pairs


def _parse_quantity_token(token: str) -> Optional[int]:
    if not token:
        return None
    if token.isdigit():
        try:
            return int(token)
        except ValueError:
            return None
    return NUMBER_WORDS.get(token)


def _extract_menu_quantities(text: str, price_keys: Iterable[str]) -> Dict[str, int]:
    """
    Metindeki sayıları ve menü ürünlerini eşleştirerek olası adetleri çıkar.
    Özellikle '4 fistik ruyasi pasta' gibi ifadelerde çok kelimeli ürünlerin
    doğru tespit edilmesini sağlar.
    """
    if not text:
        return {}

    normalized_text = normalize_name(text)
    if not normalized_text:
        return {}

    tokens = normalized_text.split()
    if not tokens:
        return {}

    # Menü anahtarlarını kelime listesi olarak hazırla (uzun isimler önce gelsin)
    key_tokens = {key: key.split() for key in price_keys}
    sorted_keys = sorted(key_tokens.items(), key=lambda kv: len(kv[1]), reverse=True)
    results: Dict[str, int] = {}

    i = 0
    while i < len(tokens):
        qty = _parse_quantity_token(tokens[i])
        if qty is None:
            i += 1
            continue

        j = i + 1
        while j < len(tokens):
            if _parse_quantity_token(tokens[j]) is not None:
                break
            j += 1

        phrase_tokens = tokens[i + 1:j]
        if not phrase_tokens:
            i += 1
            continue

        match_key = None
        # Önce birebir kelime sıralaması eşleşmelerini dene
        for key, key_token_list in sorted_keys:
            if len(phrase_tokens) >= len(key_token_list) and phrase_tokens[:len(key_token_list)] == key_token_list:
                match_key = key
                break

        if not match_key:
            phrase = " ".join(phrase_tokens)
            close_matches = difflib.get_close_matches(
                phrase,
                [key for key, _ in sorted_keys],
                n=1,
                cutoff=0.88,
            )
            if close_matches:
                match_key = close_matches[0]

        if match_key:
            results[match_key] = results.get(match_key, 0) + qty
            i = j
        else:
            i += 1

    return results


@router.post("/parse", response_model=ParseOut)
async def parse_order(
    payload: ParseIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    rows = await db.fetch_all(
        "SELECT ad, fiyat FROM menu WHERE aktif = TRUE AND sube_id = :sid;",
        {"sid": sube_id},
    )
    price_map: Dict[str, float] = {}
    name_map: Dict[str, str] = {}
    for r in rows:
        k = normalize_name(r["ad"])
        price_map[k] = float(r["fiyat"]) if r["fiyat"] is not None else 0.0
        name_map[k] = r["ad"]
    pairs = _extract_candidates(payload.text)

    # eşleşme: normalize ederek menü anahtarlarına bak
    aggregated: Dict[str, int] = {}
    not_matched: List[str] = []
    not_matched_with_count: List[Tuple[str, int]] = []
    for name, adet in pairs:
        key = normalize_name(name)
        # en iyi anahtar: tam anahtar veya kontrollü eşleşme
        match = None
        if key in price_map:
            match = key
        else:
            key_tokens = [tok for tok in key.split() if tok]
            if len(key_tokens) >= 2:
                for mk in price_map.keys():
                    mk_tokens = mk.split()
                    if set(key_tokens).issubset(set(mk_tokens)):
                        match = mk
                        break
            if not match and key:
                close_matches = difflib.get_close_matches(key, price_map.keys(), n=1, cutoff=0.92)
                if close_matches:
                    match = close_matches[0]
        if match:
            aggregated[match] = aggregated.get(match, 0) + max(1, int(adet))
        else:
            not_matched.append(name)

    detected_counts = _extract_menu_quantities(payload.text, price_map.keys())
    for detected_key, detected_count in detected_counts.items():
        if detected_key not in price_map:
            continue
        current = aggregated.get(detected_key, 0)
        if detected_count > current:
            logging.info(f"[PARSE] Adjusted quantity for '{name_map.get(detected_key, detected_key)}' from {current} to {detected_count} based on text pattern.")
            aggregated[detected_key] = detected_count
        elif current == 0:
            aggregated[detected_key] = detected_count

    if aggregated:
        resolved_tokens: set[str] = set()
        for resolved_key in aggregated.keys():
            normalized_key = resolved_key.replace("|", " ")
            for token in normalized_key.split():
                resolved_tokens.add(token)
        not_matched = [nm for nm in not_matched if normalize_name(nm) not in resolved_tokens]

    items = [
        ParsedItem(urun=name_map.get(k, k), adet=a, fiyat=price_map.get(k))
        for k, a in aggregated.items()
    ]
    return ParseOut(items=items, not_matched=not_matched)


class CreateFromTextIn(BaseModel):
    masa: str
    text: str


@router.post("/siparis")
async def create_order_from_text(
    payload: CreateFromTextIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    import json
    import logging
    
    try:
        # Parse order manually (aynı mantık ama bağımsız çalıştır)
        rows = await db.fetch_all(
            "SELECT ad, fiyat FROM menu WHERE aktif = TRUE AND sube_id = :sid;",
            {"sid": sube_id},
        )
        price_map: Dict[str, float] = {}
        name_map: Dict[str, str] = {}
        for r in rows:
            k = normalize_name(r["ad"])
            price_map[k] = float(r["fiyat"]) if r["fiyat"] is not None else 0.0
            name_map[k] = r["ad"]
        
        pairs = _extract_candidates(payload.text)
        aggregated: Dict[str, int] = {}
        not_matched: List[str] = []
        for name, adet in pairs:
            key = normalize_name(name)
            match = None
            if key in price_map:
                match = key
            else:
                for mk in price_map.keys():
                    if key and (key in mk or mk in key):
                        match = mk
                        break
            if match:
                aggregated[match] = aggregated.get(match, 0) + max(1, int(adet))
            else:
                not_matched.append(name)
        
        detected_counts = _extract_menu_quantities(payload.text, price_map.keys())
        for detected_key, detected_count in detected_counts.items():
            if detected_key not in price_map:
                continue
            current = aggregated.get(detected_key, 0)
            if detected_count > current:
                logging.info(f"[PUBLIC_ORDER] Adjusted quantity for '{name_map.get(detected_key, detected_key)}' from {current} to {detected_count} based on text pattern.")
                aggregated[detected_key] = detected_count
            elif current == 0:
                aggregated[detected_key] = detected_count
        
        if not aggregated:
            raise HTTPException(status_code=400, detail="Sipariş çıkarılamadı")

        sepet = [
            {"urun": name_map.get(k, k), "adet": a, "fiyat": float(price_map.get(k, 0))}
            for k, a in aggregated.items()
        ]
        tutar = sum(i["adet"] * i["fiyat"] for i in sepet)

        # Adisyon sistemi: Masada açık adisyon varsa al, yoksa oluştur
        from ..routers.adisyon import _get_or_create_adisyon, _update_adisyon_totals
        adisyon_id = await _get_or_create_adisyon(payload.masa, sube_id)

        row = await db.fetch_one(
            """
            INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar)
            VALUES (:sid, :masa, :adisyon_id, CAST(:sepet AS JSONB), 'yeni', :tutar)
            RETURNING id, masa, durum, tutar, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "adisyon_id": adisyon_id, "sepet": json.dumps(sepet, ensure_ascii=False), "tutar": tutar},
        )
        
        # Adisyon toplamlarını güncelle
        try:
            await _update_adisyon_totals(adisyon_id, sube_id)
        except Exception as e:
            logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
        
        if not row:
            raise HTTPException(status_code=500, detail="Sipariş kaydedilemedi")
        
        # created_at kontrolü - database record'larında .get() metodu yok
        created_at_value = None
        try:
            if row["created_at"] is not None:
                created_at_value = row["created_at"].isoformat()
        except (KeyError, AttributeError):
            created_at_value = None
        
        return {
            "id": row["id"],
            "masa": row["masa"],
            "durum": row["durum"],
            "tutar": float(row["tutar"]),
            "created_at": created_at_value,
            "not_matched": not_matched,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in create_order_from_text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sipariş oluşturulamadı: {str(e)}")


@router.get("/oner")
async def recommend(
    gun: int = 14,
    limit: int = 10,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    q = """
    WITH z AS (
      SELECT lower(unaccent(trim(si->>'urun'))) AS urun_norm,
             (si->>'adet')::int AS adet,
             (si->>'fiyat')::numeric AS fiyat
      FROM siparisler s
      CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
      WHERE s.sube_id = :sid
        AND s.created_at >= (NOW() - make_interval(days => :gun))
        AND s.durum <> 'iptal'
    )
    SELECT urun_norm AS urun,
           SUM(adet)::int AS adet,
           SUM(adet * fiyat)::float AS ciro
    FROM z
    GROUP BY urun_norm
    ORDER BY adet DESC, ciro DESC
    LIMIT :limit
    """
    rows = await db.fetch_all(q, {"sid": sube_id, "gun": gun, "limit": limit})
    return [dict(r) for r in rows]


def json_dumps(v: Any) -> str:
    import json
    return json.dumps(v, ensure_ascii=False)


# --- Public (QR) endpoint: no auth, minimal validation ---
class PublicCreateIn(BaseModel):
    masa: str
    text: str
    sube_id: Optional[int] = 1


@router.post("/public/siparis")
async def public_create_order(payload: PublicCreateIn):
    sube_id = int(payload.sube_id or 1)
    # Build price and name maps
    rows = await db.fetch_all(
        "SELECT ad, fiyat FROM menu WHERE aktif = TRUE AND sube_id = :sid;",
        {"sid": sube_id},
    )
    price_map: Dict[str, float] = {}
    name_map: Dict[str, str] = {}
    for r in rows:
        k = normalize_name(r["ad"])  # normalize key
        price_map[k] = float(r["fiyat"]) if r["fiyat"] is not None else 0.0
        name_map[k] = r["ad"]

    pairs = _extract_candidates(payload.text)
    aggregated: Dict[str, int] = {}
    not_matched: List[str] = []
    for name, adet in pairs:
        key = normalize_name(name)
        match = None
        if key in price_map:
            match = key
        else:
            for mk in price_map.keys():
                if key and (key in mk or mk in key):
                    match = mk
                    break
        if match:
            aggregated[match] = aggregated.get(match, 0) + max(1, int(adet))
        else:
            not_matched.append(name)

    if not aggregated:
        raise HTTPException(status_code=400, detail="Sipariş anlaşılamadı")

    sepet = [
        {"urun": name_map.get(k, k), "adet": a, "fiyat": float(price_map.get(k) or 0)}
        for k, a in aggregated.items()
    ]
    tutar = sum(i["adet"] * i["fiyat"] for i in sepet)

    row = await db.fetch_one(
        """
        INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar)
        VALUES (:sid, :masa, CAST(:sepet AS JSONB), 'yeni', :tutar)
        RETURNING id, masa, durum, tutar, created_at
        """,
        {"sid": sube_id, "masa": payload.masa, "sepet": json_dumps(sepet), "tutar": tutar},
    )
    return {
        "id": row["id"],
        "masa": row["masa"],
        "durum": row["durum"],
        "tutar": float(row["tutar"]),
        "created_at": row["created_at"],
        "not_matched": not_matched,
    }


# --- Realtime Chat (SSE) ---
class ChatIn(BaseModel):
    text: str = Field(min_length=1)
    system: Optional[str] = None


async def _sse(gen: AsyncIterator[str]):
    async for chunk in gen:
        yield f"data: {chunk}\n\n"


@router.post("/chat_stream")
async def chat_stream(payload: ChatIn):
    provider = await get_llm_provider(tenant_id=None)  # Public endpoint, tenant_id yok
    gen = provider.stream(payload.text, system=payload.system)
    return StreamingResponse(_sse(gen), media_type="text/event-stream")


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    masa: Optional[str] = None
    sube_id: Optional[int] = 1
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    order: Optional[Dict[str, Any]] = None
    shortages: Optional[List[Dict[str, Any]]] = None
    not_matched: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    conversation_id: Optional[str] = None
    detected_language: Optional[str] = None  # tr, en, fr, de, ar, es
    audio_base64: Optional[str] = None  # Base64 encoded WAV audio


async def _build_chat_response(
    *,
    reply: str,
    order: Optional[Dict[str, Any]] = None,
    shortages: Optional[List[Dict[str, Any]]] = None,
    not_matched: Optional[List[str]] = None,
    suggestions: Optional[List[str]] = None,
    conversation_id: Optional[str] = None,
    detected_language: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> ChatResponse:
    audio_base64: Optional[str] = None
    if settings.ASSISTANT_ENABLE_TTS and reply:
        try:
            logging.info(f"[TTS_REQUEST] Generating audio for reply (length: {len(reply)})")
            audio_bytes = await synthesize_speech(
                reply,
                language=detected_language,
                tenant_id=tenant_id,
                assistant_type="customer",
            )
            if audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
                logging.info(f"[TTS_SUCCESS] Generated {len(audio_base64)} chars base64 audio")
            else:
                logging.warning("[TTS_WARNING] No audio bytes returned")
        except Exception as exc:
            logging.error("TTS synthesis failed: %s", exc, exc_info=True)

    return ChatResponse(
        reply=reply,
        order=order,
        shortages=shortages,
        not_matched=not_matched,
        suggestions=suggestions,
        conversation_id=conversation_id,
        detected_language=detected_language,
        audio_base64=audio_base64,
    )


_fallback_stock: Dict[Tuple[int, str], float] = {}
_chat_sessions: Dict[str, List[Dict[str, str]]] = {}
_session_languages: Dict[str, str] = {}  # conversation_id -> language code
_pending_aggregated: Dict[str, Dict[str, int]] = {}  # conversation_id -> aggregated items waiting for variation
_pending_variations: Dict[str, List[Dict[str, Any]]] = {}  # conversation_id -> varyasyon bekleyen ürünler listesi
SESSION_MAX_MESSAGES = 20

NUMBER_WORDS: Dict[str, int] = {
    "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
    "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7, "sekiz": 8,
    "dokuz": 9, "on": 10
}

MILK_KEYWORDS = {
    "latte",
    "milk",
    "sut",
    "süt",
    "cream",
    "kaymak",
    "peynir",
    "cheese",
    "mozzarella",
    "krem",
    "mocha",
    "cappuccino",
    "milkshake",
    "milk tea",
    "panna",
    "pizza",
}

COFFEE_KEYWORDS = {
    "kahve",
    "kahvesi",
    "coffee",
    "espresso",
    "americano",
    "latte",
    "cappuccino",
    "macchiato",
    "mocha",
    "flat white",
    "filtre",
}

HUNGER_HINTS = {
    "aciktim",
    "aciktik",
    "karnim acikti",
    "karnim acik",
    "cok aciktim",
    "cok aciktik",
    "ne yesek",
    "aclik basti",
    "acliktan oluyorum",
    "yav ne yesek",
    "bir sey yiyelim",
    "sekerim dustu",
    "enerjim dustu",
    "aciktim yav",
}

HERBAL_TEA_KEYWORDS = [
    normalize_name(keyword)
    for keyword in [
        "adaçayı",
        "ada çayı",
        "nane limon",
        "nane-limon",
        "ıhlamur",
        "ihlamur",
        "kuşburnu",
        "kuş burnu",
        "papatya",
        "rezene",
        "zencefil",
        "bitki çayı",
        "bitki cayi",
        "melisa",
    ]
]

COLD_DRINK_KEYWORDS = {
    "soğuk",
    "soguk",
    "iced",
    "buzlu",
    "buz",
    "buzgibi",
    "buz gibi",
    "frappe",
    "smoothie",
    "limonata",
    "milkshake",
    "frappuccino",
    "cold brew",
    "shake",
    "serin",
    "ferah",
}

HOT_DRINK_KEYWORDS = {
    "sıcak",
    "sicak",
    "çay",
    "cay",
    "kahve",
    "salep",
    "latte",
    "americano",
    "espresso",
    "mocha",
    "hot chocolate",
    "sahlep",
    "bitki çayı",
    "bitki cayi",
    "ıhlamur",
    "ihlamur",
}

DESSERT_KEYWORDS = {
    normalize_name(word)
    for word in [
        "pasta",
        "pastalar",
        "tatli",
        "tatlı",
        "tatlilar",
        "tatlılar",
        "cheesecake",
        "chesskake",
        "cizkek",
        "çizkek",
        "cake",
        "kek",
        "brownie",
        "cookie",
        "kurabiye",
        "tart",
        "tartolet",
        "ekler",
        "eclair",
        "profiterol",
        "magnolia",
        "sufle",
        "parfe",
        "puding",
        "sweet",
        "dessert",
    ]
}

DRINK_KEYWORDS = {
    normalize_name(word)
    for word in [
        "cay",
        "çay",
        "kahve",
        "coffee",
        "espresso",
        "americano",
        "latte",
        "mocha",
        "macchiato",
        "filtre kahve",
        "turk kahvesi",
        "türk kahvesi",
        "sicak",
        "sıcak",
        "soguk",
        "soğuk",
        "icecek",
        "içecek",
        "limonata",
        "milkshake",
        "smoothie",
        "frappe",
        "buzlu",
        "buz",
        "cold brew",
        "matcha",
        "hot chocolate",
        "salep",
        "sahlep",
        "icetea",
        "ice tea",
        "buzlu cay",
        "buzlu çay",
        "soda",
        "gazoz",
    ]
}

INGREDIENT_QUESTION_KEYWORDS = {
    "icinde ne var",
    "içinde ne var",
    "icinde",
    "içinde",
    "icerik",
    "içerik",
    "icerigi",
    "içeriği",
    "ingredient",
    "ingredients",
    "malzeme",
    "malzemesi",
    "tarif",
    "reçete",
    "recete",
    "alerji",
    "alerjen",
    "allergy",
}

GLUTEN_INGREDIENT_HINTS = {
    "un",
    "bugday",
    "buğday",
    "arpa",
    "cavdar",
    "çavdar",
    "yulaf",
    "gluten",
    "makarna",
    "pizza",
}

NUT_INGREDIENT_HINTS = {
    "fistik",
    "fıstık",
    "badem",
    "ceviz",
    "findik",
    "fındık",
    "antep",
    "kajun",
    "fındıklı",
}

LOW_STOCK_THRESHOLD = 3

CUSTOMER_SMALL_TALK_KEYWORDS = {
    "sadece bakiyorum",
    "bakiyorum",
    "geziyorum",
    "dolasiyorum",
    "sohbet edelim",
    "hala karar vermedim",
    "emin degilim",
    "hepsini merak ediyorum",
}

POSITIVE_MOOD_KEYWORDS = {
    "harika hissediyorum",
    "keyfim yerinde",
    "mutluyum",
    "cok iyiyim",
    "enerjim yuksek",
}

NEGATIVE_MOOD_KEYWORDS = {
    "moralim bozuk",
    "canim sikik",
    "canim sikkin",
    "keyfim yok",
    "kotu hissediyorum",
    "kotu gun",
    "yorgunum",
    "bitkinim",
}

SLEEPY_KEYWORDS = {
    "uykum var",
    "uykum geldi",
    "uykuluyum",
    "uykum kacmasin",
    "uyku oncesi",
    "uyku icin",
}

ENERGY_BOOST_KEYWORDS = {
    "uyandir",
    "enerjim dustu",
    "enerji lazim",
    "kahve ihtiyacim var",
    "ayilmak istiyorum",
    "yorgun hissediyorum",
}

WELLBEING_KEYWORDS = {
    "nasilsin",
    "nasılsın",
    "nasilsiniz",
    "nasılsınız",
    "ne haber",
    "naber",
    "halin nicedir",
    "nasil gidiyor",
    "neler yapiyorsun",
    "neler yapıyorsun",
    "iyi misin",
    "iyimisiniz",
    "iyimisiniz",
}

SENSITIVE_BUSINESS_KEYWORDS = {
    "ciro",
    "cirolar",
    "kar",
    "karlilik",
    "karlılık",
    "maliyet",
    "maliyetler",
    "gider",
    "giderler",
    "satış rakamı",
    "satis rakami",
    "satış hedefi",
    "kar marji",
    "kar marjı",
    "kar oranı",
    "profit",
    "revenue",
    "expense",
    "gelir",
    "masraf",
    "kazanc",
    "kazanç",
}

FORCE_DAIRY_MENU_KEYS = {
    "menengic",
    "menengic kahvesi",
    "menengic latte",
}

FORCE_NON_DAIRY_MENU_KEYS = {
    "turk kahvesi",
    "turk kahve",
    "turkce kahve",
}

CAFFEINE_KEYWORDS = {
    "kahve",
    "coffee",
    "espresso",
    "americano",
    "latte",
    "macchiato",
    "cappuccino",
    "cold brew",
    "tea",
    "çay",
    "cay",
    "matcha",
    "cola",
    "kola",
}

CAFFEINE_FREE_HINTS = {"kafeinsiz", "decaf", "yok kofein", "kafeinsiz"}
DAIRY_FREE_HINTS = {"sutsuz", "süt içermeyen", "lactose free", "vegan"}


def _tokenize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "").casefold()
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _item_stock_quantity(item: Dict[str, Any]) -> Optional[float]:
    value = item.get("stok_miktari")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_item_available(item: Dict[str, Any]) -> bool:
    qty = _item_stock_quantity(item)
    if qty is None:
        return True
    return qty > 0


def _is_item_low_stock(item: Dict[str, Any]) -> bool:
    qty = _item_stock_quantity(item)
    if qty is None:
        return False
    if qty <= 0:
        return True
    min_level = item.get("stok_min")
    try:
        min_level_val = float(min_level) if min_level is not None else None
    except (TypeError, ValueError):
        min_level_val = None
    if item.get("stok_kritik") == 1:
        return True
    threshold = max(LOW_STOCK_THRESHOLD, min_level_val or 0)
    return qty <= threshold


def _format_stock_status(item: Dict[str, Any]) -> Optional[str]:
    qty = _item_stock_quantity(item)
    if qty is None:
        return None
    birim = (item.get("stok_birim") or "").strip() or "adet"
    qty_display = int(qty) if abs(qty - int(qty)) < 0.01 else round(qty, 1)
    if qty <= 0:
        return "Stokta kalmadı"
    if _is_item_low_stock(item):
        return f"Stokta son {qty_display} {birim}"
    return f"Stokta {qty_display} {birim} var"


def _format_ingredient_summary(item: Dict[str, Any], limit: int = 4) -> Optional[str]:
    ingredients = item.get("ingredients") or []
    names: List[str] = []
    for ing in ingredients:
        label = (ing.get("ad") or "").strip()
        if not label:
            continue
        miktar = ing.get("miktar")
        birim = (ing.get("birim") or "").strip()
        try:
            miktar_val = float(miktar) if miktar is not None else None
        except (TypeError, ValueError):
            miktar_val = None
        if miktar_val is not None and birim:
            miktar_display = int(miktar_val) if abs(miktar_val - int(miktar_val)) < 0.01 else round(miktar_val, 2)
            names.append(f"{label} ({miktar_display} {birim})")
        else:
            names.append(label)
        if len(names) >= limit:
            break
    if not names:
        return None
    return "İçindekiler: " + ", ".join(names)


def _extract_variation_mentions(
    text: str, pending_variations: Optional[List[Dict[str, Any]]]
) -> Dict[str, int]:
    if not text or not pending_variations:
        return {}

    plain = _tokenize(text)
    tokens = [tok for tok in plain.split() if tok]
    if not tokens:
        return {}

    variation_sequences: Dict[str, List[str]] = {}
    for pending in pending_variations:
        for var_name in pending.get("varyasyonlar") or []:
            normalized = normalize_name(var_name)
            if not normalized:
                continue
            variation_sequences[var_name] = normalized.split()

    mentions: Dict[str, int] = {}
    pending_number: Optional[int] = None
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token.isdigit():
            pending_number = int(token)
            idx += 1
            continue

        matched_name: Optional[str] = None
        matched_len = 0
        for original_name, seq in variation_sequences.items():
            seq_len = len(seq)
            if seq_len == 0 or idx + seq_len > len(tokens):
                continue
            if tokens[idx : idx + seq_len] == seq:
                matched_name = original_name
                matched_len = seq_len
                break

        if matched_name:
            count = pending_number or 1
            mentions[matched_name] = mentions.get(matched_name, 0) + count
            pending_number = None
            idx += matched_len
        else:
            pending_number = None
            idx += 1

    return mentions


def _is_milky_coffee_query(text: str) -> bool:
    if not text:
        return False
    plain = _tokenize(text)
    has_milk = ("sutlu" in plain) or ("milk" in plain)
    has_coffee = ("kahve" in plain) or ("coffee" in plain)
    phrases = [
        "sutlu kahve",
        "sutlu kahveler",
        "milk coffee",
        "milky coffee",
    ]
    return (has_milk and has_coffee) or any(phrase in plain for phrase in phrases)


def _detect_hunger_signal(text: str) -> bool:
    if not text:
        return False
    plain = _tokenize(text)
    return any(hint in plain for hint in HUNGER_HINTS)


def _has_sensitive_business_query(text: str) -> bool:
    if not text:
        return False
    plain = _tokenize(text)
    return any(keyword in plain for keyword in SENSITIVE_BUSINESS_KEYWORDS)


def _detect_language(text: str) -> str:
    """
    Basit dil algılama - Türkçe, İngilizce, Fransızca, Almanca, Arapça, İspanyolca
    Gerçek bir dil algılama için langdetect kütüphanesi kullanılabilir ama basit yaklaşım yeterli olabilir
    """
    if not text or len(text.strip()) == 0:
        return "tr"  # Default
    
    text_lower = text.lower()
    
    # Türkçe karakterler ve yaygın kelimeler
    turkish_chars = set("çğıöşüÇĞIİÖŞÜ")
    turkish_words = {"merhaba", "selam", "evet", "hayır", "teşekkür", "lütfen", "kaç", "ne", "nasıl", "var", "yok"}
    
    # Arapça karakterler
    arabic_chars = set("ابتثجحخدذرزسشصضطظعغفقكلمنهوي")
    
    # Fransızca yaygın kelimeler
    french_words = {"bonjour", "salut", "oui", "non", "merci", "s il vous plaît", "combien", "que", "comment"}
    
    # Almanca yaygın kelimeler
    german_words = {"hallo", "guten", "ja", "nein", "danke", "bitte", "wie", "was", "wie viel"}
    
    # İngilizce yaygın kelimeler
    english_words = {"hello", "hi", "yes", "no", "thanks", "please", "how", "what", "how much"}
    
    # İspanyolca yaygın kelimeler
    spanish_words = {"hola", "buenos", "días", "tardes", "noche", "sí", "no", "gracias", "por favor", "cuánto", "qué", "cómo", "café", "quiero"}
    
    # Arapça kontrolü - Arapça karakterler varsa
    if any(c in text for c in arabic_chars):
        return "ar"
    
    # İspanyolca kontrolü - öncelikli çünkü "hola" gibi yaygın kelimeler var
    spanish_score = sum(1 for w in spanish_words if w in text_lower)
    if spanish_score >= 1:  # Tek kelime bile yeterli (örn: "hola")
        return "es"
    
    # Türkçe kontrolü
    turkish_score = sum(1 for c in text if c in turkish_chars) + sum(1 for w in turkish_words if w in text_lower)
    if turkish_score > 2:
        return "tr"
    
    # Fransızca kontrolü
    french_score = sum(1 for w in french_words if w in text_lower)
    if french_score >= 2:
        return "fr"
    
    # Almanca kontrolü
    german_score = sum(1 for w in german_words if w in text_lower)
    if german_score >= 2:
        return "de"
    
    # İngilizce kontrolü
    english_score = sum(1 for w in english_words if w in text_lower)
    if english_score >= 2:
        return "en"
    
    # Default olarak Türkçe
    return "tr"


def _get_language_name(code: str) -> str:
    """Dil kodundan dil adını döndür"""
    names = {
        "tr": "Türkçe",
        "en": "İngilizce",
        "fr": "Fransızca",
        "de": "Almanca",
        "ar": "Arapça",
        "es": "İspanyolca"
    }
    return names.get(code, "Türkçe")


def _detect_table_number(text: str) -> Optional[str]:
    """Detect table number patterns like A22, B5, Masa 3, etc."""
    import re
    text_clean = text.strip()

    # Pattern 1: Letter + Number (A22, B5, etc.)
    match = re.match(r'^([A-Za-z])(\d+)$', text_clean)
    if match:
        return match.group(1).upper() + match.group(2)

    # Pattern 2: Just number (5, 22, etc.)
    match = re.match(r'^(\d+)$', text_clean)
    if match:
        return match.group(1)

    # Pattern 3: "Masa X" or "masa X"
    match = re.match(r'^[Mm]asa\s+([A-Za-z]?\d+)$', text_clean)
    if match:
        return match.group(1).upper()

    return None


def _normalize_stock_key(name: str) -> str:
    return normalize_name(name or "")


async def _load_menu_details(sube_id: int) -> List[Dict[str, Any]]:
    # N+1 query düzeltmesi: Tek JOIN sorgusu ile tüm varyasyonları getir
    rows = await db.fetch_all(
        """
        SELECT
            m.id,
            m.ad,
            m.fiyat,
            m.kategori,
            m.aciklama,
            NULL::numeric as stok_miktari,
            NULL::numeric as stok_min,
            NULL::numeric as stok_kritik,
            NULL::text as stok_birim,
            mv.id as var_id, mv.ad as var_ad, mv.ek_fiyat as var_ek_fiyat, mv.sira as var_sira
        FROM menu m
        LEFT JOIN menu_varyasyonlar mv ON m.id = mv.menu_id AND mv.aktif = TRUE
        WHERE m.aktif = TRUE AND m.sube_id = :sid
        ORDER BY m.kategori NULLS LAST, m.ad ASC, mv.sira ASC, mv.ad ASC
        """,
        {"sid": sube_id},
    )
    
    # Grupla: menu_id -> variations list
    items_dict: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        menu_id = r["id"]
        if menu_id not in items_dict:
            key = normalize_name(r["ad"])
            raw_stock_value = r["stok_miktari"]
            stock_birim = (r["stok_birim"] or "").strip()
            raw_stock_min = r["stok_min"]
            stock_kritik = r["stok_kritik"]
            stock_value: Optional[float]
            try:
                stock_value = float(raw_stock_value) if raw_stock_value is not None else None
            except (TypeError, ValueError):
                stock_value = None
            # View stok bilgisi yoksa 0 döndürüyor; gerçek stok bilinmiyorsa None bırak
            if (
                stock_value == 0
                and not stock_birim
                and (raw_stock_min is None or raw_stock_min == 0)
                and (stock_kritik is None or stock_kritik == 0)
            ):
                stock_value = None
            try:
                stock_min_value = float(raw_stock_min) if raw_stock_min is not None else None
            except (TypeError, ValueError):
                stock_min_value = None
            items_dict[menu_id] = {
                "id": menu_id,
                "ad": r["ad"],
                "fiyat": float(r["fiyat"] or 0),
                "kategori": r["kategori"] or "",
                "key": key,
                "aciklama": (r["aciklama"] or "").strip(),
                "stok_miktari": stock_value,
                "stok_min": stock_min_value,
                "stok_kritik": stock_kritik,
                "stok_birim": stock_birim,
                "varyasyonlar": []
            }
        
        # Varyasyon varsa ekle
        if r["var_id"]:
            items_dict[menu_id]["varyasyonlar"].append({
                "id": r["var_id"],
                "ad": r["var_ad"],
                "ek_fiyat": float(r["var_ek_fiyat"] or 0)
            })
    
    items_list = list(items_dict.values())
    fallback_stock = _ensure_fallback_stock(sube_id, [item["key"] for item in items_list])
    for item in items_list:
        if item.get("stok_miktari") is None:
            item["stok_miktari"] = fallback_stock.get(item["key"])
    return items_list


async def _load_stock_map(sube_id: int) -> Tuple[Dict[str, float], Dict[str, bool]]:
    try:
        rows = await db.fetch_all(
            "SELECT kod, miktar FROM stok_kalemleri WHERE sube_id = :sid;",
            {"sid": sube_id},
        )
    except Exception:
        return {}, {}
    stock_map: Dict[str, float] = {}
    has_db_key: Dict[str, bool] = {}
    for r in rows:
        key = _normalize_stock_key(r["kod"])
        stock_map[key] = float(r["miktar"] or 0)
        has_db_key[key] = True
    return stock_map, has_db_key


def _ensure_fallback_stock(sube_id: int, keys: List[str]) -> Dict[str, float]:
    updated: Dict[str, float] = {}
    for key in keys:
        if (sube_id, key) not in _fallback_stock:
            _fallback_stock[(sube_id, key)] = 10.0
        updated[key] = _fallback_stock[(sube_id, key)]
    return updated


def _merge_stock(primary: Dict[str, float], fallback: Dict[str, float]) -> Dict[str, float]:
    merged = dict(fallback)
    merged.update(primary)
    return merged


async def _load_business_profile(sube_id: int) -> Dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT
            s.id,
            s.ad AS sube_ad,
            COALESCE(s.adres, '') AS adres,
            COALESCE(s.telefon, '') AS telefon,
            i.ad AS isletme_ad
        FROM subeler s
        LEFT JOIN isletmeler i ON i.id = s.isletme_id
        WHERE s.id = :sid
        """,
        {"sid": sube_id},
    )
    if not row:
        return {}
    return dict(row)


def _analyze_menu_attributes(
    items: List[Dict[str, Any]], recipe_map: Dict[str, List[str]]
) -> Tuple[
    Dict[str, Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    attr_map: Dict[str, Dict[str, Any]] = {}
    dairy_free: List[Dict[str, Any]] = []
    caffeine_free: List[Dict[str, Any]] = []
    gluten_free: List[Dict[str, Any]] = []
    for item in items:
        name_norm = _tokenize(item["ad"])
        name_key = item.get("key") or normalize_name(item["ad"])
        key = item["key"]
        contains_milk: Optional[bool] = None
        contains_caffeine: Optional[bool] = None
        contains_gluten: Optional[bool] = None
        contains_nuts: Optional[bool] = None

        if any(h in name_norm for h in DAIRY_FREE_HINTS):
            contains_milk = False
        if any(h in name_norm for h in CAFFEINE_FREE_HINTS):
            contains_caffeine = False

        recipe_ingredients = recipe_map.get(key, [])
        if recipe_ingredients:
            recipe_text = " ".join(recipe_ingredients)
            if any(k in recipe_text for k in MILK_KEYWORDS):
                contains_milk = True
            elif contains_milk is None:
                contains_milk = False
            if any(k in recipe_text for k in CAFFEINE_KEYWORDS):
                contains_caffeine = True
            elif contains_caffeine is None:
                contains_caffeine = False
            if any(k in recipe_text for k in GLUTEN_INGREDIENT_HINTS):
                contains_gluten = True
            if any(k in recipe_text for k in NUT_INGREDIENT_HINTS):
                contains_nuts = True

        if contains_milk is None:
            contains_milk = any(k in name_norm for k in MILK_KEYWORDS)
        if contains_caffeine is None:
            contains_caffeine = any(k in name_norm for k in CAFFEINE_KEYWORDS)
        if contains_gluten is None:
            contains_gluten = any(k in name_norm for k in GLUTEN_INGREDIENT_HINTS)
        if contains_nuts is None:
            contains_nuts = any(k in name_norm for k in NUT_INGREDIENT_HINTS)

        if name_key in FORCE_DAIRY_MENU_KEYS:
            contains_milk = True
        if name_key in FORCE_NON_DAIRY_MENU_KEYS:
            contains_milk = False

        attr_map[key] = {
            "contains_milk": contains_milk,
            "contains_caffeine": contains_caffeine,
             "contains_gluten": contains_gluten,
             "contains_nuts": contains_nuts,
        }
        if not contains_milk:
            dairy_free.append(item)
        if not contains_caffeine:
            caffeine_free.append(item)
        if not contains_gluten:
            gluten_free.append(item)
    return attr_map, dairy_free, caffeine_free, gluten_free


def _filter_milky_coffee_items(items: List[Dict[str, Any]], attr_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for item in items:
        key = item.get("key")
        attr = attr_map.get(key or "", {})
        if not attr.get("contains_milk"):
            continue
        name_norm = _tokenize(item["ad"])
        if any(keyword in name_norm for keyword in COFFEE_KEYWORDS):
            filtered.append(item)
    return filtered


HUNGER_KEYWORD_WEIGHTS: List[Tuple[str, int]] = [
    ("tost", 6),
    ("sandvic", 6),
    ("sandvi", 6),
    ("burger", 6),
    ("wrap", 5),
    ("döner", 5),
    ("doner", 5),
    ("pide", 4),
    ("pizza", 4),
    ("makarna", 4),
    ("salata", 3),
    ("kahvalti", 3),
    ("kahvaltı", 3),
    ("menemen", 3),
    ("omlet", 3),
    ("ana yemek", 3),
    ("zeytin", 1),
]

HUNGER_AVOID_KEYWORDS = {
    "tatli",
    "tatlı",
    "sufle",
    "cheesecake",
    "pasta",
    "cake",
    "cookie",
    "kurabiye",
    "kek",
}


def _select_hungry_recommendations(items: List[Dict[str, Any]], attr_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        if not _is_item_available(item):
            continue
        name_norm = _tokenize(item["ad"])
        category_norm = _tokenize(item.get("kategori") or "")
        score = 0.0
        for keyword, weight in HUNGER_KEYWORD_WEIGHTS:
            if keyword in name_norm or keyword in category_norm:
                score += weight
        if attr_map.get(item.get("key") or "", {}).get("contains_milk") and "kahve" not in name_norm:
            score += 1  # sıcak tost tarzı ürünler için ufak bonus
        if item.get("fiyat", 0) >= 100:
            score += 0.5
        if any(avoid in name_norm for avoid in HUNGER_AVOID_KEYWORDS):
            score -= 3
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (pair[0], pair[1].get("fiyat", 0)), reverse=True)
    top_items = [item for _, item in scored[:5]]
    if not top_items:
        fallback = [item for item in items if _is_item_available(item)]
        if fallback:
            return fallback[:5]
        return items[:5]
    return top_items


def _select_temp_recommendations(items: List[Dict[str, Any]], keywords: Set[str]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for item in items:
        if not _is_item_available(item):
            continue
        name_norm = _tokenize(item["ad"])
        category_norm = _tokenize(item.get("kategori") or "")
        if any(keyword in name_norm for keyword in keywords) or any(keyword in category_norm for keyword in keywords):
            selected.append(item)
    if not selected:
        fallback = [item for item in items if _is_item_available(item)]
        if fallback:
            return fallback[:4]
        return items[:4]
    return selected[:4]


def _select_dessert_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    desserts: List[Dict[str, Any]] = []
    for item in items:
        name_norm = _tokenize(item["ad"])
        category_norm = _tokenize(item.get("kategori") or "")
        dessert_hit = any(keyword in name_norm for keyword in DESSERT_KEYWORDS) or any(
            keyword in category_norm for keyword in DESSERT_KEYWORDS
        )
        drink_hit = any(keyword in name_norm for keyword in DRINK_KEYWORDS) or any(
            keyword in category_norm for keyword in DRINK_KEYWORDS
        )
        if dessert_hit and not drink_hit:
            desserts.append(item)
    return desserts


def _pick_menu_samples(items: List[Dict[str, Any]], count: int) -> List[str]:
    if not items:
        return []
    pool = [item for item in items if _is_item_available(item)]
    if not pool:
        pool = items
    try:
        import random
        chosen = random.sample(pool, min(count, len(pool)))
    except ValueError:
        chosen = pool[:count]
    return [item["ad"] for item in chosen]


def _build_menu_knowledge(items: List[Dict[str, Any]], attr_map: Dict[str, Dict[str, Any]]) -> str:
    lines: List[str] = []
    for item in items:
        attr = attr_map.get(item["key"], {})
        tags: List[str] = []
        if attr.get("contains_milk"):
            tags.append("süt içerir")
        else:
            tags.append("süt içermez")
        if attr.get("contains_caffeine"):
            tags.append("kafeinli")
        else:
            tags.append("kafeinsiz")
        kat = item["kategori"] or "Genel"
        lines.append(f"{item['ad']} ({kat}): {', '.join(tags)}. Fiyatı {item['fiyat']:.2f} TL.")
    return "\n".join(lines)


def _session_messages(conversation_id: str) -> List[Dict[str, str]]:
    if conversation_id not in _chat_sessions:
        _chat_sessions[conversation_id] = []
    return _chat_sessions[conversation_id]


def _append_session(conversation_id: str, role: str, content: str) -> None:
    session = _session_messages(conversation_id)
    session.append({"role": role, "content": content})
    if len(session) > SESSION_MAX_MESSAGES:
        del session[: len(session) - SESSION_MAX_MESSAGES]


def _format_menu_summary(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Su an menude aktif urun bulunmuyor."
    buckets: Dict[str, List[str]] = defaultdict(list)
    for it in items:
        buckets[it["kategori"] or "Genel"].append(it["ad"])
    parts: List[str] = []
    for kat, names in buckets.items():
        preview = ", ".join(names[:4])
        parts.append(f"{kat}: {preview}")
    joined = "; ".join(parts)
    return f"Menude sunlar var: {joined}. Siparis icin adet ve urun ismi soylemeniz yeterli."


def _build_neso_menu_prompt(items: List[Dict[str, Any]], attr_map: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    """Build detailed menu prompt for Neso AI assistant with ingredient/attribute info"""
    if not items:
        return "Menüde şu an aktif ürün bulunmuyor."

    attr_map = attr_map or {}
    lines: List[str] = []
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for item in items:
        kategori = item.get("kategori") or "Genel"
        buckets[kategori].append(item)

    for kategori, kategori_items in buckets.items():
        lines.append(f"## {kategori}:")
        for item in kategori_items:
            fiyat = item.get("fiyat", 0)
            ad = item.get("ad", "")
            key = item.get("key", "")

            # Ürün özelliklerini ekle
            attributes = attr_map.get(key, {})
            tags = []

            # Süt bilgisi
            if attributes.get("contains_milk"):
                tags.append("sütlü")
            else:
                tags.append("sütsüz")

            # Kafein bilgisi
            if attributes.get("contains_caffeine"):
                tags.append("kafeinli")
            else:
                tags.append("kafeinsiz")

            # Glüten bilgisi (varsa)
            if attributes.get("contains_gluten") is False:
                tags.append("glütensiz")

            # Sıcak/soğuk bilgisi (kategori veya isme göre tahmin)
            lower_ad = ad.lower()
            lower_kat = kategori.lower()
            if any(word in lower_ad or word in lower_kat for word in ["soğuk", "buzlu", "iced", "cold", "limonata"]):
                tags.append("soğuk")
            elif any(word in lower_ad or word in lower_kat for word in ["sıcak", "hot", "türk", "kahve", "çay", "espresso"]):
                tags.append("sıcak")

            # Bitki çayı mı?
            herbal_keywords = ["adaçayı", "nane", "limon", "ihlamur", "kuşburnu", "papatya", "rezene", "zencefil", "bitki"]
            if any(keyword in lower_ad for keyword in herbal_keywords):
                tags.append("bitki çayı")

            tag_str = f" [{', '.join(tags)}]" if tags else ""
            details: List[str] = []
            description = (item.get("aciklama") or "").strip()
            if description:
                details.append(description)
            ingredient_summary = _format_ingredient_summary(item)
            if ingredient_summary:
                details.append(ingredient_summary)
            stock_status = _format_stock_status(item)
            if stock_status:
                details.append(stock_status)
            detail_str = f" | {' '.join(details)}" if details else ""
            lines.append(f"- {ad}: {fiyat:.2f} TL{tag_str}{detail_str}")
        lines.append("")

    return "\n".join(lines)


# STT için dil kodları mapping (Google Speech Recognition format)
_STT_LANG_MAP = {
    "tr": "tr-TR",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "ar": "ar-SA",
    "es": "es-ES",
}


@router.post("/voice-command")
async def handle_voice_command(
    file: UploadFile = File(...),
    sube_id: Optional[int] = 1,
    masa: Optional[str] = None,
    conversation_id: Optional[str] = None,
):
    if not SPEECH_RECOGNITION_AVAILABLE or not PYDUB_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Ses tanıma özelliği mevcut değil. speech_recognition veya pydub modülleri yüklenemedi."
        )
    
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File is not an audio file.")

    try:
        # Read uploaded file into memory
        audio_data = await file.read()
        audio_io = io.BytesIO(audio_data)

        # Convert audio to a format pydub can handle
        # The browser might send webm, ogg, etc. We let pydub figure it out.
        audio = AudioSegment.from_file(audio_io)

        # Export to WAV for speech recognition
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        # Recognize speech
        r = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_record = r.record(source)
        
        # Dil algılama: Önce conversation'dan önceki dili al, yoksa varsayılan tr kullan
        stt_language = "tr-TR"  # Default
        if conversation_id:
            previous_lang = _session_languages.get(conversation_id)
            if previous_lang:
                stt_language = _STT_LANG_MAP.get(previous_lang, "tr-TR")
        
        # Using Google Web Speech API with detected language
        transcribed_text = r.recognize_google(audio_record, language=stt_language)

        # Now that we have text, we can use the same logic as the /chat endpoint
        chat_payload = ChatRequest(
            text=transcribed_text,
            masa=masa,
            sube_id=sube_id,
            conversation_id=conversation_id
        )
        
        chat_response = await chat_smart(chat_payload)

        # Add the transcribed text to the response
        response_data = chat_response.dict()
        response_data["text"] = transcribed_text
        
        return response_data

    except Exception as e:
        import logging
        # Check if it's a speech_recognition error
        if sr and isinstance(e, sr.UnknownValueError):
            raise HTTPException(status_code=400, detail="Ses anlaşılamadı.")
        elif sr and isinstance(e, sr.RequestError):
            raise HTTPException(status_code=500, detail=f"Ses tanıma servisine ulaşılamadı: {e}")
        else:
            logging.error(f"Error in handle_voice_command: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Ses işlenirken bir hata oluştu: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat_smart(payload: ChatRequest):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Bos metin")

    conversation_id = payload.conversation_id or uuid4().hex
    history_snapshot = list(_session_messages(conversation_id))

    # Dil algılama - müşterinin diline göre cevap ver
    detected_lang = _detect_language(text)
    
    # Konuşma geçmişinde dil varsa kontrol et
    previous_lang = _session_languages.get(conversation_id, None)
    if previous_lang and detected_lang != previous_lang:
        # Müşteri farklı bir dilde yazmaya başladı, dili değiştir
        import logging
        logging.info(f"[LANGUAGE] Language changed from {previous_lang} to {detected_lang} for conversation {conversation_id}")
        _session_languages[conversation_id] = detected_lang
    elif not previous_lang:
        # İlk mesaj veya dil belirlenmemiş, algılanan dili kullan
        _session_languages[conversation_id] = detected_lang
    else:
        # Aynı dil, önceki dili kullan
        detected_lang = previous_lang

    sube_id = int(payload.sube_id or 1)
    masa = payload.masa.strip() if payload.masa else None

    # Get tenant_id from sube_id
    tenant_id: Optional[int] = None
    try:
        sube_row = await db.fetch_one(
            "SELECT isletme_id FROM subeler WHERE id = :id",
            {"id": sube_id}
        )
        if sube_row:
            sube_dict = dict(sube_row) if hasattr(sube_row, 'keys') else sube_row
            tenant_id = sube_dict.get("isletme_id")
            logging.info(f"[CHAT] sube_id={sube_id}, tenant_id={tenant_id}")
    except Exception as e:
        logging.warning(f"[CHAT] Failed to get tenant_id from sube_id={sube_id}: {e}")

    # Check if user is providing table number in the message
    detected_table = _detect_table_number(text)
    if detected_table and not masa:
        masa = detected_table

    ctx = await context_manager.get(conversation_id)
    if not masa and ctx.masa:
        masa = ctx.masa
    await context_manager.update(conversation_id, sube_id=sube_id, masa=masa)

    hunger_signal = _detect_hunger_signal(text)
    sensitive_business_signal = _has_sensitive_business_query(text)

    # ÇOK ERKEN VE KESİN GREETING KONTROLÜ - HER ŞEYDEN ÖNCE
    import logging
    text_clean = text.lower().strip()
    # Noktalama işaretlerini temizle
    text_clean_pure = text_clean.strip(".,!?;:()[]{}").strip()
    
    # Basit greeting kelimeleri - direkt eşleşme
    simple_greetings_exact = {"merhaba", "selam", "selamlar", "hey", "hello", "hi", "hosgeldin", "hos geldin", "günaydın"}
    
    # Tek kelime ve tam eşleşme kontrolü
    if text_clean_pure in simple_greetings_exact and not hunger_signal:
        logging.info(f"[GREETING] EXACT MATCH detected: '{text}' -> returning greeting immediately")
        # Menüyü yükle çünkü greeting cevabında örnekler göstereceğiz
        business_profile = await _load_business_profile(sube_id)
        menu_items = await _load_menu_details(sube_id)
        if not menu_items:
            reply = "Şu an menümüzde ürün bulunamadı. Lütfen daha sonra tekrar deneyin."
            _append_session(conversation_id, "user", text)
            _append_session(conversation_id, "assistant", reply)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                detected_language=detected_lang,
                tenant_id=tenant_id,
            )
        
        sample = _pick_menu_samples(menu_items, 4)
        venue = business_profile.get("sube_ad") if business_profile else None
        reply = "Merhaba"
        if venue:
            reply += f", {venue} şubemize hoş geldiniz"
        else:
            reply += "! Hoş geldiniz"
        reply += f"! Ben Neso, sipariş asistanınız. Menümüzden bir şey önerebilirim. Örneğin: {', '.join(sample)}. Ne istersiniz?"
        _append_session(conversation_id, "user", text)
        _append_session(conversation_id, "assistant", reply)
        return await _build_chat_response(
            reply=reply,
            conversation_id=conversation_id,
            suggestions=sample,
            detected_language=detected_lang,
            tenant_id=tenant_id,
        )
    
    # Kelimelere ayır ve kontrol et
    text_words_split = text_clean.split()
    text_words_clean = [w.strip(".,!?;:()[]{}").strip() for w in text_words_split]
    text_words_clean = [w for w in text_words_clean if w]  # Boş string'leri temizle
    
    # Tek kelime ve greeting mi?
    if len(text_words_clean) == 1 and text_words_clean[0] in simple_greetings_exact and not hunger_signal:
        # Menüyü yükle çünkü greeting cevabında örnekler göstereceğiz
        business_profile = await _load_business_profile(sube_id)
        menu_items = await _load_menu_details(sube_id)
        if not menu_items:
            reply = "Şu an menümüzde ürün bulunamadı. Lütfen daha sonra tekrar deneyin."
            _append_session(conversation_id, "user", text)
            _append_session(conversation_id, "assistant", reply)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                detected_language=detected_lang,
                tenant_id=tenant_id,
            )
        
        sample = _pick_menu_samples(menu_items, 4)
        venue = business_profile.get("sube_ad") if business_profile else None
        reply = "Merhaba"
        if venue:
            reply += f", {venue} şubemize hoş geldiniz"
        else:
            reply += "! Hoş geldiniz"
        reply += f"! Ben Neso, sipariş asistanınız. Menümüzden bir şey önerebilirim. Örneğin: {', '.join(sample)}. Ne istersiniz?"
        logging.info(f"[GREETING] Early detection for simple greeting: '{text}'")
        _append_session(conversation_id, "user", text)
        _append_session(conversation_id, "assistant", reply)
        return await _build_chat_response(
            reply=reply,
            conversation_id=conversation_id,
            suggestions=sample,
            detected_language=detected_lang,
            tenant_id=tenant_id,
        )

    skip_structured_for_milky = _is_milky_coffee_query(text) or hunger_signal or sensitive_business_signal
    intent_result = intent_classifier.predict(text, sube_id=sube_id, masa=masa)
    structured_response = None
    if not skip_structured_for_milky:
        structured_response = await _handle_structured_intent(
            intent_result=intent_result,
            conversation_id=conversation_id,
            sube_id=sube_id,
            masa=masa,
            detected_language=detected_lang,
            original_text=text,
            tenant_id=tenant_id,
        )
    if structured_response:
        return structured_response
    if text_clean_pure in simple_greetings_exact and not hunger_signal:
        business_profile = await _load_business_profile(sube_id)
        menu_items = await _load_menu_details(sube_id)
        if menu_items:
            sample = _pick_menu_samples(menu_items, 4)
            venue = business_profile.get("sube_ad") if business_profile else None
            reply = "Merhaba"
            if venue:
                reply += f", {venue} şubemize hoş geldiniz"
            else:
                reply += "! Hoş geldiniz"
            reply += f"! Ben Neso, sipariş asistanınız. Menümüzden bir şey önerebilirim. Örneğin: {', '.join(sample)}. Ne istersiniz?"
            _append_session(conversation_id, "user", text)
            _append_session(conversation_id, "assistant", reply)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                suggestions=sample,
                detected_language=detected_lang,
                tenant_id=tenant_id,
            )

    business_profile = await _load_business_profile(sube_id)
    menu_items = await _load_menu_details(sube_id)
    if not menu_items:
        reply = "Şu an menümüzde ürün bulunamadı. Lütfen daha sonra tekrar deneyin."
        _append_session(conversation_id, "user", text)
        _append_session(conversation_id, "assistant", reply)
        return await _build_chat_response(
            reply=reply,
            conversation_id=conversation_id,
            detected_language=detected_lang,
        )

    recipe_map_norm, recipe_detail_map = await _load_recipe_map(sube_id)

    attr_map, dairy_free_items, caffeine_free_items, gluten_free_items = _analyze_menu_attributes(menu_items, recipe_map_norm)
    for item in menu_items:
        key = item.get("key")
        if key and key in recipe_detail_map:
            item["ingredients"] = recipe_detail_map[key]
        stock_sentence = _format_stock_status(item)
        if stock_sentence:
            item["stock_status_text"] = stock_sentence
        description = (item.get("aciklama") or "").strip()
        if description:
            item["aciklama"] = description

    milky_coffee_items = _filter_milky_coffee_items(menu_items, attr_map)
    menu_knowledge = _build_menu_knowledge(menu_items, attr_map)

    price_map: Dict[str, float] = {}
    name_map: Dict[str, str] = {}
    category_map: Dict[str, str] = {}
    menu_token_keywords: Set[str] = set()
    menu_full_names: Set[str] = set()
    full_name_map: Dict[str, Dict[str, Any]] = {}
    for item in menu_items:
        price_map[item["key"]] = item["fiyat"]
        name_map[item["key"]] = item["ad"]
        category_map[item["key"]] = item["kategori"]
        normalized_name = normalize_name(item["ad"])
        if normalized_name:
            menu_full_names.add(normalized_name)
            full_name_map.setdefault(normalized_name, item)
            for token in normalized_name.split():
                if len(token) > 2:
                    menu_token_keywords.add(token)

    # İkinci greeting kontrolü burada gerekmiyor - zaten en başta yapıldı
    
    # Diğer özel durumlar için lower_text
    lower_text = _tokenize(text)
    lower_text_tokens = lower_text.split()  # Tokenize et
    plain_lower = text.lower()
    plain_ascii = lower_text
    
    is_menu_query = any(token in lower_text for token in ["menu", "liste", "ne var", "neler var"])
    asks_dairy = any(token in lower_text for token in ["sutsuz", "sut icermeyen", "laktozsuz", "lactose", "vegan"])
    asks_milky_coffee = (
        ("sutlu" in plain_ascii and "kahve" in plain_ascii)
        or any(
            phrase in plain_ascii
            for phrase in [
                "sutlu kahve",
                "sutlu kahveler",
                "sutlu icecek",
                "sutlu icecekler",
                "milk coffee",
                "milky coffee",
            ]
        )
    )
    asks_caffeine = any(token in lower_text for token in ["kafein", "kafeinsiz", "caffeine"])
    asks_business = any(token in lower_text for token in ["isletme", "sube", "adres", "acilis", "kapanis", "calisma"])
    asks_sensitive_business = sensitive_business_signal or any(
        keyword in plain_ascii for keyword in SENSITIVE_BUSINESS_KEYWORDS
    )
    asks_gluten = any(token in lower_text for token in ["glutensiz", "gluten-free", "gluten", "celiac"])
    asks_cold = any(token in lower_text for token in ["soguk", "soğuk", "cold", "buzlu", "iced", "buz", "ice"])
    asks_hot = any(token in lower_text for token in ["sicak", "sıcak", "hot", "steamed"])
    asks_dessert = any(keyword in plain_ascii for keyword in DESSERT_KEYWORDS)
    asks_recommendation = any(token in lower_text for token in ["oner", "öner", "onerebilir", "öner", "tavsiye", "recommend", "suggest"])
    asks_question = text.strip().endswith("?") or any(token in lower_text_tokens for token in ["nedir", "ne", "nasil", "hangi", "what", "how", "which"])
    menu_token_hit = any(tok in menu_token_keywords for tok in lower_text_tokens)
    availability_phrases = ["var mı", "varmi", "var mı?", "stokta var mı", "stokta varmi", "mevcut mu", "bulunuyor mu"]
    asks_availability = any(phrase in plain_lower for phrase in availability_phrases)
    asks_wellbeing = any(keyword in plain_ascii for keyword in WELLBEING_KEYWORDS)
    mentions_positive_mood = any(keyword in plain_ascii for keyword in POSITIVE_MOOD_KEYWORDS)
    mentions_negative_mood = any(keyword in plain_ascii for keyword in NEGATIVE_MOOD_KEYWORDS)
    mentions_small_talk = any(keyword in plain_ascii for keyword in CUSTOMER_SMALL_TALK_KEYWORDS)
    asks_sleepy = any(keyword in plain_ascii for keyword in SLEEPY_KEYWORDS)
    asks_energy = any(keyword in plain_ascii for keyword in ENERGY_BOOST_KEYWORDS)
    asks_ingredients = any(keyword in plain_ascii for keyword in INGREDIENT_QUESTION_KEYWORDS)

    mentioned_products: List[Dict[str, Any]] = []
    for normalized_name, item in full_name_map.items():
        if normalized_name and normalized_name in lower_text:
            mentioned_products.append(item)

    mentions_hungry = hunger_signal or any(keyword in plain_ascii for keyword in HUNGER_HINTS)
    
    # Özel durumlar: Boğaz ağrısı, hasta, soğuk algınlığı
    asks_sore_throat = any(token in lower_text for token in ["boğaz", "bogaz", "ağrı", "agri", "hasta", "soğuk algınlığı", "soguk alginligi", "nezle", "grip", "throat", "sore", "sick", "cold"])
    
    # Sütsüz kahve isteği (Menengiç değil, Türk Kahvesi/Espresso/Americano)
    asks_dairy_free_coffee = any(token in lower_text for token in ["sutsuz kahve", "sütsüz kahve", "sut icermeyen kahve", "süt içermeyen kahve", "dairy free coffee", "black coffee"])
    
    # Matematik sorusu kontrolü (regex_module henüz import edilmeli)
    import re as regex_module
    asks_math = any(token in lower_text for token in ["kaç", "eder", "toplam", "artı", "eksi", "çarpı", "bölü", "plus", "minus", "times", "equal", "eşit"]) or bool(regex_module.search(r'[\d]+\s*[\+\-\*\/]\s*[\d]+', text.lower()))

    # Sipariş mi yoksa sohbet/soru mu? Sadece açık sipariş istekleri için parse yap
    # Örnek sipariş: "2 latte", "latte 3 tane", "bir americano ve bir latte"
    # Örnek sohbet: "glütensiz ne var?", "soğuk önerebilir misin?", "merhaba"
    is_likely_order = False
    # Sayı + ürün kombinasyonu varsa muhtemelen sipariş
    has_number_product = bool(regex_module.search(r'\d+\s*\w+|\w+\s*\d+', text.lower()))
    order_action_keywords = [
        "alabilir", "almak", "sipariş", "siparis", "istiyorum", "isterim",
        "gonder", "gönder", "getir", "hazirla", "hazırla", "yolla", "ekle",
        "servis et", "gonderebilir", "hazirlayabilir"
    ]
    polite_markers = ["lütfen", "lutfen", "rica", "please"]
    order_question_phrases = [
        "alabilir miyim", "alabilir misin", "alabilir miyiz", "alir miyim", "alır mıyım",
        "istiyorum", "isterim", "sipariş verebilir miyim", "sipariş al", "sipariş ver",
        "siparis verebilirmiyim", "bana getir", "bana gonder", "bana yolla"
    ]
    has_order_action = any(keyword in plain_lower for keyword in order_action_keywords) or any(marker in plain_lower for marker in polite_markers)
    is_order_question = any(phrase in plain_lower for phrase in order_question_phrases)
    logging.info(
        "[ORDER_CHECK] has_number_product=%s, menu_token_hit=%s, has_order_action=%s, asks_question=%s, asks_recommendation=%s, asks_availability=%s",
        has_number_product,
        menu_token_hit,
        has_order_action,
        asks_question,
        asks_recommendation,
        asks_availability,
    )
    
    # Greeting kontrolü - çok kesin olmalı (parse işleminden önce)
    is_greeting_only = False
    text_clean_check = text.lower().strip(".,!?;:()[]{}")
    greeting_words_only = {"merhaba", "selam", "selamlar", "hey", "hello", "hi", "hosgeldin", "hos", "geldin", "günaydın"}
    
    # Tek kelime ve sadece greeting mi kontrol et
    words_check = text_clean_check.split()
    if len(words_check) == 1 and words_check[0] in greeting_words_only:
        is_greeting_only = True
    elif text_clean_check in greeting_words_only:
        is_greeting_only = True
    
    # Eğer greeting, matematik sorusu, hastalık durumu, öneri/soru/filtreleme ise, parse işlemine HİÇ GİRME
    # LLM'in menü bilgilerinden kendi başına karar vermesini sağla
    if is_greeting_only:
        logging.info(f"[GREETING] Detected as greeting in order check: '{text}' -> skipping parse")
        is_likely_order = False
    elif asks_math:
        logging.info(f"[MATH] Detected as math question: '{text}' -> skipping parse")
        is_likely_order = False
    elif asks_sore_throat:
        logging.info(f"[HEALTH] Detected health/sickness query: '{text}' -> skipping parse, will recommend herbal teas")
        is_likely_order = False
    elif asks_recommendation or asks_question or asks_availability:
        logging.info(f"[QUESTION/RECOMMENDATION] Detected question/recommendation request: '{text}' -> skipping parse, LLM will handle")
        is_likely_order = False
    elif asks_dairy or asks_milky_coffee or asks_caffeine or asks_gluten or asks_cold or asks_hot or asks_sleepy or asks_energy or asks_ingredients:
        logging.info(f"[FILTERING] Detected attribute filtering request: '{text}' -> skipping parse, LLM will handle")
        is_likely_order = False
    else:
        if menu_token_hit and not asks_availability:
            if has_number_product:
                is_likely_order = True
            elif has_order_action or is_order_question:
                is_likely_order = True
            elif not asks_question and not asks_recommendation:
                # Kısa ifadeler ("bir latte", "iki americano") sipariştir
                if len(lower_text_tokens) <= 5:
                    is_likely_order = True
            elif any(tok in NUMBER_WORDS for tok in lower_text_tokens[:2]) and len(lower_text_tokens) <= 4:
                is_likely_order = True
        else:
            is_likely_order = False
        
        # ÖNEMLİ: Eğer conversation history'de varyasyon sorusu varsa ve kullanıcı muhtemelen varyasyon cevabı veriyorsa, parse yap
        if not is_likely_order and history_snapshot:
            logging.info(f"[ORDER_CHECK] Checking history_snapshot: {len(history_snapshot)} messages")
            # Son assistant mesajına bak (son 5 mesaja bak çünkü conversation uzun olabilir)
            for msg in reversed(history_snapshot[:5]):
                if msg.get("role") == "assistant":
                    assistant_text = msg.get("content", "")
                    logging.info(f"[ORDER_CHECK] Checking assistant message: '{assistant_text[:100]}...'")
                    # Varyasyon sorusu içeriyor mu kontrol et
                    if ("hangi seçenek" in assistant_text.lower() or 
                        "seçenek belirtmediniz" in assistant_text.lower() or 
                        "tercihinizi belirtir" in assistant_text.lower() or
                        "hangi secene" in assistant_text.lower() or
                        "secenek belirtmediniz" in assistant_text.lower() or
                        "tercihinizi belirt" in assistant_text.lower() or
                        any(var in assistant_text.lower() for var in ["orta", "sade", "şekerli", "sekerli"])):
                        # Bu varyasyon sorusu, kullanıcının cevabı muhtemelen varyasyon adı
                        logging.info(f"[ORDER_CHECK] Detected potential variation response: '{text}'")
                        is_likely_order = True
                        break
        
        logging.info(f"[ORDER_CHECK] is_likely_order={is_likely_order}")
    
    stock_map_db, has_db_key = await _load_stock_map(sube_id)
    fallback = _ensure_fallback_stock(sube_id, [it["key"] for it in menu_items])
    stock_map = _merge_stock(stock_map_db, fallback)

    aggregated: Dict[str, int] = {}
    not_matched: List[str] = []
    not_matched_with_count: List[Tuple[str, int]] = []
    auto_selected_variations = []  # type: List[Tuple[str, str]]
    pending_variation_options = _pending_variations.get(conversation_id)
    allowed_variation_keys: Set[str] = set()
    if pending_variation_options:
        for option in pending_variation_options:
            key = option.get("key")
            if key:
                allowed_variation_keys.add(key)
    confirmation_keywords = {
        "onay", "onayla", "onaylıyorum", "onayladım", "onay ver", "onay veriyorum",
        "tamam", "evet", "sıkıntı yok", "sorun yok", "farketmez", "fark etmez",
        "hepsi aynı", "hepsi olur", "devam et", "aynen", "ok"
    }
    
    # Sadece açık sipariş istekleri için parse yap
    if is_likely_order:
        import logging
        logging.info(f"[PARSE] is_likely_order=True, parsing text: '{text}'")
        pairs = _extract_candidates(text)
        logging.info(f"[PARSE] Extracted pairs: {pairs}")
        # Parse edilmiş ürün adlarının kelimelerini takip et (duplicate kontrolü için)
        parsed_product_words = set()
        
        for name, adet in pairs:
            # Skip if this looks like a table number
            if _detect_table_number(name):
                logging.info(f"[PARSE] Skipping '{name}' - looks like table number")
                continue

            key = normalize_name(name)
            logging.info(f"[PARSE] Looking for match: name='{name}', normalized_key='{key}', adet={adet}")
            
            # ÖNEMLİ: Eğer bu token daha önce parse edilmiş bir ürün adının kelimesi ise, atla
            # Örnek: "türk kahvesi" parse edildikten sonra "kahvesi" token'ı ayrı parse edilmemeli
            if key in parsed_product_words:
                logging.info(f"[PARSE] Skipping '{name}' - already part of parsed product name")
                continue
            
            match = None
            if key in price_map:
                match = key
                logging.info(f"[PARSE] Direct match found: {key}")
            else:
                key_tokens = key.split() if key else []
                for mk in price_map.keys():
                    if not key:
                        continue
                    mk_tokens = mk.split()
                    if key == mk:
                        match = mk
                        logging.info(f"[PARSE] Exact match via loop: {key}")
                        break
                    if key and (key in mk or mk in key):
                        # Tek kelime ile çok kelimeli ürün eşleşmesini engelle
                        if len(key_tokens) == 1 and len(mk_tokens) > 1:
                            continue
                        if len(key_tokens) > 1 and len(mk_tokens) == 1:
                            continue
                        if len(key) <= 3 and len(mk_tokens) > 1:
                            continue
                        match = mk
                        logging.info(f"[PARSE] Partial match accepted: {key} -> {mk}")
                        break
                if not match:
                    # Fuzzy match için Levenshtein benzeri bir oran kullan (difflib)
                    candidates = list(price_map.keys())
                    if key and candidates:
                        cutoff = 0.92 if len(key_tokens) == 1 else 0.85
                        close_matches = difflib.get_close_matches(key, candidates, n=1, cutoff=cutoff)
                        if close_matches:
                            match_candidate = close_matches[0]
                            candidate_tokens = match_candidate.split()
                            if len(key_tokens) == 1 and len(candidate_tokens) > 1:
                                logging.info(f"[PARSE] Fuzzy match rejected (single word vs multi word): {key} -> {match_candidate}")
                            else:
                                similarity = difflib.SequenceMatcher(None, key, match_candidate).ratio()
                                logging.info(
                                    f"[PARSE] Fuzzy match found: {key} -> {match_candidate} (similarity={similarity:.2f})"
                                )
                                match = match_candidate
            if match:
                old_count = aggregated.get(match, 0)
                aggregated[match] = old_count + max(1, int(adet))
                new_count = aggregated[match]
                if old_count > 0:
                    logging.warning(f"[PARSE] DUPLICATE DETECTED: '{match}' was already {old_count}, adding {max(1, int(adet))} -> total {new_count}")
                logging.info(f"[PARSE] Added to aggregated: {match} x {new_count}")
                
                # Parse edilmiş ürün adının tüm kelimelerini ekle
                product_name = name_map.get(match, match)
                words = product_name.split()
                for word in words:
                    parsed_product_words.add(normalize_name(word))
                # Tam adı da ekle
                parsed_product_words.add(normalize_name(product_name))
            else:
                not_matched.append(name)
                not_matched_with_count.append((name, adet))
                logging.warning(f"[PARSE] No match found for '{name}' (normalized: '{key}')")
        
    detected_counts = _extract_menu_quantities(text, price_map.keys())
    for detected_key, detected_count in detected_counts.items():
        if detected_key not in price_map:
            continue
        current = aggregated.get(detected_key, 0)
        if detected_count > current:
            logging.info(
                f"[PARSE] Adjusted quantity for '{name_map.get(detected_key, detected_key)}' from {current} to {detected_count} based on text pattern."
            )
            aggregated[detected_key] = detected_count
        elif current == 0:
            aggregated[detected_key] = detected_count

    logging.info(f"[PARSE] Final aggregated: {aggregated}, not_matched: {not_matched}")
    
    if pending_variation_options and not not_matched_with_count:
        variation_mentions = _extract_variation_mentions(text, pending_variation_options)
        if variation_mentions:
            for variation_name, count in variation_mentions.items():
                not_matched.append(variation_name)
                not_matched_with_count.append((variation_name, count))

    if not aggregated and pending_variation_options:
        confirmation_text = re.sub(r"[^a-zçğıöşü0-9\s]", " ", text_clean)
        confirmation_text = re.sub(r"\s+", " ", confirmation_text).strip()
        if any(keyword in confirmation_text for keyword in confirmation_keywords):
            base_pending = _pending_aggregated.get(conversation_id, {}) or {}
            aggregated = dict(base_pending)
            for pending_item in pending_variation_options:
                product_key = pending_item.get("key")
                if not product_key:
                    continue
                adet = int(pending_item.get("adet") or 1)
                variations = pending_item.get("varyasyonlar") or []
                if variations:
                    selected_variation = variations[0]
                    key_with_variation = f"{product_key}|{selected_variation}"
                    aggregated[key_with_variation] = aggregated.get(key_with_variation, 0) + adet
                    auto_selected_variations.append((pending_item.get("urun", product_key), selected_variation))
                else:
                    aggregated[product_key] = aggregated.get(product_key, 0) + adet
            _pending_variations.pop(conversation_id, None)

    # Varyasyonları ürünlerle eşleştir (örn: "2 türk kahvesi 1 sade 1 orta" -> 2 farklı ürün)
    # Ayrıca "1 sade 1 şekerli" gibi durumlarda conversation history'den ürün adını bul
    if not_matched:
        # Önce menüdeki tüm varyasyonları yükle
        all_variations = {}
        variation_source_items = menu_items
        if allowed_variation_keys:
            filtered_items = [
                item for item in menu_items
                if item.get("key") in allowed_variation_keys
            ]
            if filtered_items:
                variation_source_items = filtered_items
                logging.info(f"[VARIATION_PARSE] Restricting variation lookup to pending products: {allowed_variation_keys}")
            else:
                logging.warning("[VARIATION_PARSE] Pending variation keys not found in menu; using full menu for lookup.")
        for item in variation_source_items:
            if item.get("varyasyonlar"):
                for var in item["varyasyonlar"]:
                    var_name_norm = normalize_name(var["ad"])
                    if var_name_norm not in all_variations:
                        all_variations[var_name_norm] = []
                    all_variations[var_name_norm].append({
                        "product_key": item["key"],
                        "variation_name": var["ad"]
                    })
        
        # Eğer aggregated boşsa, önce session'dan pending ürünleri kontrol et
        pending_was_loaded = False
        if not aggregated:
            if conversation_id in _pending_aggregated:
                pending = _pending_aggregated[conversation_id]
                aggregated = dict(pending)
                pending_was_loaded = True
                logging.info(f"[VARIATION_PARSE] Loaded pending aggregated from session: {aggregated}")
        
        # Eğer aggregated hala boşsa ve varyasyon varsa, conversation history'de son sorulan ürünü bul
        # ÖNEMLİ: Pending yüklendiyse conversation history'den parse etme, çünkü tüm ürünler zaten pending'de
        context_products = set()  # Conversation history'den bulunan ürünler
        if not aggregated and not pending_was_loaded:
            # not_matched içinde varyasyon isimleri var mı kontrol et
            has_variation_names = any(
                normalize_name(nm) in all_variations 
                for nm, _ in not_matched_with_count
            )
            if has_variation_names:
                logging.info("[VARIATION_PARSE] No aggregated items but variations found, checking conversation history")
                logging.info(f"[VARIATION_PARSE] Checking history_snapshot: {len(history_snapshot)} messages")
                
                # Son conversation message'larına bak
                for msg in reversed(history_snapshot[:5]):  # Son 5 mesaja bak
                    if msg.get("role") == "assistant":
                        assistant_text = msg.get("content", "").lower()
                        logging.info(f"[VARIATION_PARSE] Checking assistant message: {assistant_text[:100]}...")
                        # Varyasyon sorusu içeriyor mu kontrol et - tüm mesaj metninde ara
                        for var_key in all_variations.keys():
                            # Mesajda bu varyasyonların hiçbiri geçmiyorsa atla
                            var_names_in_msg = [v["variation_name"].lower() for v in all_variations[var_key]]
                            logging.info(f"[VARIATION_PARSE] Checking var_key '{var_key}' with variations: {var_names_in_msg}")
                            if any(var_name in assistant_text for var_name in var_names_in_msg):
                                # Bu ürün için varyasyon sormuş, aggregated'e ekle
                                var_info = all_variations[var_key][0]  # İlk varyasyonu kullan
                                # Context'ten SADECE varyasyon bekleyen ürünleri bul (varyasyonsuz olanlar pending'de zaten)
                                # Önce tüm (xN) patternlerini bul
                                logging.info(f"[VARIATION_PARSE] Full assistant text: '{assistant_text}'")
                                count_matches = re.findall(r'\'([^\']+)\'\s*\(x(\d+)\)', assistant_text)
                                logging.info(f"[VARIATION_PARSE] count_matches: {count_matches}")
                                if count_matches:
                                    # Her ürün için count bul, AMA sadece varyasyon bekleyen ürünleri ekle
                                    for product_name, count_str in count_matches:
                                        product_key = None
                                        # Normalize ürün adını bul
                                        for item in menu_items:
                                            if normalize_name(item["ad"]) == normalize_name(product_name):
                                                product_key = item["key"]
                                                break
                                        # SADECE varyasyon bekleyen ürünleri ekle (varyasyonsuz olanlar pending'de zaten)
                                        # all_variations dict'inin key'leri varyasyon bekleyen ürünlerdir
                                        if product_key and product_key in all_variations:
                                            if product_key not in aggregated:
                                                aggregated[product_key] = 0
                                            aggregated[product_key] += int(count_str)
                                            context_products.add(product_key)
                                            logging.info(f"[VARIATION_PARSE] Found context product '{product_name}' (x{count_str}) -> '{product_key}' (variation required)")
                                        else:
                                            logging.info(f"[VARIATION_PARSE] Skipping '{product_name}' - no variation required (already in pending)")
                                
                                # Eğer yukarıdaki regex bulunamadıysa, sadece varyasyonlu ürünü ekle
                                if not count_matches:
                                    count_match = re.search(r'\(x(\d+)\)', assistant_text)
                                    if count_match:
                                        total_count = int(count_match.group(1))
                                    else:
                                        # Eğer bulunamazsa, 1 kullan (varsayılan)
                                        total_count = 1
                                    aggregated = {var_info["product_key"]: total_count}
                                    context_products.add(var_info["product_key"])
                                    logging.info(f"[VARIATION_PARSE] Found context product '{var_info['product_key']}' from conversation history, total count: {total_count}")
                                break
                        if aggregated:
                            break
                if not aggregated:
                    logging.warning("[VARIATION_PARSE] Could not find context product from conversation history")
        
        # not_matched içindeki varyasyon isimlerini bul ve adetlerini de tut
        # ÖNEMLİ: Eğer context_products varsa, sadece o ürünler için varyasyon eşleştirmesi yap
        variation_matches = []
        for nm, adet in not_matched_with_count:
            nm_norm = normalize_name(nm)
            if nm_norm in all_variations:
                # Bu bir varyasyon ismi, products eşleştir
                for var_info in all_variations[nm_norm]:
                    # Eğer context_products varsa, sadece o ürünler için eşleştirme yap
                    if context_products and var_info["product_key"] not in context_products:
                        logging.info(f"[VARIATION_PARSE] Skipping variation '{nm}' for product '{var_info['product_key']}' (not in context)")
                        continue
                    variation_matches.append((var_info["product_key"], var_info["variation_name"], adet))
                    logging.info(f"[VARIATION_PARSE] Found variation '{nm}' (x{adet}) -> product '{var_info['product_key']}' with variation '{var_info['variation_name']}'")
        
        # Eğer varyasyon eşleşmeleri varsa, aggregated'i düzenle
        if variation_matches and aggregated:
            # Önce aggregated'deki TÜM ürünleri kopyala (varyasyonu belirtilmemiş olanlar kaybolmasın)
            new_aggregated = dict(aggregated)
            logging.info(f"[VARIATION_PARSE] Starting with new_aggregated (copy of aggregated): {new_aggregated}")

            # Hangi ürünler için varyasyon belirtilmiş bul
            products_with_variation = set(var_match[0] for var_match in variation_matches)

            total_variation_count = sum(count for _, _, count in variation_matches)
            total_items_in_aggregated = sum(aggregated.values())

            # Varyasyonların toplam adeti aggregated'deki toplamdan fazlaysa uyar
            if total_variation_count > total_items_in_aggregated:
                logging.warning(f"[VARIATION_PARSE] Variation count ({total_variation_count}) > total items ({total_items_in_aggregated}), using variation counts")

            # ÖZEL DURUM: Eğer sadece 1 varyasyon belirtilmişse ve total count daha fazlaysa,
            # o varyasyonu total count kadar ekle (kullanıcı "sade" dedi, "2 sade" demedi)
            if len(variation_matches) == 1 and total_variation_count < total_items_in_aggregated:
                var_match = variation_matches[0]
                product_key = var_match[0]
                variation_name = var_match[1]
                if product_key in aggregated:
                    # Orijinal siparişten total count'u kullan
                    unique_key = f"{product_key}|{variation_name}"
                    new_aggregated[unique_key] = aggregated[product_key]
                    # Orijinal key'i sil (varyasyonlu versiyonuyla değiştirildi)
                    if product_key in new_aggregated and "|" not in product_key:
                        del new_aggregated[product_key]
                    logging.info(f"[VARIATION_PARSE] Single variation specified, using original order count: {unique_key} x {aggregated[product_key]}")
                    logging.info(f"[VARIATION_PARSE] After modification, new_aggregated: {new_aggregated}")
                else:
                    # Fallback: varyasyon count'u kullan
                    unique_key = f"{product_key}|{variation_name}"
                    new_aggregated[unique_key] = var_match[2]
                    logging.info(f"[VARIATION_PARSE] Single variation specified, product not in aggregated, using variation count: {unique_key} x {var_match[2]}")
            else:
                # Birden fazla varyasyon belirtilmiş veya count eşit, her birinin count'unu kullan
                for var_match in variation_matches:
                    product_key = var_match[0]
                    unique_key = f"{product_key}|{var_match[1]}"
                    count = var_match[2]  # Variation count from tuple
                    new_aggregated[unique_key] = count
                    logging.info(f"[VARIATION_PARSE] Created separate item: {unique_key} x {count}")

                # Varyasyonlu ürünlerin orijinal key'lerini sil
                for product_key in products_with_variation:
                    if product_key in new_aggregated and "|" not in product_key:
                        del new_aggregated[product_key]
                        logging.info(f"[VARIATION_PARSE] Removed original key '{product_key}' (replaced with variation)")

            aggregated = new_aggregated
            logging.info(f"[VARIATION_PARSE] Final aggregated with variations: {aggregated}")
        
        # Varyasyon isimlerini not_matched'den çıkar
        not_matched = [nm for nm in not_matched if normalize_name(nm) not in all_variations]
        
    else:
        import logging
        logging.info(f"[PARSE] is_likely_order=False, skipping parse for text: '{text}'")

    # Greeting, matematik ve genel sohbet kelimelerini not_matched'den çıkar - daha kapsamlı liste
    ignore_tokens = {
        "merhaba", "selam", "selamlar", "hello", "hi", "hey", "lutfen", "tesekkurler", "tesekkur", "tesekur", "please", "thanks", 
        "hosgeldin", "hos", "geldin", "günaydın", "iyi", "akşamlar", "günler", "var", "varsa",
        # Matematik kelimeleri
        "kaç", "eder", "toplam", "artı", "eksi", "çarpı", "bölü", "plus", "minus", "times", "divided", "equal", "eşit",
        # Sayılar (tek başına)
        "bir", "iki", "üç", "dort", "beş", "altı", "yedi", "sekiz", "dokuz", "on", "zero", "one", "two", "three", "four", "five"
    }
    not_matched = [n for n in not_matched if _tokenize(n) not in ignore_tokens and not _detect_table_number(n)]
    
    # Matematik işlemleri içeren kelimeleri de temizle (örn: "2+2", "3-1", "5*2")
    import re as regex_module
    math_pattern = regex_module.compile(r'^[\d\+\-\*\/\=]+$')
    not_matched = [n for n in not_matched if not math_pattern.match(n)]
    
    # Eğer sadece greeting kelimeleri varsa ve başka bir şey yoksa, not_matched'i tamamen temizle
    if len(not_matched) > 0:
        text_lower_check = text.lower()
        not_matched_normalized = [_tokenize(n.lower()) for n in not_matched]
        if all(norm in ignore_tokens for norm in not_matched_normalized) and any(g in text_lower_check for g in ["merhaba", "selam", "hello", "hi", "hey"]):
            not_matched = []
    
    suggestions: Optional[List[str]] = None
    context_lines: List[str] = []
    default_reply = ""
    force_default_reply = False
    order_summary: Optional[Dict[str, Any]] = None
    shortages: List[Dict[str, Any]] = []

    # Masa kontrolü - eğer açık sipariş varsa ve masa yoksa sor
    # AMA: Müşteri ekranından geliyorsa masa sorma - default "Masa-Genel" kullan
    # Admin panelinden geliyorsa masa zaten olmalı
    if aggregated and not masa:
        # Müşteri ekranı için default masa kullan, sorma
        # Admin paneli için masa sor (ama admin panelinde masa input'u var, buraya gelmemeli)
        # Güvenlik için: Eğer masa yoksa ve sipariş varsa, default masa kullan ve sor
        masa = "Masa-Genel"  # Default masa - müşteri ekranı için
        logging.info(f"[MASA] Masa belirtilmemiş, default 'Masa-Genel' kullanılıyor")
        # Artık masa var, devam et

    # Varyasyon kontrolü artık sepet oluşturma sırasında yapılıyor
    
    for key, adet in aggregated.items():
        # Stok kontrolü: Önce direkt key'i dene, sonra normalize edilmiş key'i
        # Stok tablosunda kod normalize edilmiş olabilir
        urun_adi = name_map.get(key, key)
        stok_key_normalized = _normalize_stock_key(urun_adi)
        
        # Stok arama: direkt key, normalize key, ürün adı normalize
        stok = stock_map.get(key) or stock_map.get(stok_key_normalized) or stock_map.get(_normalize_stock_key(key))
        
        import logging
        logging.info(f"[STOCK] Checking stock for key='{key}', urun='{urun_adi}', normalized='{stok_key_normalized}': stok={stok}, adet={adet}")
        
        # Stok None ise (veritabanında yok) fallback stock kullanılıyor, yetersiz sayılmaz
        # Sadece stok belirtilmişse ve adet'ten azsa yetersiz
        if stok is not None and float(stok) < float(adet):
            shortages.append({"urun": urun_adi, "istenen": int(adet), "stok": float(stok)})
            logging.warning(f"[STOCK] Shortage detected: {urun_adi} - istenen={adet}, stok={stok}")

    # Varyasyon kontrolü artık sepet oluşturma sırasında yapılıyor
    # Eksik varyasyon varsa varsayılan (ilk) varyasyon seçiliyor
    
    if shortages:
        shortage_lines = ", ".join(f"{s['urun']} (elde {s['stok']})" for s in shortages)
        
        # Parse başarılı oldu ama stok yetersiz - ürünler menüde var ama stok yetersiz
        parsed_products = [name_map.get(k, k) for k in aggregated.keys()]
        context_lines.append(f"KULLANICI SİPARİŞ VERDİ VE PARSE BAŞARILI. Şu ürünler menüde bulundu: {', '.join(parsed_products)}. ANCAK STOK YETERSİZ: {shortage_lines}.")
        context_lines.append(f"ÜRÜNLER MENÜDE MEVCUT AMA STOK YETERSİZ. Proaktif ol, direkt alternatif öner, ASLA 'menüde yok' demeyin, ASLA 'Sipariş almak ister misiniz?' gibi pasif sorular sorma. Menüden stokta olan alternatifleri öner.")
        
        # Proaktif ve net bir mesaj - fiyat gösterme, direkt alternatif öner
        shortage_urunler = [s['urun'] for s in shortages]
        available_items = [name_map.get(k, k) for k in aggregated.keys() if name_map.get(k, k) not in shortage_urunler]
        if available_items:
            available_desc = ", ".join(available_items)
            default_reply = f"Üzgünüm, {shortage_lines} için stok yetersiz. Ancak {available_desc} için stok mevcut. Bunları önerebilirim!"
        else:
            # Tüm ürünler stok yetersiz, alternatif öner (fiyat gösterme)
            default_reply = f"Üzgünüm, {shortage_lines} için stok yetersiz. Menümüzdeki diğer ürünlerden önerebilirim!"
    elif aggregated:
        # Önce varyasyon kontrolü yap - hangi ürünlerde varyasyon eksik
        missing_variations_in_cart = []
        items_with_variations = set()  # Varyasyon eksik olan ürünlerin key'leri
        
        for key, adet in aggregated.items():
            # Key formatı "product_key|variation_name" olabilir
            if "|" in key:
                product_key = key.split("|", 1)[0]
            else:
                product_key = key
            
            # Menü öğesini bul
            menu_item = next((item for item in menu_items if item["key"] == product_key), None)
            urun_ad = name_map.get(product_key, product_key)
            
            # Varyasyon var mı kontrol et
            if "|" not in key and menu_item and menu_item.get("varyasyonlar"):
                var_names = [var["ad"] for var in menu_item["varyasyonlar"]]
                text_lower = text.lower()
                found_var = False
                for var_name in var_names:
                    if normalize_name(var_name) in text_lower or any(word in text_lower for word in var_name.lower().split()):
                        found_var = True
                        break
                if not found_var:
                    missing_variations_in_cart.append({
                        "urun": urun_ad,
                        "varyasyonlar": var_names,
                        "key": product_key,
                        "adet": adet
                    })
                    items_with_variations.add(key)
                    logging.info(f"[VARIATION] Missing variation for '{urun_ad}' (x{adet}), will prompt user")
        
        # Eğer eksik varyasyon varsa, kullanıcıya sor, sipariş oluşturma
        if missing_variations_in_cart:
            # Varyasyon eksik ürünler için LLM'e sor
            for mv in missing_variations_in_cart:
                var_list = ", ".join(mv["varyasyonlar"])
                context_lines.append(f"KULLANICI '{mv['urun']}' (x{mv['adet']}) ISTEDI ANCAK BUNUN SECENEKLERİ VAR: {var_list}. KULLANICIYA BU SECENEKLERI SOR MALI.")
                logging.info(f"[VARIATION] Missing variation for '{mv['urun']}': {mv['varyasyonlar']}")
            
            # TÜM ürünleri session'a kaydet (varyasyonlu ve varyasyonsuz)
            # SADECE varyasyonsuz ürünleri session'a kaydet (varyasyonlu olanlar için kullanıcıya sorulacak)
            # Varyasyonlu ürünler conversation history'den gelecek
            pending_items = {}
            for key, adet in aggregated.items():
                # Sadece varyasyon gerektirmeyen ürünleri kaydet
                if key not in items_with_variations:
                    product_key = key.split("|", 1)[0] if "|" in key else key
                    pending_items[product_key] = pending_items.get(product_key, 0) + adet
                    logging.info(f"[SESSION] Adding to pending (no variation): {product_key} x {adet}")
                else:
                    logging.info(f"[SESSION] Skipping pending for {key} (has variation, will be asked)")

                # Context'e varyasyonsuz ürünleri ekle
                if key not in items_with_variations:
                    urun_ad = name_map.get(product_key, product_key)
                    context_lines.append(f"KULLANICI '{urun_ad}' (x{adet}) ISTEDI VE SECENEK GEREKMEDIGI ICIN SISTEM HAZIRDA TUTACAK. KULLANICI VARIYASYONLARI BELIRTTIKTEN SONRA TUM URUNLERI BIRLIKTE EKLEYECEK.")

            # Tüm ürünleri session'a kaydet (varyasyonlu olanlar dahil)
            _pending_aggregated[conversation_id] = pending_items
            logging.info(f"[SESSION] Saved pending aggregated items (including products with missing variations): {pending_items}")
            _pending_variations[conversation_id] = [dict(item) for item in missing_variations_in_cart]
             
            context_lines.append("KULLANICI SİPARİŞ VERDİ ANCAK BAZI ÜRÜNLER İÇİN SEÇENEK BELİRTİLMEDİ. MÜŞTERİYE KISA VE NET BİR ŞEKİLDE SEÇENEKLERİ SOR. PASİF OLMA, DİREKT SEÇENEKLERİ SUN.")
            
            missing_vars_text = []
            for mv in missing_variations_in_cart:
                var_list = ", ".join(mv["varyasyonlar"])
                # Ürün adını ve adetini regex'e uygun formatta yaz (conversation history'den bulabilmek için)
                missing_vars_text.append(f"'{mv['urun']}' (x{mv['adet']}) için: {var_list}")
            default_reply = f"Merhaba! Şu ürünler için seçenek belirtmediniz: {'; '.join(missing_vars_text)}. Lütfen tercihinizi belirtir misiniz?"
            logging.info(f"[VARIATION] default_reply with product counts: {default_reply}")
            # LLM çağrısı yapılacak
        else:
            # Sepet oluştur - varyasyon bilgisini de ekle
            sepet = []
            for key, adet in aggregated.items():
                # Key formatı "product_key|variation_name" olabilir
                if "|" in key:
                    # Parse aşamasında oluşturulmuş unique key
                    product_key, pre_selected_variation = key.split("|", 1)
                    logging.info(f"[CART] Parsing key with variation: product='{product_key}', variation='{pre_selected_variation}'")
                else:
                    product_key = key
                    pre_selected_variation = None
                
                # Menü öğesini bul
                menu_item = next((item for item in menu_items if item["key"] == product_key), None)
                urun_ad = name_map.get(product_key, product_key)
                base_fiyat = float(price_map.get(product_key) or 0)
                kategori = category_map.get(product_key, "")
                
                # Varyasyon kontrolü
                varyasyon_ad = None
                ek_fiyat = 0
                
                if pre_selected_variation:
                    # Parse aşamasında varyasyon belirlenmiş
                    varyasyon_ad = pre_selected_variation
                    if menu_item and menu_item.get("varyasyonlar"):
                        for var_obj in menu_item["varyasyonlar"]:
                            if var_obj["ad"] == pre_selected_variation:
                                ek_fiyat = float(var_obj["ek_fiyat"] or 0)
                                break
                    logging.info(f"[VARIATION] Using pre-selected variation: '{varyasyon_ad}' for '{urun_ad}'")
                elif menu_item and menu_item.get("varyasyonlar"):
                    var_names = [var["ad"] for var in menu_item["varyasyonlar"]]
                    logging.info(f"[VARIATION] Product '{urun_ad}' has variations: {var_names}")
                    text_lower = text.lower()
                    for var_name in var_names:
                        if normalize_name(var_name) in text_lower or any(word in text_lower for word in var_name.lower().split()):
                            varyasyon_ad = var_name
                            logging.info(f"[VARIATION] Found variation '{var_name}' in text for '{urun_ad}'")
                            # Ek fiyatı bul
                            for var_obj in menu_item["varyasyonlar"]:
                                if var_obj["ad"] == var_name:
                                    ek_fiyat = float(var_obj["ek_fiyat"] or 0)
                                    break
                            break
                
                # Sepete ekle
                sepet_item = {
                    "urun": urun_ad,
                    "adet": adet,
                    "fiyat": base_fiyat,
                    "kategori": kategori
                }
                if varyasyon_ad:
                    sepet_item["varyasyon"] = varyasyon_ad
                    sepet_item["fiyat"] = base_fiyat + ek_fiyat
                    logging.info(f"[VARIATION] Adding to cart: {urun_ad} x {adet} with variation '{varyasyon_ad}' (total: {base_fiyat + ek_fiyat} TL)")
                
                sepet.append(sepet_item)
            
            tutar = sum(item["adet"] * item["fiyat"] for item in sepet)

            # Adisyon sistemi: Masada açık adisyon varsa al, yoksa oluştur
            from ..routers.adisyon import _get_or_create_adisyon, _update_adisyon_totals
            adisyon_id = await _get_or_create_adisyon(masa, sube_id)

            row = await db.fetch_one(
                """
                INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar)
                VALUES (:sid, :masa, :adisyon_id, CAST(:sepet AS JSONB), 'yeni', :tutar)
                RETURNING id, masa, durum, tutar, created_at
                """,
                {"sid": sube_id, "masa": masa, "adisyon_id": adisyon_id, "sepet": json_dumps(sepet), "tutar": tutar},
            )
            logging.info(f"[ORDER] Created order #{row['id']} with sepet: {json_dumps(sepet)}")
            
            # Adisyon toplamlarını güncelle
            try:
                await _update_adisyon_totals(adisyon_id, sube_id)
            except Exception as e:
                logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)

            for key, adet in aggregated.items():
                # Key formatı "product_key|variation_name" olabilir
                if "|" in key:
                    stok_key = key.split("|", 1)[0]
                else:
                    stok_key = key
                new_value = stock_map.get(stok_key, 0) - adet
                _fallback_stock[(sube_id, stok_key)] = max(0.0, new_value)
                if stok_key in has_db_key:
                    await db.execute(
                        """
                        UPDATE stok_kalemleri
                        SET miktar = GREATEST(0, miktar - :adet)
                        WHERE sube_id = :sid AND LOWER(kod) = LOWER(:kod)
                        """,
                        {"adet": adet, "sid": sube_id, "kod": name_map.get(stok_key, stok_key)},
                    )

            order_summary = {"id": row["id"], "masa": row["masa"], "durum": row["durum"], "tutar": float(row["tutar"]), "created_at": row["created_at"], "sepet": sepet}
            sepet_desc = ", ".join(f"{item['urun']} x{item['adet']}" for item in sepet)
            
            # WebSocket broadcast for new order
            from ..websocket.manager import manager, Topics
            await manager.broadcast({
                "type": "new_order",
                "order_id": row["id"],
                "masa": row["masa"],
                "durum": row["durum"],
                "sube_id": sube_id
            }, topic=Topics.KITCHEN)
            
            await manager.broadcast({
                "type": "order_added",
                "order_id": row["id"],
                "masa": row["masa"],
                "status": row["durum"],
                "sube_id": sube_id
            }, topic=Topics.ORDERS)
            
            # Clear pending aggregated items from session
            if conversation_id in _pending_aggregated:
                del _pending_aggregated[conversation_id]
                logging.info(f"[SESSION] Cleared pending aggregated for conversation {conversation_id}")
            if conversation_id in _pending_variations:
                del _pending_variations[conversation_id]
                logging.info(f"[SESSION] Cleared pending variations for conversation {conversation_id}")
            
            # ÖNEMLİ: Parse işlemi başarılı oldu, LLM'e parse edilen ürünlerin menüde olduğunu açıkça belirt
            parsed_products = [name_map.get(k, k) for k in aggregated.keys()]
            context_lines.append(f"KULLANICI SİPARİŞ VERDİ VE SİPARİŞ BAŞARIYLA OLUŞTURULDU. Parse işlemi şu ürünleri buldu: {', '.join(parsed_products)}. BU ÜRÜNLER MENÜDE MEVCUT VE SİPARİŞ OLUŞTURULDU.")
            context_lines.append(f"Siparis olusturuldu. Masa {masa}, tutar {tutar:.2f} TL, urunler: {sepet_desc}.")
            if not_matched:
                context_lines.append(f"Menude bulunamayanlar: {', '.join(not_matched)}.")
            
            # Parse başarılı ve sipariş oluşturuldu - neşeli ve açıklayıcı bir onay mesajı
            summary_map: Dict[Tuple[str, Optional[str]], int] = defaultdict(int)
            for item in sepet:
                urun_ad = item.get("urun")
                varyasyon_ad = item.get("varyasyon")
                adet_raw = item.get("adet", 0)
                try:
                    adet_val = int(adet_raw)
                except (TypeError, ValueError):
                    adet_val = max(1, int(float(adet_raw or 1)))
                summary_map[(urun_ad, varyasyon_ad)] += adet_val

            summary_parts: List[str] = []
            for (urun_ad, varyasyon_ad), adet_val in summary_map.items():
                if varyasyon_ad:
                    summary_parts.append(f"{adet_val} {urun_ad} ({varyasyon_ad})")
                else:
                    summary_parts.append(f"{adet_val} {urun_ad}")
            parsed_items_desc = ", ".join(summary_parts)
            default_reply = f"Harika! Siparişinizi oluşturdum. {parsed_items_desc}. Toplam {tutar:.2f} TL. Afiyet olsun!"
            if auto_selected_variations:
                defaults_sentence = " ".join(
                    f"{urun} için varsayılan olarak '{varyasyon}' hazırlıyoruz."
                    for urun, varyasyon in auto_selected_variations
                )
                default_reply += " " + defaults_sentence

    dairy_free_names = [item["ad"] for item in dairy_free_items if _is_item_available(item)]
    caffeine_free_names = [item["ad"] for item in caffeine_free_items if _is_item_available(item)]
    gluten_free_names = [item["ad"] for item in gluten_free_items if _is_item_available(item)]
    milky_coffee_names = [item["ad"] for item in milky_coffee_items if _is_item_available(item)]
    if dairy_free_names:
        context_lines.append("Sut icermeyen secenekler: " + ", ".join(dairy_free_names) + ".")
    if caffeine_free_names:
        context_lines.append("Kafeinsiz secenekler: " + ", ".join(caffeine_free_names) + ".")
    if gluten_free_names:
        context_lines.append("Glutensiz secenekler: " + ", ".join(gluten_free_names) + ".")
    if milky_coffee_names:
        context_lines.append("Sutlu kahve secenekleri: " + ", ".join(milky_coffee_names) + ".")

    if asks_dairy and dairy_free_names:
        suggestions = dairy_free_names[:5]
    elif asks_milky_coffee and milky_coffee_names:
        suggestions = milky_coffee_names[:5]
    elif asks_caffeine and caffeine_free_names:
        suggestions = caffeine_free_names[:5]
    elif asks_gluten and gluten_free_names:
        suggestions = gluten_free_names[:5]
    elif asks_dessert:
        dessert_items = _select_dessert_items(menu_items)
        suggestions = [item["ad"] for item in dessert_items] if dessert_items else _pick_menu_samples(menu_items, 4)
    elif aggregated:
        suggestions = [item["urun"] for item in order_summary["sepet"]] if order_summary else None
    elif is_menu_query:
        suggestions = _pick_menu_samples(menu_items, 5)

    # Sohbet/soru durumları için context hazırla
    if not aggregated and not shortages:
        if asks_sensitive_business:
            suggestions = _pick_menu_samples(menu_items, 4)
            default_reply = (
                "Bu bilgiler sadece işletme yetkilileriyle paylaşılabilir. "
                "Benim görevim size menüden siparişlerde yardımcı olmak; sıcak bir kahve "
                "ya da tost isterseniz hemen hazırlayabilirim!"
            )
            context_lines.append("Kullanıcı finansal/satış verisi soruyor. Nazikçe reddet ve menüye yönlendir.")
            force_default_reply = True
        elif mentioned_products:
            available_mentions = [item for item in mentioned_products if _is_item_available(item)]
            out_of_stock_mentions = [item for item in mentioned_products if not _is_item_available(item)]
            mentioned_names = [item["ad"] for item in available_mentions] or [item["ad"] for item in mentioned_products]
            extra_names = [
                item["ad"]
                for item in menu_items
                if item["ad"] not in mentioned_names and _is_item_available(item)
            ][:2]
            suggestions = (mentioned_names + extra_names)[:5] if mentioned_names else extra_names[:5]
            if out_of_stock_mentions:
                default_reply = (
                    f"{', '.join(item['ad'] for item in out_of_stock_mentions)} maalesef stokta kalmadı. "
                )
                if mentioned_names:
                    default_reply += f"Ama {', '.join(mentioned_names)} hemen hazırlayabilirim. "
                elif extra_names:
                    default_reply += f"Yerine {', '.join(extra_names)} öneririm. "
            else:
                if mentions_hungry:
                    default_reply = f"Çok acıktıysan {', '.join(mentioned_names)} harika gider! "
                else:
                    default_reply = f"{', '.join(mentioned_names)} hemen hazırlayabilirim. "
            if extra_names:
                default_reply += f"Yanında {', '.join(extra_names)} de öneririm."
            else:
                default_reply += "İstersen içecek veya tatlı da seçebilirsin."
            low_stock = [item["ad"] for item in available_mentions if _is_item_low_stock(item)]
            if low_stock:
                default_reply += f" Bu arada {', '.join(low_stock)} için stokta son birkaç adet kaldı."
            context_lines.append(
                f"Kullanıcı menüden {', '.join(item['ad'] for item in mentioned_products)} istedi. Ürün stok durumunu kontrol et, biterse alternatif öner."
            )
            force_default_reply = True
        elif mentions_hungry:
            hungry_items = _select_hungry_recommendations(menu_items, attr_map)
            hungry_names = [item["ad"] for item in hungry_items[:4]] if hungry_items else []
            suggestions = hungry_names or _pick_menu_samples(menu_items, 4)
            if hungry_names:
                default_reply = (
                    f"Çok acıktıysan {', '.join(hungry_names)} çok doyurucu seçenekler. "
                    "Yanında sıcak çay veya ferah bir limonata da harika gider."
                )
            else:
                default_reply = "Şu an sıcak tostlarımız ve sandviçlerimiz çok popüler, hemen hazırlayabilirim!"
            context_lines.append(
                "Kullanıcı acıktığını söylüyor. Doyurucu yiyecekleri öner, yanına içecek eşleştir."
            )
            force_default_reply = True
        elif asks_sleepy:
            sleepy_items = [
                item["ad"]
                for item in menu_items
                if any(keyword in normalize_name(item["ad"]) for keyword in HERBAL_TEA_KEYWORDS)
            ]
            if not sleepy_items and caffeine_free_names:
                sleepy_items = caffeine_free_names[:4]
            suggestions = sleepy_items or _pick_menu_samples(menu_items, 4)
            if sleepy_items:
                default_reply = (
                    f"Uyku öncesi hafif ve kafeinsiz {', '.join(sleepy_items[:3])} çok rahatlatır. "
                    "Hangisini demleyeyim?"
                )
            else:
                default_reply = "Uyku dostu bitki çaylarımızdan birini önerebilirim; istersen hemen hazırlayayım."
            context_lines.append("Kullanıcı uykulu olduğunu söylüyor. Kafeinsiz/bitki çayı öner, uyku dostu olduğunu vurgula.")
            force_default_reply = True
        elif asks_energy:
            energy_items = [
                item["ad"]
                for item in menu_items
                if attr_map.get(item.get("key") or "", {}).get("contains_caffeine")
                and any(keyword in _tokenize(item["ad"]) for keyword in COFFEE_KEYWORDS)
            ]
            if not energy_items:
                energy_items = [
                    item["ad"]
                    for item in menu_items
                    if attr_map.get(item.get("key") or "", {}).get("contains_caffeine")
                ][:4]
            suggestions = energy_items or _pick_menu_samples(menu_items, 4)
            if energy_items:
                default_reply = (
                    f"Enerjini yükseltmek için {', '.join(energy_items[:3])} güçlü seçenekler. "
                    "Hangisini hazırlayayım?"
                )
            else:
                default_reply = "Enerji veren kahvelerimizden birini önerebilirim; istersen espresso bazlı hazırlayayım."
            context_lines.append("Kullanıcı enerji/ayıltıcı içecek arıyor. Kafeinli kahveleri öner ve etkilerini açıkla.")
            force_default_reply = True
        elif mentions_negative_mood:
            comfort_items = _select_dessert_items(menu_items) or _select_temp_recommendations(menu_items, HOT_DRINK_KEYWORDS)
            comfort_names = [item["ad"] for item in comfort_items[:4]] if comfort_items else _pick_menu_samples(menu_items, 4)
            suggestions = comfort_names
            default_reply = (
                f"Morali yerine getirecek {', '.join(comfort_names[:3])} çok iyi gider. "
                "İstersen yanında sıcak bir içecek de öneririm."
            )
            context_lines.append("Kullanıcı kötü hissettiğini söylüyor. Empati kur, moral yükseltecek tatlı/sıcak seçenekler öner.")
            force_default_reply = True
        elif mentions_positive_mood:
            cheerful_samples = _pick_menu_samples(menu_items, 4)
            suggestions = cheerful_samples
            default_reply = (
                f"Harika! Kutlamak için {', '.join(cheerful_samples[:3])} süper gider. "
                "Hangisiyle devam edelim?"
            )
            context_lines.append("Kullanıcı mutlu olduğunu söylüyor. Enerjik ve kutlama havasında öneriler sun.")
            force_default_reply = True
        elif mentions_small_talk:
            small_talk_samples = _pick_menu_samples(menu_items, 4)
            suggestions = small_talk_samples
            default_reply = (
                f"Sohbet harika, bu arada {', '.join(small_talk_samples[:3])} çok seviliyor. "
                "İstersen hemen hazırlayayım."
            )
            context_lines.append("Kullanıcı sadece sohbet ediyor. Samimi kal, menüden öneriyle sohbeti siparişe çevir.")
            force_default_reply = True
        elif asks_ingredients:
            if mentioned_products:
                ingredient_responses = []
                for product in mentioned_products[:2]:
                    summary = _format_ingredient_summary(product)
                    attr = attr_map.get(product.get("key"), {})
                    allergen_notes = []
                    if attr.get("contains_milk"):
                        allergen_notes.append("süt içerir")
                    if attr.get("contains_gluten"):
                        allergen_notes.append("glüten içerir")
                    if attr.get("contains_nuts"):
                        allergen_notes.append("kuruyemiş içerir")
                    parts = [f"{product['ad']}"]
                    if summary:
                        parts.append(summary)
                    if allergen_notes:
                        parts.append("Allerjen notu: " + ", ".join(allergen_notes))
                    ingredient_responses.append(" ".join(parts))
                default_reply = " ".join(ingredient_responses) + " Hazırsan siparişi hemen oluşturabilirim."
            else:
                default_reply = "Hangi ürünün içeriğini merak ediyorsan söyle, reçetemizden tüm malzemeleri paylaşayım."
            suggestions = [prod["ad"] for prod in mentioned_products[:5]] if mentioned_products else None
            context_lines.append("Kullanıcı ürün içeriği/allerjen soruyor. Reçetedeki malzemeleri ve süt/glüten/kuruyemiş gibi allerjenleri açıkla, stok durumundan da bahset.")
            force_default_reply = True
        elif asks_cold:
            cold_items = _select_temp_recommendations(menu_items, COLD_DRINK_KEYWORDS)
            cold_names = [item["ad"] for item in cold_items]
            suggestions = cold_names
            default_reply = (
                f"Buz gibi ferahlamak istersen {', '.join(cold_names)} çok iyi gider. "
                "Hangisini hazırlayayım?"
            )
            context_lines.append("Kullanıcı soğuk bir şey istiyor. Menüdeki soğuk içecekleri öner.")
            force_default_reply = True
        elif asks_hot:
            hot_items = _select_temp_recommendations(menu_items, HOT_DRINK_KEYWORDS)
            hot_names = [item["ad"] for item in hot_items]
            suggestions = hot_names
            default_reply = (
                f"İçinizi ısıtacak {', '.join(hot_names)} seçeneklerimiz var. "
                "Yanına taze bir tatlı da önerebilirim!"
            )
            context_lines.append("Kullanıcı sıcak bir şey istiyor. Menüdeki sıcak içecekleri öner.")
            force_default_reply = True
        elif asks_dessert:
            dessert_items = _select_dessert_items(menu_items)
            dessert_names = [item["ad"] for item in dessert_items] if dessert_items else _pick_menu_samples(menu_items, 4)
            suggestions = dessert_names
            if dessert_names:
                default_reply = (
                    f"Tatlı vitrinimizde {', '.join(dessert_names)} çok seviliyor. "
                    "Hangisini hazırlayayım?"
                )
            else:
                default_reply = "Tatlı listemiz için menüyü kontrol etmem gerekiyor ama istersen sıcak içecek önerebilirim."
            context_lines.append("Kullanıcı tatlı/pasta istiyor. Menüden tatlıları seçip kısa açıklamalarla öner.")
            force_default_reply = True
        elif asks_cold:
            cold_items = _select_temp_recommendations(menu_items, COLD_DRINK_KEYWORDS)
            cold_names = [item["ad"] for item in cold_items]
            suggestions = cold_names
            default_reply = (
                f"Buz gibi ferahlamak istersen {', '.join(cold_names)} çok iyi gider. "
                "Hangisini hazırlayayım?"
            )
            context_lines.append("Kullanıcı soğuk bir şey istiyor. Menüdeki soğuk içecekleri öner.")
            force_default_reply = True
        elif asks_hot:
            hot_items = _select_temp_recommendations(menu_items, HOT_DRINK_KEYWORDS)
            hot_names = [item["ad"] for item in hot_items]
            suggestions = hot_names
            default_reply = (
                f"İçinizi ısıtacak {', '.join(hot_names)} seçeneklerimiz var. "
                "Yanına taze bir tatlı da önerebilirim!"
            )
            context_lines.append("Kullanıcı sıcak bir şey istiyor. Menüdeki sıcak içecekleri öner.")
            force_default_reply = True
        elif asks_sore_throat:
            # Bitki çaylarını menüden bul
            soothing_items = [
                item["ad"]
                for item in menu_items
                if any(keyword in normalize_name(item["ad"]) for keyword in HERBAL_TEA_KEYWORDS)
            ]

            if soothing_items:
                top_pick = soothing_items[:3]
                suggestions = top_pick
                default_reply = (
                    f"Geçmiş olsun! {', '.join(top_pick)} çok iyi gelir, "
                    "ikisi de boğazı rahatlatır. Hangisini istersiniz?"
                )
            else:
                # Menüde bitki çayı yok - sıcak içecekler öner
                hot_items = [item["ad"] for item in menu_items if "sicak" in normalize_name(item.get("kategori", "")) or "çay" in normalize_name(item["ad"])]
                suggestions = hot_items[:4] if hot_items else _pick_menu_samples(menu_items, 4)
                default_reply = (
                    "Geçmiş olsun! Sıcak bir içecek iyi gelir. "
                    f"{', '.join(suggestions[:2])} önerebilirim."
                )
            context_lines.append(f"Kullanıcı hasta/boğaz ağrısı belirtiyor. Önerilen ürünler: {', '.join(suggestions)}")
            force_default_reply = True
        elif asks_wellbeing:
            suggestions = _pick_menu_samples(menu_items, 4)
            default_reply = (
                "Çok iyiyim, teşekkür ederim! Sizinle ilgilenmek için buradayım. "
                "Menümüzde {0} gibi harika seçenekler var; hangisinden başlayalım?"
            ).format(", ".join(suggestions[:3]))
            context_lines.append("Kullanıcı hal hatır soruyor. Kısa, sıcak bir yanıt ver ve menüye yönlendir.")
            force_default_reply = True
        elif is_menu_query:
            default_reply = _format_menu_summary(menu_items)
            context_lines.append("Kullanıcı menüyü soruyor. Kategorilere göre kısa özet sun.")
        elif asks_dairy and dairy_free_names:
            default_reply = "Sut icermeyen urunler: " + ", ".join(dairy_free_names) + "."
            suggestions = dairy_free_names[:5]
            context_lines.append("Kullanıcı süt içermeyen ürün soruyor. Menüden uygun seçenekleri öner.")
            force_default_reply = True
        elif asks_milky_coffee:
            if milky_coffee_names:
                default_reply = "Sutlu kahvelerimiz: " + ", ".join(milky_coffee_names) + "."
                suggestions = milky_coffee_names[:5]
                context_lines.append("Kullanıcı sütlü kahve istiyor. Menüden süt içeren kahve bazlı içecekleri listele ve kısa açıklama yap.")
                force_default_reply = True
            else:
                context_lines.append("Kullanıcı sütlü kahve istiyor ancak menüde süt içeren kahve bulunmuyor. Nazikçe açıklayıp uygun alternatif öner.")
        elif asks_caffeine and caffeine_free_names:
            default_reply = "Kafeinsiz urunler: " + ", ".join(caffeine_free_names) + "."
            suggestions = caffeine_free_names[:5]
            context_lines.append("Kullanıcı kafeinsiz ürün soruyor. Menüden uygun seçenekleri öner.")
            force_default_reply = True
        elif asks_gluten:
            if gluten_free_names:
                default_reply = "Glutensiz urunler: " + ", ".join(gluten_free_names) + "."
                suggestions = gluten_free_names[:5]
                context_lines.append(f"Kullanıcı glütensiz ürün soruyor. Menüdeki glütensiz seçenekler: {', '.join(gluten_free_names)}. İçeriklerden glüten olup olmadığını kontrol et.")
                force_default_reply = True
            else:
                context_lines.append("Kullanıcı glütensiz ürün soruyor ancak reçetelerde uygun seçenek bulunamadı. Menüdeki en yakın alternatifleri belirt ve glüten içerdiğini açıkla.")
        elif asks_sore_throat:
            # Boğaz ağrısı/hastalık için özel öneriler: SADECE bitki çayları
            herbal_teas = [
                item["ad"] for item in menu_items
                if any(keyword in normalize_name(item["ad"]) for keyword in HERBAL_TEA_KEYWORDS)
            ]

            if herbal_teas:
                # Menüde bitki çayı var - bunları öner
                context_lines.append(
                    f"MÜŞTERİ HASTA/BOĞAZ AĞRISI BELİRTİYOR!\n"
                    f"- MUTLAKA 'Geçmiş olsun!' veya benzeri empati göster\n"
                    f"- SADECE ŞU BİTKİ ÇAYLARINI ÖNER: {', '.join(herbal_teas[:4])}\n"
                    f"- Her birinin özelliklerini kısaca açıkla (örn: 'boğazı rahatlatır', 'şifalı')\n"
                    f"- ASLA pasta, tatlı, limonata, kahve gibi ürünler önerme\n"
                    f"- ASLA genel 'Çay' önerme, SADECE bitki çaylarını öner\n"
                    f"- Kısa ve samimi ol: 2-3 cümle yeterli"
                )
            else:
                # Menüde bitki çayı yok - en uygun alternatifi öner
                context_lines.append(
                    f"MÜŞTERİ HASTA/BOĞAZ AĞRISI BELİRTİYOR ama menüde bitki çayı yok!\n"
                    f"- MUTLAKA 'Geçmiş olsun!' veya benzeri empati göster\n"
                    f"- Menüden sıcak ve rahatlatıcı ürünleri öner (örn: sade çay, sıcak içecekler)\n"
                    f"- ASLA pasta, tatlı, soğuk içecek önerme\n"
                    f"- Kısa ve samimi ol: 2-3 cümle yeterli"
                )
        elif asks_dairy_free_coffee:
            # Sütsüz kahve için özel öneriler: Türk Kahvesi, Espresso, Americano (Menengiç değil!)
            context_lines.append("Kullanıcı sütsüz kahve istiyor. ÇOK ÖNEMLİ: Türk Kahvesi, Espresso, Americano gibi süt içermeyen kahveler öner. Menengiç Kahvesi önerme çünkü Menengiç Kahvesi farklı bir tattır (menengiç tohumundan yapılır, kahve çekirdeği değildir). Sütsüz kahve = Türk Kahvesi, Espresso, Americano. Menüden bu ürünleri bul ve öner.")
        elif asks_dessert:
            context_lines.append("Kullanıcı tatlı/pasta soruyor. Menüdeki tatlıları ve pastaları listele, popüler olanları vurgula, kısa tatlı betimlemeleri ekle ve isterse yanında uyumlu içecek öner.")
        elif asks_cold:
            context_lines.append("Kullanıcı soğuk içecek/ürün soruyor. Menüdeki soğuk içecekleri, buzlu seçenekleri öner ve özelliklerini belirt.")
        elif asks_hot:
            context_lines.append("Kullanıcı sıcak içecek/ürün soruyor. Menüdeki sıcak içecekleri öner ve özelliklerini belirt.")
        elif asks_recommendation:
            context_lines.append("Kullanıcı öneri istiyor. Menüden popüler veya uygun ürünleri öner, özelliklerini kısaca açıkla.")
        elif asks_math:
            context_lines.append("Kullanıcı matematik sorusu soruyor. Soruyu çöz ve neşeli bir şekilde cevap ver, ardından menüden bir şey önerebilirsin.")
        elif asks_business and business_profile:
            default_reply = f"{business_profile.get('isletme_ad') or 'Neso'} {business_profile.get('sube_ad') or ''} subemiz hizmetinizde."
        elif asks_question:
            context_lines.append("Kullanıcı soru soruyor. Soruyu anlayıp menüden uygun cevaplar ver.")
        # Greeting kontrolü artık parse öncesinde yapılıyor, buraya gelmemeli
        else:
            # Sohbet durumu veya parse başarısız - LLM'e bırak
            if not_matched and len(not_matched) > 0:
                # Parse başarısız, ürün bulunamadı - PROAKTİF ol, direkt alternatif öner
                context_lines.append(f"Kullanıcı menüde olmayan bir ürün istedi: {', '.join(not_matched)}. PROAKTİF OL: Direkt alternatif öner, ASLA 'Sipariş almak ister misiniz?' gibi pasif sorular sorma. Menüden uygun ürünleri öner ve yönlendir.")
            else:
                context_lines.append("Kullanıcı sohbet ediyor veya genel bir soru soruyor. Samimi ve yardımcı ol, menüden uygun öneriler sun.")

    # Build Fıstık Kafe Neso System Prompt with attributes
    menu_prompt_data = _build_neso_menu_prompt(menu_items, attr_map)
    business_name = business_profile.get('isletme_ad') or 'Fıstık Kafe' if business_profile else 'Fıstık Kafe'

    system_prompt = f"""Sen {business_name} için **Neso** adında, son derece zeki, neşeli, konuşkan, müşteriyle empati kurabilen, hafif esprili ve satış yapmayı seven ama asla bunaltmayan bir sipariş asistanısın.

Görevin, müşterilerin taleplerini doğru anlamak, onlara {business_name}'nin MENÜSÜNDEKİ lezzetleri coşkuyla tanıtmak ve siparişlerini almaktır.

# ÖNEMLİ: ZEKA VE ANLAYIŞ SEVIYESI + PROAKTİFLİK
- Çok zeki ol, müşterinin ne istediğini derinden anla
- Bağlamı (konuşma geçmişini) iyi kullan, önceki mesajları hatırla ve referans ver
- Müşterinin niyetini anlamaya çalış, sadece kelimelere değil anlamına odaklan
- Belirsizlikleri akıllıca çöz, direkt önerilerde bulun - soru sorma, harekete geç
- Ürün önerileri yaparken müşterinin tercihlerini, önceki siparişlerini ve konuşma bağlamını kullan
- PROAKTİF OL: Pasif kalma, beklemeye alma, sorularla zaman kaybetme. Direkt öner, yönlendir, işlem yap.

# GÜNCEL STOKTAKİ ÜRÜNLER, FİYATLARI VE ÖZELLİKLERİ
Her ürünün yanında [özellikler] içinde şu bilgiler var:
- sütlü/sütsüz: Ürünün süt içerip içermediği
- kafeinli/kafeinsiz: Ürünün kafein içerip içermediği
- sıcak/soğuk: Ürünün sıcak mı soğuk mu servis edildiği
- bitki çayı: Bitki çayı mı yoksa normal çay/kahve mi
- stok durumu: "Stokta var", "son X adet" veya "stokta yok" bilgisi
- İçindekiler: Reçetede yer alan ana malzemeler ve varsa birim/miktar bilgisi

{menu_prompt_data}

# ÜRÜN ÖZELLİKLERİNİ NASIL KULLANACAKSIN:
## Müşteri Talepleri ve Ürün Eşleştirme:
1. **"Sütlü kahveleriniz nedir?"** → Menüden [sütlü, kafeinli] etiketli kahveleri ara ve listele
2. **"Kafeinsiz bir şey istiyorum"** → Menüden [kafeinsiz] etiketli tüm ürünleri ara ve öner
3. **"Soğuk içecek"** → Menüden [soğuk] etiketli ürünleri ara
4. **"Biraz hastayım"** → Menüden [bitki çayı] etiketli ürünleri ara, özellikle Adaçayı, Nane Limon
5. **"Baş ağrım var"** → Menüden [kafeinli] ürünler öner (kafein baş ağrısına iyi gelir)
6. **"Uykum var / Uyuyamıyorum"** → Menüden [kafeinsiz, bitki çayı] ürünler öner
7. **"Sütsüz kahve"** → Menüden [sütsüz, kafeinli] etiketli kahveleri ara (Türk Kahvesi, Espresso, Americano)

## SAĞLIK DURUMLARINA GÖRE ÖNERİ TABLOSU (ÇOK ÖNEMLİ):
- **Hasta, boğaz ağrısı, nezle, grip** → [bitki çayı] (Adaçayı, Nane Limon, Ihlamur öncelik)
- **Baş ağrısı, migren** → [kafeinli] (Türk Kahvesi, Espresso, Americano) + "Kafein baş ağrısına iyi gelir"
- **Uykusuzluk, uyku sorunu** → [kafeinsiz] (bitki çayları öncelik) + "Uyku dostu, rahatlatıcı"
- **Yorgunluk, enerji düşük** → [kafeinli] (kahveler) + "Sizi canlandırır"
- **Mide hassasiyeti** → [kafeinsiz, bitki çayı] (Ihlamur, Papatya) + "Mideye yumuşak gelir"
- **Sütü tolere edememe** → [sütsüz] ürünler (Türk Kahvesi, Espresso, Americano, bitki çayları)

## FİLTRELEME MANTIĞI:
Müşteri birden fazla kriter söyleyebilir. HEPSINÎ birden karşılayan ürünleri bul:
- "Sıcak ama kafeinsiz" → [sıcak, kafeinsiz] (bitki çayları)
- "Soğuk ve sütlü" → [soğuk, sütlü] (Soğuk Latte, Iced Cappuccino gibi)
- "Kafeinli ama sütsüz" → [kafeinli, sütsüz] (Türk Kahvesi, Espresso, Americano)

# KESİN KURAL (MENÜ SADAKATİ):
1. Yukarıdaki MENÜ güncel ve doğrudur. İşleyebileceğin TÜM ürünler, kategoriler ve fiyatlar BU LİSTEYLE SINIRLIDIR.
2. Ürün isimlerini, fiyatlarını ve kategorilerini AYNEN BU LİSTEDE GÖRDÜĞÜN GİBİ KULLAN.
3. Bu listede olmayan hiçbir şeyi siparişe ekleme, önerme, hakkında yorum yapma veya varmış gibi davranma.
4. ASLA MENÜ DIŞI BİR ÜRÜN UYDURMA, VARSAYIM YAPMA VEYA MENÜDEKİ BİR ÜRÜNÜ İSTENEN FARKLI BİR ÜRÜN YERİNE KOYMA.

# ÖNEMLİ KURALLAR:

## 0. Yetkisiz Konular:
   - Muhasebe, ciro, kar marjı, maliyet, stok maliyeti ve işletme içi finansal detaylar müşterilerle paylaşılmaz.
   - Bu tip soruları nazikçe reddet ve müşteriyi menü/sipariş konularına yönlendir.
   - "Bu bilgiler yalnızca işletme yetkilileriyle paylaşılabilir" mesajını her zaman hatırla.

## 1. Menü Dışı Talepler:
   - Müşteri MENÜDE olmayan bir ürün sorarsa, ürünün MENÜDE olmadığını KISA, NET ve KİBARCA belirt.
   - ASLA o ürün hakkında yorum yapma, VARSAYIMDA BULUNARAK BENZER BİR ÜRÜN EKLEME veya varmış gibi davranma.
   - Hemen konuyu {business_name}'nin MENÜSÜNE geri getirerek SADECE MENÜDE BULUNAN ÜRÜNLERDEN bir alternatif öner.
   - **PROAKTİF OL**: "Hangisini istersiniz?" gibi sorular sorma. Direkt alternatif öner ve müşteriyi yönlendir.
   - Örnek İYİ: "Papatya çayımız maalesef şu an menümüzde bulunmuyor. Ama menümüzde Adaçayı ve Kuşburnu Çayı var. Bunlardan birini önerebilirim!"
   - Örnek KÖTÜ: "Papatya çayımız maalesef şu an menümüzde bulunmuyor. Hangisini istersiniz?" (PASİF - SORMA!)
   
## 1.5. PARSE İŞLEMİ SONUÇLARI:
   - Eğer context'te "KULLANICI SİPARİŞ VERDİ VE SİPARİŞ BAŞARIYLA OLUŞTURULDU" mesajı varsa, bu ürünlerin MENÜDE MEVCUT olduğunu ve siparişin oluşturulduğunu KABUL ET.
   - ASLA parse işlemi başarıyla bir ürün bulmuşsa ve sipariş oluşturulmuşsa, o ürünün "menüde yok" olduğunu söyleme.
   - Parse işlemi başarılıysa, sipariş oluşturulmuş demektir ve bu ürünler kesinlikle menüde vardır.

## 2. Ürün Eşleştirme ve Öneriler:
   - Kullanıcı tam ürün adını söylemese bile, yalnızca MENÜ LİSTESİNDEKİ ürünlerle %100'e yakın eşleşme bulabiliyorsan bu ürünü dikkate al.
   - Eğer eşleşmeden %100 emin değilsen, ASLA varsayım yapma. Soru sorarak MENÜDEN netleştir.
   - Kullanıcı belirsiz bir istekte bulunduğunda (örn: "soğuk bir şey", "tatlı bir şey", "enerji veren bir şey", "glütensiz bir şey"), MENÜDEN uygun ürünleri bulup öner ve özelliklerini kısaca açıkla.
   - **ÇOK ÖNEMLİ**: Kullanıcı "glütensiz ürün ver", "soğuk ne önerebilirsin", "öneri ver" gibi sorular sorduğunda:
     * ASLA "menüde yok" veya "bulamadım" gibi olumsuz cevaplar verme
     * MENÜYÜ DİKKATLİCE İNCELE, kategorileri kontrol et
     * Glütensiz, soğuk, sıcak gibi özelliklere göre menüden uygun ürünleri BUL ve ÖNER
     * Eğer gerçekten uygun ürün yoksa, en yakın alternatifleri öner
     * Örnek: "Glütensiz ürünlerimiz: [menüden glütensiz ürünler]. [Ürün adı] deneyebilirsiniz!"
   - **FİYAT BİLGİSİ ÖNEMLİ KURAL**: 
     * Ürün önerilerinde (örn: "Çay önerebilirsiniz") ASLA fiyat söyleme
     * Sadece müşteri direkt sipariş verdiğinde ve sipariş oluşturulduğunda fiyat söyle
     * Öneri mesajlarında: "2 Çay önerebilirsiniz" (fiyat yok)
     * Sipariş onayında: "2 Çay. Toplam 50.00 TL" (fiyat var)

## 3. Fiyat ve Kategori Bilgisi:
   - Her ürün için fiyat ve kategori bilgisini KESİNLİKLE VE SADECE yukarıdaki MENÜ listesinden al.
   - Fiyatları ASLA TAHMİN ETME.
   - **FİYAT NE ZAMAN SÖYLENİR**: 
     * Müşteri direkt sipariş verdiğinde ve sipariş oluşturulduğunda: Fiyat SÖYLE (örn: "2 Çay. Toplam 50.00 TL")
     * Ürün önerirken veya alternatif sunarken: Fiyat SÖYLEME (örn: "2 Çay önerebilirsiniz" - fiyat yok)
     * Müşteri fiyat sorduğunda: Fiyat SÖYLE (örn: "Çay 25.00 TL")

## 4. Sipariş Onayı ve Proaktif Davranış:
   - **ÖNEMLİ**: ASLA "Siparişinizi almak ister misiniz?", "Sipariş verecek misiniz?" gibi pasif sorular sorma.
   - Sen bir SİPARİŞ ASİSTANISIN - görevin sipariş almak, kullanıcıya sormak değil.
   - Müşteriden net sipariş aldığında, direkt ürün ve adeti onayla ve siparişi işle.
   - Toplam tutarı hesapla ve net bir şekilde söyle.
   - Menüde olmayan ürün istendiğinde, direkt alternatif öner ve "şunu önerebilirsiniz" de - müşteriyi yönlendir, soru sorma.
   - Sipariş alındığında neşeli bir şekilde teşekkür et, "Afiyet olsun!" veya "Çok yakında hazır!" gibi samimi ifadeler kullan.
   - Proaktif ol: Müşteriyi yönlendir, karar ver, harekete geç. Pasif kalma, bekleme, soru sorma.

## 5. İletişim Stili ve Proaktiflik:
   - Samimi, enerjik ve neşeli ol - ama asla aşırıya kaçma veya yapay görünme
   - Kısa ve net yanıtlar ver - uzun paragraflardan kaçın, 2-3 cümleyi geçme
   - Müşteri memnuniyetini ön planda tut
   - **PROAKTİF OL, PASİF KALMA**: Belirsiz durumlarda bile direkt önerilerde bulun, çok fazla soru sorma.
   - Ürünleri tanıtırken kısa ve öz özelliklerini belirt (kategori, sıcak/soğuk, popülerlik vb.)
   - İlk karşılaşmada sıcak bir hoş geldin mesajı ver ve menü hakkında kısa bilgi ver
   - Müşterinin sorularına sabırla ve anlayışla cevap ver
   - Öneri yaparken müşterinin tercihlerini anlamaya çalış ama direkt öner, soru sorma.
   - Örnek İYİ: "Sıcak içeceklerimizden Latte veya Çay önerebilirim. Hangisini tercih ederseniz hemen hazırlayayım!" (ÖNER + HAREKETE GEÇİR)
   - Örnek KÖTÜ: "Sıcak bir şey mi yoksa soğuk bir şey mi tercih edersiniz?" (PASİF - SORMA!)
   - Sipariş verme sürecini kolaylaştır, müşteriyi yönlendir ve direkt işlem yap.
   - **ASLA "Sipariş almak ister misiniz?", "Sipariş verecek misiniz?", "Ne istersiniz?" gibi açık uçlu pasif sorular sorma.**
   - Teşekkür etmeyi unutma - hem sipariş aldığında hem de müşteri teşekkür ettiğinde

## 6. Ürün Önerileri:
   - Kategorilere göre öneriler yap (sıcak içecekler, soğuk içecekler, yiyecekler, tatlılar vb.)
   - Popüler ürünleri vurgula ama abartma
   - Müşterinin tercihlerine göre özelleştirilmiş öneriler sun
   - "En çok sevilen" veya "özel" ürünleri öne çıkar ama sadece gerçekten öyleler ise
   - Kategoriler arası geçiş yaparken doğal ol, zorlama görünme

## 7. Özel Durumlar ve Proaktiflik:
   - Müşteri sadece "merhaba" dediğinde, sıcak bir karşılama yap ve menü hakkında kısa bilgi ver, popüler ürünleri öner (örn: "Merhaba! Hoş geldiniz! Menümüzde lezzetli kahveler, çaylar ve daha fazlası var. Latte veya Çay önerebilirim!")
   - Müşteri sadece "menü" istediğinde, kategorilere göre düzenlenmiş bir özet sun ama uzun olma
   - Müşteri teşekkür ettiğinde, nazikçe karşılık ver ve yardımcı olmaya hazır olduğunu belirt - ama pasif sorular sorma
   - Müşteri "ne var?" veya "neler var?" gibi genel sorular sorduğunda, kategorilere göre kısa bir özet ver ve direkt önerilerde bulun
   - **KRİTİK KURAL**: Menüde olmayan ürün istendiğinde, ASLA "Sipariş almak ister misiniz?" gibi sorular sorma. Direkt alternatif öner: "Türk Kahvesi menümüzde yok. Ama Çay veya Latte önerebilirim!" (Proaktif, yönlendirici)

## 8. Konuşma Akışı:
   - Konuşmayı doğal tut, müşteriyi yönlendir ama robot gibi görünme
   - Önceki mesajları hatırla ve referans ver
   - Müşterinin tercihlerini not et ve sonraki önerilerde kullan
   - Sipariş sürecini adım adım ilerlet ama hızlı ol

## 9. Zeka ve Anlayış (GELİŞMİŞ):
   - **DERİN ANLAMA**: Müşterinin mesajlarını derinlemesine analiz et, sadece yüzeydeki kelimeleri değil niyetini, duygusunu ve bağlamını anla
   - **BAĞLAM YÖNETİMİ**: Önceki konuşma geçmişini (conversation history) aktif olarak kullan:
     * Önceki siparişleri hatırla ve referans ver
     * Müşterinin tercihlerini öğren (sıcak/soğuk, kafeinli/kafeinsiz, tatlı/tuzlu vb.)
     * Önceki soruları ve cevapları hatırla, tekrar sorulmasını önle
     * Konuşma akışını takip et, mantıklı devam ettir
   - **NİYET TESPİTİ**: Müşterinin gerçek niyetini anla:
     * Sipariş mi veriyor, bilgi mi istiyor, öneri mi bekliyor?
     * Acele mi, rahat mı, kararsız mı?
     * Memnun mu, şikayet mi var, yardım mı istiyor?
   - **AKILLI YORUMLAMA**: Belirsiz ifadeleri akıllıca yorumla:
     * "soğuk bir şey" → Soğuk içecekler listesi + öneri
     * "tatlı" → Tatlı kategorisi + popüler tatlılar
     * "enerji veren" → Kafeinli içecekler + özellikleri
     * "hafif" → Düşük kalorili, hafif içecekler
   - **KÜLTÜREL BAĞLAM**: Kültürel bağlamı anla ve kullan:
     * Türk kahve kültürü (Türk Kahvesi, Menengiç Kahvesi vb.)
     * Çay tercihleri (Çay, Adaçayı, Kuşburnu vb.)
     * Yöresel tatlar ve özellikler
     * Mevsimsel tercihler (yaz: soğuk, kış: sıcak)
   - **ÜRÜN ÖZELLİKLERİ VE KULLANIM SENARYOLARI (ÇOK ÖNEMLİ)**:
     * **Boğaz ağrısı, hasta, soğuk algınlığı**: Adaçayı, Nane Limon, Ihlamur, Kuşburnu Çayı gibi rahatlatıcı bitki çayları öner. Çay değil, çünkü çay genel bir kategoridir. Özellikle Nane Limon ve Adaçayı boğaz ağrısına çok iyi gelir.
     * **Sütsüz kahve isteği**: Türk Kahvesi, Espresso, Americano gibi süt içermeyen kahveler öner. Menengiç Kahvesi önerme çünkü Menengiç Kahvesi farklı bir tattır (menengiç tohumundan yapılır, kahve çekirdeği değildir). Sütsüz kahve = Türk Kahvesi, Espresso, Americano.
     * **Kafeinli içecek**: Türk Kahvesi, Espresso, Americano, Latte, Cappuccino, Mocha gibi kahveler. Menengiç Kahvesi kafein içermez (menengiç tohumundan yapılır).
     * **Rahatlama, sakinleşme**: Adaçayı, Nane Limon, Ihlamur, Kuşburnu Çayı gibi bitki çayları.
     * **Enerji, uyanıklık**: Türk Kahvesi, Espresso, Americano, Latte gibi kafeinli kahveler.
     * **Soğuk içecek**: Limonata, Soğuk Kahve, Buzlu Çay, Soğuk Latte gibi soğuk kategorisindeki ürünler.
     * **Sıcak içecek**: Çay, Türk Kahvesi, Latte, Cappuccino, Adaçayı, Nane Limon gibi sıcak kategorisindeki ürünler.
     * **ÜRÜN FARKLARI**:
       - Türk Kahvesi: Süt içermez, kafeinli, geleneksel Türk kahvesi
       - Menengiç Kahvesi: Süt içermez, kafeinsiz, menengiç tohumundan yapılır (kahve çekirdeği değil), farklı bir tattır
       - Espresso: Süt içermez, kafeinli, yoğun kahve
       - Americano: Süt içermez, kafeinli, espresso + su
       - Latte: Süt içerir, kafeinli, espresso + süt
       - Cappuccino: Süt içerir, kafeinli, espresso + süt + köpük
       - Adaçayı: Bitki çayı, kafeinsiz, rahatlatıcı, boğaz ağrısına iyi gelir
       - Nane Limon: Bitki çayı, kafeinsiz, rahatlatıcı, boğaz ağrısına çok iyi gelir
       - Çay: Genel kategoridir, kafeinli, sıcak içecek
       - Limonata: Soğuk içecek, kafeinsiz, ferahlatıcı
   - **RUH HALİ TESPİTİ**: Müşterinin ruh halini sez ve ona göre yaklaş:
     * Acele → Hızlı, net, direkt öneriler
     * Rahat → Detaylı bilgi, özellikler, öneriler
     * Kararsız → Alternatifler, karşılaştırma, yönlendirme
     * Memnun → Teşekkür, ek öneriler
     * Şikayet → Anlayış, çözüm, alternatif
   - **KİŞİSELLEŞTİRME**: Önceki konuşmalardan öğren ve kişiselleştirilmiş öneriler yap:
     * Müşterinin favori kategorilerini hatırla
     * Önceki siparişlerine benzer öneriler yap
     * Tercihlerine göre özelleştir (sıcak/soğuk, kafeinli/kafeinsiz)
   - **ZENGİN YANITLAR**: Yanıtlarını zenginleştir ama gereksiz detaylara dalmadan:
     * Ürün özelliklerini kısaca belirt (kategori, sıcak/soğuk, popülerlik)
     * Fiyat bilgisini doğru zamanda ver
     * Alternatifleri sun ama çok fazla seçenek sunma (3-5 arası ideal)
     * Önerileri mantıklı sırala (popüler → özel → alternatif)

## 10. Doğal Dil Anlama (GELİŞMİŞ):
   - **DİL ESNEKLİĞİ**: Türkçe'nin esnekliğini anla:
     * Tam kelime söylenmese bile anlamaya çalış ("çay" → "Çay", "kahve" → "Türk Kahvesi" veya "Menengiç Kahvesi")
     * Kısaltmaları anla ("latte" → "Latte", "americano" → "Americano")
     * Argo ifadeleri anla ("buzlu" → soğuk içecek, "sıcak" → sıcak içecek)
   - **YAZIM HATALARI**: Farklı yazım hatalarına toleranslı ol ama doğru ürünü bul:
     * "menengic" → "Menengiç Kahvesi"
     * "turk kahvesi" → "Türk Kahvesi"
     * "cay" → "Çay"
   - **MANTIKLI ÇIKARIMLAR**: Soru-cevap akışında mantıklı çıkarımlar yap:
     * "2 çay 2 menengiç" → 2 adet Çay + 2 adet Menengiç Kahvesi
     * "soğuk ne var?" → Soğuk içecekler listesi
     * "öneri ver" → Popüler ürünler + özellikleri
   - **BAĞLAMSAL ANLAMA**: Konuşma bağlamını kullan:
     * Önceki mesajlardan referans al
     * Eksik bilgileri önceki konuşmalardan tamamla
     * Mantıklı devam ettir

## 11. ÇOK DİLLİ DESTEK:
   - Müşteri hangi dilde konuşuyorsa, o dilde cevap ver
   - Desteklenen diller: Türkçe (tr), İngilizce (en), Fransızca (fr), Almanca (de), Arapça (ar), İspanyolca (es)
   - Müşteri dil değiştirdiğinde, onun diline uyum sağla
   - Aynı konuşma içinde dil tutarlılığını koru
   - Dil kodları: tr=Türkçe, en=English, fr=Français, de=Deutsch, ar=العربية, es=Español
   - Müşterinin dilini tespit ettikten sonra, tüm yanıtlarını o dilde ver
   - Greeting'lerde müşterinin dilini kullan (örn: "Hello" → İngilizce devam et, "Bonjour" → Fransızca devam et, "Hola" → İspanyolca devam et)
   - Menü bilgilerini ve ürün açıklamalarını müşterinin dilinde sun

## 12. REASONING SÜRECI (ÇOK ÖNEMLİ - İÇ SESİN):
   Her müşteri mesajında şu adımları izle (içinden, müşteriye göstermeden):

   **ADIM 1 - İÇ ANALİZ**: Müşteri ne diyor? Ne istiyor gerçekten?
   - Müşterinin KELİMELERİ: [kelimeler]
   - Müşterinin NİYETİ: [sipariş/soru/öneri/şikayet]
   - BAĞLAM: [hasta mı, acele mi, kararsız mı, ruh hali ne]
   - ÖNCELİK: [en önemli ihtiyacı ne]

   **ADIM 2 - MENÜ TARAMA**: Hangi ürünler uygun?
   - Eşleşen ürünler: [menüden bulunan ürünler]
   - Özelliklere göre filtreleme: [sıcak/soğuk, kafeinli/kafeinsiz, bitki çayı vs]
   - En iyi seçenekler: [3-5 ürün]

   **ADIM 3 - KARAR**: Ne yapmalıyım?
   - Direkt sipariş mi alacağım? → Sipariş oluştur + onayla
   - Öneri mi vereceğim? → 2-3 ürün öner + özelliklerini açıkla
   - Soru mu soracağım? → Hayır, proaktif ol, direkt öner

   **ADIM 4 - CEVAP**: Nasıl söyleyeyim?
   - Ton: [samimi/neşeli/anlayışlı]
   - İçerik: [sipariş onayı/öneri/açıklama]
   - Uzunluk: [kısa 2-3 cümle]

## 13. FEW-SHOT ÖRNEKLER (GERÇEK DİYALOGLAR):

### ÖRNEK 1 - Karmaşık Sağlık Talebi:
MÜŞTERİ: "Biraz hastayım, ne önerebilirsin?"

İÇ REASONING:
- İÇ ANALİZ: Müşteri hasta → rahatlatıcı/şifalı içecek istiyor → Bitki çayları ideal
- MENÜ TARAMA: Adaçayı (boğaz ağrısına iyi), Nane Limon (rahatlatıcı), Ihlamur, Kuşburnu
- KARAR: Direkt öneri ver, 2-3 bitki çayı öner, özelliklerini kısa açıkla
- CEVAP: Samimi + anlayışlı ton, kısa

SEN (NESO): "Geçmiş olsun! Hasta olduğunuzda Adaçayı veya Nane Limon çok iyi gelir. İkisi de boğazı rahatlatır. Hangisini istersiniz?"

### ÖRNEK 2 - Çok Katmanlı İstek:
MÜŞTERİ: "Yorgunum ama aynı zamanda boğazım da ağrıyor. Ne alsam?"

İÇ REASONING:
- İÇ ANALİZ: 2 ihtiyaç var → 1) Yorgunluk (enerji) 2) Boğaz ağrısı (rahatlatıcı)
- ÖNCELİK: Boğaz ağrısı daha acil → bitki çayı öncelik
- MENÜ TARAMA: Adaçayı (rahatlatıcı + boğaz), Nane Limon (rahatlatıcı)
- İKİNCİL: Eğer kafein de isterse → Çay (hafif kafeinli)
- KARAR: Önce rahatlatıcı öner, sonra opsiyonel enerji için hafif kafeinli ekle
- CEVAP: Anlayışlı + yardımsever ton

SEN (NESO): "Geçmiş olsun! Boğazınız için Adaçayı veya Nane Limon önerebilirim, ikisi de çok rahatlatıcı. Enerjiye de ihtiyacınız varsa yanına bir Çay da ekleyebiliriz."

### ÖRNEK 3 - Belirsiz Öneri İsteği:
MÜŞTERİ: "Soğuk bir şey istiyorum ama çok tatlı olmasın."

İÇ REASONING:
- İÇ ANALİZ: Soğuk içecek + az tatlı/hafif
- MENÜ TARAMA: Limonata (ferahlatıcı, hafif asidik), Buzlu Çay (hafif), Soğuk Latte (süt bazlı ama tatlı değil)
- KARAR: 2-3 seçenek sun, özelliklerini açıkla
- CEVAP: Enerjik + yardımsever ton

SEN (NESO): "Soğuk içeceklerimizden Limonata veya Buzlu Çay harika seçenekler, ikisi de çok tatlı değil. Limonata ferahlatıcı ve hafif ekşi. Hangisini istersiniz?"

### ÖRNEK 4 - Eksik Bilgi ile Sipariş:
MÜŞTERİ: "2 kahve"

İÇ REASONING:
- İÇ ANALİZ: Sipariş veriyor ama "kahve" çok genel
- MENÜ TARAMA: Türk Kahvesi, Latte, Americano, Cappuccino, Espresso → hepsi "kahve"
- KARAR: Hangi kahve türünü istediğini anlayamıyorum → Popüler seçenekleri öner
- CEVAP: Yardımsever + net ton

SEN (NESO): "2 kahve, harika! Latte mi, Türk Kahvesi mi yoksa Americano mu istersiniz? En popüler seçeneklerimiz bunlar."

### ÖRNEK 5 - Çok Spesifik Talep:
MÜŞTERİ: "Kafeinli ama sütsüz bir şey istiyorum."

İÇ REASONING:
- İÇ ANALİZ: 2 kriter → 1) Kafeinli 2) Sütsüz
- MENÜ TARAMA: Türk Kahvesi (kafeinli+sütsüz), Espresso (kafeinli+sütsüz), Americano (kafeinli+sütsüz)
- KARAR: 3 seçenek sun, hepsi kriterlere uygun
- CEVAP: Net + proaktif ton

SEN (NESO): "Kafeinli ve sütsüz içeceklerimiz: Türk Kahvesi, Espresso veya Americano. Türk Kahvesi geleneksel ve yoğun, Americano daha hafif. Hangisini tercih edersiniz?"

### ÖRNEK 6 - Menüde Olmayan Ürün:
MÜŞTERİ: "Çikolatalı pasta var mı?"

İÇ REASONING:
- İÇ ANALİZ: Çikolatalı pasta istiyor
- MENÜ TARAMA: [Çikolatalı pasta yok]
- KARAR: Menüde yok → Alternatif öner (tatlı kategorisi)
- CEVAP: Nazik + proaktif ton, direkt alternatif sun

SEN (NESO): "Çikolatalı pasta maalesef şu an menümüzde bulunmuyor. Ama tatlı seçeneklerimizden [MENÜDEN TATLI ÖRNEK] önerebilirim!"

### ÖRNEK 7 - Greeting + Anlık Sipariş:
MÜŞTERİ: "Merhaba, 2 latte lütfen."

İÇ REASONING:
- İÇ ANALİZ: Greeting + direkt sipariş → net ve hızlı müşteri
- MENÜ TARAMA: Latte mevcut
- KARAR: Direkt sipariş al, greeting'e kısa cevap ver
- CEVAP: Samimi + hızlı ton

SEN (NESO): "Merhaba! 2 Latte hemen hazırlıyorum. Toplam [FİYAT] TL. Afiyet olsun!"

### ÖRNEK 8 - Çok Kelimeli Karmaşık İstek:
MÜŞTERİ: "Biraz üşüdüm de sıcak bir şey içsem iyi olur ama kafein istemiyorum çünkü geceleri uyuyamıyorum."

İÇ REASONING:
- İÇ ANALİZ: 3 kriter → 1) Sıcak 2) Kafeinsiz 3) Uyku dostu
- MENÜ TARAMA: Adaçayı (sıcak+kafeinsiz+rahatlatıcı), Nane Limon (sıcak+kafeinsiz), Ihlamur
- KARAR: Bitki çayları ideal → 2-3 seçenek öner
- CEVAP: Anlayışlı + samimi ton

SEN (NESO): "Sıcak ve kafeinsiz içeceklerimizden Adaçayı veya Nane Limon harika olur. İkisi de rahatlatıcı ve uyku dostu. Hangisini istersiniz?"

### ÖRNEK 9 - Ürün Özelliği Sorusu:
MÜŞTERİ: "Sütlü kahveleriniz nedir?"

İÇ REASONING:
- İÇ ANALİZ: Müşteri menüdeki sütlü kahveleri öğrenmek istiyor → Filtreleme talebi
- MENÜ TARAMA: Menüden [sütlü, kafeinli] etiketli ürünleri ara → Latte, Cappuccino, Mocha vb.
- KARAR: Tüm sütlü kahveleri listele, kısa açıklama ekle
- CEVAP: Net + bilgilendirici ton

SEN (NESO): "Sütlü kahvelerimiz: Latte, Cappuccino ve Mocha. Latte en hafif ve sütlü, Cappuccino köpüklü ve dengeli. Hangisini istersiniz?"

### ÖRNEK 10 - Sağlık Durumu (Baş Ağrısı):
MÜŞTERİ: "Baş ağrım var, ne önerebilirsin?"

İÇ REASONING:
- İÇ ANALİZ: Baş ağrısı → Kafein baş ağrısına iyi gelir
- MENÜ TARAMA: Menüden [kafeinli] ürünler → Türk Kahvesi, Espresso, Americano
- KARAR: Kafeinli içecekler öner + "kafein baş ağrısına iyi gelir" bilgisi ver
- CEVAP: Yardımsever + bilgilendirici ton

SEN (NESO): "Baş ağrınız için Türk Kahvesi veya Espresso önerebilirim. Kafein baş ağrısını hafifletmeye yardımcı olur. Hangisini istersiniz?"

### ÖRNEK 11 - Uyku Problemi:
MÜŞTERİ: "Uykum var ama bir şey içmek istiyorum."

İÇ REASONING:
- İÇ ANALİZ: Uyku problemi/uykusuzluk → Kafeinsiz + rahatlatıcı
- MENÜ TARAMA: Menüden [kafeinsiz, bitki çayı] ürünler → Adaçayı, Ihlamur, Nane Limon
- KARAR: Bitki çayları öner + "uyku dostu, rahatlatıcı" bilgisi ver
- CEVAP: Anlayışlı + samimi ton

SEN (NESO): "Uykulu olduğunuzda Adaçayı veya Ihlamur harika olur. İkisi de kafeinsiz ve rahatlatıcı, uykunuzu kaçırmaz. Hangisini istersiniz?"

### ÖRNEK 12 - Çoklu Kriter Filtresi:
MÜŞTERİ: "Kafeinli ama sütsüz soğuk bir şey var mı?"

İÇ REASONING:
- İÇ ANALİZ: 3 kriter birden → 1) Kafeinli 2) Sütsüz 3) Soğuk
- MENÜ TARAMA: Menüden [kafeinli, sütsüz, soğuk] etiketli ürünleri ara → Soğuk Americano, Buzlu Espresso
- KARAR: Kriterlere uyan ürünleri listele
- CEVAP: Net + proaktif ton

SEN (NESO): "Kafeinli, sütsüz ve soğuk içeceklerimizden Soğuk Americano var. Ferahlatıcı ve güçlü bir kahve. İster misiniz?"

## 14. KRİTİK HATALARDAN KAÇIN:
   ❌ YANLIŞ: "Sipariş almak ister misiniz?" → ✅ DOĞRU: "Hemen hazırlıyorum!"
   ❌ YANLIŞ: "Hangi kahveyi tercih edersiniz?" (çok açık) → ✅ DOĞRU: "Latte mı Türk Kahvesi mi?"
   ❌ YANLIŞ: "Menümüzde [ürün] yok. Başka bir şey?" → ✅ DOĞRU: "[Ürün] menümüzde yok. Ama [alternatif] önerebilirim!"
   ❌ YANLIŞ: "Çay önerebilirim. 25 TL." → ✅ DOĞRU: "Çay önerebilirim!" (öneri sırasında fiyat yok)
   ❌ YANLIŞ: Müşteri "hasta" deyince genel "Çay" önermek → ✅ DOĞRU: Adaçayı, Nane Limon gibi spesifik bitki çayları önermek
   ❌ YANLIŞ: "Sütlü kahveleriniz nedir?" → "Kahvelerimiz var" (belirsiz) → ✅ DOĞRU: Menüden [sütlü] etiketli kahveleri ara ve listele
   ❌ YANLIŞ: "Baş ağrım var" → "Geçmiş olsun, çay önerebilirim" (yanlış) → ✅ DOĞRU: Kafeinli içecekler öner (kafein baş ağrısına iyi gelir)
   ❌ YANLIŞ: "Uykum var" → "Kahve önerebilirim" (yanlış!) → ✅ DOĞRU: Kafeinsiz bitki çayları öner (uyku dostu)

"""

    # Add current context if available
    if context_lines:
        system_prompt += "\n# GÜNCEL SİPARİŞ DURUMU:\n"
        system_prompt += "\n".join(context_lines)
        system_prompt += "\n"
    
    # Add conversation history context to system prompt for better understanding
    if history_snapshot and len(history_snapshot) > 0:
        system_prompt += "\n# KONUŞMA GEÇMİŞİ (ÖNEMLİ - BAĞLAM İÇİN KULLAN):\n"
        system_prompt += "Aşağıdaki konuşma geçmişi müşterinin önceki mesajlarını ve senin cevaplarını içerir.\n"
        system_prompt += "BU GEÇMİŞİ AKTİF OLARAK KULLAN:\n"
        system_prompt += "- Önceki siparişleri hatırla ve referans ver\n"
        system_prompt += "- Müşterinin tercihlerini öğren (sıcak/soğuk, kafeinli/kafeinsiz vb.)\n"
        system_prompt += "- Önceki soruları ve cevapları hatırla, tekrar sorulmasını önle\n"
        system_prompt += "- Konuşma akışını takip et, mantıklı devam ettir\n"
        system_prompt += "- Müşterinin ruh halini ve niyetini anlamak için kullan\n"
        system_prompt += "\nSon 5 mesaj (en yeni en altta):\n"
        recent_history = history_snapshot[-5:] if len(history_snapshot) > 5 else history_snapshot
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]  # İlk 200 karakter
            if role == "user":
                system_prompt += f"  MÜŞTERİ: {content}\n"
            elif role == "assistant":
                system_prompt += f"  SEN (NESO): {content}\n"
        system_prompt += "\n"
    
    # Add detected language to system prompt
    lang_names = {
        "tr": "Türkçe",
        "en": "English",
        "fr": "Français",
        "de": "Deutsch",
        "ar": "العربية",
        "es": "Español"
    }
    detected_lang_name = lang_names.get(detected_lang, "Türkçe")
    system_prompt += f"\n# DİL BİLGİSİ:\n"
    system_prompt += f"Müşteri şu anda {detected_lang_name} ({detected_lang}) dilinde konuşuyor.\n"
    system_prompt += f"TÜM yanıtlarını MUTLAKA {detected_lang_name} dilinde ver. Menü açıklamaları, ürün önerileri, sipariş onayları - HER ŞEY {detected_lang_name} dilinde olmalı.\n"

    system_parts = [system_prompt]

    # Tenant ID'yi al (sube_id'den)
    tenant_id = None
    if payload.sube_id:
        sube_row = await db.fetch_one(
            "SELECT isletme_id FROM subeler WHERE id = :id",
            {"id": payload.sube_id}
        )
        if sube_row:
            sube_dict = dict(sube_row) if hasattr(sube_row, 'keys') else sube_row
            tenant_id = sube_dict.get("isletme_id")
    
    provider = await get_llm_provider(tenant_id=tenant_id, assistant_type="customer")
    messages_for_llm: List[Dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
    messages_for_llm.extend(history_snapshot)
    messages_for_llm.append({"role": "user", "content": text})

    reply_text = ""
    
    # ÖNEMLİ: Parse işlemi başarılı olduysa (aggregated var), LLM'e sormadan direkt default_reply kullan
    # Çünkü parse işlemi zaten ürünlerin menüde olduğunu doğruladı
    # Varyasyon eksikse varsayılan varyasyon seçiliyor, bu yüzden her zaman sipariş oluşturuluyor
    # ANCAK: Eğer missing_variations_in_cart varsa, LLM'e sormalıyız
    missing_variations_in_scope = 'missing_variations_in_cart' in locals() and missing_variations_in_cart
    
    if aggregated and not missing_variations_in_scope:
        import logging
        if order_summary:
            logging.info(f"[ORDER] Parse successful, order created (#{order_summary['id']}), using default_reply instead of LLM")
            reply_text = default_reply or f"Harika! {masa} masası için siparişinizi oluşturdum. Toplam {order_summary['tutar']:.2f} TL. Afiyet olsun!"
        elif shortages:
            logging.info(f"[ORDER] Parse successful but stock shortage, using default_reply instead of LLM")
            reply_text = default_reply or "Üzgünüm, stok yetersiz. Menümüzdeki diğer ürünlerden önerebilirim!"
        else:
            logging.info(f"[ORDER] Parse successful but no order/shortage, using default_reply instead of LLM")
            reply_text = default_reply or "Size yardimci olmaya hazirim. Menuden bir sey onerebilirim!"
    elif force_default_reply and default_reply:
        reply_text = default_reply
    else:
        # Parse başarısız veya sipariş oluşturulmadı, LLM'e sor
        try:
            import logging
            logging.info(f"[LLM] Calling LLM provider for text: '{text[:50]}...'")
            
            # OpenAIProvider tuple döndürür (text, usage_info), diğerleri string
            result = await provider.chat(messages_for_llm)
            if isinstance(result, tuple):
                reply_text, usage_info = result
            else:
                reply_text, usage_info = result, None
            
            # API kullanımını logla (tenant_id varsa)
            if usage_info and tenant_id:
                from ..services.api_usage_tracker import log_api_usage
                customization_row = await db.fetch_one(
                    "SELECT openai_model FROM tenant_customizations WHERE isletme_id = :id",
                    {"id": tenant_id}
                )
                model = "gpt-4o-mini"
                if customization_row:
                    customization_dict = dict(customization_row) if hasattr(customization_row, 'keys') else customization_row
                    model = customization_dict.get("openai_model") or "gpt-4o-mini"
                
                await log_api_usage(
                    isletme_id=tenant_id,
                    api_type="openai",
                    model=model,
                    endpoint="/v1/chat/completions",
                    prompt_tokens=usage_info.get("prompt_tokens", 0),
                    completion_tokens=usage_info.get("completion_tokens", 0),
                    total_tokens=usage_info.get("total_tokens", 0),
                    cost_usd=usage_info.get("cost_usd", 0.0),
                    response_time_ms=usage_info.get("response_time_ms"),
                    status="success",
                )
            
            logging.info(f"[LLM] Received reply (length: {len(reply_text) if reply_text else 0})")
            
            if not reply_text or len(reply_text.strip()) == 0:
                logging.warning("[LLM] Empty reply from LLM, using default")
        except Exception as e:
            import logging
            logging.error(f"[LLM] Error calling LLM provider: {e}", exc_info=True)
            reply_text = ""

        if not reply_text or len(reply_text.strip()) == 0:
            reply_text = default_reply or "Size yardimci olmaya hazirim. Menuden bir sey onerebilirim!"

    # Eğer reply'de greeting varsa ve not_matched sadece greeting kelimeleri içeriyorsa, temizle
    reply_lower = reply_text.lower()
    if any(g in reply_lower for g in ["merhaba", "hoş geldin", "hos geldin"]) and len(not_matched) > 0:
        greeting_in_reply = any(g in reply_lower for g in ["merhaba", "hoş geldiniz", "hos geldiniz"])
        if greeting_in_reply:
            # Greeting kelimelerini not_matched'den temizle
            not_matched = [n for n in not_matched if _tokenize(n.lower()) not in ignore_tokens]
            if len(not_matched) == 0:
                not_matched = None

    _append_session(conversation_id, "user", text)
    _append_session(conversation_id, "assistant", reply_text)

    # Parse başarısız olduğunda (aggregated yok) not_matched uyarısını gösterme
    # Kullanıcı deneyimi için sadece LLM'in cevabını göster, teknik detayları gösterme
    final_not_matched = None
    if aggregated and order_summary:
        # Parse başarılı, sipariş oluşturuldu - sadece gerçekten bulunamayanlar varsa göster
        if not_matched and len(not_matched) > 0:
            final_not_matched = not_matched
    else:
        # Parse başarısız olduğunda (aggregated yok) not_matched'i kesinlikle None yap
        # Çünkü LLM zaten ürünün menüde olmadığını açıkladı, teknik detay göstermeye gerek yok
        final_not_matched = None

    # Stok yetersiz durumunda shortages gönder, ama parse başarılı ve default_reply kullanıldıysa
    # frontend'e göndermeye gerek yok çünkü default_reply zaten stok bilgisini içeriyor
    # Sadece sipariş oluşturuldu ama kısmi stok yetersizliği varsa gönder
    final_shortages = None
    if aggregated and order_summary and shortages:
        # Sipariş oluşturuldu ama bazı ürünlerde stok yetersiz - gönder (kısmi stok eksikliği)
        final_shortages = shortages
    elif aggregated and shortages and not order_summary:
        # Parse başarılı ama stok yetersiz - default_reply zaten stok bilgisini içeriyor, gönderme
        final_shortages = None
    
    context_lines: List[str] = []

    if auto_selected_variations:
        for auto_urun, auto_var in auto_selected_variations:
            context_lines.append(
                f"KULLANICI varyasyon belirtmediği için '{auto_urun}' ürünü varsayılan '{auto_var}' seçeneği ile siparişe eklenecek."
            )

    return await _build_chat_response(
        reply=reply_text,
        order=order_summary,
        shortages=final_shortages,
        not_matched=final_not_matched,
        suggestions=suggestions,
        conversation_id=conversation_id,
        detected_language=detected_lang,
        tenant_id=tenant_id,
    )


# ---- Asistan Ayarları ----
class VoicePresetOut(BaseModel):
    id: str
    provider: str
    label: str
    tone: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    enabled: bool = True


class AssistantSettingsIn(BaseModel):
    tts_voice_id: Optional[str] = None
    tts_speech_rate: Optional[float] = 1.0  # 0.25 - 4.0 (1.0 = normal)
    tts_provider: Optional[str] = "system"  # "system", "google", "azure", "aws", "openai"


class AssistantSettingsOut(BaseModel):
    tts_voice_id: str
    tts_speech_rate: float
    tts_provider: str
    available_voices: List[VoicePresetOut]
    supported_providers: List[str]


def _coerce_str(value: Any, default: Optional[str] = None) -> Optional[str]:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            if value.startswith('"') and value.endswith('"'):
                return json.loads(value)
        except Exception:
            pass
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return str(value.get("value", default))
    return default


def _coerce_float(value: Any, default: float = 1.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            if value.startswith('"') and value.endswith('"'):
                return float(json.loads(value))
            return float(value)
        except Exception:
            return default
    if isinstance(value, dict):
        try:
            return float(value.get("value", default))
        except Exception:
            return default
    return default


@router.get("/settings", response_model=AssistantSettingsOut)
async def get_assistant_settings(_: Dict[str, Any] = Depends(get_current_user)):
    """Asistan TTS ayarlarını getir."""
    try:
        rows = await db.fetch_all(
            """
            SELECT key, value
              FROM app_settings
             WHERE key IN (
                 'assistant_tts_voice_id',
                 'assistant_tts_speech_rate',
                 'assistant_tts_provider',
                 'assistant_tts_voice_gender' -- legacy
             )
            """
        )
        settings_dict = {r["key"]: r["value"] for r in rows}

        provider_val = _coerce_str(settings_dict.get("assistant_tts_provider"), "system")
        provider = (provider_val or "system").lower()
        valid_providers = ["system", "google", "azure", "aws", "openai"]
        if provider not in valid_providers:
            provider = "system"

        # Eğer provider "system" ise ama farklı servis anahtarlarımız varsa daha kaliteli sağlayıcıyı varsayılan yap
        if provider == "system":
            if settings.GOOGLE_TTS_API_KEY:
                provider = "google"
            elif settings.OPENAI_API_KEY:
                provider = "openai"
            elif settings.AZURE_SPEECH_KEY:
                provider = "azure"

        rate = _coerce_float(settings_dict.get("assistant_tts_speech_rate"), 1.0)
        voice_id = _coerce_str(settings_dict.get("assistant_tts_voice_id"))

        # Eski sürümden kalan gender bilgisini sese map'le
        if not voice_id:
            legacy_gender = _coerce_str(settings_dict.get("assistant_tts_voice_gender"), "female")
            preset_candidates = get_voice_presets_by_provider(provider) or list_voice_presets()
            if legacy_gender and preset_candidates:
                legacy_gender = legacy_gender.lower()
                # Gender'a göre uygun preset bulmaya çalış
                gender_pref = "female" if legacy_gender == "female" else "male"
                for preset in preset_candidates:
                    voice_params = preset.get("voice") or {}
                    ssml_gender = str(voice_params.get("ssmlGender", "")).lower()
                    if ssml_gender and gender_pref in ssml_gender:
                        voice_id = preset["id"]
                        break

        preset = get_voice_preset(voice_id)
        if not preset or preset["provider"] != provider:
            preset = get_default_voice_for_provider(provider)
            voice_id = preset["id"]
            provider = preset["provider"]

        available_presets = list_voice_presets()
        available_voice_out = [
            VoicePresetOut(
                id=p["id"],
                provider=p["provider"],
                label=p.get("label", p["id"]),
                tone=p.get("tone"),
                description=p.get("description"),
                language=p.get("language"),
                enabled=_provider_enabled(p["provider"]),
            )
            for p in available_presets
        ]

        configured_providers = [prov for prov in valid_providers if _provider_enabled(prov)]

        return AssistantSettingsOut(
            tts_voice_id=voice_id,
            tts_speech_rate=rate,
            tts_provider=provider,
            available_voices=available_voice_out,
            supported_providers=configured_providers,
        )
    except Exception as e:
        logging.warning(f"Error loading assistant settings: {e}", exc_info=True)
        preset = get_default_voice_for_provider(None)
        fallback_provider = preset["provider"]
        configured_providers = [prov for prov in ["system", "google", "azure", "aws", "openai"] if _provider_enabled(prov)]
        available_voice_out = [
            VoicePresetOut(
                id=p["id"],
                provider=p["provider"],
                label=p.get("label", p["id"]),
                tone=p.get("tone"),
                description=p.get("description"),
                language=p.get("language"),
                enabled=_provider_enabled(p["provider"]),
            )
            for p in list_voice_presets()
        ]
        return AssistantSettingsOut(
            tts_voice_id=preset["id"],
            tts_speech_rate=1.0,
            tts_provider=fallback_provider,
            available_voices=available_voice_out,
            supported_providers=configured_providers,
        )


@router.put("/settings")
async def update_assistant_settings(
    payload: AssistantSettingsIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Asistan TTS ayarlarını güncelle."""
    
    def json_dumps(v: Any) -> str:
        return json.dumps(v, ensure_ascii=False)
    
    async with db.transaction():
        valid_providers = ["system", "google", "azure", "aws", "openai"]
        provider_value = (payload.tts_provider or "system").lower()
        if provider_value not in valid_providers:
            provider_value = "system"

        preset = get_voice_preset(payload.tts_voice_id)
        if not preset or preset["provider"] != provider_value:
            preset = get_default_voice_for_provider(provider_value)

        voice_id_value = preset["id"]
        provider_value = preset["provider"]

        rate_value = float(payload.tts_speech_rate or 1.0)
        rate_value = max(0.25, min(4.0, rate_value))

        await db.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:k, CAST(:v AS JSONB), NOW())
            ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value,
                   updated_at = EXCLUDED.updated_at
            """,
            {
                "k": "assistant_tts_voice_id",
                "v": json_dumps(voice_id_value),
            },
        )

        await db.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:k, CAST(:v AS JSONB), NOW())
            ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value,
                   updated_at = EXCLUDED.updated_at
            """,
            {
                "k": "assistant_tts_speech_rate",
                "v": json_dumps(rate_value),
            },
        )

        await db.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:k, CAST(:v AS JSONB), NOW())
            ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value,
                   updated_at = EXCLUDED.updated_at
            """,
            {
                "k": "assistant_tts_provider",
                "v": json_dumps(provider_value),
            },
        )

        await db.execute("DELETE FROM app_settings WHERE key = 'assistant_tts_voice_gender'")

        logging.info(
            "[ASSISTANT_SETTINGS] Updated -> voice=%s provider=%s rate=%.2f",
            voice_id_value,
            provider_value,
            rate_value,
        )

    return {"status": "ok"}


async def _handle_structured_intent(
    *,
    intent_result: IntentResult,
    conversation_id: str,
    sube_id: int,
    masa: Optional[str],
    detected_language: str,
    original_text: str,
    tenant_id: Optional[int] = None,
) -> Optional[ChatResponse]:
    intent = intent_result.intent
    if not intent:
        return None

    masa_from_text = intent_result.entities.get("masa")
    if not masa and masa_from_text:
        masa = masa_from_text

    await context_manager.update(conversation_id, sube_id=sube_id, masa=masa)
    
    # Get tenant_id from sube_id if not provided
    if tenant_id is None:
        try:
            sube_row = await db.fetch_one(
                "SELECT isletme_id FROM subeler WHERE id = :id",
                {"id": sube_id}
            )
            if sube_row:
                sube_dict = dict(sube_row) if hasattr(sube_row, 'keys') else sube_row
                tenant_id = sube_dict.get("isletme_id")
        except Exception as e:
            logging.warning(f"[STRUCTURED_INTENT] Failed to get tenant_id from sube_id={sube_id}: {e}")
    
    keywords_raw = intent_result.entities.get("keywords", "")
    keyword_list = [kw for kw in keywords_raw.split(",") if kw]

    try:
        if intent == "stok_durumu":
            menu_items = await _load_menu_details(sube_id)
            menu_names = [item["ad"] for item in menu_items]
            product_name: Optional[str] = None
            for kw in keyword_list:
                match = closest_match(kw, menu_names, threshold=0.55)
                if match:
                    product_name = match[0]
                    break
            if not product_name:
                reply = "Hangi ürünün stok durumunu kontrol etmemi istersiniz?"
                _append_session(conversation_id, "user", original_text)
                _append_session(conversation_id, "assistant", reply)
                await context_manager.set_last_intent(conversation_id, intent)
                return await _build_chat_response(
                    reply=reply,
                    conversation_id=conversation_id,
                    detected_language=detected_language,
                    tenant_id=tenant_id,
                )

            request = DataQueryRequest(
                intent="stok_durumu",
                entities={"sube_id": sube_id},
                filters={"ad": product_name},
                limit=1,
            )
            result = await resolve_data_query(db, request)
            rows = result.rows
            if not rows:
                reply = f"{product_name} için stok kaydı bulamadım."
            else:
                row = rows[0]
                stok = row.get("stok_miktari", 0)
                birim = (row.get("stok_birim") or "").strip()
                reply = f"{product_name} için stokta {stok} {birim or ''} görünüyor."
                warnings = evaluate_rules(intent, rows)
                if warnings:
                    reply += " " + " ".join(warnings)
            _append_session(conversation_id, "user", original_text)
            _append_session(conversation_id, "assistant", reply)
            await context_manager.set_last_intent(conversation_id, intent)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                detected_language=detected_language,
                tenant_id=tenant_id,
            )

        if intent == "menu_liste":
            request = DataQueryRequest(
                intent="menu_liste",
                entities={"sube_id": sube_id},
                limit=8,
            )
            result = await resolve_data_query(db, request)
            rows = result.rows
            if not rows:
                reply = "Menüde listelenen ürün bulamadım."
                suggestions = None
            else:
                plain_ascii = _tokenize(original_text)
                wants_dessert = any(keyword in plain_ascii for keyword in DESSERT_KEYWORDS)
                dessert_rows: List[Dict[str, Any]] = []
                available_rows: List[Dict[str, Any]] = []
                for row in rows:
                    stok_value = row.get("stok_miktari")
                    try:
                        stok_qty = float(stok_value) if stok_value is not None else None
                    except (TypeError, ValueError):
                        stok_qty = None
                    if stok_qty is None or stok_qty > 0:
                        available_rows.append(row)
                if wants_dessert:
                    for row in available_rows or rows:
                        name_raw = row.get("ad") or row.get("urun_adi") or ""
                        category_raw = row.get("kategori") or ""
                        name_norm = _tokenize(name_raw)
                        category_norm = _tokenize(category_raw)
                        dessert_hit = any(keyword in name_norm for keyword in DESSERT_KEYWORDS) or any(
                            keyword in category_norm for keyword in DESSERT_KEYWORDS
                        )
                        drink_hit = any(keyword in name_norm for keyword in DRINK_KEYWORDS) or any(
                            keyword in category_norm for keyword in DRINK_KEYWORDS
                        )
                        if dessert_hit and not drink_hit:
                            dessert_rows.append(row)
                target_rows = dessert_rows if dessert_rows else (available_rows or rows)

                def _display_name(row: Dict[str, Any]) -> str:
                    base_name = row.get("ad") or row.get("urun_adi") or ""
                    stok_value = row.get("stok_miktari")
                    stok_birim = (row.get("stok_birim") or "").strip()
                    stok_min = row.get("stok_min")
                    stok_kritik = row.get("stok_kritik")
                    try:
                        stok_qty = float(stok_value) if stok_value is not None else None
                    except (TypeError, ValueError):
                        stok_qty = None

                    has_real_stock_info = False
                    if stok_value is not None:
                        if stok_birim or (stok_min not in (None, 0)) or (stok_kritik not in (None, 0)):
                            has_real_stock_info = True

                    if not has_real_stock_info:
                        stok_qty = None

                    if stok_qty is None:
                        return base_name
                    if stok_qty <= 0:
                        return f"{base_name} (stokta yok)"
                    if stok_kritik == 1 or stok_qty <= max(LOW_STOCK_THRESHOLD, float(stok_min or 0)):
                        qty_display = int(stok_qty) if abs(stok_qty - int(stok_qty)) < 0.01 else round(stok_qty, 1)
                        return f"{base_name} (son {qty_display} {(stok_birim or 'adet')})"
                    return base_name

                target_names = [
                    _display_name(row)
                    for row in target_rows
                    if row.get("ad") or row.get("urun_adi")
                ]
                fallback_names = [
                    _display_name(row)
                    for row in rows
                    if row.get("ad") or row.get("urun_adi")
                ]
                suggestions = target_names[:5] if target_names else fallback_names[:5]
                if dessert_rows:
                    reply = "Tatlı vitrinimizde " + ", ".join(suggestions) + " var. Hangisini denemek istersiniz?"
                else:
                    reply = "Menümüzde şu ürünler öne çıkıyor: " + ", ".join(suggestions) + "."
            _append_session(conversation_id, "user", original_text)
            _append_session(conversation_id, "assistant", reply)
            await context_manager.set_last_intent(conversation_id, intent)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                suggestions=suggestions,
                detected_language=detected_language,
                tenant_id=tenant_id,
            )

        if intent == "aktif_adisyonlar":
            if not masa:
                reply = "Hangi masanın hesabını kontrol etmemi istersiniz?"
                _append_session(conversation_id, "user", original_text)
                _append_session(conversation_id, "assistant", reply)
                await context_manager.set_last_intent(conversation_id, intent)
                return await _build_chat_response(
                    reply=reply,
                    conversation_id=conversation_id,
                    detected_language=detected_language,
                    tenant_id=tenant_id,
                )

            request = DataQueryRequest(
                intent="aktif_adisyonlar",
                entities={"sube_id": sube_id},
                filters={"masa": masa},
                limit=1,
            )
            result = await resolve_data_query(db, request)
            rows = result.rows
            if not rows:
                reply = f"{masa} masası için açık adisyon bulunmuyor."
            else:
                row = rows[0]
                bakiye = float(row.get("bakiye", 0) or 0)
                bekleyen = float(row.get("bekleyen_tutar", 0) or 0)
                reply = f"{masa} masasında ödenmemiş bakiye {bakiye:.2f} ₺. Bekleyen sipariş tutarı {bekleyen:.2f} ₺."
                warnings = evaluate_rules(intent, rows)
                if warnings:
                    reply += " " + " ".join(warnings)
            _append_session(conversation_id, "user", original_text)
            _append_session(conversation_id, "assistant", reply)
            await context_manager.set_last_intent(conversation_id, intent)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                detected_language=detected_language,
                tenant_id=tenant_id,
            )

        if intent == "satis_ozet":
            request = DataQueryRequest(
                intent="satis_ozet",
                entities={"sube_id": sube_id},
                limit=7,
            )
            result = await resolve_data_query(db, request)
            rows = result.rows
            if not rows:
                reply = "Henüz kayıtlı satış verisi yok gibi görünüyor."
            else:
                toplam = sum(float(row.get("toplam_ciro", 0) or 0) for row in rows)
                toplam_siparis = sum(int(row.get("siparis_adedi", 0) or 0) for row in rows)
                reply = f"Son günlerde toplam {toplam_siparis} sipariş ile {toplam:.2f} ₺ ciro oluşmuş."
            _append_session(conversation_id, "user", original_text)
            _append_session(conversation_id, "assistant", reply)
            await context_manager.set_last_intent(conversation_id, intent)
            return await _build_chat_response(
                reply=reply,
                conversation_id=conversation_id,
                detected_language=detected_language,
                tenant_id=tenant_id,
            )

    except DataAccessError as exc:
        logger.warning("Structured intent data erişimi başarısız: %s", exc)
    except Exception:
        logger.exception("Structured intent işlenirken hata oluştu")

    return None


async def _load_recipe_map(sube_id: int) -> Tuple[Dict[str, List[str]], Dict[str, List[Dict[str, Any]]]]:
    rows = await db.fetch_all(
        """
        SELECT urun, stok, miktar, birim
        FROM receteler
        WHERE sube_id = :sid
        """,
        {"sid": sube_id},
    )
    recipe_norm_map: Dict[str, List[str]] = defaultdict(list)
    recipe_detail_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        menu_key = normalize_name(row["urun"])
        ingredient_name = (row["stok"] or "").strip()
        ingredient_key = normalize_name(ingredient_name)
        if ingredient_key:
            recipe_norm_map[menu_key].append(ingredient_key)
        if ingredient_name:
            detail: Dict[str, Any] = {"ad": ingredient_name}
            if "miktar" in row.keys() and row["miktar"] is not None:
                detail["miktar"] = row["miktar"]
            if "birim" in row.keys() and row["birim"]:
                detail["birim"] = row["birim"]
            recipe_detail_map[menu_key].append(detail)
    return recipe_norm_map, recipe_detail_map

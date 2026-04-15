#!/usr/bin/env python3
"""
Fıstık Cafe demo işletmesi için API yapılandırması ve asistanları etkinleştirme scripti.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Backend dizinine ekle
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from databases import Database
from app.core.config import settings

load_dotenv(backend_dir / ".env")

# API Key'i environment variable'dan al veya kullanıcıdan iste
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("⚠️  OPENAI_API_KEY environment variable bulunamadı.")
    print("   .env dosyasına OPENAI_API_KEY=sk-... ekleyin veya aşağıya girin:")
    api_key_input = input("OpenAI API Key (Enter to skip): ").strip()
    if api_key_input:
        OPENAI_API_KEY = api_key_input
    else:
        print("⚠️  API key girilmedi. Asistanlar kural tabanlı modda çalışacak.")
        OPENAI_API_KEY = None

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def setup_fistik_cafe():
    """Fıstık Cafe için API yapılandırması ve asistanları etkinleştir"""
    db_url = settings.DATABASE_URL
    db = Database(db_url)
    await db.connect()

    try:
        print("=" * 60)
        print("Fıstık Cafe Demo İşletmesi Yapılandırması")
        print("=" * 60)
        
        # 1. Fıstık Cafe işletmesini bul veya oluştur
        print("\n1. İşletme kontrolü...")
        isletme = await db.fetch_one(
            """
            SELECT id, ad, aktif
            FROM isletmeler
            WHERE LOWER(ad) LIKE '%fıstık%' OR LOWER(ad) LIKE '%fistik%' OR id = 1
            ORDER BY id ASC
            LIMIT 1
            """
        )
        
        if not isletme:
            print("   Fıstık Cafe işletmesi bulunamadı. Oluşturuluyor...")
            isletme = await db.fetch_one(
                """
                INSERT INTO isletmeler (ad, aktif)
                VALUES ('Fıstık Cafe', TRUE)
                RETURNING id, ad, aktif
                """
            )
            print(f"   ✓ İşletme oluşturuldu: ID={isletme['id']}, Ad={isletme['ad']}")
        else:
            isletme_dict = dict(isletme) if hasattr(isletme, 'keys') else isletme
            isletme_id = isletme_dict.get('id') if isinstance(isletme_dict, dict) else getattr(isletme, 'id', None)
            isletme_ad = isletme_dict.get('ad') if isinstance(isletme_dict, dict) else getattr(isletme, 'ad', 'Bilinmeyen')
            print(f"   ✓ İşletme bulundu: ID={isletme_id}, Ad={isletme_ad}")
            isletme = {"id": isletme_id, "ad": isletme_ad}
        
        isletme_id = isletme["id"]
        
        # 2. Assistant kolonlarının varlığını kontrol et ve ekle
        print("\n2. Assistant kolonları kontrol ediliyor...")
        assistant_columns = [
            "customer_assistant_openai_api_key",
            "customer_assistant_openai_model",
            "customer_assistant_tts_voice_id",
            "customer_assistant_tts_speech_rate",
            "customer_assistant_tts_provider",
            "business_assistant_openai_api_key",
            "business_assistant_openai_model",
            "business_assistant_tts_voice_id",
            "business_assistant_tts_speech_rate",
            "business_assistant_tts_provider",
        ]
        
        for col in assistant_columns:
            try:
                if "api_key" in col:
                    await db.execute(f"ALTER TABLE tenant_customizations ADD COLUMN IF NOT EXISTS {col} TEXT;")
                elif "model" in col:
                    await db.execute(f"ALTER TABLE tenant_customizations ADD COLUMN IF NOT EXISTS {col} TEXT DEFAULT 'gpt-4o-mini';")
                elif "speech_rate" in col:
                    await db.execute(f"ALTER TABLE tenant_customizations ADD COLUMN IF NOT EXISTS {col} NUMERIC(3,2) DEFAULT 1.0;")
                elif "provider" in col:
                    await db.execute(f"ALTER TABLE tenant_customizations ADD COLUMN IF NOT EXISTS {col} TEXT DEFAULT 'system';")
                else:
                    await db.execute(f"ALTER TABLE tenant_customizations ADD COLUMN IF NOT EXISTS {col} TEXT;")
                print(f"   ✓ Kolon kontrol edildi: {col}")
            except Exception as e:
                print(f"   ⚠️  Kolon eklenirken hata (muhtemelen zaten var): {col} - {e}")
        
        # 3. Tenant customization kaydını bul veya oluştur
        print("\n3. Özelleştirme kaydı kontrol ediliyor...")
        customization = await db.fetch_one(
            """
            SELECT id FROM tenant_customizations WHERE isletme_id = :id
            """,
            {"id": isletme_id}
        )
        
        if not customization:
            print("   Özelleştirme kaydı oluşturuluyor...")
            await db.execute(
                """
                INSERT INTO tenant_customizations (
                    isletme_id, app_name, domain, primary_color, secondary_color
                )
                VALUES (
                    :isletme_id, 'Fıstık Cafe', 'fistikkafe', '#00c67f', '#00e699'
                )
                """,
                {"isletme_id": isletme_id}
            )
            print("   ✓ Özelleştirme kaydı oluşturuldu")
        else:
            print("   ✓ Özelleştirme kaydı mevcut")
        
        # 4. API key'leri ve asistan ayarlarını güncelle
        print("\n4. API key'leri ve asistan ayarları güncelleniyor...")
        
        update_fields = []
        update_values = {"isletme_id": isletme_id}
        
        if OPENAI_API_KEY:
            # Genel API key (fallback için)
            update_fields.append("openai_api_key = :openai_api_key")
            update_fields.append("openai_model = :openai_model")
            update_values["openai_api_key"] = OPENAI_API_KEY
            update_values["openai_model"] = OPENAI_MODEL
            
            # Müşteri asistanı API key
            update_fields.append("customer_assistant_openai_api_key = :customer_assistant_openai_api_key")
            update_fields.append("customer_assistant_openai_model = :customer_assistant_openai_model")
            update_fields.append("customer_assistant_tts_provider = :customer_assistant_tts_provider")
            update_values["customer_assistant_openai_api_key"] = OPENAI_API_KEY
            update_values["customer_assistant_openai_model"] = OPENAI_MODEL
            update_values["customer_assistant_tts_provider"] = "system"
            
            # İşletme asistanı API key
            update_fields.append("business_assistant_openai_api_key = :business_assistant_openai_api_key")
            update_fields.append("business_assistant_openai_model = :business_assistant_openai_model")
            update_fields.append("business_assistant_tts_provider = :business_assistant_tts_provider")
            update_values["business_assistant_openai_api_key"] = OPENAI_API_KEY
            update_values["business_assistant_openai_model"] = OPENAI_MODEL
            update_values["business_assistant_tts_provider"] = "system"
            
            print(f"   ✓ API key'ler yapılandırıldı (Model: {OPENAI_MODEL})")
            print(f"   ✓ Müşteri asistanı etkinleştirildi")
            print(f"   ✓ İşletme asistanı etkinleştirildi")
        else:
            print("   ⚠️  API key girilmedi. Asistanlar kural tabanlı modda çalışacak.")
            # Yine de kolonları NULL olarak ayarla
            update_fields.append("openai_api_key = NULL")
            update_fields.append("customer_assistant_openai_api_key = NULL")
            update_fields.append("business_assistant_openai_api_key = NULL")
        
        if update_fields:
            query = f"""
                UPDATE tenant_customizations
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE isletme_id = :isletme_id
            """
            await db.execute(query, update_values)
            print("   ✓ Güncelleme tamamlandı")
        
        # 5. Şube kontrolü (varsa)
        print("\n5. Şube kontrolü...")
        sube = await db.fetch_one(
            """
            SELECT id, ad FROM subeler WHERE isletme_id = :id AND aktif = TRUE LIMIT 1
            """,
            {"id": isletme_id}
        )
        if sube:
            sube_dict = dict(sube) if hasattr(sube, 'keys') else sube
            print(f"   ✓ Şube mevcut: {sube_dict.get('ad', 'Bilinmeyen')}")
        else:
            print("   ⚠️  Aktif şube bulunamadı. Şube oluşturuluyor...")
            sube = await db.fetch_one(
                """
                INSERT INTO subeler (isletme_id, ad, aktif)
                VALUES (:isletme_id, 'Merkez Şube', TRUE)
                RETURNING id, ad
                """,
                {"isletme_id": isletme_id}
            )
            print(f"   ✓ Şube oluşturuldu: {sube['ad']}")
        
        # 6. Özet
        print("\n" + "=" * 60)
        print("Yapılandırma Tamamlandı!")
        print("=" * 60)
        print(f"İşletme ID: {isletme_id}")
        print(f"İşletme Adı: {isletme['ad']}")
        if OPENAI_API_KEY:
            print(f"API Key: {'*' * 20}...{OPENAI_API_KEY[-4:]}")
            print(f"Model: {OPENAI_MODEL}")
            print("✓ Müşteri Asistanı: Etkin")
            print("✓ İşletme Asistanı: Etkin")
        else:
            print("⚠️  API Key: Girilmedi (Kural tabanlı mod)")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(setup_fistik_cafe())





#!/usr/bin/env python3
"""
Relax admin kullanıcısının tenant_id'sini düzelt
"""
import asyncio
from app.db.database import db
from app.core.config import settings

async def fix_relax_admin():
    """Relax admin kullanıcısının tenant_id'sini 4 (Relax Cafe) olarak ayarla"""
    await db.connect()
    
    try:
        # Relax Cafe'nin ID'sini kontrol et
        relax_tenant = await db.fetch_one(
            "SELECT id FROM isletmeler WHERE ad ILIKE '%relax%' ORDER BY id LIMIT 1",
        )
        
        if not relax_tenant:
            print("[ERROR] Relax Cafe bulunamadi!")
            return
        
        tenant_id = relax_tenant["id"]
        print(f"[OK] Relax Cafe bulundu: ID = {tenant_id}")
        
        # Relax admin kullanıcısını bul
        relax_user = await db.fetch_one(
            "SELECT id, username, tenant_id FROM users WHERE username = 'relax'",
        )
        
        if not relax_user:
            print("[ERROR] Relax admin kullanicisi bulunamadi!")
            return
        
        # Dict'e çevir
        relax_user_dict = dict(relax_user) if hasattr(relax_user, 'keys') else relax_user
        current_tenant_id = relax_user_dict.get("tenant_id") if isinstance(relax_user_dict, dict) else getattr(relax_user, "tenant_id", None)
        user_id = relax_user_dict.get("id") if isinstance(relax_user_dict, dict) else getattr(relax_user, "id", None)
        print(f"[OK] Relax admin bulundu: ID = {user_id}, mevcut tenant_id = {current_tenant_id}")
        
        if current_tenant_id == tenant_id:
            print(f"[OK] Relax admin zaten dogru tenant_id'ye sahip: {tenant_id}")
            return
        
        # Tenant_id'yi güncelle
        await db.execute(
            "UPDATE users SET tenant_id = :tid WHERE username = 'relax'",
            {"tid": tenant_id}
        )
        
        print(f"[SUCCESS] Relax admin kullanicisinin tenant_id'si {tenant_id} olarak guncellendi!")
        
        # Doğrula
        updated_user = await db.fetch_one(
            "SELECT id, username, tenant_id FROM users WHERE username = 'relax'",
        )
        print(f"[OK] Dogrulama: tenant_id = {updated_user.get('tenant_id')}")
        
    except Exception as e:
        print(f"[ERROR] Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(fix_relax_admin())


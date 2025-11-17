from databases import Database
from pathlib import Path
import logging

# Bu dosya temel tabloları güvenli şekilde oluşturur (IF NOT EXISTS/IF NOT EXISTS column)
# Mevcut şemalara zarar vermeden çok-şubeli ve çok-tenant kurulumunu destekler.

EXT_UNACCENT = """
CREATE EXTENSION IF NOT EXISTS unaccent;
"""

CREATE_ISLETMELER = """
CREATE TABLE IF NOT EXISTS isletmeler (
    id BIGSERIAL PRIMARY KEY,
    ad TEXT NOT NULL,
    vergi_no TEXT,
    telefon TEXT,
    aktif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_SUBELER = """
CREATE TABLE IF NOT EXISTS subeler (
    id BIGSERIAL PRIMARY KEY,
    isletme_id BIGINT REFERENCES isletmeler(id) ON DELETE CASCADE,
    ad TEXT NOT NULL,
    adres TEXT,
    telefon TEXT,
    aktif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    sifre_hash TEXT,
    role TEXT,
    tenant_id BIGINT REFERENCES isletmeler(id) ON DELETE SET NULL,
    aktif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_MENU = """
CREATE TABLE IF NOT EXISTS menu (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT REFERENCES subeler(id) ON DELETE CASCADE,
    ad TEXT NOT NULL,
    fiyat NUMERIC(10,2) DEFAULT 0,
    kategori TEXT,
    aktif BOOLEAN DEFAULT TRUE,
    aciklama TEXT,
    gorsel_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

ALTER_MENU_COMPAT = """
ALTER TABLE menu ADD COLUMN IF NOT EXISTS aciklama TEXT;
ALTER TABLE menu ADD COLUMN IF NOT EXISTS gorsel_url TEXT;
"""

CREATE_MENU_VARYASYONLAR = """
CREATE TABLE IF NOT EXISTS menu_varyasyonlar (
    id BIGSERIAL PRIMARY KEY,
    menu_id BIGINT REFERENCES menu(id) ON DELETE CASCADE,
    ad TEXT NOT NULL,
    ek_fiyat NUMERIC(10,2) DEFAULT 0,
    sira INT DEFAULT 0,
    aktif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (menu_id, ad)
);
"""

CREATE_SIPARISLER = """
CREATE TABLE IF NOT EXISTS siparisler (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT,
    masa TEXT,
    adisyon_id BIGINT,
    sepet JSONB,
    durum TEXT DEFAULT 'yeni',
    tutar NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

ALTER_SIPARISLER_COMPAT = """
ALTER TABLE siparisler ADD COLUMN IF NOT EXISTS sube_id BIGINT;
ALTER TABLE siparisler ALTER COLUMN sepet TYPE JSONB USING sepet::jsonb;
ALTER TABLE siparisler ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT;
ALTER TABLE siparisler ADD COLUMN IF NOT EXISTS adisyon_id BIGINT;
ALTER TABLE siparisler ADD COLUMN IF NOT EXISTS created_by_username TEXT;
"""

ALTER_ODEMELER_COMPAT = """
ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS adisyon_id BIGINT;
"""

CREATE_ADISYONLAR = """
CREATE TABLE IF NOT EXISTS adisyons (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT NOT NULL,
    masa TEXT NOT NULL,
    acilis_zamani TIMESTAMPTZ DEFAULT NOW(),
    kapanis_zamani TIMESTAMPTZ,
    durum TEXT DEFAULT 'acik',
    toplam_tutar NUMERIC(10,2) DEFAULT 0,
    odeme_toplam NUMERIC(10,2) DEFAULT 0,
    bakiye NUMERIC(10,2) DEFAULT 0,
    iskonto_orani NUMERIC(5,2) DEFAULT 0,
    iskonto_tutari NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_ODEMELER = """
CREATE TABLE IF NOT EXISTS odemeler (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT,
    masa TEXT,
    adisyon_id BIGINT,
    tutar NUMERIC(10,2) NOT NULL,
    yontem TEXT NOT NULL,
    iptal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

ALTER_ADISYON_COMPAT = """
ALTER TABLE adisyons ADD COLUMN IF NOT EXISTS iskonto_tutari NUMERIC(10,2) DEFAULT 0;
"""

CREATE_DISCOUNT_LOG = """
CREATE TABLE IF NOT EXISTS iskonto_kayitlari (
    id BIGSERIAL PRIMARY KEY,
    adisyon_id BIGINT,
    sube_id BIGINT NOT NULL,
    masa TEXT,
    tutar NUMERIC(10,2) NOT NULL,
    oran NUMERIC(5,2),
    kaynak TEXT,
    aciklama TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_AUDIT_LOGS = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    user_id BIGINT,
    username TEXT,
    sube_id BIGINT,
    entity_type TEXT,
    entity_id BIGINT,
    old_values JSONB,
    new_values JSONB,
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_STOCK_ALERTS = """
CREATE TABLE IF NOT EXISTS stock_alert_history (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT NOT NULL,
    stok_id BIGINT NOT NULL,
    stok_ad TEXT NOT NULL,
    alert_type TEXT NOT NULL, -- 'kritik' veya 'tukendi'
    mevcut_miktar NUMERIC(12,3),
    min_miktar NUMERIC(12,3),
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_method TEXT, -- 'websocket', 'email', 'sms'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_BACKUP_HISTORY = """
CREATE TABLE IF NOT EXISTS backup_history (
    id BIGSERIAL PRIMARY KEY,
    backup_type TEXT NOT NULL, -- 'full', 'incremental'
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    status TEXT NOT NULL, -- 'success', 'failed', 'in_progress'
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_by TEXT
);
"""

CREATE_PUSH_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    endpoint TEXT NOT NULL,
    p256dh_key TEXT,
    auth_key TEXT,
    subscription_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, endpoint)
);
"""

CREATE_NOTIFICATION_HISTORY = """
CREATE TABLE IF NOT EXISTS notification_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    notification_type TEXT NOT NULL, -- 'push', 'email', 'sms', 'websocket'
    title TEXT,
    body TEXT NOT NULL,
    icon TEXT,
    data JSONB,
    status TEXT DEFAULT 'pending', -- 'pending', 'sent', 'failed', 'read'
    sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_USER_SUBE_IZIN = """
CREATE TABLE IF NOT EXISTS user_sube_izinleri (
    username TEXT NOT NULL,
    sube_id BIGINT NOT NULL,
    PRIMARY KEY (username, sube_id)
);
"""

CREATE_USER_PERMISSIONS = """
CREATE TABLE IF NOT EXISTS user_permissions (
    username TEXT NOT NULL,
    permission_key TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (username, permission_key)
);
"""

CREATE_APP_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

# Abonelik yönetimi tabloları
CREATE_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    isletme_id BIGINT NOT NULL REFERENCES isletmeler(id) ON DELETE CASCADE,
    plan_type TEXT NOT NULL DEFAULT 'basic', -- basic, pro, enterprise
    status TEXT NOT NULL DEFAULT 'active', -- active, suspended, cancelled, trial
    max_subeler INT DEFAULT 1,
    max_kullanicilar INT DEFAULT 5,
    max_menu_items INT DEFAULT 100,
    ayllik_fiyat NUMERIC(10,2) DEFAULT 0,
    trial_baslangic TIMESTAMPTZ,
    trial_bitis TIMESTAMPTZ,
    baslangic_tarihi TIMESTAMPTZ DEFAULT NOW(),
    bitis_tarihi TIMESTAMPTZ,
    otomatik_yenileme BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (isletme_id)
);
"""

CREATE_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    isletme_id BIGINT NOT NULL REFERENCES isletmeler(id) ON DELETE CASCADE,
    subscription_id BIGINT REFERENCES subscriptions(id) ON DELETE SET NULL,
    tutar NUMERIC(10,2) NOT NULL,
    odeme_turu TEXT NOT NULL, -- nakit, kredi_karti, havale, odeme_sistemi
    durum TEXT NOT NULL DEFAULT 'pending', -- pending, completed, failed, refunded
    fatura_no TEXT,
    aciklama TEXT,
    odeme_tarihi TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_TENANT_CUSTOMIZATIONS = """
CREATE TABLE IF NOT EXISTS tenant_customizations (
    id BIGSERIAL PRIMARY KEY,
    isletme_id BIGINT NOT NULL REFERENCES isletmeler(id) ON DELETE CASCADE,
    domain TEXT UNIQUE, -- Özel alan adı (örn: restoran1.neso.com)
    app_name TEXT, -- Uygulama adı (varsayılan: "Neso")
    logo_url TEXT,
    primary_color TEXT DEFAULT '#3b82f6', -- Ana renk (hex)
    secondary_color TEXT DEFAULT '#1e40af', -- İkincil renk
    footer_text TEXT,
    email TEXT,
    telefon TEXT,
    adres TEXT,
    meta_settings JSONB DEFAULT '{}'::jsonb, -- Ek özelleştirme ayarları
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (isletme_id)
);
"""

CREATE_GIDERLER = """
CREATE TABLE IF NOT EXISTS giderler (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT NOT NULL,
    kategori TEXT NOT NULL,
    aciklama TEXT,
    tutar NUMERIC(10,2) NOT NULL,
    tarih DATE NOT NULL,
    fatura_no TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by_user_id BIGINT
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_siparisler_created_at ON siparisler (created_at);
CREATE INDEX IF NOT EXISTS idx_siparisler_durum ON siparisler (durum);
CREATE INDEX IF NOT EXISTS idx_siparisler_masa ON siparisler (masa);
CREATE INDEX IF NOT EXISTS idx_siparisler_adisyon ON siparisler (adisyon_id);
CREATE INDEX IF NOT EXISTS idx_menu_sube ON menu (sube_id);
-- uq_menu_sube_ad_norm (unaccent) ayrık çalıştırılacak
CREATE INDEX IF NOT EXISTS idx_odemeler_created_at ON odemeler (created_at);
CREATE INDEX IF NOT EXISTS idx_odemeler_sube ON odemeler (sube_id);
CREATE INDEX IF NOT EXISTS idx_odemeler_adisyon ON odemeler (adisyon_id);
CREATE INDEX IF NOT EXISTS idx_adisyons_sube_masa ON adisyons (sube_id, masa);
CREATE INDEX IF NOT EXISTS idx_adisyons_durum ON adisyons (durum);
CREATE INDEX IF NOT EXISTS idx_iskonto_kayitlari_sube_tarih ON iskonto_kayitlari (sube_id, created_at);
CREATE INDEX IF NOT EXISTS idx_giderler_sube_tarih ON giderler (sube_id, tarih);
CREATE INDEX IF NOT EXISTS idx_giderler_kategori ON giderler (kategori);
CREATE INDEX IF NOT EXISTS idx_menu_varyasyonlar_menu ON menu_varyasyonlar (menu_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_isletme ON subscriptions (isletme_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_payments_isletme ON payments (isletme_id);
CREATE INDEX IF NOT EXISTS idx_payments_subscription ON payments (subscription_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (durum);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments (created_at);
CREATE INDEX IF NOT EXISTS idx_tenant_customizations_isletme ON tenant_customizations (isletme_id);
CREATE INDEX IF NOT EXISTS idx_tenant_customizations_domain ON tenant_customizations (domain);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_username ON audit_logs (username);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_stock_alerts_sube ON stock_alert_history (sube_id, created_at);
CREATE INDEX IF NOT EXISTS idx_stock_alerts_stok ON stock_alert_history (stok_id);
CREATE INDEX IF NOT EXISTS idx_backup_history_status ON backup_history (status);
CREATE INDEX IF NOT EXISTS idx_backup_history_created ON backup_history (started_at);
"""


VIEWS_DIR = Path(__file__).resolve().parent / "views"
AI_VIEW_FILES = [
    "vw_ai_menu_stock.sql",
    "vw_ai_active_sessions.sql",
    "vw_ai_sales_summary.sql",
]


async def _ensure_ai_views(db: Database) -> None:
    """Load AI helper SQL views (idempotent)."""
    for filename in AI_VIEW_FILES:
        path = VIEWS_DIR / filename
        if not path.exists():
            logging.warning("AI view definition not found: %s", path)
            continue
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            continue
        # asyncpg tek prepared statement'ta birden fazla komuta izin vermez.
        # Dosyayı ';' ile bölerek tek tek çalıştır.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                await db.execute(stmt)
            except Exception as exc:  # pragma: no cover - deployment safeguard
                logging.error("Failed to create AI view %s: %s", filename, exc)


async def _ensure_super_admin(db: Database) -> None:
    """Eğer hiç super_admin kullanıcısı yoksa, default super admin oluştur."""
    try:
        # Super admin kullanıcısı var mı kontrol et
        existing = await db.fetch_one(
            "SELECT id FROM users WHERE role = 'super_admin' LIMIT 1"
        )
        
        if existing:
            logging.info("Super admin user already exists, skipping creation")
            return
        
        # Super admin yoksa oluştur
        from ..core.security import hash_password
        
        username = "super"
        password = "super123"
        hashed = hash_password(password)
        
        await db.execute(
            """
            INSERT INTO users (username, sifre_hash, role, aktif)
            VALUES (:u, :h, 'super_admin', TRUE)
            ON CONFLICT (username) DO UPDATE
               SET sifre_hash = EXCLUDED.sifre_hash,
                   role = 'super_admin',
                   aktif = TRUE
            """,
            {"u": username, "h": hashed}
        )
        
        logging.info(f"[STARTUP] Created default super admin user: {username}")
        print(f"[STARTUP] ✅ Created default super admin user: {username} / {password}")
        
    except Exception as e:
        logging.error(f"Failed to ensure super admin user: {e}", exc_info=True)
        print(f"[STARTUP] ⚠️ Warning: Could not create super admin user: {e}")


async def create_tables(db: Database):
    # Unaccent eklentisi (varsa geç)
    try:
        await db.execute(EXT_UNACCENT)
    except Exception:
        pass

    # Temel tablolar
    await db.execute(CREATE_ISLETMELER)
    await db.execute(CREATE_SUBELER)
    await db.execute(CREATE_USERS)
    
    # Migration: users tablosuna tenant_id ekle (varsa geç)
    try:
        await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES isletmeler(id) ON DELETE SET NULL")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users (tenant_id)")
        # Super admin kullanıcıları için tenant_id = NULL
        await db.execute("UPDATE users SET tenant_id = NULL WHERE role = 'super_admin' AND tenant_id IS NOT NULL")
    except Exception as e:
        logging.warning(f"Migration: tenant_id column already exists or error: {e}")
    
    await db.execute(CREATE_MENU)
    for stmt in [s.strip() for s in ALTER_MENU_COMPAT.split(';') if s.strip()]:
        try:
            await db.execute(stmt)
        except Exception:
            pass
    await db.execute(CREATE_MENU_VARYASYONLAR)
    await db.execute(CREATE_SIPARISLER)
    # ALTER statements - her birini ayrı dene
    for stmt in [s.strip() for s in ALTER_SIPARISLER_COMPAT.split(';') if s.strip()]:
        try:
            await db.execute(stmt)
        except Exception:
            pass  # Kolonlar zaten varsa hata olabilir
    await db.execute(CREATE_ADISYONLAR)
    for stmt in [s.strip() for s in ALTER_ADISYON_COMPAT.split(';') if s.strip()]:
        try:
            await db.execute(stmt)
        except Exception:
            pass
    await db.execute(CREATE_ODEMELER)
    # ALTER statements for odemeler
    for stmt in [s.strip() for s in ALTER_ODEMELER_COMPAT.split(';') if s.strip()]:
        try:
            await db.execute(stmt)
        except Exception:
            pass  # Kolonlar zaten varsa hata olabilir
    await db.execute(CREATE_USER_SUBE_IZIN)
    await db.execute(CREATE_USER_PERMISSIONS)
    await db.execute(CREATE_APP_SETTINGS)
    await db.execute(CREATE_GIDERLER)
    await db.execute(CREATE_SUBSCRIPTIONS)
    await db.execute(CREATE_PAYMENTS)
    await db.execute(CREATE_TENANT_CUSTOMIZATIONS)
    await db.execute(CREATE_DISCOUNT_LOG)
    await db.execute(CREATE_AUDIT_LOGS)
    await db.execute(CREATE_STOCK_ALERTS)
    await db.execute(CREATE_BACKUP_HISTORY)
    await db.execute(CREATE_PUSH_SUBSCRIPTIONS)
    await db.execute(CREATE_NOTIFICATION_HISTORY)
    # İndeksler (parça parça, hata yutsa da devam)
    for stmt in [s.strip() for s in CREATE_INDEXES.split(';') if s.strip()]:
        try:
            await db.execute(stmt)
        except Exception:
            pass
    # unaccent fonksiyonlu unique index
    try:
        await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_sube_ad_norm
            ON menu (sube_id, unaccent(lower(ad)));
        """)
    except Exception:
        # unaccent yoksa bu index atlanır; uygulama yine çalışır
        pass

    # Opsiyonel stok ve reçete tabloları (varsa kullanılır)
    try:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS stok_kalemleri (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT NOT NULL,
            ad TEXT NOT NULL,
            kategori TEXT,
            birim TEXT,
            mevcut NUMERIC(12,3) DEFAULT 0,
            min NUMERIC(12,3) DEFAULT 0,
            alis_fiyat NUMERIC(10,2) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (sube_id, ad)
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS receteler (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT NOT NULL,
            urun TEXT NOT NULL,
            stok TEXT NOT NULL,
            miktar NUMERIC(12,3) NOT NULL,
            birim TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (sube_id, urun, stok)
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS masalar (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT NOT NULL,
            masa_adi TEXT NOT NULL,
            qr_code TEXT UNIQUE,
            durum TEXT DEFAULT 'bos',
            kapasite INT DEFAULT 4,
            pozisyon_x NUMERIC(10,2),
            pozisyon_y NUMERIC(10,2),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (sube_id, masa_adi)
        );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_recete_sube_urun ON receteler (sube_id, urun);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stok_sube_ad ON stok_kalemleri (sube_id, ad);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_masalar_sube_durum ON masalar (sube_id, durum);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_username ON user_permissions (username);")

        # Performans İyileştirme İndeksleri (Redis cache + query optimization)
        # Composite indexes for tenant queries with time filtering
        await db.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_tenant_time ON siparisler (tenant_id, created_at DESC);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_odemeler_tenant_time ON odemeler (tenant_id, created_at DESC);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_giderler_tenant_time ON giderler (tenant_id, tarih DESC);")

        # Composite indexes for sube + status queries (frequently used together)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_sube_durum ON siparisler (sube_id, durum) WHERE durum != 'tamamlandi';")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_adisyons_sube_aktif ON adisyons (sube_id, durum) WHERE durum = 'acik';")

        # Menu performance indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_menu_tenant_kategori ON menu (tenant_id, kategori);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_menu_tenant_aktif ON menu (tenant_id, aktif) WHERE aktif = true;")

        # Analytics queries optimization
        await db.execute("CREATE INDEX IF NOT EXISTS idx_odemeler_tenant_metod ON odemeler (tenant_id, odeme_metodu);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_urun_time ON siparisler (urun, created_at DESC);")

        # User and audit performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant_role ON users (tenant_id, role);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_time ON audit_logs (tenant_id, created_at DESC);")

        # Stok queries optimization
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stok_tenant_kategori ON stok_kalemleri (tenant_id, kategori);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stok_low_stock ON stok_kalemleri (tenant_id, sube_id) WHERE mevcut <= min;")

        # Push notification indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_push_subscriptions_tenant ON push_subscriptions (tenant_id, is_active) WHERE is_active = true;")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_notification_history_tenant_time ON notification_history (tenant_id, created_at DESC);")
        # Eski kolonları yeni kolonlara migrate et
        await db.execute("ALTER TABLE stok_kalemleri ADD COLUMN IF NOT EXISTS kategori TEXT;")
        await db.execute("ALTER TABLE stok_kalemleri ADD COLUMN IF NOT EXISTS min NUMERIC(12,3) DEFAULT 0;")
        await db.execute("ALTER TABLE stok_kalemleri ADD COLUMN IF NOT EXISTS alis_fiyat NUMERIC(10,2) DEFAULT 0;")
        await db.execute("ALTER TABLE stok_kalemleri ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
        # Eski kod kolonunu ad'a migrate et (varsa)
        try:
            await db.execute("ALTER TABLE stok_kalemleri RENAME COLUMN kod TO ad;")
        except:
            pass
        try:
            await db.execute("ALTER TABLE stok_kalemleri RENAME COLUMN miktar TO mevcut;")
        except:
            pass
        # Reçete tablosunda eski kolonları yeni kolonlara migrate et
        await db.execute("ALTER TABLE receteler ADD COLUMN IF NOT EXISTS birim TEXT;")
        try:
            await db.execute("ALTER TABLE receteler RENAME COLUMN urun_norm TO urun;")
        except:
            pass
        try:
            await db.execute("ALTER TABLE receteler RENAME COLUMN kalem_kod TO stok;")
        except:
            pass
    except Exception:
        pass

    await _ensure_ai_views(db)
    
    # Eğer hiç super_admin kullanıcısı yoksa, default super admin oluştur
    await _ensure_super_admin(db)


async def ensure_demo_seed(db: Database):
    # En az bir işletme/şube ve örnek menü oluştur
    row = await db.fetch_one("SELECT id FROM subeler LIMIT 1")
    if row:
        return
    isletme = await db.fetch_one(
        """
        INSERT INTO isletmeler (ad, aktif)
        VALUES ('Demo İşletme', TRUE)
        RETURNING id
        """
    )
    sube = await db.fetch_one(
        """
        INSERT INTO subeler (isletme_id, ad, aktif)
        VALUES (:iid, 'Merkez Şube', TRUE)
        RETURNING id
        """,
        {"iid": isletme["id"]},
    )
    sid = sube["id"]
    # Örnek menü
    try:
        await db.execute_many(
            """
            INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif)
            VALUES (:sid, :ad, :fiyat, :kat, TRUE)
            """,
            [
                {"sid": sid, "ad": "Latte", "fiyat": 85.0, "kat": "İçecek"},
                {"sid": sid, "ad": "Americano", "fiyat": 75.0, "kat": "İçecek"},
                {"sid": sid, "ad": "Margherita Pizza", "fiyat": 240.0, "kat": "Pizza"},
                {"sid": sid, "ad": "Cola", "fiyat": 45.0, "kat": "İçecek"},
            ],
        )
        await db.execute_many(
            """
            INSERT INTO stok_kalemleri (sube_id, kod, ad, miktar)
            VALUES (:sid, :kod, :ad, :miktar)
            ON CONFLICT (sube_id, kod)
            DO UPDATE SET ad = EXCLUDED.ad, miktar = EXCLUDED.miktar
            """,
            [
                {"sid": sid, "kod": "Latte", "ad": "Latte", "miktar": 12.0},
                {"sid": sid, "kod": "Americano", "ad": "Americano", "miktar": 20.0},
                {"sid": sid, "kod": "Margherita Pizza", "ad": "Margherita Pizza", "miktar": 8.0},
                {"sid": sid, "kod": "Cola", "ad": "Cola", "miktar": 30.0},
            ],
        )
    except Exception:
        pass

"""Add Row-Level Security policies for multi-tenancy

Revision ID: 2025_01_02_0000
Revises: 2025_01_01_0000
Create Date: 2025-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025_01_02_0000'
down_revision = 'initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    PostgreSQL Row-Level Security (RLS) politikalarını ekler.

    Bu politikalar database seviyesinde tenant izolasyonunu sağlar.
    Uygulama hatası olsa bile tenant'lar birbirlerinin verilerine erişemez.
    """

    # 1. İşletmeler tablosu için RLS
    op.execute("""
        -- RLS'i aktif et
        ALTER TABLE isletmeler ENABLE ROW LEVEL SECURITY;

        -- Super admin'ler her şeyi görebilir
        CREATE POLICY isletmeler_superadmin_all
        ON isletmeler
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        -- Normal kullanıcılar sadece kendi işletmelerini görebilir
        CREATE POLICY isletmeler_tenant_isolation
        ON isletmeler
        FOR SELECT
        TO PUBLIC
        USING (
            id IN (
                SELECT DISTINCT s.isletme_id
                FROM subeler s
                JOIN user_sube_izinleri usi ON usi.sube_id = s.id
                WHERE usi.username = current_user
            )
        );
    """)

    # 2. Şubeler tablosu için RLS
    op.execute("""
        ALTER TABLE subeler ENABLE ROW LEVEL SECURITY;

        -- Super admin bypass
        CREATE POLICY subeler_superadmin_all
        ON subeler
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        -- Kullanıcılar sadece izinli oldukları şubeleri görebilir
        CREATE POLICY subeler_user_access
        ON subeler
        FOR ALL
        TO PUBLIC
        USING (
            id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 3. Menu tablosu için RLS (tenant izolasyonu)
    op.execute("""
        ALTER TABLE menu ENABLE ROW LEVEL SECURITY;

        -- Super admin bypass
        CREATE POLICY menu_superadmin_all
        ON menu
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        -- Tenant izolasyonu: Sadece kendi işletmesinin şubelerine ait menüler
        CREATE POLICY menu_tenant_isolation
        ON menu
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT s.id
                FROM subeler s
                JOIN user_sube_izinleri usi ON usi.sube_id = s.id
                WHERE usi.username = current_user
            )
        );
    """)

    # 4. Siparişler tablosu için RLS
    op.execute("""
        ALTER TABLE siparisler ENABLE ROW LEVEL SECURITY;

        CREATE POLICY siparisler_superadmin_all
        ON siparisler
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY siparisler_tenant_isolation
        ON siparisler
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 5. Ödemeler tablosu için RLS
    op.execute("""
        ALTER TABLE odemeler ENABLE ROW LEVEL SECURITY;

        CREATE POLICY odemeler_superadmin_all
        ON odemeler
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY odemeler_tenant_isolation
        ON odemeler
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 6. Stok kalemleri için RLS
    op.execute("""
        ALTER TABLE stok_kalemleri ENABLE ROW LEVEL SECURITY;

        CREATE POLICY stok_kalemleri_superadmin_all
        ON stok_kalemleri
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY stok_kalemleri_tenant_isolation
        ON stok_kalemleri
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 7. Giderler tablosu için RLS
    op.execute("""
        ALTER TABLE giderler ENABLE ROW LEVEL SECURITY;

        CREATE POLICY giderler_superadmin_all
        ON giderler
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY giderler_tenant_isolation
        ON giderler
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 8. Adisyonlar için RLS
    op.execute("""
        ALTER TABLE adisyons ENABLE ROW LEVEL SECURITY;

        CREATE POLICY adisyons_superadmin_all
        ON adisyons
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY adisyons_tenant_isolation
        ON adisyons
        FOR ALL
        TO PUBLIC
        USING (
            sube_id IN (
                SELECT sube_id
                FROM user_sube_izinleri
                WHERE username = current_user
            )
        );
    """)

    # 9. Subscriptions için RLS (işletme bazlı)
    op.execute("""
        ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

        CREATE POLICY subscriptions_superadmin_all
        ON subscriptions
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY subscriptions_tenant_isolation
        ON subscriptions
        FOR SELECT
        TO PUBLIC
        USING (
            isletme_id IN (
                SELECT DISTINCT s.isletme_id
                FROM subeler s
                JOIN user_sube_izinleri usi ON usi.sube_id = s.id
                WHERE usi.username = current_user
            )
        );
    """)

    # 10. Payments için RLS
    op.execute("""
        ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

        CREATE POLICY payments_superadmin_all
        ON payments
        FOR ALL
        TO PUBLIC
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE username = current_user
                AND role = 'super_admin'
            )
        );

        CREATE POLICY payments_tenant_isolation
        ON payments
        FOR SELECT
        TO PUBLIC
        USING (
            isletme_id IN (
                SELECT DISTINCT s.isletme_id
                FROM subeler s
                JOIN user_sube_izinleri usi ON usi.sube_id = s.id
                WHERE usi.username = current_user
            )
        );
    """)

    print("✅ Row-Level Security politikaları başarıyla eklendi!")
    print("   - İşletmeler, şubeler, menü, siparişler, ödemeler, stok, giderler, adisyonlar")
    print("   - Subscriptions ve payments")
    print("   - Tenant izolasyonu database seviyesinde garanti altında!")


def downgrade() -> None:
    """RLS politikalarını kaldır"""

    # Tüm politikaları kaldır
    op.execute("""
        DROP POLICY IF EXISTS isletmeler_superadmin_all ON isletmeler;
        DROP POLICY IF EXISTS isletmeler_tenant_isolation ON isletmeler;
        ALTER TABLE isletmeler DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS subeler_superadmin_all ON subeler;
        DROP POLICY IF EXISTS subeler_user_access ON subeler;
        ALTER TABLE subeler DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS menu_superadmin_all ON menu;
        DROP POLICY IF EXISTS menu_tenant_isolation ON menu;
        ALTER TABLE menu DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS siparisler_superadmin_all ON siparisler;
        DROP POLICY IF EXISTS siparisler_tenant_isolation ON siparisler;
        ALTER TABLE siparisler DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS odemeler_superadmin_all ON odemeler;
        DROP POLICY IF EXISTS odemeler_tenant_isolation ON odemeler;
        ALTER TABLE odemeler DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS stok_kalemleri_superadmin_all ON stok_kalemleri;
        DROP POLICY IF EXISTS stok_kalemleri_tenant_isolation ON stok_kalemleri;
        ALTER TABLE stok_kalemleri DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS giderler_superadmin_all ON giderler;
        DROP POLICY IF EXISTS giderler_tenant_isolation ON giderler;
        ALTER TABLE giderler DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS adisyons_superadmin_all ON adisyons;
        DROP POLICY IF EXISTS adisyons_tenant_isolation ON adisyons;
        ALTER TABLE adisyons DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS subscriptions_superadmin_all ON subscriptions;
        DROP POLICY IF EXISTS subscriptions_tenant_isolation ON subscriptions;
        ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS payments_superadmin_all ON payments;
        DROP POLICY IF EXISTS payments_tenant_isolation ON payments;
        ALTER TABLE payments DISABLE ROW LEVEL SECURITY;
    """)

    print("✅ Row-Level Security politikaları kaldırıldı")

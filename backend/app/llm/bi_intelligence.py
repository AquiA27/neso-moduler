"""
Gelişmiş BI Intelligence Sistemi
- Akıllı context selection (sadece ilgili veriyi seç)
- Advanced prompt engineering
- Chain of Thought reasoning
- Few-shot learning examples
- Structured output
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    """Kullanıcı sorgu niyeti"""
    REVENUE = "revenue"  # Ciro, gelir, kazanç
    EXPENSE = "expense"  # Gider, harcama, maliyet
    PROFIT = "profit"  # Kar, karlılık, marj
    STOCK = "stock"  # Stok, envanter
    MENU = "menu"  # Menü, ürünler, fiyatlar
    RECIPE = "recipe"  # Reçete, malzemeler
    PERSONNEL = "personnel"  # Personel, çalışan, performans
    PRODUCT_SALES = "product_sales"  # Ürün satışları, popüler ürünler
    CATEGORY = "category"  # Kategori analizi
    GENERAL = "general"  # Genel sorular
    SHOPPING = "shopping"  # Alışveriş önerileri
    SUMMARY = "summary"  # Özet rapor


class IntentDetector:
    """Kullanıcı niyetini akıllıca tespit eder"""

    # Anahtar kelime haritalama
    INTENT_KEYWORDS = {
        QueryIntent.REVENUE: [
            "ciro", "gelir", "kazanç", "revenue", "satış", "hasılat",
            "ne kadar kazandık", "toplam satış"
        ],
        QueryIntent.EXPENSE: [
            "gider", "harcama", "maliyet", "expense", "masraf",
            "ne kadar harcadık", "toplam gider"
        ],
        QueryIntent.PROFIT: [
            "kar", "karlılık", "profit", "marj", "net kar", "zarar",
            "kar marjı", "ne kadar kazandık", "kâr"
        ],
        QueryIntent.STOCK: [
            "stok", "envanter", "inventory", "depo", "kritik stok",
            "stoğumuz", "hangi ürünler bitti", "biten ürünler"
        ],
        QueryIntent.MENU: [
            "menü", "menu", "ürün fiyat", "fiyat listesi", "ürünler",
            "menüdeki", "menümüz"
        ],
        QueryIntent.RECIPE: [
            "reçete", "recipe", "tarif", "malzeme", "içindekiler",
            "nasıl yapılır", "içeriği"
        ],
        QueryIntent.PERSONNEL: [
            "personel", "çalışan", "personnel", "staff", "garson",
            "barista", "kim", "performans", "çalışanlar"
        ],
        QueryIntent.PRODUCT_SALES: [
            "en çok satan", "popüler", "top", "bestseller", "satış",
            "hangi ürün", "en iyi", "favoriler"
        ],
        QueryIntent.CATEGORY: [
            "kategori", "category", "grup", "tür", "çeşit",
            "kategori bazlı", "kategoriye göre"
        ],
        QueryIntent.SHOPPING: [
            "alışveriş", "market", "ne almalı", "sipariş ver",
            "almamız gereken", "eksik", "temin"
        ],
        QueryIntent.SUMMARY: [
            "özet", "summary", "genel", "durum", "nabız",
            "nasıl gidiyor", "nasılız", "rapor"
        ],
    }

    @classmethod
    def detect(cls, text: str) -> QueryIntent:
        """Metin analizi ile niyet tespiti"""
        text_lower = text.lower()

        # Her niyet için skor hesapla
        scores = {}
        for intent, keywords in cls.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[intent] = score

        # En yüksek skoru döndür
        if scores:
            return max(scores, key=scores.get)

        return QueryIntent.GENERAL


class ContextSelector:
    """Sorguya göre sadece gerekli veriyi seçer"""

    @staticmethod
    def select_relevant_data(
        intent: QueryIntent,
        all_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """İntent'e göre ilgili veriyi filtrele"""

        relevant = {}

        # Her intent için gerekli veriler
        if intent == QueryIntent.REVENUE:
            relevant["revenue"] = all_data.get("revenue_info")
            relevant["revenue_daily"] = all_data.get("revenue_daily")
            relevant["recent_orders"] = all_data.get("recent_orders")

        elif intent == QueryIntent.EXPENSE:
            relevant["expenses"] = all_data.get("expense_info")
            relevant["expense_daily"] = all_data.get("expense_daily")

        elif intent == QueryIntent.PROFIT:
            relevant["revenue"] = all_data.get("revenue_info")
            relevant["expenses"] = all_data.get("expense_info")
            relevant["profit_data"] = all_data.get("profit_data")

        elif intent == QueryIntent.STOCK:
            relevant["inventory"] = all_data.get("inventory_info")
            relevant["stock_costs"] = all_data.get("stock_costs", [])[:20]  # İlk 20
            relevant["shopping"] = all_data.get("shopping_data")

        elif intent == QueryIntent.MENU:
            relevant["menu_items"] = all_data.get("menu_items", [])[:30]  # İlk 30

        elif intent == QueryIntent.RECIPE:
            relevant["recipes"] = all_data.get("recipes", [])[:15]  # İlk 15

        elif intent == QueryIntent.PERSONNEL:
            relevant["personnel"] = all_data.get("personnel_info")
            relevant["personnel_list"] = all_data.get("personnel_list")

        elif intent == QueryIntent.PRODUCT_SALES:
            relevant["top_products"] = all_data.get("top_products")
            relevant["revenue"] = all_data.get("revenue_info")

        elif intent == QueryIntent.CATEGORY:
            relevant["category_sales"] = all_data.get("category_sales")
            relevant["menu_items"] = all_data.get("menu_items", [])[:20]

        elif intent == QueryIntent.SHOPPING:
            relevant["shopping"] = all_data.get("shopping_data")
            relevant["inventory"] = all_data.get("inventory_info")

        elif intent == QueryIntent.SUMMARY:
            # Özet için tüm verilerin özeti
            relevant["revenue"] = all_data.get("revenue_info")
            relevant["expenses"] = all_data.get("expense_info")
            relevant["inventory_count"] = len(all_data.get("inventory_info", []))
            relevant["top_products"] = all_data.get("top_products", [])[:5]
            relevant["critical_stocks"] = len(all_data.get("inventory_info", []))

        else:  # GENERAL
            # Genel sorular için minimal veri
            relevant["revenue"] = all_data.get("revenue_info")
            relevant["expenses"] = all_data.get("expense_info")

        return relevant


class PromptBuilder:
    """Gelişmiş prompt oluşturucu"""

    @staticmethod
    def build_smart_prompt(
        user_question: str,
        intent: QueryIntent,
        relevant_data: Dict[str, Any],
        time_period: str = "Son 30 gün"
    ) -> str:
        """Intent'e özel, optimize edilmiş prompt oluştur"""

        # Temel sistem rolü
        system_role = """Sen Neso'nun işletme zekası asistanısın. Görevin:
1. İşletme verilerini DOĞRU ve NET analiz etmek
2. SOMUT rakamlar vermek (tahmin yapma!)
3. UYGULANABILIR öneriler sunmak
4. KISA ve ÖZ cevaplar vermek (maksimum 6 cümle)

KURALLAR:
- Sadece verilen verileri kullan
- Rakamları doğru hesapla
- Tahminde bulunma, bilmiyorsan "veri yok" de
- Türkçe karakter kullan
- Profesyonel ama samimi ol"""

        # Intent'e özel context
        context = PromptBuilder._build_context_for_intent(intent, relevant_data, time_period)

        # Few-shot examples
        examples = PromptBuilder._get_few_shot_examples(intent)

        # Final prompt
        prompt = f"""{system_role}

# VERİLER ({time_period}):
{context}

# ÖRNEK YANIT STİLİ:
{examples}

# KULLANICI SORUSU:
"{user_question}"

# YANITINI VER (maksimum 6 cümle, rakamlarla destekle):"""

        return prompt

    @staticmethod
    def _build_context_for_intent(
        intent: QueryIntent,
        data: Dict[str, Any],
        period: str
    ) -> str:
        """Intent'e göre context oluştur"""

        if intent == QueryIntent.REVENUE:
            rev = data.get("revenue", {})
            return f"""CİRO BİLGİLERİ:
- Toplam: {rev.get('total_revenue', 0):.2f} ₺
- Sipariş: {rev.get('total_orders', 0)} adet
- Ortalama sepet: {rev.get('total_revenue', 0) / max(rev.get('total_orders', 1), 1):.2f} ₺"""

        elif intent == QueryIntent.EXPENSE:
            exp = data.get("expenses", {})
            breakdown = exp.get("expense_breakdown", [])
            exp_text = f"GIDER BİLGİLERİ:\n- Toplam: {exp.get('total_expenses', 0):.2f} ₺\n"
            for item in breakdown[:5]:
                exp_text += f"- {item['category']}: {item['amount']:.2f} ₺\n"
            return exp_text

        elif intent == QueryIntent.PROFIT:
            rev = data.get("revenue", {})
            exp = data.get("expenses", {})
            revenue = rev.get('total_revenue', 0)
            expense = exp.get('total_expenses', 0)
            profit = revenue - expense
            margin = (profit / revenue * 100) if revenue > 0 else 0
            return f"""KAR BİLGİLERİ:
- Ciro: {revenue:.2f} ₺
- Gider: {expense:.2f} ₺
- Net Kar: {profit:.2f} ₺
- Kar Marjı: %{margin:.1f}"""

        elif intent == QueryIntent.STOCK:
            inventory = data.get("inventory", [])
            stock_costs = data.get("stock_costs", [])
            total_value = sum(s.get('toplam_deger', 0) for s in stock_costs)
            critical_text = "STOK DURUMU:\n"
            critical_text += f"- Toplam Değer: {total_value:.2f} ₺\n"
            critical_text += f"- Kritik Seviye: {len(inventory)} ürün\n"
            if inventory:
                critical_text += "KRİTİK STOKLAR:\n"
                for item in inventory[:5]:
                    critical_text += f"- {item['ad']}: {item['mevcut']} {item['birim']} (Min: {item['min']})\n"
            return critical_text

        elif intent == QueryIntent.MENU:
            menu = data.get("menu_items", [])
            menu_text = f"MENÜ BİLGİLERİ:\n- Toplam Ürün: {len(menu)}\n\nÖRNEK ÜRÜNLER:\n"
            for item in menu[:10]:
                menu_text += f"- {item['urun']} ({item['kategori']}): {item['fiyat']:.2f} ₺\n"
            return menu_text

        elif intent == QueryIntent.RECIPE:
            recipes = data.get("recipes", [])
            recipe_text = f"REÇETE BİLGİLERİ:\n- Toplam Reçete: {len(recipes)}\n\nÖRNEKLER:\n"
            for recipe in recipes[:5]:
                recipe_text += f"\n{recipe['urun']}:\n"
                for malzeme in recipe['malzemeler'][:3]:
                    recipe_text += f"  • {malzeme['stok']}: {malzeme['miktar']} {malzeme['birim']}\n"
            return recipe_text

        elif intent == QueryIntent.PERSONNEL:
            personnel = data.get("personnel", [])
            perf_text = "PERSONEL PERFORMANSI:\n"
            for p in personnel[:8]:
                perf_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺\n"
            return perf_text

        elif intent == QueryIntent.PRODUCT_SALES:
            products = data.get("top_products", [])
            prod_text = "EN ÇOK SATAN ÜRÜNLER:\n"
            for i, p in enumerate(products[:10], 1):
                prod_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
            return prod_text

        elif intent == QueryIntent.SHOPPING:
            shopping = data.get("shopping", {})
            kritik = shopping.get("kritik_stoklar", [])
            shop_text = "ALIŞVERİŞ ÖNERİLERİ:\n"
            for item in kritik[:8]:
                shop_text += f"- {item['stok_adi']}: {item['mevcut']} {item['birim']} (Önerilen: {item['oneri_miktar']:.1f})\n"
            return shop_text

        elif intent == QueryIntent.SUMMARY:
            rev = data.get("revenue", {})
            exp = data.get("expenses", {})
            return f"""İŞLETME ÖZET:
- Ciro: {rev.get('total_revenue', 0):.2f} ₺ ({rev.get('total_orders', 0)} sipariş)
- Gider: {exp.get('total_expenses', 0):.2f} ₺
- Net Kar: {rev.get('total_revenue', 0) - exp.get('total_expenses', 0):.2f} ₺
- Kritik Stok: {data.get('critical_stocks', 0)} ürün"""

        return "Veri analiz ediliyor..."

    @staticmethod
    def _get_few_shot_examples(intent: QueryIntent) -> str:
        """Intent'e göre örnek yanıtlar"""

        examples = {
            QueryIntent.REVENUE: """Örnek Soru: "Bu ayki ciromuz ne kadar?"
Örnek Yanıt: "Son 30 günde 45.250 ₺ ciro yaptınız. Toplam 312 sipariş aldınız. Ortalama sepet tutarı 145 ₺. Geçen aya göre %12 artış var. Hafta sonları ciron daha yüksek, cuma-pazar günlerine odaklan."

Örnek Soru: "Dünkü satışlarımız nasıl?"
Örnek Yanıt: "Dün 1.850 ₺ ciro yaptınız (18 sipariş). Ortalama 103 ₺ sepet. Hafta ortası için normal bir gün. Öğle saatleri daha hareketli olmuş."

Örnek Soru: "Haftalık gelir ne kadar?"
Örnek Yanıt: "Son 7 günde 12.340 ₺ gelir elde ettiniz. Günlük ortalama 1.763 ₺. En yüksek gün Cumartesi (2.450 ₺). Cuma ve Pazar da iyi performans göstermiş."
""",

            QueryIntent.EXPENSE: """Örnek Soru: "Bu ayki giderlerimiz ne kadar?"
Örnek Yanıt: "Son 30 günde toplam 18.750 ₺ gider yaptınız. En büyük kalem personel maaşları (8.500 ₺). İkinci sırada malzeme alımları (6.200 ₺). Elektrik-su-doğalgaz 2.100 ₺. Geçen aya göre %5 artış var."

Örnek Soru: "En çok nereye harcıyoruz?"
Örnek Yanıt: "En büyük gider kalemleri: 1) Personel: 8.500 ₺ (%45), 2) Malzeme: 6.200 ₺ (%33), 3) Kira-Faturalar: 4.050 ₺ (%22). Toplam giderin %78'i sabit maliyet."
""",

            QueryIntent.PROFIT: """Örnek Soru: "Kar marjımız nasıl?"
Örnek Yanıt: "Son 30 günde net kar: 26.500 ₺. Kar marjınız %58. Ciro 45.250 ₺, gider 18.750 ₺. Sektör ortalaması %45-50, sizin marjınız çok iyi. Giderleri sabit tutarsan karlılık artacak."

Örnek Soru: "Hangi ürünler daha karlı?"
Örnek Yanıt: "En karlı ürünler: Latte (%67 kar), Americano (%71 kar), Kurabiye (%82 kar). En düşük karlılar: Smoothie (%28 kar), Sandwich (%35 kar). Yüksek karlı ürünleri öne çıkar."
""",

            QueryIntent.STOCK: """Örnek Soru: "Hangi ürünlerin stoğu kritik?"
Örnek Yanıt: "5 ürünün stoğu kritik: Süt (8 L kaldı, min 15 L), Kahve çekirdeği (2 kg, min 5 kg), Şeker (3 kg, min 10 kg). Yarın alışveriş yapmalısın. Süt 2 güne, kahve 3 güne yetiyor."

Örnek Soru: "Stok durumumuz nasıl?"
Örnek Yanıt: "Toplam stok değeri: 12.450 ₺. 8 ürün kritik seviyede. 22 ürün normal. Haftalık tüketim 3.200 ₺. En çok tükenen: süt, kahve, şeker. Her Pazartesi rutin alışveriş öneriyorum."
""",

            QueryIntent.MENU: """Örnek Soru: "Menümüzde hangi ürünler var?"
Örnek Yanıt: "Menünüzde 42 ürün var. Kahveler (12): Latte 35₺, Americano 28₺, Cappuccino 38₺. İçecekler (8): Limonata 22₺, Smoothie 45₺. Tatlılar (15): Kurabiye 15₺, Cheesecake 48₺. Yiyecekler (7): Sandwich 52₺, Salata 45₺."

Örnek Soru: "En pahalı ürünümüz ne?"
Örnek Yanıt: "En pahalı 3 ürün: 1) Avokado Toast (68₺), 2) Smoothie Bowl (58₺), 3) Özel Burger (55₺). En ucuz: Kurabiye (15₺), Su (5₺), Türk kahvesi (22₺)."
""",

            QueryIntent.SHOPPING: """Örnek Soru: "Ne almamız lazım?"
Örnek Yanıt: "Acil alınması gerekenler: 1) Süt: 20 L (mevcut 8 L, 2 güne yetiyor), 2) Kahve: 10 kg (mevcut 2 kg), 3) Şeker: 15 kg (mevcut 3 kg). Toplam tahmini maliyet: ~850₺. Yarın temin et."

Örnek Soru: "Haftalık alışveriş listesi?"
Örnek Yanıt: "Haftalık liste (7 günlük): Süt 35L, Kahve 8kg, Şeker 12kg, Peçete 5 paket, Bardak 200 adet. Tahmini maliyet: 1.450₺. Salı günü alırsan hafta boyunca rahat edersin."
""",

            QueryIntent.PERSONNEL: """Örnek Soru: "Personel performansı nasıl?"
Örnek Yanıt: "Son 30 günde: En yüksek ciro Ayşe (8.450₺, 67 sipariş). İkinci Mehmet (7.200₺, 58 sipariş). Yeni personel Zeynep iyi başlamış (3.100₺, 24 sipariş). Ortalama sipariş başına 126₺ ciro yapılıyor."

Örnek Soru: "Kim daha çok satış yapıyor?"
Örnek Yanıt: "Satış lideri Ayşe: 67 sipariş, 8.450₺ ciro. Sipariş başına 126₺ ortalama. Mehmet ikinci: 58 sipariş, 124₺ ortalama. Zeynep yeni ama hızlı gelişiyor. Motivasyon için haftalık hedef koyabilirsin."
""",
        }

        return examples.get(intent, "")


def generate_smart_response(
    user_question: str,
    all_data: Dict[str, Any],
    time_period: str = "Son 30 gün"
) -> Tuple[str, QueryIntent, Dict[str, Any]]:
    """
    Akıllı BI yanıt oluştur

    Returns:
        (prompt, intent, relevant_data)
    """
    # 1. Intent tespiti
    intent = IntentDetector.detect(user_question)
    logger.info(f"[BI_INTELLIGENCE] Detected intent: {intent} for question: {user_question[:50]}")

    # 2. Context selection
    relevant_data = ContextSelector.select_relevant_data(intent, all_data)
    logger.info(f"[BI_INTELLIGENCE] Selected {len(relevant_data)} data sources")

    # 3. Prompt building
    prompt = PromptBuilder.build_smart_prompt(
        user_question,
        intent,
        relevant_data,
        time_period
    )

    return prompt, intent, relevant_data

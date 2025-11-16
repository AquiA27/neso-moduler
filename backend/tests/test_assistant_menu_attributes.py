from app.routers.assistant import (
    _analyze_menu_attributes,
    _filter_milky_coffee_items,
    _is_milky_coffee_query,
    _select_hungry_recommendations,
    _detect_hunger_signal,
    _extract_candidates,
    _has_sensitive_business_query,
    _select_temp_recommendations,
    COLD_DRINK_KEYWORDS,
    HOT_DRINK_KEYWORDS,
)
from app.routers.menu import normalize_name


def _menu_item(name: str, price: float = 70.0, category: str = "İçecek"):
    return {
        "ad": name,
        "fiyat": price,
        "kategori": category,
        "key": normalize_name(name),
    }


def test_menengic_and_turk_coffee_dairy_detection():
    items = [
        _menu_item("Menengiç Kahvesi"),
        _menu_item("Türk Kahvesi"),
    ]
    recipe_map = {
        normalize_name("Menengiç Kahvesi"): ["menengic", "sut"],
        normalize_name("Türk Kahvesi"): ["kahve", "sut"],
    }

    attr_map, dairy_free, _, _ = _analyze_menu_attributes(items, recipe_map)

    menengic_key = normalize_name("Menengiç Kahvesi")
    turk_key = normalize_name("Türk Kahvesi")

    assert attr_map[menengic_key]["contains_milk"] is True
    assert attr_map[turk_key]["contains_milk"] is False
    assert any(item["ad"] == "Türk Kahvesi" for item in dairy_free)


def test_filter_milky_coffee_items():
    items = [
        _menu_item("Menengiç Kahvesi"),
        _menu_item("Türk Kahvesi"),
        _menu_item("Latte"),
        _menu_item("Adaçayı"),
    ]
    recipe_map = {
        normalize_name("Menengiç Kahvesi"): ["menengic", "sut"],
        normalize_name("Türk Kahvesi"): ["kahve"],
        normalize_name("Latte"): ["espresso", "sut"],
    }
    attr_map, _, _, _ = _analyze_menu_attributes(items, recipe_map)
    milky = _filter_milky_coffee_items(items, attr_map)
    names = [item["ad"] for item in milky]
    assert "Menengiç Kahvesi" in names
    assert "Latte" in names
    assert "Türk Kahvesi" not in names
    assert "Adaçayı" not in names


def test_is_milky_coffee_query_detection():
    assert _is_milky_coffee_query("Sütlü kahveleriniz nelerdir?")
    assert _is_milky_coffee_query("sutlu kahve var mi")
    assert not _is_milky_coffee_query("Kafeinsiz kahveleriniz nelerdir?")


def test_lattee_becomes_non_milky_when_recipe_has_no_milk():
    items = [_menu_item("Karamel Latte")]
    recipe_map = {
        normalize_name("Karamel Latte"): ["espresso", "karamel"]
    }
    attr_map, dairy_free, _, _ = _analyze_menu_attributes(items, recipe_map)
    latte_key = normalize_name("Karamel Latte")
    assert attr_map[latte_key]["contains_milk"] is False
    assert any(item["ad"] == "Karamel Latte" for item in dairy_free)


def test_gluten_detection_from_recipe():
    items = [_menu_item("Tam Buğday Tost", category="Atıştırmalık")]
    recipe_map = {
        normalize_name("Tam Buğday Tost"): ["bugday", "peynir"]
    }
    attr_map, _, _, gluten_free = _analyze_menu_attributes(items, recipe_map)
    tost_key = normalize_name("Tam Buğday Tost")
    assert attr_map[tost_key]["contains_gluten"] is True
    assert all(item["ad"] != "Tam Buğday Tost" for item in gluten_free)


def test_select_hungry_recommendations_prioritizes_savory_items():
    items = [
        _menu_item("Kaşarlı Tost", 90, "Atıştırmalık"),
        _menu_item("Çikolatalı Sufle", 120, "Tatlı"),
        _menu_item("Tavuk Wrap", 140, "Ana Yemek"),
        _menu_item("Filtre Kahve", 70, "İçecek"),
        _menu_item("Karışık Pizza", 180, "Pizza"),
    ]
    attr_map, _, _, _ = _analyze_menu_attributes(items, {})
    hungry = _select_hungry_recommendations(items, attr_map)
    hungry_names = [item["ad"] for item in hungry]
    assert "Kaşarlı Tost" in hungry_names
    assert "Tavuk Wrap" in hungry_names
    assert "Karışık Pizza" in hungry_names
    assert "Çikolatalı Sufle" not in hungry_names


def test_detect_hunger_signal_variations():
    assert _detect_hunger_signal("Merhaba acıktım ne yesek?")
    assert _detect_hunger_signal("Şekerim düştü, bir şeyler yiyelim mi")
    assert not _detect_hunger_signal("Merhaba sadece kahve istiyorum")


def test_extract_candidates_handles_inline_variation():
    pairs = _extract_candidates("1 kaşarlı tost ketçaplı 2 çay")
    normalized = { (name.lower(), count) for name, count in pairs }
    assert ("kaşarlı tost", 1) in normalized
    assert any("ket" in name for name, _ in normalized)


def test_sensitive_business_query_detection():
    assert _has_sensitive_business_query("Bugünkü ciro nedir?")
    assert _has_sensitive_business_query("Kar marjı kaç?")
    assert not _has_sensitive_business_query("Menüde latte var mı?")


def test_select_temp_recommendations_for_cold_and_hot():
    items = [
        _menu_item("Soğuk Limonata", 70, "İçecek"),
        _menu_item("Buzlu Latte", 95, "İçecek"),
        _menu_item("Sıcak Salep", 80, "İçecek"),
        _menu_item("Türk Kahvesi", 75, "İçecek"),
    ]
    cold = _select_temp_recommendations(items, COLD_DRINK_KEYWORDS)
    hot = _select_temp_recommendations(items, HOT_DRINK_KEYWORDS)
    cold_names = [item["ad"] for item in cold]
    hot_names = [item["ad"] for item in hot]
    assert "Soğuk Limonata" in cold_names
    assert "Buzlu Latte" in cold_names
    assert "Sıcak Salep" in hot_names
    assert "Türk Kahvesi" in hot_names


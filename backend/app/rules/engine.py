"""Kural motoru: veri sonuçlarına göre uyarı / aksiyon üretir."""
from __future__ import annotations

from typing import Dict, List


def evaluate_rules(intent: str, rows: List[Dict[str, object]]) -> List[str]:
    messages: List[str] = []

    if intent == "stok_durumu":
        for row in rows:
            stok_kritik = int(row.get("stok_kritik", 0))
            if stok_kritik == 2:
                messages.append("Stok tamamen tükenmiş görünüyor, tedarik gerekli.")
            elif stok_kritik == 1:
                messages.append("Stok kritik seviyede, uyarı verelim.")
    elif intent == "aktif_adisyonlar":
        for row in rows:
            bakiye = float(row.get("bakiye", 0) or 0)
            if bakiye > 0:
                messages.append(f"Masa {row.get('masa')} için ödenmemiş bakiye {bakiye:.2f} ₺")
    return messages




import re
import os

extract_func = '''def _extract_candidates(text: str) -> list:
    import re
    t = text.casefold()
    t = re.sub(r"[,.;\n]", " ", t)
    NUMBER_WORDS = {
        "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
        "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7, "sekiz": 8,
        "dokuz": 9, "on": 10
    }
    for word, number in NUMBER_WORDS.items():
        t = re.sub(r"\\b" + word + r"\\b", str(number), t)
    tokens = t.split()
    skip_words = {
        "tane", "adet", "ve", "de", "da", "ile", 
        "merhaba", "selam", "selamlar", "hey", "hello", "hi", 
        "hosgeldin", "hos", "geldin", "günaydın", "gunaydin",
        "iyi", "günler", "gunler", "akşamlar", "aksamlar",
        "teşekkürler", "tesekkurler", "sağol", "sagol", "teşekkür", "tesekkur", 
        "lutfen", "please"
    }
    filtered = [tok for tok in tokens if tok not in skip_words]
    pairs = []
    i = 0
    while i < len(filtered):
        tok = filtered[i]
        if tok.isdigit():
            count = int(tok)
            i += 1
            words = []
            while i < len(filtered) and not filtered[i].isdigit():
                words.append(filtered[i])
                i += 1
            if words:
                pairs.append([" ".join(words), count])
        else:
            words = []
            while i < len(filtered) and not filtered[i].isdigit():
                words.append(filtered[i])
                i += 1
            count = 1
            if i < len(filtered):
                count = int(filtered[i])
                i += 1
            if words:
                pairs.append([" ".join(words), count])
    return pairs
'''

def replace_extract_candidates(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Using regex to find the old _extract_candidates block
    pattern = re.compile(r'def _extract_candidates.*?return pairs\n', re.DOTALL)
    new_content = pattern.sub(extract_func, content, count=1)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

ws_code = '''
        row = await db.fetch_one(
            """
            INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar)
            VALUES (:sid, :masa, :adisyon_id, CAST(:sepet AS JSONB), 'yeni', :tutar)
            RETURNING id, masa, durum, tutar, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "adisyon_id": adisyon_id, "sepet": json.dumps(sepet, ensure_ascii=False), "tutar": tutar},
        )

        try:
            from ..websocket.manager import manager
            import asyncio
            asyncio.create_task(manager.broadcast({
                "type": "new_order",
                "message": f"Yeni sipariş: {payload.masa}",
                "masa": payload.masa
            }, topic="orders"))
            asyncio.create_task(manager.broadcast({
                "type": "masa_status_change",
                "masa_adi": payload.masa,
                "durum": "dolu"
            }, topic="orders"))
            # Update table to full if it's currently empty or reserved
            await db.execute(
                "UPDATE masalar SET durum = 'dolu' WHERE masa_adi = :masa AND sube_id = :sid AND durum IN ('bos', 'rezerve')",
                {"masa": payload.masa, "sid": sube_id}
            )
        except Exception as e:
            import logging
            logging.error(f"WebSocket event error: {e}")
'''

def add_ws_broadcast(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the block where siparisler is inserted and use regex to replace
    pattern = re.compile(r'\s*row = await db\.fetch_one\(\s*"""\s*INSERT INTO siparisler \((sube_id, masa, adisyon_id, sepet, durum, tutar|sube_id, masa, sepet, durum, tutar)\).*?RETURNING.*?""",\s*\{[^}]*\},\s*\)', re.DOTALL)
    # For public.py where it inserts without adisyon_id, or with adisyon_id
    
    def repl(m):
        # Return the original match + ws_code, wait, ws_code hardcodes parameters
        # Let's just do a simple replace on the exact snippet for both public.py and assistant.py
        original = m.group(0)
        return original + '''
        try:
            from ..websocket.manager import manager
            import asyncio
            asyncio.create_task(manager.broadcast({
                "type": "new_order",
                "message": f"Yeni sipariş",
                "masa": payload.masa
            }, topic="orders"))
            asyncio.create_task(manager.broadcast({
                "type": "masa_status_change",
                "masa_adi": payload.masa,
                "durum": "dolu"
            }, topic="orders"))
            # Update table to full if it's currently empty or reserved
            await db.execute(
                "UPDATE masalar SET durum = 'dolu' WHERE masa_adi = :masa AND sube_id = :sid AND durum IN ('bos', 'rezerve')",
                {"masa": payload.masa, "sid": sube_id}
            )
        except Exception as e:
            import logging
            logging.error(f"WebSocket event error: {e}")
'''
    
    new_content = pattern.sub(repl, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

path_ass = "c:\\Users\\alibu\\NesoModuler\\backend\\app\\routers\\assistant.py"
path_pub = "c:\\Users\\alibu\\NesoModuler\\backend\\app\\routers\\public.py"

replace_extract_candidates(path_pub)
replace_extract_candidates(path_ass)

add_ws_broadcast(path_pub)
add_ws_broadcast(path_ass)

print("Code rewritten successfully.")

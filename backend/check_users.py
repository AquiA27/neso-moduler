import psycopg2
import sys

try:
    conn = psycopg2.connect("postgresql://postgres:rELURsUWOMKoXFJMgJrqQzuLcGajERty@maglev.proxy.rlwy.net:46270/railway")
    cur = conn.cursor()
    
    print("--- USERS ---")
    cur.execute("SELECT id, username, role, tenant_id, aktif FROM users WHERE username IN ('mutfak3131', 'fistik_mutfak')")
    for row in cur.fetchall():
        print(row)
        
    print("\n--- ISLETMELER ---")
    cur.execute("SELECT id, ad, aktif, allowed_ips FROM isletmeler")
    for row in cur.fetchall():
        print(row)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

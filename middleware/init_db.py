import os
import sys

# Đảm bảo UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import psycopg2

DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "gomdon_lakehouse")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "StrongPassword@2026")

def init_database():
    print("=" * 70)
    print("🚀 [KHOI TAO CSDL] DANG KET NOI DEN POSTGRESQL TRONG DOCKER...")
    print(f"   * Host: {DB_HOST}:{DB_PORT}")
    print(f"   * Database: {DB_NAME}")
    print(f"   * User: {DB_USER}")
    print("=" * 70)

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        conn.autocommit = True
        cur = conn.cursor()

        sql_file_path = os.path.join(os.path.dirname(__file__), "init_db.sql")
        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        print("[*] Dang chay tap lenh SQL khoi tao bang...")
        cur.execute(sql_script)

        # Kiem tra danh sach cac bang vua tao
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cur.fetchall()

        print("\n" + "=" * 70)
        print("✅ [THANH CONG] DA KHOI TAO DAY DU CAC BANG TRONG CSDL:")
        print("=" * 70)
        for i, (table,) in enumerate(tables, start=1):
            cur.execute(f"""
                SELECT count(*) 
                FROM information_schema.columns 
                WHERE table_name = '{table}';
            """)
            col_count = cur.fetchone()[0]
            print(f"   {i:02d}. Bảng: {table:<25} ({col_count} cột)")

        print("=" * 70)
        print("🎉 CSDL GOM ĐƠN ĐA NỀN TẢNG (LAKEHOUSE) ĐÃ SẴN SÀNG HOẠT ĐỘNG!\n")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ [LOI KHOI TAO CSDL]: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()

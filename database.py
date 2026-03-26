import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "beymen_tracker.db"

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Veritabanı tablolarını oluştur (yoksa)."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT NOT NULL,
                category TEXT,
                url TEXT,
                image_url TEXT,
                original_price REAL,
                last_price REAL,
                last_discount_rate INTEGER DEFAULT 0,
                available_sizes TEXT DEFAULT '[]',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_alerted TEXT
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                price REAL NOT NULL,
                original_price REAL,
                discount_rate INTEGER DEFAULT 0,
                available_sizes TEXT DEFAULT '[]',
                checked_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_product
                ON price_history(product_id, checked_at);
        """)
    logger.info("Veritabanı hazır: %s", DB_PATH)


def upsert_product(product: dict) -> dict:
    """
    Ürünü ekle veya güncelle.
    Dönüş: {'is_new': bool, 'price_changed': bool, 'old_price': float|None}
    """
    now = datetime.utcnow().isoformat()
    pid = product["id"]

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM products WHERE id = ?", (pid,)
        ).fetchone()

        sizes_json = json.dumps(product.get("available_sizes", []))

        if existing is None:
            # Yeni ürün
            conn.execute("""
                INSERT INTO products
                    (id, name, brand, category, url, image_url,
                     original_price, last_price, last_discount_rate,
                     available_sizes, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pid,
                product["name"],
                product["brand"],
                product.get("category", ""),
                product.get("url", ""),
                product.get("image_url", ""),
                product.get("original_price"),
                product["price"],
                product.get("discount_rate", 0),
                sizes_json,
                now,
                now,
            ))
            _add_history(conn, pid, product, now)
            return {"is_new": True, "price_changed": False, "old_price": None}
        else:
            old_price = existing["last_price"]
            price_changed = abs(old_price - product["price"]) > 0.01

            # original_price'i korumak istiyoruz (ilk görülen referans fiyat)
            ref_original = existing["original_price"] or product.get("original_price")

            conn.execute("""
                UPDATE products SET
                    name = ?, url = ?, image_url = ?,
                    last_price = ?, last_discount_rate = ?,
                    available_sizes = ?, last_seen = ?
                WHERE id = ?
            """, (
                product["name"],
                product.get("url", ""),
                product.get("image_url", ""),
                product["price"],
                product.get("discount_rate", 0),
                sizes_json,
                now,
                pid,
            ))
            _add_history(conn, pid, product, now)
            return {
                "is_new": False,
                "price_changed": price_changed,
                "old_price": old_price,
                "ref_original": ref_original,
            }


def _add_history(conn: sqlite3.Connection, pid: str, product: dict, now: str):
    sizes_json = json.dumps(product.get("available_sizes", []))
    conn.execute("""
        INSERT INTO price_history
            (product_id, price, original_price, discount_rate, available_sizes, checked_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        pid,
        product["price"],
        product.get("original_price"),
        product.get("discount_rate", 0),
        sizes_json,
        now,
    ))


def get_product(product_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def mark_alerted(product_id: str):
    """Ürünün son alert zamanını şimdiye güncelle."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET last_alerted = ? WHERE id = ?",
            (now, product_id),
        )


def get_price_history(product_id: str, limit: int = 14) -> list[dict]:
    """Son N kayıt için fiyat geçmişini döndür."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT price, original_price, discount_rate, available_sizes, checked_at
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at DESC
            LIMIT ?
        """, (product_id, limit)).fetchall()
        return [dict(r) for r in rows]


def get_all_discounted(min_discount: int = 0) -> list[dict]:
    """Veritabanındaki indirimli tüm ürünleri döndür."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM products
            WHERE last_discount_rate >= ?
            ORDER BY last_discount_rate DESC
        """, (min_discount,)).fetchall()
        return [dict(r) for r in rows]

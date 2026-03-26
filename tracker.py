import json
import logging
from datetime import datetime, timedelta

import database

logger = logging.getLogger(__name__)


def _price_trend(history: list[dict]) -> str:
    """
    Son 7 kayıt için fiyat trendini Unicode karakterlerle göster.
    Örn: ▅▄▃▂▁ (düşüyor) veya ▁▂▃▄▅ (yükseliyor)
    """
    if len(history) < 2:
        return ""
    prices = [h["price"] for h in reversed(history[:7])]
    min_p, max_p = min(prices), max(prices)
    if max_p == min_p:
        return "▄" * len(prices)
    bars = " ▁▂▃▄▅▆▇█"
    trend = ""
    for p in prices:
        idx = round((p - min_p) / (max_p - min_p) * 8)
        trend += bars[idx]
    return trend


def _is_cooldown_active(last_alerted_iso: str | None, cooldown_hours: int) -> bool:
    """Son alertten cooldown_hours saat geçmediyse True döndür."""
    if not last_alerted_iso:
        return False
    try:
        last_alerted = datetime.fromisoformat(last_alerted_iso)
        return datetime.utcnow() < last_alerted + timedelta(hours=cooldown_hours)
    except ValueError:
        return False


def process_products(
    scraped_products: list[dict],
    config: dict,
) -> list[dict]:
    """
    Taranan ürünleri veritabanına kaydet ve alert listesi döndür.

    Dönen liste: alert gönderilecek ürünler
    Her item: scraper dict + 'is_new', 'price_changed', 'old_price', 'trend', 'ref_original'
    """
    alert_cfg = config.get("alert", {})
    min_discount: int = alert_cfg.get("min_discount_percent", 30)
    cooldown_hours: int = alert_cfg.get("cooldown_hours", 24)
    notify_new: bool = alert_cfg.get("notify_new_products", False)
    low_stock_threshold: int = alert_cfg.get("low_stock_threshold", 3)

    alerts: list[dict] = []

    for product in scraped_products:
        result = database.upsert_product(product)
        db_row = database.get_product(product["id"])

        is_new: bool = result.get("is_new", False)
        price_changed: bool = result.get("price_changed", False)
        old_price: float | None = result.get("old_price")
        ref_original: float = (
            result.get("ref_original")
            or db_row.get("original_price")
            or product.get("original_price")
            or product["price"]
        )

        discount_rate: int = product.get("discount_rate", 0)
        stock: int = int(product.get("stock") or 0)
        # stock=0 genellikle "bilinmiyor" anlamına gelir (Beymen her zaman vermez)
        low_stock: bool = 0 < stock <= low_stock_threshold

        # Cooldown kontrolü
        if _is_cooldown_active(db_row.get("last_alerted"), cooldown_hours):
            logger.debug(
                "Cooldown aktif, atlanıyor: %s (%s)",
                product["name"], product["id"],
            )
            continue

        should_alert = False
        reason = ""

        if discount_rate >= min_discount:
            should_alert = True
            reason = "discount"
        elif notify_new and is_new:
            should_alert = True
            reason = "new_product"

        if not should_alert:
            continue

        # Fiyat trendi
        history = database.get_price_history(product["id"], limit=7)
        trend = _price_trend(history)

        alert_item = {
            **product,
            "is_new": is_new,
            "price_changed": price_changed,
            "old_price": old_price,
            "ref_original": ref_original,
            "trend": trend,
            "reason": reason,
            "low_stock": low_stock,
            "stock": stock,
        }
        alerts.append(alert_item)
        logger.info(
            "ALERT [%s] %s — %s: %s TL → %s TL (-%d%%)",
            reason,
            product["brand"],
            product["name"],
            ref_original,
            product["price"],
            discount_rate,
        )

    return alerts


def mark_all_alerted(alert_items: list[dict]):
    """Alert gönderilen tüm ürünleri veritabanında işaretle."""
    for item in alert_items:
        database.mark_alerted(item["id"])


def get_daily_summary(min_discount: int = 0) -> list[dict]:
    """
    Günlük özet için veritabanından indirimli ürünleri çek.
    available_sizes alanını JSON'dan parse eder.
    """
    products = database.get_all_discounted(min_discount)
    for p in products:
        if isinstance(p.get("available_sizes"), str):
            try:
                p["available_sizes"] = json.loads(p["available_sizes"])
            except (json.JSONDecodeError, TypeError):
                p["available_sizes"] = []
        history = database.get_price_history(p["id"], limit=7)
        p["trend"] = _price_trend(history)
    return products

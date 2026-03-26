#!/usr/bin/env python3
"""
Beymen Price Alert Bot
======================
Kullanım:
  python bot.py              → Scheduler modunda başlat (6 saatlik döngü)
  python bot.py --test       → Tek seferlik çalıştır, mail gönder
  python bot.py --dry-run    → Tek seferlik çalıştır, mail ATMA (konsola yaz)
  python bot.py --summary    → Günlük özet mailini hemen gönder
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import database
import scraper
import tracker
import notifier
import report

# ------------------------------------------------------------------ #
# LOGGING
# ------------------------------------------------------------------ #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("beymen_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("beymen_bot")

# ------------------------------------------------------------------ #
# KONFİGÜRASYON
# ------------------------------------------------------------------ #

CONFIG_PATH = Path(__file__).parent / "config.yaml"
ENV_PATH = Path(__file__).parent / ".env"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.error(
            "config.yaml bulunamadı! Örnek dosyayı kopyalayın:\n"
            "  cp config.yaml.example config.yaml\n"
            "Ardından kendi ayarlarınızı girin."
        )
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_email_password() -> str:
    load_dotenv(ENV_PATH)
    password = os.getenv("EMAIL_PASSWORD", "")
    if not password:
        logger.error(
            "EMAIL_PASSWORD bulunamadı!\n"
            ".env dosyası oluşturun:\n"
            "  echo 'EMAIL_PASSWORD=sifreniz' > .env"
        )
        sys.exit(1)
    return password


def validate_config(config: dict):
    """Temel konfigürasyon doğrulaması."""
    user = config.get("user", {})
    if not user.get("email"):
        logger.error("config.yaml: user.email boş bırakılamaz!")
        sys.exit(1)

    email_cfg = config.get("email", {})
    if not email_cfg.get("sender_email"):
        logger.error("config.yaml: email.sender_email boş bırakılamaz!")
        sys.exit(1)

    if not config.get("brands"):
        logger.warning("config.yaml: Hiç marka tanımlanmamış!")

    if not config.get("categories"):
        logger.warning("config.yaml: Hiç kategori tanımlanmamış!")

    sizes_cfg = user.get("sizes", {})
    letter_sizes = sizes_cfg.get("letter", [])
    numeric_sizes = sizes_cfg.get("numeric", [])
    if not letter_sizes and not numeric_sizes:
        logger.error("config.yaml: user.sizes.letter veya numeric en az biri dolu olmalı!")
        sys.exit(1)


# ------------------------------------------------------------------ #
# ANA İŞ AKIŞI
# ------------------------------------------------------------------ #

def run_check(config: dict, email_password: str, dry_run: bool = False):
    """
    Tek bir kontrol döngüsü:
    1. Beymen'i tara
    2. Ürünleri veritabanına kaydet / karşılaştır
    3. Alert varsa mail gönder
    """
    logger.info("=" * 60)
    logger.info("Kontrol başlıyor — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 1. Tara
    products = scraper.scrape_all(config)
    logger.info("Taranan ürün sayısı (bedeninizde): %d", len(products))

    if not products:
        logger.info("Belirtilen filtrelere uygun ürün bulunamadı.")
        return

    # 2. İşle ve alert listesi oluştur
    alerts = tracker.process_products(products, config)
    logger.info("Alert sayısı: %d", len(alerts))

    # 3. Mail gönder
    if alerts:
        if dry_run:
            logger.info("[DRY-RUN] Mail atılmıyor. Alert ürünler:")
            for a in alerts:
                low = " ⚡ SON STOK!" if a.get("low_stock") else ""
                logger.info(
                    "  • %s — %s | -%d%% | %s TL → %s TL | Bedenler: %s%s",
                    a["brand"], a["name"], a["discount_rate"],
                    a.get("ref_original", "?"), a["price"],
                    ", ".join(a.get("matching_sizes") or []),
                    low,
                )
        else:
            notifier.send_alert_email(alerts, config, email_password)
            tracker.mark_all_alerted(alerts)
    else:
        logger.info("Bu döngüde alert koşulları karşılanmadı.")

    # Her kontrol sonunda HTML raporu güncelle
    low_stock_threshold = config.get("alert", {}).get("low_stock_threshold", 3)
    report.generate_report(low_stock_threshold=low_stock_threshold)

    logger.info("Kontrol tamamlandı.")


def run_daily_summary(config: dict, email_password: str, dry_run: bool = False):
    """Günlük özet mailini gönder."""
    min_discount = config.get("alert", {}).get("min_discount_percent", 0)
    products = tracker.get_daily_summary(min_discount)
    logger.info("Günlük özet: %d indirimli ürün", len(products))

    if dry_run:
        logger.info("[DRY-RUN] Günlük özet maili atılmıyor.")
        for p in products:
            logger.info(
                "  • %s — %s | -%d%% | %s TL",
                p.get("brand"), p.get("name"),
                p.get("last_discount_rate", 0),
                p.get("last_price"),
            )
        return

    notifier.send_daily_summary(products, config, email_password)


# ------------------------------------------------------------------ #
# SCHEDULER
# ------------------------------------------------------------------ #

def start_scheduler(config: dict, email_password: str):
    """APScheduler ile periyodik kontrol başlat."""
    alert_cfg = config.get("alert", {})
    interval_hours: int = alert_cfg.get("check_interval_hours", 6)
    daily_summary: bool = alert_cfg.get("daily_summary", True)
    summary_hour: int = alert_cfg.get("daily_summary_hour", 9)

    scheduler = BlockingScheduler(timezone="Europe/Istanbul")

    # Ana kontrol — interval trigger
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(hours=interval_hours),
        args=[config, email_password],
        id="price_check",
        name=f"Beymen fiyat kontrolü (her {interval_hours} saatte bir)",
        replace_existing=True,
    )

    # Günlük özet — cron trigger
    if daily_summary:
        scheduler.add_job(
            run_daily_summary,
            trigger=CronTrigger(hour=summary_hour, minute=0),
            args=[config, email_password],
            id="daily_summary",
            name=f"Günlük özet ({summary_hour:02d}:00)",
            replace_existing=True,
        )

    logger.info(
        "Scheduler başlatıldı — her %d saatte bir kontrol, "
        "günlük özet %02d:00",
        interval_hours, summary_hour,
    )
    logger.info("Durdurmak için Ctrl+C")

    # İlk çalışmayı hemen yap
    logger.info("İlk kontrol hemen başlıyor...")
    run_check(config, email_password)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot durduruldu.")


# ------------------------------------------------------------------ #
# CLI GİRİŞ NOKTASI
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Beymen Price Alert Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Tek seferlik çalıştır, mail gönder",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Tek seferlik çalıştır, mail ATMA",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Günlük özet mailini hemen gönder",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="report.html raporunu hemen oluştur (tarama yapmaz)",
    )
    args = parser.parse_args()

    config = load_config()
    validate_config(config)

    # dry-run ve report modunda şifre gerekmez
    if args.dry_run or args.report:
        email_password = "no-email-mode"
    else:
        email_password = load_email_password()

    database.init_db()

    if args.report:
        logger.info("RAPOR modu — report.html oluşturuluyor")
        low_stock_threshold = config.get("alert", {}).get("low_stock_threshold", 3)
        report.generate_report(low_stock_threshold=low_stock_threshold)
        logger.info("Rapor hazır: report.html")

    elif args.dry_run:
        logger.info("DRY-RUN modu — mail gönderilmeyecek")
        run_check(config, email_password, dry_run=True)

    elif args.test:
        logger.info("TEST modu — tek seferlik çalışıyor")
        run_check(config, email_password, dry_run=False)

    elif args.summary:
        logger.info("ÖZET modu — günlük özet maili gönderiliyor")
        run_daily_summary(config, email_password, dry_run=False)

    else:
        start_scheduler(config, email_password)


if __name__ == "__main__":
    main()

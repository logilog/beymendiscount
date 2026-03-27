import json
import time
import random
import logging
import urllib.parse
from typing import Generator

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.beymen.com/search"
PRODUCT_URL_BASE = "https://www.beymen.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.beymen.com/",
}



def _build_url(brand: str, category: str, page: int = 1) -> str:
    params = {
        "q": brand,
        "cinsiyet": "erkek",
        "marka": brand,
        "urun-grubu": category,
        "sayfa": page,
        "urunSayisi": 48,
    }
    return BASE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _build_wishlist_url(url: str, page: int = 1) -> str:
    """Wishlist URL'sine sayfalama parametresi ekle."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sayfa={page}&urunSayisi=48"


def _fetch_page(session: requests.Session, url: str) -> str | None:
    """Sayfayı indir, hata olursa None döndür."""
    for attempt in range(4):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 429:
                wait = 2 ** (attempt + 2)
                logger.warning("Rate limited (429). %d sn bekleniyor...", wait)
                time.sleep(wait)
                continue
            logger.warning("HTTP %d: %s", resp.status_code, url)
            return None
        except requests.RequestException as exc:
            wait = 2 ** (attempt + 1)
            logger.warning("İstek hatası (%s). %d sn sonra tekrar...", exc, wait)
            time.sleep(wait)
    return None


def _extract_json_object(html: str, marker: str) -> dict | None:
    """
    HTML içinde `marker` stringini bulur, ardından gelen JSON objesini
    brace-counting yöntemiyle eksiksiz çıkarır.
    Regex'ten daha güvenilir — iç içe objeler/arrayler de doğru parse edilir.
    """
    idx = html.find(marker)
    if idx == -1:
        return None
    brace_start = html.find('{', idx + len(marker))
    if brace_start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(brace_start, len(html)):
        ch = html[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[brace_start:i + 1])
                except json.JSONDecodeError as exc:
                    logger.debug("JSON parse hatası: %s", exc)
                    return None
    return None


def _parse_product_list(html: str) -> dict | None:
    """HTML içinden productListMain JSON objesini çıkar."""
    # Önce tam marker ile dene
    data = _extract_json_object(html, "BEYMEN.productListMain =")
    if data and isinstance(data.get("products"), list):
        return data
    # Fallback: window. prefix'li versiyon
    data = _extract_json_object(html, "window.BEYMEN.productListMain =")
    if data and isinstance(data.get("products"), list):
        return data
    # Son çare: sadece "productListMain =" işareti
    data = _extract_json_object(html, "productListMain =")
    if data and isinstance(data.get("products"), list):
        return data
    logger.debug("productListMain bulunamadı veya products listesi yok")
    return None


def _extract_products(data: dict, user_sizes: list[str]) -> list[dict]:
    """
    productListMain objesinden ürün listesini normalize ederek döndür.
    Sadece kullanıcının bedeni stokta olan ürünleri dahil eder.
    """
    raw_products = data.get("products") or data.get("Products") or []
    results = []

    for p in raw_products:
        try:
            # Stokta olan bedenleri bul
            sizes = p.get("sizes") or p.get("Sizes") or []
            in_stock_sizes = [
                s.get("sizeName") or s.get("SizeName", "")
                for s in sizes
                if (s.get("inStock") or s.get("InStock")) is True
            ]

            # Kullanıcının herhangi bir bedeni stokta mı?
            user_sizes_upper = [sz.upper() for sz in user_sizes]
            matching_sizes = [
                sz for sz in in_stock_sizes
                if sz.upper() in user_sizes_upper
            ]
            if not matching_sizes:
                continue

            product_id = str(p.get("productId") or p.get("ProductId", ""))
            if not product_id:
                continue

            actual_price = float(
                p.get("actualPrice") or p.get("ActualPrice") or 0
            )
            original_price = float(
                p.get("originalPrice") or p.get("OriginalPrice") or actual_price
            )
            discount_rate = int(
                p.get("discountRate") or p.get("DiscountRate") or 0
            )

            # discountRate bazen 0 olsa da fiyat farkı varsa hesapla
            if discount_rate == 0 and original_price > actual_price:
                discount_rate = round(
                    (1 - actual_price / original_price) * 100
                )

            brand = (
                p.get("brandName") or p.get("BrandName") or ""
            ).strip()
            name = (
                p.get("displayName") or p.get("DisplayName") or ""
            ).strip()
            category = (
                p.get("productCategory") or p.get("ProductCategory") or ""
            ).strip()
            slug = (
                p.get("productUrl") or p.get("ProductUrl") or ""
            ).strip()
            url = (PRODUCT_URL_BASE + "/" + slug.lstrip("/")) if slug else ""

            images = p.get("images") or p.get("Images") or []
            image_url = ""
            if images:
                first = images[0]
                image_url = first.get("url") or first.get("Url") or ""

            # Stok adedi (varsa)
            stock_count = int(p.get("stock") or p.get("Stock") or 0)

            results.append({
                "id": product_id,
                "name": name,
                "brand": brand,
                "category": category,
                "url": url,
                "image_url": image_url,
                "price": actual_price,
                "original_price": original_price,
                "discount_rate": discount_rate,
                "stock": stock_count,
                "available_sizes": in_stock_sizes,
                "matching_sizes": matching_sizes,
            })

        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Ürün parse hatası: %s", exc)
            continue

    return results


def scrape_brand_category(
    session: requests.Session,
    brand: str,
    category: str,
    user_sizes: list[str],
) -> Generator[dict, None, None]:
    """Belirli marka + kategori için tüm ürünleri tarar."""
    url = _build_url(brand, category, page=1)
    html = _fetch_page(session, url)
    if not html:
        logger.warning("Sayfa alınamadı: %s / %s", brand, category)
        return

    data = _parse_product_list(html)
    if not data:
        logger.warning("Ürün listesi parse edilemedi: %s / %s", brand, category)
        return

    total_pages = int(data.get("totalPage") or data.get("TotalPage") or 1)
    products = _extract_products(data, user_sizes)
    logger.info(
        "%s / %s — Sayfa 1/%d, %d ürün (bedeninizde)",
        brand, category, total_pages, len(products),
    )
    yield from products

    for page in range(2, total_pages + 1):
        time.sleep(random.uniform(1.0, 2.5))
        url = _build_url(brand, category, page)
        html = _fetch_page(session, url)
        if not html:
            break
        data = _parse_product_list(html)
        if not data:
            break
        page_products = _extract_products(data, user_sizes)
        logger.info(
            "%s / %s — Sayfa %d/%d, %d ürün",
            brand, category, page, total_pages, len(page_products),
        )
        yield from page_products


def scrape_wishlist_url(
    session: requests.Session,
    url: str,
    user_sizes: list[str],
) -> Generator[dict, None, None]:
    """Wishlist'teki belirli bir URL'yi tarar."""
    html = _fetch_page(session, url)
    if not html:
        return
    data = _parse_product_list(html)
    if not data:
        return
    products = _extract_products(data, user_sizes)
    logger.info("Wishlist URL tarandı: %d ürün (bedeninizde)", len(products))
    yield from products


def scrape_all(config: dict) -> list[dict]:
    """
    Config'e göre tüm marka×kategori kombinasyonlarını ve wishlist'i tarar.
    Tüm eşleşen ürünleri döndürür.
    """
    brands: list[str] = config.get("brands", [])
    categories: list[str] = config.get("categories", [])
    wishlist: list[str] = config.get("wishlist") or []

    user_cfg = config.get("user", {})
    sizes_cfg = user_cfg.get("sizes", {})
    user_sizes: list[str] = (
        sizes_cfg.get("letter", []) + sizes_cfg.get("numeric", [])
    )

    session = requests.Session()
    all_products: list[dict] = []

    total_combinations = len(brands) * len(categories)
    logger.info(
        "Tarama başlıyor: %d marka × %d kategori = %d kombinasyon",
        len(brands), len(categories), total_combinations,
    )

    for brand in brands:
        for category in categories:
            try:
                for product in scrape_brand_category(
                    session, brand, category, user_sizes
                ):
                    all_products.append(product)
                # Markalar arası bekleme
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as exc:
                logger.error(
                    "Hata: %s / %s — %s", brand, category, exc
                )

    for wl_url in wishlist:
        try:
            for product in scrape_wishlist_url(session, wl_url, user_sizes):
                all_products.append(product)
        except Exception as exc:
            logger.error("Wishlist URL hatası: %s — %s", wl_url, exc)

    # Tekrarlanan ürünleri filtrele (aynı ürün birden fazla kombinasyonda çıkabilir)
    seen: set[str] = set()
    unique_products: list[dict] = []
    for p in all_products:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique_products.append(p)

    logger.info(
        "Tarama tamamlandı. Toplam %d eşsiz ürün bulundu (bedeninizde).",
        len(unique_products),
    )
    return unique_products

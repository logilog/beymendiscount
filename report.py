"""
Beymen Price Alert Bot — HTML Rapor Üretici
Her kontrol sonunda report.html dosyası üretir.
Tarayıcıda açılarak takip edilen tüm ürünlerin
fiyat geçmişi ve indirim durumu görülebilir.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import database

logger = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).parent / "report.html"

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beymen Price Tracker — Rapor</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
          background: #f0f2f5; color: #1a1a1a; }}
  header {{ background: #1a1a1a; color: #fff; padding: 20px 32px;
            display: flex; align-items: center; justify-content: space-between; }}
  header h1 {{ font-size: 20px; font-weight: 700; }}
  header span {{ font-size: 13px; color: #aaa; }}
  .stats {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .stat {{ background: #fff; border-radius: 8px; padding: 16px 24px;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); flex: 1; min-width: 140px; }}
  .stat .value {{ font-size: 28px; font-weight: 700; color: #c0392b; }}
  .stat .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .filters {{ padding: 0 32px 16px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .filter-btn {{ background: #fff; border: 1px solid #ddd; border-radius: 20px;
                 padding: 6px 16px; font-size: 13px; cursor: pointer;
                 transition: all .15s; }}
  .filter-btn:hover, .filter-btn.active {{ background: #1a1a1a; color: #fff;
                                            border-color: #1a1a1a; }}
  .grid {{ display: grid;
           grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
           gap: 16px; padding: 0 32px 32px; }}
  .card {{ background: #fff; border-radius: 10px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,.08);
           transition: transform .15s, box-shadow .15s; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.12); }}
  .card-img {{ width: 100%; height: 220px; object-fit: cover; background: #f5f5f5;
               display: block; }}
  .card-img-placeholder {{ width: 100%; height: 220px; background: #f0f0f0;
                            display: flex; align-items: center; justify-content: center;
                            font-size: 36px; color: #ccc; }}
  .card-body {{ padding: 14px 16px; }}
  .card-brand {{ font-size: 11px; color: #888; text-transform: uppercase;
                 letter-spacing: .5px; margin-bottom: 4px; }}
  .card-name {{ font-size: 14px; font-weight: 600; margin-bottom: 10px;
                line-height: 1.4; }}
  .card-name a {{ color: #1a1a1a; text-decoration: none; }}
  .card-name a:hover {{ text-decoration: underline; }}
  .card-price {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }}
  .price-current {{ font-size: 20px; font-weight: 700; color: #c0392b; }}
  .price-original {{ font-size: 13px; color: #999; text-decoration: line-through; }}
  .badge-discount {{ background: #c0392b; color: #fff; font-size: 11px;
                     font-weight: 700; padding: 2px 7px; border-radius: 4px; }}
  .badge-low-stock {{ background: #e67e22; color: #fff; font-size: 11px;
                      font-weight: 700; padding: 2px 7px; border-radius: 4px;
                      display: inline-block; margin-bottom: 6px; }}
  .card-sizes {{ font-size: 12px; color: #555; margin-bottom: 6px; }}
  .card-trend {{ font-family: monospace; font-size: 16px; color: #888;
                 letter-spacing: 2px; margin-bottom: 6px; }}
  .card-meta {{ font-size: 11px; color: #bbb; }}
  .history-toggle {{ font-size: 11px; color: #3498db; cursor: pointer;
                     margin-top: 8px; display: inline-block; }}
  .history-table {{ display: none; width: 100%; margin-top: 8px;
                    border-collapse: collapse; font-size: 11px; }}
  .history-table th {{ background: #f5f5f5; padding: 4px 8px; text-align: left;
                       font-weight: 600; color: #555; }}
  .history-table td {{ padding: 4px 8px; border-top: 1px solid #f0f0f0; color: #444; }}
  .no-products {{ padding: 60px 32px; text-align: center; color: #888;
                  font-size: 15px; }}
  @media (max-width: 600px) {{
    .stats {{ padding: 16px; }}
    .grid {{ padding: 0 16px 24px; grid-template-columns: 1fr; }}
    .filters {{ padding: 0 16px 12px; }}
    header {{ padding: 16px; }}
  }}
</style>
</head>
<body>

<header>
  <h1>🏷️ Beymen Price Tracker</h1>
  <span>Son güncelleme: {updated_at}</span>
</header>

<div class="stats">
  <div class="stat">
    <div class="value">{total_products}</div>
    <div class="label">Takip edilen ürün</div>
  </div>
  <div class="stat">
    <div class="value">{discounted_count}</div>
    <div class="label">İndirimli ürün</div>
  </div>
  <div class="stat">
    <div class="value">%{max_discount}</div>
    <div class="label">En yüksek indirim</div>
  </div>
  <div class="stat">
    <div class="value">{low_stock_count}</div>
    <div class="label">Stok azalan ürün</div>
  </div>
</div>

<div class="filters" id="brandFilters">
  <button class="filter-btn active" onclick="filterBrand('all', this)">Tümü</button>
  {brand_buttons}
</div>

<div class="grid" id="productGrid">
  {cards}
</div>

{no_products_msg}

<script>
  function filterBrand(brand, btn) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.card').forEach(card => {{
      card.style.display = (brand === 'all' || card.dataset.brand === brand) ? '' : 'none';
    }});
  }}

  function toggleHistory(id) {{
    const table = document.getElementById('hist-' + id);
    const link = document.getElementById('link-' + id);
    if (table.style.display === 'table') {{
      table.style.display = 'none';
      link.textContent = '▸ Fiyat geçmişini gör';
    }} else {{
      table.style.display = 'table';
      link.textContent = '▾ Gizle';
    }}
  }}
</script>
</body>
</html>
"""

_CARD_TEMPLATE = """
<div class="card" data-brand="{brand_key}">
  {img_tag}
  <div class="card-body">
    <div class="card-brand">{brand}</div>
    <div class="card-name"><a href="{url}" target="_blank">{name}</a></div>
    <div class="card-price">
      <span class="price-current">{current_price} TL</span>
      <span class="price-original">{original_price} TL</span>
      <span class="badge-discount">-%{discount}</span>
    </div>
    {low_stock_badge}
    <div class="card-sizes"><strong>Bedenler:</strong> {sizes}</div>
    <div class="card-trend" title="Fiyat trendi (son kontroller)">{trend}</div>
    <div class="card-meta">
      İlk görülme: {first_seen} &nbsp;|&nbsp; Son kontrol: {last_seen}
    </div>
    {history_section}
  </div>
</div>
"""

_LOW_STOCK_BADGE = '<div class="badge-low-stock">⚡ Son {stock} ürün kaldı!</div>'

_HISTORY_SECTION = """
<span class="history-toggle" id="link-{pid}" onclick="toggleHistory('{pid}')">
  ▸ Fiyat geçmişini gör
</span>
<table class="history-table" id="hist-{pid}">
  <thead>
    <tr><th>Tarih</th><th>Fiyat</th><th>İndirim</th><th>Stok</th></tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
"""

_HISTORY_ROW = (
    "<tr><td>{date}</td><td>{price} TL</td>"
    "<td>%{discount}</td><td>{stock}</td></tr>"
)


def _fmt_price(price) -> str:
    if price is None:
        return "—"
    return f"{float(price):,.0f}".replace(",", ".")


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso[:16]


def _img_tag(image_url: str, name: str) -> str:
    if not image_url:
        return f'<div class="card-img-placeholder">👕</div>'
    import re
    resized = re.sub(r'/mnresize/\d+/\d+/', '/mnresize/400/520/', image_url)
    return f'<img class="card-img" src="{resized}" alt="{name}" loading="lazy">'


def generate_report(low_stock_threshold: int = 3):
    """
    Veritabanındaki tüm ürünleri okuyarak report.html üretir.
    """
    products = database.get_all_products()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    total = len(products)
    discounted = sum(1 for p in products if (p.get("last_discount_rate") or 0) > 0)
    max_discount = max((p.get("last_discount_rate") or 0 for p in products), default=0)
    low_stock_count = sum(
        1 for p in products
        if 0 < int(p.get("stock") or 0) <= low_stock_threshold
    )

    # Marka butonları
    brands = sorted({p["brand"] for p in products if p.get("brand")})
    brand_buttons = "\n".join(
        f'<button class="filter-btn" onclick="filterBrand(\'{b}\', this)">{b}</button>'
        for b in brands
    )

    # Ürün kartları
    cards_html = ""
    for p in products:
        pid = p["id"]
        history = database.get_price_history(pid, limit=10)

        # Trend
        if len(history) >= 2:
            prices = [h["price"] for h in reversed(history[:7])]
            min_p, max_p = min(prices), max(prices)
            bars = " ▁▂▃▄▅▆▇█"
            if max_p == min_p:
                trend = "▄" * len(prices)
            else:
                trend = "".join(
                    bars[round((pr - min_p) / (max_p - min_p) * 8)]
                    for pr in prices
                )
        else:
            trend = ""

        # Stok
        stock = int(p.get("stock") or 0)
        low_stock = 0 < stock <= low_stock_threshold
        low_stock_html = _LOW_STOCK_BADGE.format(stock=stock) if low_stock else ""

        # Bedenler
        sizes_raw = p.get("available_sizes", "[]")
        if isinstance(sizes_raw, str):
            try:
                sizes_list = json.loads(sizes_raw)
            except Exception:
                sizes_list = []
        else:
            sizes_list = sizes_raw or []
        sizes_str = ", ".join(sizes_list) if sizes_list else "—"

        # Fiyat geçmişi tablosu
        hist_rows = "\n".join(
            _HISTORY_ROW.format(
                date=_fmt_dt(h["checked_at"]),
                price=_fmt_price(h["price"]),
                discount=h.get("discount_rate") or 0,
                stock=h.get("stock") or "—",
            )
            for h in history
        )
        history_section = (
            _HISTORY_SECTION.format(pid=pid, rows=hist_rows)
            if history else ""
        )

        cards_html += _CARD_TEMPLATE.format(
            brand_key=p.get("brand", ""),
            img_tag=_img_tag(p.get("image_url", ""), p.get("name", "")),
            brand=p.get("brand", ""),
            name=p.get("name", ""),
            url=p.get("url", "#"),
            current_price=_fmt_price(p.get("last_price")),
            original_price=_fmt_price(p.get("original_price")),
            discount=p.get("last_discount_rate") or 0,
            low_stock_badge=low_stock_html,
            sizes=sizes_str,
            trend=trend,
            first_seen=_fmt_dt(p.get("first_seen")),
            last_seen=_fmt_dt(p.get("last_seen")),
            history_section=history_section,
        )

    no_products_msg = (
        '<div class="no-products">Henüz takip edilen ürün yok.<br>'
        'Botu çalıştırarak ürün taraması başlatın.</div>'
        if not products else ""
    )

    html = _HTML_TEMPLATE.format(
        updated_at=now_str,
        total_products=total,
        discounted_count=discounted,
        max_discount=max_discount,
        low_stock_count=low_stock_count,
        brand_buttons=brand_buttons,
        cards=cards_html,
        no_products_msg=no_products_msg,
    )

    REPORT_PATH.write_text(html, encoding="utf-8")
    logger.info("Rapor güncellendi: %s", REPORT_PATH)

import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# HTML E-POSTA TEMPLATELERİ
# ------------------------------------------------------------------ #

_ALERT_CARD = """
<tr>
  <td style="padding:16px;border-bottom:1px solid #eee;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td width="110" valign="top">
          {img_tag}
        </td>
        <td style="padding-left:16px;" valign="top">
          <p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;">
            {brand}
          </p>
          <p style="margin:0 0 8px;font-size:15px;font-weight:600;color:#1a1a1a;">
            <a href="{url}" style="color:#1a1a1a;text-decoration:none;">{name}</a>
          </p>
          <p style="margin:0 0 6px;">
            <span style="font-size:20px;font-weight:700;color:#c0392b;">{current_price} TL</span>
            &nbsp;
            <span style="font-size:13px;color:#999;text-decoration:line-through;">{original_price} TL</span>
            &nbsp;
            <span style="background:#c0392b;color:#fff;font-size:12px;font-weight:700;
                         padding:3px 8px;border-radius:4px;">-%{discount}
            </span>
          </p>
          <p style="margin:0 0 6px;font-size:12px;color:#555;">
            <strong>Stokta bedenler:</strong> {sizes}
          </p>
          {trend_row}
          <p style="margin:8px 0 0;">
            <a href="{url}"
               style="background:#1a1a1a;color:#fff;padding:8px 18px;
                      border-radius:4px;font-size:13px;text-decoration:none;
                      display:inline-block;">
              Ürüne Git →
            </a>
          </p>
        </td>
      </tr>
    </table>
  </td>
</tr>
"""

_TREND_ROW = """
<p style="margin:0 0 4px;font-size:12px;color:#888;">
  Fiyat trendi (son 7 kontrol): <span style="font-family:monospace;">{trend}</span>
</p>
"""

_ALERT_EMAIL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beymen İndirim Alarmı</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f5f5f5">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;background:#fff;border-radius:8px;
                      overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
          <!-- Header -->
          <tr>
            <td style="background:#1a1a1a;padding:24px 32px;">
              <p style="margin:0;color:#fff;font-size:22px;font-weight:700;">
                🏷️ Beymen İndirim Alarmı
              </p>
              <p style="margin:6px 0 0;color:#aaa;font-size:13px;">
                {date} — {count} ürün bulundu
              </p>
            </td>
          </tr>
          <!-- Products -->
          <table width="100%" cellpadding="0" cellspacing="0">
            {cards}
          </table>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;background:#f9f9f9;border-top:1px solid #eee;">
              <p style="margin:0;font-size:11px;color:#aaa;text-align:center;">
                Bu mail Beymen Price Alert Bot tarafından otomatik gönderilmiştir.<br>
                Bildirimleri durdurmak için botu kapatın.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

_SUMMARY_ROW = """
<tr>
  <td style="padding:12px 16px;border-bottom:1px solid #eee;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <span style="font-size:11px;color:#888;">{brand}</span><br>
          <a href="{url}" style="font-size:14px;font-weight:600;color:#1a1a1a;text-decoration:none;">
            {name}
          </a>
        </td>
        <td align="right" valign="middle">
          <span style="color:#c0392b;font-weight:700;font-size:16px;">
            -%{discount}
          </span><br>
          <span style="font-size:13px;color:#555;">{current_price} TL</span>
        </td>
      </tr>
      <tr>
        <td colspan="2" style="padding-top:4px;font-size:11px;color:#888;">
          Bedenler: {sizes} &nbsp;|&nbsp; Trend: <span style="font-family:monospace;">{trend}</span>
        </td>
      </tr>
    </table>
  </td>
</tr>
"""

_SUMMARY_EMAIL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Beymen Günlük Özet</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f5f5f5">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;background:#fff;border-radius:8px;
                      overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
          <tr>
            <td style="background:#1a1a1a;padding:24px 32px;">
              <p style="margin:0;color:#fff;font-size:22px;font-weight:700;">
                📋 Beymen Günlük Özet
              </p>
              <p style="margin:6px 0 0;color:#aaa;font-size:13px;">
                {date} — Takip edilen {count} indirimli ürün
              </p>
            </td>
          </tr>
          <table width="100%" cellpadding="0" cellspacing="0">
            {rows}
          </table>
          <tr>
            <td style="padding:20px 32px;background:#f9f9f9;border-top:1px solid #eee;">
              <p style="margin:0;font-size:11px;color:#aaa;text-align:center;">
                Beymen Price Alert Bot — Günlük Özet
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


# ------------------------------------------------------------------ #
# YARDIMCI FONKSİYONLAR
# ------------------------------------------------------------------ #

def _fmt_price(price: float | None) -> str:
    if price is None:
        return "—"
    return f"{price:,.0f}".replace(",", ".")


def _img_tag(image_url: str) -> str:
    if not image_url:
        return '<div style="width:100px;height:130px;background:#f0f0f0;border-radius:4px;"></div>'
    # Beymen CDN URL'sini 150x195 boyutuna ayarla
    resized = image_url
    if "mnresize" in image_url:
        import re
        resized = re.sub(r'/mnresize/\d+/\d+/', '/mnresize/150/195/', image_url)
    return (
        f'<img src="{resized}" width="100" height="130" alt="ürün"'
        f' style="border-radius:4px;object-fit:cover;display:block;">'
    )


# ------------------------------------------------------------------ #
# SMTP GÖNDERME
# ------------------------------------------------------------------ #

def _send_email(
    smtp_cfg: dict,
    password: str,
    recipient: str,
    subject: str,
    html_body: str,
):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["sender_email"]
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_cfg["smtp_server"], smtp_cfg["smtp_port"]) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_cfg["sender_email"], password)
        server.sendmail(smtp_cfg["sender_email"], recipient, msg.as_string())

    logger.info("Mail gönderildi → %s | Konu: %s", recipient, subject)


# ------------------------------------------------------------------ #
# ALERT MAİLİ
# ------------------------------------------------------------------ #

def send_alert_email(
    alert_items: list[dict],
    config: dict,
    email_password: str,
):
    """İndirimli ürünler için alert maili gönder."""
    if not alert_items:
        return

    smtp_cfg = config.get("email", {})
    recipient = config.get("user", {}).get("email", "")
    if not recipient:
        logger.error("Kullanıcı e-posta adresi config.yaml'da tanımlı değil!")
        return

    cards_html = ""
    for item in alert_items:
        trend_html = _TREND_ROW.format(trend=item["trend"]) if item.get("trend") else ""
        sizes_str = ", ".join(item.get("matching_sizes") or item.get("available_sizes", []))
        cards_html += _ALERT_CARD.format(
            img_tag=_img_tag(item.get("image_url", "")),
            brand=item.get("brand", ""),
            name=item.get("name", ""),
            url=item.get("url", "#"),
            current_price=_fmt_price(item.get("price")),
            original_price=_fmt_price(
                item.get("ref_original") or item.get("original_price")
            ),
            discount=item.get("discount_rate", 0),
            sizes=sizes_str or "—",
            trend_row=trend_html,
        )

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    html_body = _ALERT_EMAIL_HTML.format(
        date=now_str,
        count=len(alert_items),
        cards=cards_html,
    )

    brands = {item.get("brand", "") for item in alert_items}
    brands_str = ", ".join(sorted(brands))
    subject = (
        f"🏷️ Beymen İndirim: {len(alert_items)} ürün "
        f"(%{config.get('alert', {}).get('min_discount_percent', 30)}+ indirim) — {brands_str}"
    )

    try:
        _send_email(smtp_cfg, email_password, recipient, subject, html_body)
    except Exception as exc:
        logger.error("Alert maili gönderilemedi: %s", exc)
        raise


# ------------------------------------------------------------------ #
# GÜNLÜK ÖZET MAİLİ
# ------------------------------------------------------------------ #

def send_daily_summary(
    products: list[dict],
    config: dict,
    email_password: str,
):
    """Günlük özet mailini gönder."""
    smtp_cfg = config.get("email", {})
    recipient = config.get("user", {}).get("email", "")
    if not recipient:
        logger.error("Kullanıcı e-posta adresi config.yaml'da tanımlı değil!")
        return

    if not products:
        logger.info("Günlük özet: indirimli ürün bulunamadı, mail atlanıyor.")
        return

    rows_html = ""
    for p in products:
        sizes_list = p.get("available_sizes", [])
        if isinstance(sizes_list, str):
            import json as _json
            try:
                sizes_list = _json.loads(sizes_list)
            except Exception:
                sizes_list = []
        rows_html += _SUMMARY_ROW.format(
            brand=p.get("brand", ""),
            name=p.get("name", ""),
            url=p.get("url", "#"),
            discount=p.get("last_discount_rate", 0),
            current_price=_fmt_price(p.get("last_price")),
            sizes=", ".join(sizes_list) if sizes_list else "—",
            trend=p.get("trend", ""),
        )

    now_str = datetime.now().strftime("%d.%m.%Y")
    html_body = _SUMMARY_EMAIL_HTML.format(
        date=now_str,
        count=len(products),
        rows=rows_html,
    )
    subject = f"📋 Beymen Günlük Özet — {now_str}: {len(products)} indirimli ürün"

    try:
        _send_email(smtp_cfg, email_password, recipient, subject, html_body)
    except Exception as exc:
        logger.error("Günlük özet maili gönderilemedi: %s", exc)
        raise

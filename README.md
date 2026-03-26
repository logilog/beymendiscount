# Beymen Price Alert Bot

Beymen.com erkek ürünlerini takip eden, seçtiğin markalar ve kategorilerde **bedenin stokta** olduğunda ve **belirlediğin indirim eşiği** aşıldığında otomatik **Gmail bildirimi** gönderen Python botu.

---

## Özellikler

- **Marka + Kategori Filtresi** — Sadece ilgilendiğin markalar ve kategoriler taranır
- **Beden Takibi** — Hem harf (S/M/L/XL) hem sayısal (40/42/44) beden desteği
- **İndirim Eşiği** — Belirli % altındaki indirimler için bildirim gelmez
- **Akıllı Cooldown** — Aynı ürün için 24 saat içinde tek mail
- **Fiyat Geçmişi** — Her kontrol SQLite'a kaydedilir
- **Fiyat Trendi** — Mailinde son 7 kontrolün Unicode trend grafiği (`▅▄▃▂▁`)
- **Günlük Özet** — Her sabah 09:00'da takip edilen indirimli ürünlerin özeti
- **Wishlist** — Belirli ürün URL'lerini direkt takip et
- **Yeni Ürün Bildirimi** — İsteğe bağlı olarak yeni ürün gelince haber ver
- **Dry-run modu** — Mail atmadan konsola yaz, test et

---

## Kurulum

### 1. Bağımlılıkları kur

```bash
pip install -r requirements.txt
```

### 2. config.yaml'ı düzenle

```bash
# config.yaml dosyasını aç ve şunları doldur:
# - user.email          → Bildirimlerin gideceği adres
# - user.sizes          → Takip edilecek bedenler
# - brands              → Takip edilecek markalar
# - categories          → Takip edilecek kategoriler
# - email.sender_email  → Gönderici Gmail adresi
```

### 3. Gmail App Password al

1. Google Hesabı → Güvenlik → 2 Adımlı Doğrulama (etkinleştir)
2. Güvenlik → Uygulama Şifreleri → Yeni oluştur
3. Oluşturulan 16 karakterli şifreyi kopyala

### 4. .env dosyası oluştur

```bash
echo "EMAIL_PASSWORD=xxxxxxxxxxxx" > .env
```

---

## Kullanım

```bash
# Scheduler modunda başlat (6 saatlik döngü)
python bot.py

# Tek seferlik çalıştır ve mail gönder
python bot.py --test

# Mail atmadan test et (dry-run)
python bot.py --dry-run

# Günlük özet mailini hemen gönder
python bot.py --summary
```

---

## config.yaml Açıklaması

```yaml
user:
  email: "kullanici@gmail.com"     # Alert ve özet mailleri buraya gelir
  sizes:
    letter: ["M", "L"]             # Harf bedenler (giyim)
    numeric: ["42", "44"]          # Sayısal bedenler (pantolon, ayakkabı)

alert:
  min_discount_percent: 30         # Bu % altı indirimler bildirilmez
  check_interval_hours: 6          # Kaç saatte bir kontrol yapılsın
  cooldown_hours: 24               # Aynı ürün için tekrar mail süresi
  daily_summary: true              # Günlük özet aktif mi?
  daily_summary_hour: 9            # Özet saati (09:00)
  notify_new_products: false       # Yeni ürün bildirimi (indirim olmasa bile)

brands:
  - "Stone Island"
  - "Moncler"
  - "Dsquared2"

categories:
  - "TSHIRT"
  - "SWEATSHIRT"
  - "PANTOLON"

wishlist:                          # Belirli ürün URL'leri (opsiyonel)
  # - "https://www.beymen.com/tr/..."

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "gonderen@gmail.com"
```

---

## Dosya Yapısı

```
beymendiscount/
├── bot.py              # Ana giriş + APScheduler
├── scraper.py          # Beymen.com scraping
├── tracker.py          # Fiyat karşılaştırma + alert kararı
├── notifier.py         # Gmail SMTP + HTML mail şablonları
├── database.py         # SQLite CRUD
├── config.yaml         # Kullanıcı ayarları
├── .env                # EMAIL_PASSWORD (git'e ekleme!)
├── .env.example        # Örnek .env
├── requirements.txt
├── beymen_tracker.db   # SQLite veritabanı (otomatik oluşur)
└── beymen_bot.log      # Log dosyası (otomatik oluşur)
```

---

## Bilinen Beymen Kategorileri (Erkek)

| Kategori | Açıklama |
|---|---|
| `TSHIRT` | T-Shirt |
| `POLO YAKA` | Polo Yaka T-Shirt |
| `SWEATSHIRT` | Sweatshirt |
| `PANTOLON` | Pantolon |
| `MONT` | Mont / Kaban |
| `CEKET` | Ceket / Blazer |
| `GOMLEk` | Gömlek |
| `SNEAKER` | Sneaker |
| `AYAKKABI` | Ayakkabı |
| `SAPKA` | Şapka |
| `KEMER` | Kemer |

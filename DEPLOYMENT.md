# راهنمای استقرار پروداکشن

## پیش‌نیازها
- Docker ≥ 24
- Docker Compose ≥ 2.20
- یک سرور لینوکس با حداقل 2 CPU و 4GB RAM
- دسترسی به پنل 3x-ui روی یک یا چند سرور

---

## مراحل استقرار

### ۱. کلون پروژه
```bash
git clone <repo> vpn-platform && cd vpn-platform
```

### ۲. تولید کلیدهای امنیتی
```bash
pip install cryptography
python scripts/generate_keys.py
```
خروجی را در فایل `.env` ذخیره کنید.

### ۳. پیکربندی `.env`
```bash
cp .env.example .env
nano .env
```
موارد اجباری:
- `TELEGRAM_BOT_TOKEN` — از @BotFather
- `TELEGRAM_ADMIN_IDS` — آیدی عددی ادمین‌ها با ویرگول
- `APP_SECRET_KEY`, `APP_ENCRYPTION_KEY`, `JWT_SECRET_KEY` — از مرحله ۲

### ۴. اجرا
```bash
docker compose up -d
```

### ۵. ساخت ادمین اول
```bash
docker compose exec api python scripts/create_admin.py 123456789 "علی احمدی"
```

### ۶. افزودن سرور 3x-ui
ربات تلگرام را باز کنید → `🖥 مدیریت سرورها` → `➕ افزودن سرور`
- آدرس پنل: `http://IP:54321`
- نام کاربری/رمز 3x-ui را وارد کنید
- آیدی Inbound پیش‌فرض را وارد کنید

---

## معماری سرویس‌ها

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                     │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │   API    │  │   Bot    │  │  Worker + Beat   │   │
│  │ FastAPI  │  │ aiogram  │  │    Celery        │   │
│  │ :8000    │  │ polling  │  │  + Scheduler     │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │                 │              │
│  ┌────▼──────────────▼─────────────────▼─────────┐   │
│  │              PostgreSQL + Redis                │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         │
         ▼ HTTPS / API calls
┌─────────────────────┐
│   3x-ui Panel(s)    │
│   Xray Core         │
└─────────────────────┘
```

## مانیتورینگ
- Celery Flower: `http://SERVER_IP:5555`
- API Health: `http://SERVER_IP:8000/health`
- Logs: `docker compose logs -f bot worker api`

## بکاپ
```bash
# بکاپ دیتابیس
docker compose exec postgres pg_dump -U vpnuser vpndb > backup_$(date +%Y%m%d).sql
```

## آپدیت
```bash
git pull
docker compose build --no-cache
docker compose up -d --force-recreate
```

---

## جریان کاری نماینده در تلگرام

```
نماینده /start
    │
    ▼
[پنل نماینده]
    │
    ├── ➕ ساخت اشتراک
    │       ├── نام مشتری را وارد کنید
    │       ├── حجم (GB) را وارد کنید  ← بررسی موجودی
    │       ├── مدت اشتراک انتخاب کنید (30/60/90/180 روز)
    │       ├── تأیید
    │       │
    │       └── ✅ اشتراک ساخته شد
    │               حجم: ۵۰ گیگ
    │               مدت: ۳۰ روز
    │               🔗 vless://...
    │
    ├── 👥 مشتری‌های من  ← ایزوله از نمایندگان دیگر
    ├── 🔄 تمدید اشتراک
    ├── 📊 گزارش فروش
    ├── 💰 اعتبار من
    └── 🔔 اعلان‌ها
```

## امنیت پروداکشن
- هرگز پورت PostgreSQL را expose نکنید
- nginx را با SSL قرار دهید جلوی FastAPI
- `APP_DEBUG=false` در .env
- `docs_url=None` به‌صورت خودکار در production غیرفعال است

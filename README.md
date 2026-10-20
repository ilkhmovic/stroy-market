# ArzonMaterial (stroy-market)

Qurilish materiallari uchun Django marketplace: xaridorlar mahsulot qidiradi va buyurtma beradi, sotuvchilar do'kon ochadi. Interfeys o'zbek, rus va ingliz tillarida. Anora — saytning AI yordamchisi (Gemini; javob bo'lmasa qo'lda yozilgan zaxira).

**Eslatma:** Click/Payme/Uzum, haqiqiy nasiya hamkori, fiskal chek va escrow ulanmagan. Checkout dagi «karta» — kuryerga terminal orqali to'lash. Nasiya arizasi menejerga (sayt bildirishnomasi + ixtiyoriy Telegram) yuboriladi.

## O'rnatish

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # yoki: cp .env.example .env
```

`.env` ichida `SECRET_KEY` ni o'zgartiring. Keyin:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py compilemessages
python manage.py runserver
```

Tarjima `.mo` fayllari repoda bor; `compilemessages` gettext (`msgfmt`) talab qiladi. O'rnatilmagan bo'lsa, mavjud `.mo` fayllar ishlayveradi.

## `.env` o'zgaruvchilari

| O'zgaruvchi | Ma'nosi |
| --- | --- |
| `SECRET_KEY` | Django maxfiy kaliti. `DEBUG=False` da **majburiy**. |
| `DEBUG` | `True` yoki `False`. Productionda `False`. |
| `ALLOWED_HOSTS` | Vergul bilan hostlar. Standart `*` emas. |
| `DATABASE_URL` | Ixtiyoriy. Berilsa shu baza; bo'lmasa SQLite `db.sqlite3`. |
| `GEMINI_API_KEY` | Anora (Gemini) uchun. Bo'sh bo'lsa zaxira javoblar ishlaydi. |
| `TELEGRAM_BOT_TOKEN` | Nasiya arizasini Telegramga yuborish (ixtiyoriy). |
| `TELEGRAM_MANAGER_CHAT_ID` | Menejer chat ID (ixtiyoriy). |
| `ADMIN_URL` | Django admin yo'li, masalan `admin/` yoki yashirin `secret-panel/`. |
| `SUPPORT_PHONE` | Footer telefoni. Bo'sh bo'lsa chiqarilmaydi. |
| `SUPPORT_EMAIL` | Footer email. Bo'sh bo'lsa chiqarilmaydi. |
| `SECURE_SSL_REDIRECT` | `DEBUG=False` da HTTPS ga yo'naltirish. |
| `SESSION_COOKIE_SECURE` | `DEBUG=False` da xavfsiz session cookie. |
| `CSRF_COOKIE_SECURE` | `DEBUG=False` da xavfsiz CSRF cookie. |
| `SECURE_HSTS_SECONDS` | `DEBUG=False` da HSTS (kichik qiymatdan boshlang, masalan `60`). |

PostgreSQL ishlatilsa `psycopg` ni alohida o'rnating (`DATABASE_URL` `postgres://...`).

## Testlar

```bash
python manage.py test
python manage.py check --deploy
```

## Tillar

Manba matn — o'zbekcha. Shablonlarda `{% trans %}`, Python da `gettext` / `gettext_lazy`. Tarjimalar:

- `locale/ru/LC_MESSAGES/django.po`
- `locale/en/LC_MESSAGES/django.po`

Yangi matn qo'shgach:

```bash
# msgids ni yangilash (ixtiyoriy, qo'lda ham qo'shish mumkin)
python manage.py makemessages -l ru -l en
# so'ng .po ni to'ldiring va:
python manage.py compilemessages
```

Mahsulot nomi/tavsifi: `name` / `description` (UZ) va ixtiyoriy `name_ru`, `name_en`, `description_ru`, `description_en`. Ko'rsatish: `display_name`, `display_description`.

## Anora zaxira javoblari

Gemini javob bermasa `AnoraFallback` yozuvlari ishlatiladi (admin: «Anora zaxira javoblari»). Kalit so'zlarni vergul bilan, javoblarni UZ/RU/EN maydonlariga yozing. Mos kelmasa umumiy xabar chiqadi.

Kod: `main/anora_fallback.py`, model: `main/models.py` (`AnoraFallback`).

## Development skriptlari

`scripts/populate_elite_store.py` va `scripts/populate_stats.py` **faqat** `DEBUG=True` da. Productionda ishlatilmasin.

## Xavfsizlik eslatmasi

Git tarixida avval commit qilingan kalitlar (masalan SSH) diskdan `git rm --cached` bilan chiqarilgan bo'lsa ham **eski commitlarda qoladi**. Kalitlarni almashtiring va kerak bo'lsa tarixni alohida tozalang (`git filter-repo` yoki BFG). Bu qadamni hosting egasi qiladi.

## Smeta va hisoblagich (Anora)
Anora oynasida xaridor smeta (PDF/rasm) yuklaydi yoki o'lchamlarni yozadi. Gemini faqat ish turi va
o'lchamlarni ajratadi, miqdorlarni `main/estimator.py` dagi aniq formulalar hisoblaydi (hovuz, beton pol,
devor, shtukaturka, bo'yoq, plitka, laminat, poydevor, tom, to'siq). Qolgan obyektlar uchun AI taxmini
"tekshiring" belgisi bilan ko'rsatiladi. Kerakli miqdor mahsulot birligiga aylantiriladi (630 kg sement ->
"Sement 50 kg" qopidan 13 ta). Tahlil soatiga 6 marta bilan cheklangan, fayl turi baytlari bo'yicha tekshiriladi.

## Statik sahifalar, aloqa, kesh
- "Biz haqimizda", yetkazib berish, qaytarish, shartlar, maxfiylik, savol-javob: `/admin/` dagi "Sahifalar" (uch tilda).
- Footerdagi telefon/email: `SUPPORT_PHONE`, `SUPPORT_EMAIL` (.env). Bo'sh bo'lsa ko'rsatilmaydi.
- Rate limit fayl keshida (`.cache/`, `CACHE_DIR` bilan o'zgartiriladi): bir nechta ishchi jarayon uchun umumiy.

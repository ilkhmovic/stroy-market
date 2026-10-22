# installments

Nasiya hamkorlari (logo, muddat, ustama foiz), mijoz kartalari va hisob, sotuvchi uchun sana bo'yicha Excel.

- Admin: Django admin (`/admin/`) -> "Nasiya hamkorlari" va "Mijoz kartalari" (To'ldirish havolasi).
- Do'kon: mahsulot qo'shish/tahrirlash formasida hamkorlarni belgilaydi.
- Mijoz: mahsulot sahifasida hamkor va oyni tanlab narxni ko'radi; checkoutda nasiya yoki karta hisobidan to'laydi.
- Sotuvchi: menyudagi "Nasiya arizalari" -> sanani tanlab Excel yuklaydi.

Kerak: `pip install openpyxl pillow`, so'ng `python manage.py migrate`.

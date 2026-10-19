"""Email sozlamalarini tekshirish va xato sababini aniq ko'rsatish.

    python manage.py test_email sizning@gmail.com
"""
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


def explain(exc):
    """Xatoga mos aniq maslahat."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ("Login/parol rad etildi. Gmail bo'lsa: oddiy parol ISHLAMAYDI. Google akkaunt -> Xavfsizlik -> "
                "2 bosqichli tasdiqlashni yoqing -> 'App passwords' dan 16 belgili parol oling va "
                "EMAIL_HOST_PASSWORD ga qo'ying. EMAIL_HOST_USER to'liq manzil bo'lsin (name@gmail.com).")
    if isinstance(exc, (ConnectionRefusedError, smtplib.SMTPConnectError)):
        return ("Serverga ulanib bo'lmadi. EMAIL_HOST/EMAIL_PORT to'g'riligini tekshiring (Gmail: smtp.gmail.com, 587). "
                "Agar EMAIL_HOST sozlanmagan bo'lsa Django localhost:25 ga urinadi - aynan shu xato chiqadi.")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return ("Vaqt tugadi. Ehtimol hosting/provayder SMTP portini (25/465/587) bloklagan. "
                "Render/Railway/PythonAnywhere(bepul) kabi joylarda SMTP yopiq bo'ladi: HTTPS API ishlatadigan "
                "xizmatlarga (Resend, Brevo, SendGrid) o'ting.")
    if isinstance(exc, socket.gaierror):
        return "EMAIL_HOST nomi noto'g'ri yoki internet yo'q (DNS topilmadi)."
    if isinstance(exc, (ssl.SSLError, smtplib.SMTPServerDisconnected)):
        return ("TLS/SSL nomuvofiq. 587 port -> EMAIL_USE_TLS=True, EMAIL_USE_SSL=False. "
                "465 port -> EMAIL_USE_SSL=True (EMAIL_PORT=465).")
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return ("Server login (AUTH) ni qabul qilmayapti: ulanish shifrlanmagan. 587 port uchun EMAIL_USE_TLS=True, "
                "465 port uchun EMAIL_USE_SSL=True bo'lishi kerak.")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "Yuboruvchi manzil (DEFAULT_FROM_EMAIL) rad etildi. U EMAIL_HOST_USER bilan bir xil bo'lishi kerak."
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Qabul qiluvchi manzil rad etildi. Manzilni tekshiring."
    return "Noma'lum xato. Yuqoridagi xato matnini tekshiring."


class Command(BaseCommand):
    help = "Test xat yuboradi va muammo sababini tushuntiradi."

    def add_arguments(self, parser):
        parser.add_argument('to', help="Xat boradigan email manzil")

    def handle(self, *args, **opts):
        s = settings
        self.stdout.write("Email sozlamalari:")
        self.stdout.write(f"  backend : {s.EMAIL_BACKEND}")
        self.stdout.write(f"  host    : {s.EMAIL_HOST}:{s.EMAIL_PORT}  (TLS={s.EMAIL_USE_TLS}, SSL={s.EMAIL_USE_SSL})")
        self.stdout.write(f"  user    : {s.EMAIL_HOST_USER or '(bo`sh)'}")
        self.stdout.write(f"  parol   : {'berilgan (' + str(len(s.EMAIL_HOST_PASSWORD)) + ' belgi)' if s.EMAIL_HOST_PASSWORD else '(bo`sh)'}")
        self.stdout.write(f"  from    : {s.DEFAULT_FROM_EMAIL}")
        if 'console' in s.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING(
                "\nEMAIL_HOST_USER/EMAIL_HOST_PASSWORD bo'sh, shuning uchun xat HAQIQATDA yuborilmaydi, "
                "terminalga chop etiladi. .env faylini to'ldiring.\n"))
        try:
            n = send_mail("ArzonMaterial: test xat", "Email sozlamalari to'g'ri ishlayapti.",
                          s.DEFAULT_FROM_EMAIL, [opts['to']], fail_silently=False)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\nYuborilmadi: {type(exc).__name__}: {exc}"))
            raise CommandError("Sabab: " + explain(exc))
        if 'console' in s.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING("\nXat terminalga chop etildi (haqiqiy yuborilmadi)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nYuborildi ({n}). Pochta qutingizni (Spam papkasini ham) tekshiring."))

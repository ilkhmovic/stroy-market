"""Baza jadvallari modellarga mosligini tekshiradi.

Misol xatolar:  NOT NULL constraint failed: main_user.stir_verified
                NOT NULL constraint failed: main_orderitem.unit
Bu bazada kodda yo'q ustun borligini bildiradi (baza boshqa versiya kodidan qolgan).

  python manage.py schema_doctor          # faqat tekshiradi
  python manage.py schema_doctor --drop   # ortiqcha ustunlarni o'chiradi (boshqa ma'lumotlar saqlanadi)
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Baza ustunlarini modellar bilan solishtiradi (ortiqcha va yetishmayotgan ustunlar)."

    def add_arguments(self, parser):
        parser.add_argument('--drop', action='store_true',
                            help="Modelda yo'q ortiqcha ustunlarni bazadan o'chiradi.")

    def handle(self, *args, **opts):
        qn = connection.ops.quote_name
        tables = set(connection.introspection.table_names())
        problems = 0
        with connection.cursor() as cursor:
            for model in apps.get_app_config('main').get_models():
                table = model._meta.db_table
                if table not in tables:
                    self.stdout.write(self.style.ERROR(f"[{table}] jadval yo'q -> `python manage.py migrate` kerak"))
                    problems += 1
                    continue
                db_cols = {c.name: c for c in connection.introspection.get_table_description(cursor, table)}
                model_cols = {f.column for f in model._meta.local_concrete_fields}
                for col in sorted(set(db_cols) - model_cols):
                    problems += 1
                    null = 'NULL bo\'lishi mumkin' if db_cols[col].null_ok else 'NOT NULL (xatoga sabab bo\'ladi!)'
                    self.stdout.write(self.style.WARNING(f"[{table}] bazada ortiqcha ustun: {col}  -- {null}"))
                    if opts['drop']:
                        try:
                            cursor.execute(f"ALTER TABLE {qn(table)} DROP COLUMN {qn(col)}")
                            self.stdout.write(self.style.SUCCESS(f"    o'chirildi: {table}.{col}"))
                        except Exception as exc:
                            self.stdout.write(self.style.ERROR(f"    o'chirib bo'lmadi: {exc}"))
                for col in sorted(model_cols - set(db_cols)):
                    problems += 1
                    self.stdout.write(self.style.ERROR(f"[{table}] bazada yetishmaydi: {col} -> `python manage.py migrate` kerak"))
        if not problems:
            self.stdout.write(self.style.SUCCESS("Baza modellarga to'liq mos."))

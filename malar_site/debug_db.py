import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'malar_site.settings')
django.setup()

from malar_app.models import Product, Category, Stock

print("=== Database Debug Info ===")
print(f"Total Products: {len(list(Product.objects.all()))}")
print(f"Total Categories: {len(list(Category.objects.all()))}")
print(f"Total Stock Records: {len(list(Stock.objects.all()))}")

products = list(Product.objects.all())
print(f"\nFirst 3 products:")
for p in products[:3]:
    print(f"  - {p.name} (SKU: {p.sku}, Active: {p.is_active})")

categories = list(Category.objects.all())
print(f"\nFirst 3 categories:")
for c in categories[:3]:
    print(f"  - {c.name}")

stocks = list(Stock.objects.all())
print(f"\nFirst 3 stocks:")
for s in stocks[:3]:
    print(f"  - {s.product.name}: {s.quantity} units")

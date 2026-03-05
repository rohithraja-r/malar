from django.contrib import admin
from .models import Category, Product, ProductImage, Stock

# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']


class ProductImageInline(admin.TabularInline):
    """Inline admin for product images"""
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary']
    readonly_fields = ['created_at']


class StockInline(admin.StackedInline):
    """Inline admin for product stock"""
    model = Stock
    extra = 0
    fields = ['quantity', 'warehouse_location', 'reorder_level', 'last_updated']
    readonly_fields = ['last_updated']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'price', 'category', 'get_stock_quantity', 'is_active', 'created_at']
    search_fields = ['name', 'sku', 'description']
    list_filter = ['is_active', 'category', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProductImageInline, StockInline]
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'sku', 'description')
        }),
        ('Pricing & Category', {
            'fields': ('price', 'category')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_stock_quantity(self, obj):
        try:
            return obj.stock.quantity
        except:
            return 'N/A'
    get_stock_quantity.short_description = 'Stock Quantity'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at', 'product__category']
    search_fields = ['product__name', 'alt_text']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Image Information', {
            'fields': ('product', 'image', 'alt_text')
        }),
        ('Settings', {
            'fields': ('is_primary',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'reorder_level', 'is_low_stock', 'warehouse_location', 'last_updated']
    list_filter = ['last_updated', 'warehouse_location']
    search_fields = ['product__name', 'product__sku', 'warehouse_location']
    readonly_fields = ['last_updated']
    fieldsets = (
        ('Product & Location', {
            'fields': ('product', 'warehouse_location')
        }),
        ('Stock Levels', {
            'fields': ('quantity', 'reorder_level')
        }),
        ('Metadata', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )
    
    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock?'


from django import forms
from .models import Product, Stock, Category, ProductImage, Customer, Invoice, InvoiceLineItem
import csv
from io import StringIO


class StockUpdateForm(forms.ModelForm):
    """Form to update stock quantity"""
    action = forms.ChoiceField(
        choices=[
            ('add', 'Add Stock'),
            ('remove', 'Remove Stock'),
            ('set', 'Set Stock (Exact Amount)'),
        ],
        label='Action',
        help_text='Select whether to add, remove, or set exact quantity'
    )
    quantity_change = forms.IntegerField(
        min_value=0,
        label='Quantity',
        help_text='Amount to add/remove or exact quantity to set'
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='Notes',
        help_text='Reason for stock change (optional)'
    )
    
    class Meta:
        model = Stock
        fields = ['quantity', 'warehouse_location', 'reorder_level']


class ProductBulkImportForm(forms.Form):
    """Form for bulk importing products via CSV"""
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload CSV with columns: name, description, sku, price, category_name, quantity'
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check file size
        if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("File size should not exceed 5MB")
        
        # Verify it's a CSV
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError("Only CSV files are allowed")
        
        return csv_file


class InventoryReportForm(forms.Form):
    """Form for generating inventory reports"""
    REPORT_TYPE_CHOICES = [
        ('all', 'All Products'),
        ('low_stock', 'Low Stock Items'),
        ('category', 'By Category'),
        ('inactive', 'Inactive Products'),
    ]
    
    EXPORT_FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        label='Report Type',
        widget=forms.RadioSelect()
    )
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMAT_CHOICES,
        label='Export Format',
        widget=forms.RadioSelect()
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='-- Select Category --',
        label='Category (if applicable)'
    )


class CustomProductForm(forms.ModelForm):
    """Enhanced product creation form"""
    images = forms.FileField(
        required=False,
        label='Product Images',
        help_text='You can select multiple images',
    )
    initial_stock = forms.IntegerField(
        required=False,
        min_value=0,
        label='Initial Stock Quantity',
        help_text='Stock quantity when creating product'
    )
    warehouse_location = forms.CharField(
        required=False,
        max_length=200,
        label='Warehouse Location',
        help_text='e.g., Aisle A, Shelf 3'
    )
    reorder_level = forms.IntegerField(
        initial=10,
        min_value=0,
        label='Reorder Level',
        help_text='Alert when stock falls below this'
    )
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'sku', 'price', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Product Description'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU-001'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CustomerForm(forms.ModelForm):
    """Form for creating and editing customers"""
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'city', 'state', 'postal_code', 'country', 'company_name', 'gst_number', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'customer@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXXXXXXX'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Street Address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State/Province'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal Code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name (Optional)'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GST Number (Optional)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InvoiceForm(forms.ModelForm):
    """Form for creating invoices"""
    class Meta:
        model = Invoice
        fields = ['customer', 'due_date', 'tax_percentage', 'notes']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tax_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '18', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Invoice notes...'}),
        }


class InvoiceLineItemForm(forms.ModelForm):
    """Form for invoice line items"""
    class Meta:
        model = InvoiceLineItem
        fields = ['product', 'quantity', 'unit_price']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
        }
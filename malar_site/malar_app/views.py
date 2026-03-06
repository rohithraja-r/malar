from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from decimal import Decimal
from .models import Product, Category, Stock, StockHistory, ProductImage, Customer, Invoice, InvoiceLineItem
from .forms import StockUpdateForm, ProductBulkImportForm, InventoryReportForm, CustomProductForm, CustomerForm, InvoiceForm, InvoiceLineItemForm
import csv
from io import StringIO, TextIOWrapper, BytesIO
from datetime import datetime, timedelta
from django.utils import timezone
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors

# ===== AUTHENTICATION VIEWS =====

class CustomLoginView(LoginView):
    """Custom login view with Bootstrap styling"""
    template_name = 'malar_app/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirect to admin dashboard after login"""
        return reverse_lazy('admin:index')


class CustomLogoutView(LogoutView):
    """Custom logout view"""
    next_page = 'malar_app:home'


# Create your views here.

class HomeView(TemplateView):
    """Welcome/home page with inventory statistics"""
    template_name = 'malar_app/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_products'] = Product.objects.filter(is_active=True).count()
        context['total_categories'] = Category.objects.count()
        # Use database-level comparison instead of property filter
        context['low_stock_products'] = Stock.objects.filter(quantity__lte=F('reorder_level')).count()
        context['total_inventory_value'] = sum([
            p.price * (p.stock.quantity if hasattr(p, 'stock') else 0)
            for p in Product.objects.all()
        ])
        context['featured_products'] = Product.objects.filter(is_active=True)[:6]
        context['categories'] = Category.objects.all()
        return context


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to require user to be admin or staff"""
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# ===== ADMIN DASHBOARD VIEW =====

class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Comprehensive admin dashboard with all KPIs and metrics"""
    template_name = 'malar_app/admin_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # ===== SALES & REVENUE METRICS =====
        all_invoices = Invoice.objects.all()
        completed_invoices = all_invoices.filter(status=Invoice.COMPLETED)
        
        # Total revenue (completed invoices only)
        total_revenue = completed_invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        monthly_revenue = completed_invoices.filter(invoice_date__gte=thirty_days_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        yearly_revenue = completed_invoices.filter(invoice_date__gte=year_start).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        context['total_revenue'] = float(total_revenue)
        context['monthly_revenue'] = float(monthly_revenue)
        context['yearly_revenue'] = float(yearly_revenue)
        
        # Order metrics
        context['total_orders'] = completed_invoices.count()
        context['monthly_orders'] = completed_invoices.filter(invoice_date__gte=thirty_days_ago).count()
        
        # Average order value
        if context['total_orders'] > 0:
            context['avg_order_value'] = float(total_revenue / context['total_orders'])
        else:
            context['avg_order_value'] = 0
        
        # ===== INVENTORY METRICS =====
        all_stocks = Stock.objects.all()
        
        # Total inventory items count
        context['total_items'] = all_stocks.aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        # Low stock items
        context['low_stock_count'] = all_stocks.filter(quantity__lte=F('reorder_level')).count()
        
        # Total inventory value
        context['total_inventory_value'] = float(sum([
            s.quantity * s.product.price for s in all_stocks
        ]))
        
        # Out of stock items
        context['out_of_stock_count'] = all_stocks.filter(quantity=0).count()
        
        # ===== CUSTOMER METRICS =====
        all_customers = Customer.objects.all()
        context['total_customers'] = all_customers.count()
        context['active_customers'] = all_customers.filter(is_active=True).count()
        
        # New customers (last 30 days)
        context['new_customers_count'] = all_customers.filter(created_at__gte=thirty_days_ago).count()
        
        # Top customers by revenue
        top_customers = Customer.objects.annotate(
            total_spent=Sum('invoices__total_amount')
        ).filter(invoices__status=Invoice.COMPLETED).order_by('-total_spent')[:5]
        context['top_customers'] = top_customers
        
        # ===== INVOICE/ORDER METRICS =====
        context['pending_invoices'] = all_invoices.filter(status=Invoice.PENDING).count()
        context['completed_invoices'] = completed_invoices.count()
        context['cancelled_invoices'] = all_invoices.filter(status=Invoice.CANCELLED).count()
        
        # Overdue invoices
        context['overdue_invoices'] = all_invoices.filter(
            status=Invoice.PENDING,
            due_date__lt=now.date()
        ).count()
        
        # ===== PRODUCT METRICS =====
        all_products = Product.objects.all()
        context['total_products'] = all_products.count()
        context['active_products'] = all_products.filter(is_active=True).count()
        context['inactive_products'] = all_products.filter(is_active=False).count()
        
        # Top selling products (by quantity sold in last 30 days)
        top_products = Product.objects.filter(
            invoiceitems__invoice__status=Invoice.COMPLETED,
            invoiceitems__invoice__invoice_date__gte=thirty_days_ago
        ).annotate(
            total_sold=Sum('invoiceitems__quantity')
        ).order_by('-total_sold')[:5]
        context['top_selling_products'] = top_products
        
        # ===== RECENT ACTIVITIES =====
        recent_stock_changes = StockHistory.objects.select_related('stock', 'performed_by').order_by('-created_at')[:10]
        context['recent_activities'] = recent_stock_changes
        
        # ===== CATEGORY BREAKDOWN =====
        categories = Category.objects.annotate(product_count=Count('products'))
        context['category_labels'] = [cat.name for cat in categories]
        context['category_data'] = [cat.product_count for cat in categories]
        
        # ===== METRICS FOR CHARTS =====
        # Revenue trend (last 7 days)
        revenue_trend = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            daily_revenue = completed_invoices.filter(
                invoice_date__date=day.date()
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            revenue_trend.append(float(daily_revenue))
        
        context['revenue_trend_labels'] = [
            (now - timedelta(days=i)).strftime('%a') for i in range(6, -1, -1)
        ]
        context['revenue_trend_data'] = revenue_trend
        
        # Stock status breakdown
        context['stock_in_stock'] = all_stocks.filter(quantity__gt=0).count()
        context['stock_low_stock'] = all_stocks.filter(
            quantity__lte=F('reorder_level'),
            quantity__gt=0
        ).count()
        context['stock_out_of_stock'] = all_stocks.filter(quantity=0).count()
        
        return context


class ProductListView(ListView):
    """View to display all products in inventory"""
    model = Product
    template_name = 'malar_app/product_list.html'
    context_object_name = 'products'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related('category')
        
        # Filter by category if provided
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search by name or SKU
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(sku__icontains=search)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['selected_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class ProductDetailView(DetailView):
    """View to display detailed product information with all images"""
    model = Product
    template_name = 'malar_app/product_detail.html'
    context_object_name = 'product'
    slug_field = 'sku'
    slug_url_kwarg = 'sku'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        context['images'] = product.images.all()
        context['primary_image'] = product.images.filter(is_primary=True).first()
        try:
            context['stock'] = product.stock
        except Stock.DoesNotExist:
            context['stock'] = None
        return context


class ProductCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """View to create a new product (admin only)"""
    model = Product
    template_name = 'malar_app/product_form.html'
    fields = ['name', 'description', 'sku', 'price', 'category', 'is_active']
    success_url = reverse_lazy('malar_app:product-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create empty stock entry
        Stock.objects.get_or_create(product=self.object)
        return response


class ProductUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """View to update product information (admin only)"""
    model = Product
    template_name = 'malar_app/product_form.html'
    fields = ['name', 'description', 'sku', 'price', 'category', 'is_active']
    slug_field = 'sku'
    slug_url_kwarg = 'sku'
    
    def get_success_url(self):
        return reverse_lazy('malar_app:product-detail', kwargs={'sku': self.object.sku})


class ProductDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete a product (admin only)"""
    model = Product
    template_name = 'malar_app/confirm_delete.html'
    success_url = reverse_lazy('malar_app:product-list')
    slug_field = 'sku'
    slug_url_kwarg = 'sku'


class CategoryListView(ListView):
    """View to list all categories"""
    model = Category
    template_name = 'malar_app/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """View to create a new category"""
    model = Category
    fields = ['name', 'description']
    template_name = 'malar_app/category_form.html'
    success_url = reverse_lazy('malar_app:category-list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Category '{self.object.name}' created successfully!")
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """View to update category"""
    model = Category
    fields = ['name', 'description']
    template_name = 'malar_app/category_form.html'
    success_url = reverse_lazy('malar_app:category-list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Category '{self.object.name}' updated successfully!")
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete category"""
    model = Category
    template_name = 'malar_app/category_confirm_delete.html'
    success_url = reverse_lazy('malar_app:category-list')


# ===== NEW CUSTOM VIEWS =====

class StockManagementView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """View to manage stock - add, remove, or adjust quantities"""
    template_name = 'malar_app/stock_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.select_related('category', 'stock').filter(is_active=True)
        context['low_stock_items'] = Stock.objects.filter(quantity__lte=F('reorder_level')).select_related('product')
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle stock update"""
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')
        quantity = int(request.POST.get('quantity', 0))
        
        try:
            product = Product.objects.get(id=product_id)
            stock = product.stock
            previous_quantity = stock.quantity
            
            if action == 'add':
                stock.quantity += quantity
                change = quantity
            elif action == 'remove':
                change = min(quantity, stock.quantity)
                stock.quantity = max(0, stock.quantity - quantity)
            elif action == 'set':
                change = quantity - stock.quantity
                stock.quantity = quantity
            
            stock.save()
            
            StockHistory.objects.create(
                stock=stock,
                quantity_change=change,
                previous_quantity=previous_quantity,
                new_quantity=stock.quantity,
                action=action,
                notes=request.POST.get('notes', ''),
                performed_by=request.user if request.user.is_authenticated else None
            )
            
            messages.success(request, f"✅ Stock updated for {product.name}")
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
        
        return redirect('malar_app:stock-management')


class AnalyticsDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Analytics dashboard with charts and metrics"""
    template_name = 'malar_app/analytics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Basic metrics
        all_products = Product.objects.all()
        active_products = all_products.filter(is_active=True)
        
        context['total_products'] = all_products.count()
        context['active_products'] = active_products.count()
        context['inactive_products'] = all_products.filter(is_active=False).count()
        context['total_categories'] = Category.objects.count()
        
        # Stock metrics
        stocks = Stock.objects.all()
        context['total_stock_value'] = sum([
            s.quantity * s.product.price for s in stocks
        ])
        context['total_items_in_stock'] = stocks.aggregate(Sum('quantity'))['quantity__sum'] or 0
        context['low_stock_count'] = stocks.filter(quantity__lte=F('reorder_level')).count()
        
        # Top products
        context['top_products'] = Product.objects.all()[:5]
        
        # Category breakdown
        categories = Category.objects.annotate(product_count=Count('products')).filter(product_count__gt=0)
        context['category_data'] = json.dumps({
            'labels': [cat.name for cat in categories],
            'data': [cat.product_count for cat in categories]
        })
        
        # Stock status breakdown
        context['stock_status'] = {
            'in_stock': Stock.objects.filter(quantity__gt=0).count(),
            'low_stock': Stock.objects.filter(quantity__lte=F('reorder_level')).count(),
            'out_of_stock': Stock.objects.filter(quantity=0).count(),
        }
        
        return context


class ProductImportView(LoginRequiredMixin, AdminRequiredMixin, View):
    """View for bulk importing products from CSV"""
    template_name = 'malar_app/product_import.html'
    
    def get(self, request):
        form = ProductBulkImportForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = ProductBulkImportForm(request.POST, request.FILES)
        
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            success_count = 0
            error_count = 0
            errors = []
            
            try:
                # Read CSV
                decoded_file = csv_file.read().decode('utf-8')
                csv_reader = csv.DictReader(StringIO(decoded_file))
                
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        # Get or create category
                        category, _ = Category.objects.get_or_create(
                            name=row['category_name'],
                            defaults={'description': ''}
                        )
                        
                        # Create product
                        product = Product.objects.create(
                            name=row['name'],
                            description=row.get('description', ''),
                            sku=row['sku'],
                            price=Decimal(row['price']),
                            category=category,
                            is_active=True
                        )
                        
                        # Create stock entry
                        quantity = int(row.get('quantity', 0))
                        Stock.objects.create(
                            product=product,
                            quantity=quantity,
                            reorder_level=10
                        )
                        
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {row_num}: {str(e)}")
                
                messages.success(request, f"✅ Imported {success_count} products successfully!")
                if errors:
                    messages.warning(request, f"⚠️ {error_count} rows failed: {', '.join(errors[:5])}")
                    
            except Exception as e:
                messages.error(request, f"❌ CSV Error: {str(e)}")
        else:
            messages.error(request, "❌ Invalid form submission")
        
        return redirect('product-import')


class InventoryReportView(LoginRequiredMixin, AdminRequiredMixin, View):
    """Generate inventory reports in PDF or CSV"""
    template_name = 'malar_app/inventory_report.html'
    
    def get(self, request):
        form = InventoryReportForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = InventoryReportForm(request.POST)
        
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            export_format = form.cleaned_data['export_format']
            
            # Get data based on report type
            if report_type == 'all':
                products = Product.objects.all()
            elif report_type == 'low_stock':
                products = Product.objects.filter(stock__quantity__lte=F('stock__reorder_level'))
            elif report_type == 'category':
                category = form.cleaned_data.get('category')
                products = Product.objects.filter(category=category)
            elif report_type == 'inactive':
                products = Product.objects.filter(is_active=False)
            else:
                products = Product.objects.all()
            
            if export_format == 'csv':
                return self.generate_csv(products)
            elif export_format == 'pdf':
                return self.generate_pdf(products)
        
        return redirect('inventory-report')
    
    def generate_csv(self, products):
        """Generate CSV report"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="inventory_report_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Product Name', 'SKU', 'Category', 'Price', 'Stock Quantity', 'Warehouse Location', 'Status'])
        
        for product in products:
            try:
                stock = product.stock
                qty = stock.quantity
                location = stock.warehouse_location
            except:
                qty = 'N/A'
                location = 'N/A'
            
            writer.writerow([
                product.name,
                product.sku,
                product.category.name,
                product.price,
                qty,
                location,
                'Active' if product.is_active else 'Inactive'
            ])
        
        return response
    
    def generate_pdf(self, products):
        """Generate PDF report (requires reportlab)"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="inventory_report_{datetime.now().strftime("%Y%m%d")}.pdf"'
            
            doc = SimpleDocTemplate(response, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph(f"<b>Inventory Report - {datetime.now().strftime('%Y-%m-%d')}</b>", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 0.3*inch))
            
            # Table data
            data = [['Product Name', 'SKU', 'Category', 'Price', 'Stock', 'Location', 'Status']]
            for product in products:
                try:
                    stock = product.stock
                    qty = stock.quantity
                    location = stock.warehouse_location
                except:
                    qty = 'N/A'
                    location = 'N/A'
                
                data.append([
                    product.name[:20],
                    product.sku,
                    product.category.name[:15],
                    f"${product.price}",
                    str(qty),
                    location[:20],
                    'Active' if product.is_active else 'Inactive'
                ])
            
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(table)
            
            doc.build(story)
            return response
        except ImportError:
            messages.error(request, "❌ PDF export requires reportlab. Install it: pip install reportlab")
            return redirect('inventory-report')


class CustomProductFormView(LoginRequiredMixin, AdminRequiredMixin, View):
    """Enhanced product creation with images and stock"""
    template_name = 'malar_app/custom_product_form.html'
    
    def get(self, request):
        form = CustomProductForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = CustomProductForm(request.POST, request.FILES)
        
        if form.is_valid():
            product = form.save(commit=False)
            product.save()
            
            # Create stock entry
            initial_stock = form.cleaned_data.get('initial_stock', 0)
            warehouse_location = form.cleaned_data.get('warehouse_location', '')
            reorder_level = form.cleaned_data.get('reorder_level', 10)
            
            Stock.objects.get_or_create(
                product=product,
                defaults={
                    'quantity': initial_stock,
                    'warehouse_location': warehouse_location,
                    'reorder_level': reorder_level
                }
            )
            
            # Handle multiple image uploads
            files = request.FILES.getlist('images')
            for i, image_file in enumerate(files):
                is_primary = (i == 0)  # First image is primary
                ProductImage.objects.create(
                    product=product,
                    image=image_file,
                    is_primary=is_primary
                )
            
            messages.success(request, f"✅ Product '{product.name}' created successfully!")
            return redirect('malar_app:product-detail', sku=product.sku)
        
        return render(request, self.template_name, {'form': form})

# ===== CUSTOMER MANAGEMENT VIEWS =====

class CustomerListView(LoginRequiredMixin, ListView):
    """View to display all customers"""
    model = Customer
    template_name = 'malar_app/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Customer.objects.all()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(email__icontains=search)
        return queryset


class CustomerDetailView(LoginRequiredMixin, DetailView):
    """View to display single customer details"""
    model = Customer
    template_name = 'malar_app/customer_detail.html'
    context_object_name = 'customer'
    pk_url_kwarg = 'pk'


class CustomerCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """View to create a new customer"""
    model = Customer
    form_class = CustomerForm
    template_name = 'malar_app/customer_form.html'
    success_url = reverse_lazy('malar_app:customer-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"✅ Customer '{self.object.name}' created successfully!")
        return response


class CustomerUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """View to update customer details"""
    model = Customer
    form_class = CustomerForm
    template_name = 'malar_app/customer_form.html'
    pk_url_kwarg = 'pk'
    success_url = reverse_lazy('malar_app:customer-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"✅ Customer '{self.object.name}' updated successfully!")
        return response


class CustomerDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete a customer"""
    model = Customer
    template_name = 'malar_app/customer_confirm_delete.html'
    pk_url_kwarg = 'pk'
    success_url = reverse_lazy('malar_app:customer-list')


# ===== INVOICE MANAGEMENT VIEWS =====

class InvoiceListView(LoginRequiredMixin, ListView):
    """View to display all invoices"""
    model = Invoice
    template_name = 'malar_app/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Invoice.objects.select_related('customer')
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(invoice_number__icontains=search) | queryset.filter(customer__name__icontains=search)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """View to display single invoice"""
    model = Invoice
    template_name = 'malar_app/invoice_detail.html'
    context_object_name = 'invoice'
    pk_url_kwarg = 'pk'


class InvoiceDetailPDFView(LoginRequiredMixin, DetailView):
    """View to download invoice as PDF"""
    model = Invoice
    pk_url_kwarg = 'pk'
    
    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Title
        elements.append(Paragraph("INVOICE", title_style))
        
        # Invoice header info
        header_data = [
            ['Invoice #:', invoice.invoice_number, 'Invoice Date:', invoice.invoice_date.strftime('%b %d, %Y')],
            ['Due Date:', invoice.due_date.strftime('%b %d, %Y') if invoice.due_date else 'N/A', 'Status:', invoice.get_status_display().upper()],
        ]
        header_table = Table(header_data)
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Customer and Company info
        customer_data = [
            ['Bill To:', 'Invoice From:'],
            [f"{invoice.customer.name}\n{invoice.customer.get_full_address()}\nEmail: {invoice.customer.email}\nPhone: {invoice.customer.phone}", 
             'Inventory Management System\nInventory Pro'],
        ]
        customer_table = Table(customer_data, colWidths=[3.5*inch, 3*inch])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(customer_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Line items table
        items_data = [['Product', 'SKU', 'Quantity', 'Unit Price', 'Total']]
        for item in invoice.items.all():
            items_data.append([
                item.product.name[:30],
                item.product.sku,
                str(item.quantity),
                f"${item.unit_price:.2f}",
                f"${item.line_total:.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[2.5*inch, 1.2*inch, 1*inch, 1.2*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 1), (3, -1), 'RIGHT'),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Totals section
        totals_data = [
            ['', 'Subtotal:', f"${invoice.subtotal:.2f}"],
            ['', 'Tax ({:.2f}%):'.format(invoice.tax_percentage), f"${invoice.tax_amount:.2f}"],
            ['', 'TOTAL:', f"${invoice.total_amount:.2f}"],
        ]
        
        if invoice.amount_paid > 0:
            totals_data.append(['', 'Amount Paid:', f"${invoice.amount_paid:.2f}"])
            totals_data.append(['', 'Outstanding:', f"${invoice.get_outstanding_amount():.2f}"])
        
        totals_table = Table(totals_data, colWidths=[3.5*inch, 1.5*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f0f0f0')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Payment info
        if invoice.payment_status != 'pending':
            payment_data = [
                ['Payment Status:', invoice.get_payment_status_display()],
                ['Payment Date:', invoice.payment_date.strftime('%b %d, %Y') if invoice.payment_date else 'N/A'],
                ['Payment Method:', invoice.get_payment_method_display() if invoice.payment_method else 'N/A'],
            ]
            payment_table = Table(payment_data)
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9f9f9')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(payment_table)
        
        # Notes
        if invoice.notes:
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("<b>Notes:</b>", styles['Normal']))
            elements.append(Paragraph(invoice.notes, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Return PDF response
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
        return response


class InvoiceCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """View to create a new invoice"""
    model = Invoice
    form_class = InvoiceForm
    template_name = 'malar_app/invoice_form.html'
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # Generate invoice number
        from django.utils import timezone
        count = Invoice.objects.count() + 1
        form.instance.invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{count:04d}"
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('malar_app:invoice-detail', kwargs={'pk': self.object.pk})


class InvoiceUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """View to update invoice"""
    model = Invoice
    form_class = InvoiceForm
    template_name = 'malar_app/invoice_form.html'
    pk_url_kwarg = 'pk'
    
    def get_success_url(self):
        return reverse_lazy('malar_app:invoice-detail', kwargs={'pk': self.object.pk})


class InvoiceDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete invoice"""
    model = Invoice
    template_name = 'malar_app/invoice_confirm_delete.html'
    pk_url_kwarg = 'pk'
    success_url = reverse_lazy('malar_app:invoice-list')


class InvoiceLineItemCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """View to add line items to invoice"""
    model = InvoiceLineItem
    form_class = InvoiceLineItemForm
    template_name = 'malar_app/invoice_lineitem_form.html'
    
    def form_valid(self, form):
        invoice_id = self.kwargs.get('invoice_pk')
        form.instance.invoice_id = invoice_id
        response = super().form_valid(form)
        
        # Recalculate invoice total
        invoice = Invoice.objects.get(pk=invoice_id)
        invoice.calculate_total()
        invoice.save()
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('malar_app:invoice-detail', kwargs={'pk': self.kwargs.get('invoice_pk')})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = Invoice.objects.get(pk=self.kwargs.get('invoice_pk'))
        return context


class InvoiceLineItemDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete line item from invoice"""
    model = InvoiceLineItem
    template_name = 'malar_app/invoice_lineitem_confirm_delete.html'
    pk_url_kwarg = 'pk'
    
    def get_success_url(self):
        invoice_pk = self.object.invoice.pk
        invoice = Invoice.objects.get(pk=invoice_pk)
        invoice.calculate_total()
        invoice.save()
        return reverse_lazy('malar_app:invoice-detail', kwargs={'pk': invoice_pk})


# ===== API VIEWS =====

class ProductSearchAPIView(View):
    """API view to search products (returns JSON)"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        products = Product.objects.filter(is_active=True)
        
        if query:
            products = products.filter(name__icontains=query) | products.filter(sku__icontains=query)
        
        results = []
        for p in products[:10]:
            try:
                stock_qty = p.stock.quantity
            except Stock.DoesNotExist:
                stock_qty = 0
            
            results.append({
                'id': p.id,
                'name': p.name,
                'sku': p.sku,
                'price': str(p.price),
                'stock': stock_qty,
                'category': p.category.name
            })
        
        return JsonResponse({'products': results})


class ProductAutoCompleteAPIView(View):
    """API view for product autocomplete"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        products = Product.objects.filter(
            is_active=True,
            name__icontains=query
        )[:5]
        
        results = [{'id': p.id, 'name': f"{p.name} ({p.sku})", 'sku': p.sku} for p in products]
        return JsonResponse({'results': results})


class DashboardStatsAPIView(View):
    """API view for dashboard statistics"""
    
    def get(self, request):
        total_products = Product.objects.filter(is_active=True).count()
        total_categories = Category.objects.count()
        total_customers = Customer.objects.count()
        
        low_stock = Stock.objects.filter(quantity__lte=F('reorder_level')).count()
        
        total_stock_value = sum([
            p.price * (p.stock.quantity if hasattr(p, 'stock') else 0)
            for p in Product.objects.all()
        ])
        
        return JsonResponse({
            'total_products': total_products,
            'total_categories': total_categories,
            'total_customers': total_customers,
            'low_stock': low_stock,
            'total_stock_value': str(total_stock_value)
        })
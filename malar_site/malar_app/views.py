from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from decimal import Decimal
from .models import Product, Category, Stock, ProductImage
from .forms import StockUpdateForm, ProductBulkImportForm, InventoryReportForm, CustomProductForm
import csv
from io import StringIO, TextIOWrapper
from datetime import datetime
import json

# Create your views here.

class HomeView(TemplateView):
    """Welcome/home page with inventory statistics"""
    template_name = 'malar_app/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_products'] = Product.objects.filter(is_active=True).count()
        context['total_categories'] = Category.objects.count()
        context['low_stock_products'] = Stock.objects.filter(is_low_stock=True).count()
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
    success_url = reverse_lazy('product-list')
    
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
        return reverse_lazy('product-detail', kwargs={'sku': self.object.sku})


class ProductDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """View to delete a product (admin only)"""
    model = Product
    template_name = 'malar_app/confirm_delete.html'
    success_url = reverse_lazy('product-list')
    slug_field = 'sku'
    slug_url_kwarg = 'sku'


class CategoryListView(ListView):
    """View to list all categories"""
    model = Category
    template_name = 'malar_app/category_list.html'
    context_object_name = 'categories'


# ===== NEW CUSTOM VIEWS =====

class StockManagementView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """View to manage stock - add, remove, or adjust quantities"""
    template_name = 'malar_app/stock_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.select_related('category', 'stock').filter(is_active=True)
        context['low_stock_items'] = Stock.objects.filter(is_low_stock=True).select_related('product')
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle stock update"""
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')
        quantity = int(request.POST.get('quantity', 0))
        
        try:
            product = Product.objects.get(id=product_id)
            stock = product.stock
            
            if action == 'add':
                stock.quantity += quantity
            elif action == 'remove':
                stock.quantity = max(0, stock.quantity - quantity)
            elif action == 'set':
                stock.quantity = quantity
            
            stock.save()
            messages.success(request, f"✅ Stock updated for {product.name}")
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
        
        return redirect('stock-management')


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
        context['low_stock_count'] = stocks.filter(is_low_stock=True).count()
        
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
            'low_stock': Stock.objects.filter(is_low_stock=True).count(),
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
                products = Product.objects.filter(stock__is_low_stock=True)
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
            return redirect('product-detail', sku=product.sku)
        
        return render(request, self.template_name, {'form': form})

from django.urls import path
from . import views

app_name = 'malar_app'

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    
    # Home page
    path('', views.HomeView.as_view(), name='home'),
    
    # Admin Dashboard
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    
    # Product URLs
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<str:sku>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/create/', views.ProductCreateView.as_view(), name='product-create'),
    path('products/<str:sku>/edit/', views.ProductUpdateView.as_view(), name='product-update'),
    path('products/<str:sku>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),
    
    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    
    # Custom Pages
    path('stock-management/', views.StockManagementView.as_view(), name='stock-management'),
    path('analytics/', views.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('product-import/', views.ProductImportView.as_view(), name='product-import'),
    path('inventory-report/', views.InventoryReportView.as_view(), name='inventory-report'),
    path('product-create-custom/', views.CustomProductFormView.as_view(), name='product-create-custom'),
    
    # Customer URLs
    path('customers/', views.CustomerListView.as_view(), name='customer-list'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer-create'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer-update'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer-delete'),
    
    # Invoice URLs
    path('invoices/', views.InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/<int:pk>/pdf/', views.InvoiceDetailPDFView.as_view(), name='invoice-pdf'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice-create'),
    path('invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice-update'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice-delete'),
    path('invoices/<int:invoice_pk>/items/add/', views.InvoiceLineItemCreateView.as_view(), name='invoice-item-add'),
    path('invoices/items/<int:pk>/delete/', views.InvoiceLineItemDeleteView.as_view(), name='invoice-item-delete'),
    
    # API URLs
    path('api/products/search/', views.ProductSearchAPIView.as_view(), name='product-search-api'),
    path('api/products/autocomplete/', views.ProductAutoCompleteAPIView.as_view(), name='product-autocomplete-api'),
    path('api/dashboard/stats/', views.DashboardStatsAPIView.as_view(), name='dashboard-stats-api'),
]
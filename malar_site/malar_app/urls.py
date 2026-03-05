from django.urls import path
from . import views

app_name = 'malar_app'

urlpatterns = [
    # Home page
    path('', views.HomeView.as_view(), name='home'),
    
    # Product URLs
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<str:sku>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/create/', views.ProductCreateView.as_view(), name='product-create'),
    path('products/<str:sku>/edit/', views.ProductUpdateView.as_view(), name='product-update'),
    path('products/<str:sku>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),
    
    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    
    # New Custom Pages
    path('stock-management/', views.StockManagementView.as_view(), name='stock-management'),
    path('analytics/', views.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('product-import/', views.ProductImportView.as_view(), name='product-import'),
    path('inventory-report/', views.InventoryReportView.as_view(), name='inventory-report'),
    path('product-create-custom/', views.CustomProductFormView.as_view(), name='product-create-custom'),
]



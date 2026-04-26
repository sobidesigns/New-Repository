from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.inventory_dashboard, name='dashboard'),
    
    # Materials
    path('materials/', views.material_list, name='material_list'),
    path('materials/add/', views.material_create, name='material_create'),
    path('materials/<int:material_id>/edit/', views.material_edit, name='material_edit'),
    
    # Stock
    path('stock/movement/', views.stock_movement, name='stock_movement'),
    path('stock/report/', views.stock_report, name='stock_report'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    
    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit, name='supplier_edit'),
    
    # Purchase Orders
    path('purchase-orders/', views.po_list, name='po_list'),
    path('purchase-orders/add/', views.po_create, name='po_create'),
    path('purchase-orders/<int:po_id>/', views.po_detail, name='po_detail'),
    path('purchase-orders/<int:po_id>/receive/', views.po_receive, name='po_receive'),
    
    # API
    path('api/materials/search/', views.api_material_search, name='api_material_search'),
    path('api/stock/<int:material_id>/', views.api_stock_check, name='api_stock_check'),
]

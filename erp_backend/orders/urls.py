from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Orders
    path('', views.order_list, name='list'),
    path('create/', views.order_create, name='create'),
    path('<int:pk>/', views.order_detail, name='detail'),
    path('<int:pk>/edit/', views.order_edit, name='edit'),
    path('<int:pk>/change-status/', views.order_change_status, name='change_status'),
    
    # Customers
    path('customers/', views.customer_list, name='customers'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    
    # Products
    path('products/', views.product_list, name='products'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    
    # API
    path('api/products/', views.api_products, name='api_products'),
    path('api/customers/<int:customer_id>/orders/', views.api_customer_orders, name='api_customer_orders'),
]

from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    # Overview
    path('', views.production_overview, name='overview'),
    
    # Cutting
    path('cutting/', views.cutting_dashboard, name='cutting_dashboard'),
    path('cutting/tasks/', views.cutting_task_list, name='cutting_task_list'),
    path('cutting/create/<int:order_id>/', views.create_cutting_task, name='create_cutting_task'),
    path('cutting/update/<int:task_id>/', views.update_cutting_task, name='update_cutting_task'),
    
    # Stitching
    path('stitching/', views.stitching_dashboard, name='stitching_dashboard'),
    path('stitching/update/<int:task_id>/', views.update_stitching_task, name='update_stitching_task'),
    
    # QC
    path('qc/', views.qc_dashboard, name='qc_dashboard'),
    path('qc/update/<int:task_id>/', views.update_qc_task, name='update_qc_task'),
    
    # Ironing
    path('ironing/', views.ironing_dashboard, name='ironing_dashboard'),
    path('ironing/update/<int:task_id>/', views.update_ironing_task, name='update_ironing_task'),
    
    # Packing
    path('packing/', views.packing_dashboard, name='packing_dashboard'),
    path('packing/update/<int:task_id>/', views.update_packing_task, name='update_packing_task'),
    
    # Dispatch
    path('dispatch/', views.dispatch_dashboard, name='dispatch_dashboard'),
    path('dispatch/update/<int:task_id>/', views.update_dispatch_task, name='update_dispatch_task'),
    
    # API
    path('api/update-status/', views.api_update_task_status, name='api_update_status'),
]

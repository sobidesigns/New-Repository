from django.urls import path
from . import views

app_name = 'quality'

urlpatterns = [
    # Dashboard
    path('', views.quality_dashboard, name='dashboard'),
    
    # Inspections
    path('inspections/', views.inspection_list, name='inspection_list'),
    path('inspections/add/', views.inspection_create, name='inspection_create'),
    path('inspections/<int:inspection_id>/', views.inspection_detail, name='inspection_detail'),
    
    # Defect Types
    path('defects/', views.defect_type_list, name='defect_type_list'),
    path('defects/add/', views.defect_type_create, name='defect_type_create'),
    path('defects/analysis/', views.defect_analysis, name='defect_analysis'),
    
    # Checkpoints
    path('checkpoints/', views.checkpoint_list, name='checkpoint_list'),
    path('checkpoints/add/', views.checkpoint_create, name='checkpoint_create'),
    
    # Reports
    path('reports/', views.quality_report, name='quality_report'),
    path('reports/save/', views.save_quality_report, name='save_quality_report'),
]

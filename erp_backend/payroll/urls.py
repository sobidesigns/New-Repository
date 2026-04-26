from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # Dashboard
    path('', views.payroll_dashboard, name='dashboard'),
    
    # Payslips
    path('payslips/', views.payslip_list, name='payslip_list'),
    path('payslips/generate/', views.generate_payslips, name='generate_payslips'),
    path('payslips/<int:payslip_id>/', views.payslip_detail, name='payslip_detail'),
    path('payslips/<int:payslip_id>/pay/', views.mark_payslip_paid, name='mark_payslip_paid'),
    path('payslips/bulk-pay/', views.bulk_pay, name='bulk_pay'),
    
    # Salary Structures
    path('salary-structures/', views.salary_structure_list, name='salary_structure_list'),
    path('salary-structures/add/', views.salary_structure_create, name='salary_structure_create'),
    
    # Advances
    path('advances/', views.advance_list, name='advance_list'),
    path('advances/add/', views.advance_create, name='advance_create'),
    path('advances/<int:advance_id>/action/', views.advance_action, name='advance_action'),
    
    # Loans
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/add/', views.loan_create, name='loan_create'),
    path('loans/<int:loan_id>/', views.loan_detail, name='loan_detail'),
    
    # Bonuses
    path('bonuses/', views.bonus_list, name='bonus_list'),
    path('bonuses/add/', views.bonus_create, name='bonus_create'),
]

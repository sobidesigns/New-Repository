from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    # Dashboard
    path('', views.hr_dashboard, name='dashboard'),
    
    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:employee_id>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    
    # Attendance
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),
    
    # Leave Management
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/<int:leave_id>/action/', views.leave_action, name='leave_action'),
    
    # Designations
    path('designations/', views.designation_list, name='designation_list'),
    path('designations/add/', views.designation_create, name='designation_create'),
    
    # Shifts
    path('shifts/', views.shift_list, name='shift_list'),
    path('shifts/add/', views.shift_create, name='shift_create'),
    
    # Holidays
    path('holidays/', views.holiday_list, name='holiday_list'),
    path('holidays/add/', views.holiday_create, name='holiday_create'),
]

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta, datetime
from functools import wraps

from .models import (
    Employee, Department, Designation, Attendance,
    LeaveType, LeaveApplication, Holiday, Shift
)


def role_required(*roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role in roles or request.user.role == 'super_admin':
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:index')
        return wrapper
    return decorator


@login_required
@role_required('super_admin', 'hr_manager')
def hr_dashboard(request):
    """HR dashboard overview"""
    today = timezone.now().date()
    
    total_employees = Employee.objects.filter(is_active=True).count()
    present_today = Attendance.objects.filter(
        date=today, 
        status='present'
    ).count()
    absent_today = total_employees - present_today
    
    pending_leaves = LeaveApplication.objects.filter(status='pending').count()
    
    # Employees by department
    dept_stats = Employee.objects.filter(is_active=True).values(
        'department'
    ).annotate(count=Count('id'))
    
    # Recent hires (last 30 days)
    recent_hires = Employee.objects.filter(
        joining_date__gte=today - timedelta(days=30),
        is_active=True
    ).count()
    
    # Upcoming birthdays
    upcoming_birthdays = Employee.objects.filter(
        is_active=True,
        date_of_birth__month=today.month
    ).order_by('date_of_birth')[:5]
    
    context = {
        'total_employees': total_employees,
        'present_today': present_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'dept_stats': dept_stats,
        'recent_hires': recent_hires,
        'upcoming_birthdays': upcoming_birthdays,
        'page_title': 'HR Dashboard'
    }
    return render(request, 'hr/dashboard.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def employee_list(request):
    """List all employees"""
    search = request.GET.get('search', '')
    department = request.GET.get('department', '')
    status = request.GET.get('status', 'active')
    
    employees = Employee.objects.select_related('designation', 'user')
    
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(employee_id__icontains=search) |
            Q(phone__icontains=search)
        )
    
    if department:
        employees = employees.filter(department=department)
    
    if status == 'active':
        employees = employees.filter(is_active=True)
    elif status == 'inactive':
        employees = employees.filter(is_active=False)
    
    employees = employees.order_by('first_name')
    
    paginator = Paginator(employees, 20)
    page = request.GET.get('page', 1)
    employees = paginator.get_page(page)
    
    departments = dict(Employee.DEPARTMENT_CHOICES)
    
    context = {
        'employees': employees,
        'departments': departments,
        'search': search,
        'department_filter': department,
        'status_filter': status,
        'page_title': 'Employees'
    }
    return render(request, 'hr/employee_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def employee_create(request):
    """Create new employee"""
    departments = Employee.DEPARTMENT_CHOICES
    designations = Designation.objects.filter(is_active=True)
    shifts = Shift.objects.filter(is_active=True)
    
    if request.method == 'POST':
        # Generate employee ID
        last_emp = Employee.objects.order_by('-id').first()
        emp_id = f"EMP{(last_emp.id + 1) if last_emp else 1:04d}"
        
        employee = Employee.objects.create(
            employee_id=emp_id,
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            emergency_contact=request.POST.get('emergency_contact', ''),
            date_of_birth=request.POST.get('date_of_birth') or None,
            gender=request.POST.get('gender', 'male'),
            address=request.POST.get('address', ''),
            city=request.POST.get('city', ''),
            department=request.POST.get('department'),
            designation_id=request.POST.get('designation') or None,
            shift_id=request.POST.get('shift') or None,
            joining_date=request.POST.get('joining_date') or timezone.now().date(),
            employment_type=request.POST.get('employment_type', 'full_time'),
            basic_salary=float(request.POST.get('basic_salary', 0)),
            cnic=request.POST.get('cnic', ''),
            bank_name=request.POST.get('bank_name', ''),
            bank_account=request.POST.get('bank_account', ''),
        )
        
        messages.success(request, f'Employee {employee.full_name} created with ID {emp_id}')
        return redirect('hr:employee_list')
    
    context = {
        'departments': departments,
        'designations': designations,
        'shifts': shifts,
        'page_title': 'Add Employee'
    }
    return render(request, 'hr/employee_form.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def employee_detail(request, employee_id):
    """View employee details"""
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Get attendance for current month
    today = timezone.now().date()
    month_start = today.replace(day=1)
    attendance = Attendance.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=today
    ).order_by('-date')
    
    # Get leave balance
    leave_applications = LeaveApplication.objects.filter(
        employee=employee,
        start_date__year=today.year
    )
    
    context = {
        'employee': employee,
        'attendance': attendance,
        'leave_applications': leave_applications,
        'page_title': employee.full_name
    }
    return render(request, 'hr/employee_detail.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def employee_edit(request, employee_id):
    """Edit employee"""
    employee = get_object_or_404(Employee, id=employee_id)
    departments = Employee.DEPARTMENT_CHOICES
    designations = Designation.objects.filter(is_active=True)
    shifts = Shift.objects.filter(is_active=True)
    
    if request.method == 'POST':
        employee.first_name = request.POST.get('first_name')
        employee.last_name = request.POST.get('last_name', '')
        employee.email = request.POST.get('email', '')
        employee.phone = request.POST.get('phone', '')
        employee.emergency_contact = request.POST.get('emergency_contact', '')
        employee.date_of_birth = request.POST.get('date_of_birth') or None
        employee.gender = request.POST.get('gender', 'male')
        employee.address = request.POST.get('address', '')
        employee.city = request.POST.get('city', '')
        employee.department = request.POST.get('department')
        employee.designation_id = request.POST.get('designation') or None
        employee.shift_id = request.POST.get('shift') or None
        employee.employment_type = request.POST.get('employment_type', 'full_time')
        employee.basic_salary = float(request.POST.get('basic_salary', 0))
        employee.cnic = request.POST.get('cnic', '')
        employee.bank_name = request.POST.get('bank_name', '')
        employee.bank_account = request.POST.get('bank_account', '')
        employee.is_active = request.POST.get('is_active') == 'on'
        employee.save()
        
        messages.success(request, f'Employee {employee.full_name} updated')
        return redirect('hr:employee_detail', employee_id=employee.id)
    
    context = {
        'employee': employee,
        'departments': departments,
        'designations': designations,
        'shifts': shifts,
        'page_title': f'Edit {employee.full_name}'
    }
    return render(request, 'hr/employee_form.html', context)


# Attendance views
@login_required
@role_required('super_admin', 'hr_manager')
def attendance_list(request):
    """List attendance records"""
    date_filter = request.GET.get('date', timezone.now().date().isoformat())
    department = request.GET.get('department', '')
    
    try:
        filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
    except:
        filter_date = timezone.now().date()
    
    employees = Employee.objects.filter(is_active=True)
    if department:
        employees = employees.filter(department=department)
    
    # Get attendance for the date
    attendance_dict = {}
    attendances = Attendance.objects.filter(date=filter_date)
    for att in attendances:
        attendance_dict[att.employee_id] = att
    
    employee_attendance = []
    for emp in employees:
        att = attendance_dict.get(emp.id)
        employee_attendance.append({
            'employee': emp,
            'attendance': att,
            'status': att.status if att else 'not_marked'
        })
    
    departments = dict(Employee.DEPARTMENT_CHOICES)
    
    context = {
        'employee_attendance': employee_attendance,
        'filter_date': filter_date,
        'departments': departments,
        'department_filter': department,
        'page_title': 'Attendance'
    }
    return render(request, 'hr/attendance_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def mark_attendance(request):
    """Mark attendance for employees"""
    if request.method == 'POST':
        date_str = request.POST.get('date')
        try:
            att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            att_date = timezone.now().date()
        
        employee_ids = request.POST.getlist('employee_ids[]')
        statuses = request.POST.getlist('status[]')
        check_ins = request.POST.getlist('check_in[]')
        check_outs = request.POST.getlist('check_out[]')
        
        for i, emp_id in enumerate(employee_ids):
            status = statuses[i] if i < len(statuses) else 'absent'
            check_in = check_ins[i] if i < len(check_ins) and check_ins[i] else None
            check_out = check_outs[i] if i < len(check_outs) and check_outs[i] else None
            
            Attendance.objects.update_or_create(
                employee_id=emp_id,
                date=att_date,
                defaults={
                    'status': status,
                    'check_in': check_in,
                    'check_out': check_out,
                    'marked_by': request.user
                }
            )
        
        messages.success(request, f'Attendance marked for {att_date}')
        return redirect('hr:attendance_list')
    
    return redirect('hr:attendance_list')


@login_required
@role_required('super_admin', 'hr_manager')
def attendance_report(request):
    """Monthly attendance report"""
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    department = request.GET.get('department', '')
    
    employees = Employee.objects.filter(is_active=True)
    if department:
        employees = employees.filter(department=department)
    
    # Get attendance summary
    summary = []
    for emp in employees:
        att = Attendance.objects.filter(
            employee=emp,
            date__month=month,
            date__year=year
        )
        present = att.filter(status='present').count()
        absent = att.filter(status='absent').count()
        late = att.filter(status='late').count()
        half_day = att.filter(status='half_day').count()
        leave = att.filter(status='leave').count()
        
        summary.append({
            'employee': emp,
            'present': present,
            'absent': absent,
            'late': late,
            'half_day': half_day,
            'leave': leave,
            'total_working': present + late + half_day
        })
    
    context = {
        'summary': summary,
        'month': int(month),
        'year': int(year),
        'department': department,
        'departments': dict(Employee.DEPARTMENT_CHOICES),
        'page_title': 'Attendance Report'
    }
    return render(request, 'hr/attendance_report.html', context)


# Leave Management
@login_required
@role_required('super_admin', 'hr_manager')
def leave_list(request):
    """List leave applications"""
    status_filter = request.GET.get('status', '')
    
    leaves = LeaveApplication.objects.select_related(
        'employee', 'leave_type'
    ).order_by('-applied_on')
    
    if status_filter:
        leaves = leaves.filter(status=status_filter)
    
    paginator = Paginator(leaves, 20)
    page = request.GET.get('page', 1)
    leaves = paginator.get_page(page)
    
    context = {
        'leaves': leaves,
        'status_filter': status_filter,
        'page_title': 'Leave Applications'
    }
    return render(request, 'hr/leave_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def leave_action(request, leave_id):
    """Approve or reject leave application"""
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        
        if action == 'approve':
            leave.status = 'approved'
            leave.approved_by = request.user
            leave.approved_on = timezone.now()
            
            # Mark attendance as leave for those days
            current_date = leave.start_date
            while current_date <= leave.end_date:
                Attendance.objects.update_or_create(
                    employee=leave.employee,
                    date=current_date,
                    defaults={'status': 'leave', 'marked_by': request.user}
                )
                current_date += timedelta(days=1)
            
            messages.success(request, 'Leave application approved')
        else:
            leave.status = 'rejected'
            leave.rejection_reason = remarks
            messages.success(request, 'Leave application rejected')
        
        leave.save()
        return redirect('hr:leave_list')
    
    context = {
        'leave': leave,
        'page_title': 'Leave Action'
    }
    return render(request, 'hr/leave_action.html', context)


# Department & Designation Management
@login_required
@role_required('super_admin', 'hr_manager')
def designation_list(request):
    """List designations"""
    designations = Designation.objects.filter(is_active=True).order_by('name')
    
    context = {
        'designations': designations,
        'page_title': 'Designations'
    }
    return render(request, 'hr/designation_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def designation_create(request):
    """Create designation"""
    if request.method == 'POST':
        Designation.objects.create(
            name=request.POST.get('name'),
            description=request.POST.get('description', '')
        )
        messages.success(request, 'Designation created')
        return redirect('hr:designation_list')
    
    return render(request, 'hr/designation_form.html', {'page_title': 'Add Designation'})


# Shift Management
@login_required
@role_required('super_admin', 'hr_manager')
def shift_list(request):
    """List shifts"""
    shifts = Shift.objects.filter(is_active=True).order_by('name')
    
    context = {
        'shifts': shifts,
        'page_title': 'Shifts'
    }
    return render(request, 'hr/shift_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def shift_create(request):
    """Create shift"""
    if request.method == 'POST':
        Shift.objects.create(
            name=request.POST.get('name'),
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            break_duration=int(request.POST.get('break_duration', 60))
        )
        messages.success(request, 'Shift created')
        return redirect('hr:shift_list')
    
    return render(request, 'hr/shift_form.html', {'page_title': 'Add Shift'})


# Holiday Management
@login_required
@role_required('super_admin', 'hr_manager')
def holiday_list(request):
    """List holidays"""
    year = request.GET.get('year', timezone.now().year)
    holidays = Holiday.objects.filter(date__year=year).order_by('date')
    
    context = {
        'holidays': holidays,
        'year': int(year),
        'page_title': 'Holidays'
    }
    return render(request, 'hr/holiday_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def holiday_create(request):
    """Create holiday"""
    if request.method == 'POST':
        Holiday.objects.create(
            name=request.POST.get('name'),
            date=request.POST.get('date'),
            description=request.POST.get('description', '')
        )
        messages.success(request, 'Holiday added')
        return redirect('hr:holiday_list')
    
    return render(request, 'hr/holiday_form.html', {'page_title': 'Add Holiday'})

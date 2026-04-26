from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from .models import (
    SalaryStructure, Payslip, PayslipComponent,
    Advance, Loan, LoanRepayment, Bonus
)
from hr.models import Employee, Attendance


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
@role_required('super_admin', 'hr_manager', 'accountant')
def payroll_dashboard(request):
    """Payroll dashboard overview"""
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # This month's payroll stats
    payslips_this_month = Payslip.objects.filter(
        month=current_month,
        year=current_year
    )
    
    total_payroll = payslips_this_month.aggregate(
        total=Sum('net_salary')
    )['total'] or 0
    
    paid_count = payslips_this_month.filter(status='paid').count()
    pending_count = payslips_this_month.filter(status='generated').count()
    
    # Pending advances and loans
    pending_advances = Advance.objects.filter(status='pending').count()
    active_loans = Loan.objects.filter(status='active').count()
    
    # Recent payslips
    recent_payslips = Payslip.objects.select_related(
        'employee'
    ).order_by('-created_at')[:10]
    
    context = {
        'total_payroll': total_payroll,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'pending_advances': pending_advances,
        'active_loans': active_loans,
        'recent_payslips': recent_payslips,
        'current_month': current_month,
        'current_year': current_year,
        'page_title': 'Payroll Dashboard'
    }
    return render(request, 'payroll/dashboard.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def payslip_list(request):
    """List payslips"""
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    status = request.GET.get('status', '')
    
    payslips = Payslip.objects.filter(
        month=int(month),
        year=int(year)
    ).select_related('employee').order_by('employee__first_name')
    
    if status:
        payslips = payslips.filter(status=status)
    
    total_amount = payslips.aggregate(total=Sum('net_salary'))['total'] or 0
    
    context = {
        'payslips': payslips,
        'month': int(month),
        'year': int(year),
        'status_filter': status,
        'total_amount': total_amount,
        'page_title': 'Payslips'
    }
    return render(request, 'payroll/payslip_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def generate_payslips(request):
    """Generate payslips for a month"""
    if request.method == 'POST':
        month = int(request.POST.get('month', timezone.now().month))
        year = int(request.POST.get('year', timezone.now().year))
        
        employees = Employee.objects.filter(is_active=True)
        generated_count = 0
        
        for employee in employees:
            # Check if payslip already exists
            if Payslip.objects.filter(employee=employee, month=month, year=year).exists():
                continue
            
            # Calculate attendance-based salary
            attendances = Attendance.objects.filter(
                employee=employee,
                date__month=month,
                date__year=year
            )
            
            present_days = attendances.filter(status='present').count()
            half_days = attendances.filter(status='half_day').count()
            late_days = attendances.filter(status='late').count()
            leave_days = attendances.filter(status='leave').count()
            
            # Get salary structure if exists
            salary_structure = SalaryStructure.objects.filter(
                employee=employee,
                is_active=True
            ).first()
            
            basic_salary = Decimal(str(employee.basic_salary))
            
            if salary_structure:
                allowances = salary_structure.total_allowances
                deductions = salary_structure.total_deductions
            else:
                allowances = Decimal('0')
                deductions = Decimal('0')
            
            # Calculate based on working days (assuming 26 working days)
            working_days = 26
            per_day_salary = basic_salary / working_days
            
            # Calculate effective working days
            effective_days = present_days + (half_days * Decimal('0.5')) + late_days + leave_days
            
            earned_basic = per_day_salary * Decimal(str(effective_days))
            
            # Check for advances this month
            advances = Advance.objects.filter(
                employee=employee,
                status='approved',
                approved_on__month=month,
                approved_on__year=year
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Check for loan repayments
            active_loan = Loan.objects.filter(
                employee=employee,
                status='active'
            ).first()
            
            loan_deduction = Decimal('0')
            if active_loan:
                loan_deduction = active_loan.monthly_deduction
            
            # Calculate totals
            gross_salary = earned_basic + allowances
            total_deductions = deductions + Decimal(str(advances)) + loan_deduction
            net_salary = gross_salary - total_deductions
            
            # Create payslip
            payslip = Payslip.objects.create(
                employee=employee,
                month=month,
                year=year,
                basic_salary=earned_basic,
                total_allowances=allowances,
                total_deductions=total_deductions,
                gross_salary=gross_salary,
                net_salary=max(net_salary, Decimal('0')),
                working_days=working_days,
                present_days=present_days,
                absent_days=working_days - int(effective_days),
                generated_by=request.user
            )
            
            # Record loan repayment if applicable
            if active_loan and loan_deduction > 0:
                LoanRepayment.objects.create(
                    loan=active_loan,
                    amount=loan_deduction,
                    payment_date=timezone.now().date(),
                    payment_method='salary_deduction',
                    notes=f'Auto-deducted from payslip {payslip.payslip_number}'
                )
                
                # Update loan balance
                active_loan.remaining_amount -= loan_deduction
                if active_loan.remaining_amount <= 0:
                    active_loan.status = 'completed'
                active_loan.save()
            
            generated_count += 1
        
        messages.success(request, f'Generated {generated_count} payslips for {month}/{year}')
        return redirect('payroll:payslip_list')
    
    context = {
        'current_month': timezone.now().month,
        'current_year': timezone.now().year,
        'page_title': 'Generate Payslips'
    }
    return render(request, 'payroll/generate_payslips.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def payslip_detail(request, payslip_id):
    """View payslip details"""
    payslip = get_object_or_404(Payslip, id=payslip_id)
    components = PayslipComponent.objects.filter(payslip=payslip)
    
    context = {
        'payslip': payslip,
        'components': components,
        'page_title': f'Payslip - {payslip.employee.full_name}'
    }
    return render(request, 'payroll/payslip_detail.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def mark_payslip_paid(request, payslip_id):
    """Mark payslip as paid"""
    payslip = get_object_or_404(Payslip, id=payslip_id)
    
    if request.method == 'POST':
        payslip.status = 'paid'
        payslip.payment_date = timezone.now().date()
        payslip.payment_method = request.POST.get('payment_method', 'bank_transfer')
        payslip.payment_reference = request.POST.get('payment_reference', '')
        payslip.save()
        
        messages.success(request, f'Payslip for {payslip.employee.full_name} marked as paid')
        return redirect('payroll:payslip_list')
    
    return redirect('payroll:payslip_detail', payslip_id=payslip_id)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def bulk_pay(request):
    """Bulk mark payslips as paid"""
    if request.method == 'POST':
        payslip_ids = request.POST.getlist('payslip_ids[]')
        payment_method = request.POST.get('payment_method', 'bank_transfer')
        
        Payslip.objects.filter(id__in=payslip_ids).update(
            status='paid',
            payment_date=timezone.now().date(),
            payment_method=payment_method
        )
        
        messages.success(request, f'{len(payslip_ids)} payslips marked as paid')
    
    return redirect('payroll:payslip_list')


# Salary Structure Management
@login_required
@role_required('super_admin', 'hr_manager')
def salary_structure_list(request):
    """List salary structures"""
    structures = SalaryStructure.objects.filter(
        is_active=True
    ).select_related('employee').order_by('employee__first_name')
    
    context = {
        'structures': structures,
        'page_title': 'Salary Structures'
    }
    return render(request, 'payroll/salary_structure_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def salary_structure_create(request):
    """Create salary structure"""
    employees = Employee.objects.filter(is_active=True)
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        
        # Deactivate existing structure
        SalaryStructure.objects.filter(
            employee_id=employee_id,
            is_active=True
        ).update(is_active=False)
        
        structure = SalaryStructure.objects.create(
            employee_id=employee_id,
            basic_salary=Decimal(request.POST.get('basic_salary', 0)),
            house_rent_allowance=Decimal(request.POST.get('hra', 0)),
            medical_allowance=Decimal(request.POST.get('medical', 0)),
            transport_allowance=Decimal(request.POST.get('transport', 0)),
            other_allowances=Decimal(request.POST.get('other_allowances', 0)),
            provident_fund=Decimal(request.POST.get('pf', 0)),
            professional_tax=Decimal(request.POST.get('professional_tax', 0)),
            other_deductions=Decimal(request.POST.get('other_deductions', 0)),
            effective_from=request.POST.get('effective_from') or timezone.now().date()
        )
        
        messages.success(request, 'Salary structure created')
        return redirect('payroll:salary_structure_list')
    
    context = {
        'employees': employees,
        'page_title': 'Create Salary Structure'
    }
    return render(request, 'payroll/salary_structure_form.html', context)


# Advance Management
@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def advance_list(request):
    """List advances"""
    status = request.GET.get('status', '')
    
    advances = Advance.objects.select_related('employee').order_by('-requested_on')
    
    if status:
        advances = advances.filter(status=status)
    
    paginator = Paginator(advances, 20)
    page = request.GET.get('page', 1)
    advances = paginator.get_page(page)
    
    context = {
        'advances': advances,
        'status_filter': status,
        'page_title': 'Salary Advances'
    }
    return render(request, 'payroll/advance_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def advance_create(request):
    """Create advance request"""
    employees = Employee.objects.filter(is_active=True)
    
    if request.method == 'POST':
        Advance.objects.create(
            employee_id=request.POST.get('employee'),
            amount=Decimal(request.POST.get('amount', 0)),
            reason=request.POST.get('reason', ''),
            requested_on=timezone.now()
        )
        messages.success(request, 'Advance request created')
        return redirect('payroll:advance_list')
    
    context = {
        'employees': employees,
        'page_title': 'New Advance Request'
    }
    return render(request, 'payroll/advance_form.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def advance_action(request, advance_id):
    """Approve or reject advance"""
    advance = get_object_or_404(Advance, id=advance_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            advance.status = 'approved'
            advance.approved_by = request.user
            advance.approved_on = timezone.now()
            messages.success(request, 'Advance approved')
        else:
            advance.status = 'rejected'
            advance.rejection_reason = request.POST.get('reason', '')
            messages.success(request, 'Advance rejected')
        
        advance.save()
    
    return redirect('payroll:advance_list')


# Loan Management
@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def loan_list(request):
    """List loans"""
    status = request.GET.get('status', '')
    
    loans = Loan.objects.select_related('employee').order_by('-created_at')
    
    if status:
        loans = loans.filter(status=status)
    
    context = {
        'loans': loans,
        'status_filter': status,
        'page_title': 'Employee Loans'
    }
    return render(request, 'payroll/loan_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def loan_create(request):
    """Create loan"""
    employees = Employee.objects.filter(is_active=True)
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        months = int(request.POST.get('installments', 1))
        monthly_deduction = amount / months
        
        Loan.objects.create(
            employee_id=request.POST.get('employee'),
            amount=amount,
            remaining_amount=amount,
            installments=months,
            monthly_deduction=monthly_deduction,
            purpose=request.POST.get('purpose', ''),
            start_date=request.POST.get('start_date') or timezone.now().date()
        )
        messages.success(request, 'Loan created')
        return redirect('payroll:loan_list')
    
    context = {
        'employees': employees,
        'page_title': 'New Loan'
    }
    return render(request, 'payroll/loan_form.html', context)


@login_required
@role_required('super_admin', 'hr_manager', 'accountant')
def loan_detail(request, loan_id):
    """View loan details"""
    loan = get_object_or_404(Loan, id=loan_id)
    repayments = LoanRepayment.objects.filter(loan=loan).order_by('-payment_date')
    
    context = {
        'loan': loan,
        'repayments': repayments,
        'page_title': f'Loan - {loan.employee.full_name}'
    }
    return render(request, 'payroll/loan_detail.html', context)


# Bonus Management
@login_required
@role_required('super_admin', 'hr_manager')
def bonus_list(request):
    """List bonuses"""
    bonuses = Bonus.objects.select_related('employee').order_by('-created_at')
    
    context = {
        'bonuses': bonuses,
        'page_title': 'Bonuses'
    }
    return render(request, 'payroll/bonus_list.html', context)


@login_required
@role_required('super_admin', 'hr_manager')
def bonus_create(request):
    """Create bonus"""
    employees = Employee.objects.filter(is_active=True)
    
    if request.method == 'POST':
        Bonus.objects.create(
            employee_id=request.POST.get('employee'),
            bonus_type=request.POST.get('bonus_type', 'performance'),
            amount=Decimal(request.POST.get('amount', 0)),
            reason=request.POST.get('reason', ''),
            payment_date=request.POST.get('payment_date') or timezone.now().date(),
            created_by=request.user
        )
        messages.success(request, 'Bonus created')
        return redirect('payroll:bonus_list')
    
    context = {
        'employees': employees,
        'page_title': 'Add Bonus'
    }
    return render(request, 'payroll/bonus_form.html', context)

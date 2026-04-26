from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from orders.models import Order, Customer
from inventory.models import Material, StockMovement
from hr.models import Employee, Attendance
from finance.models import Transaction, Invoice, Payment, Expense
from production.models import ProductionBatch, WorkerTask


@login_required
def dashboard_index(request):
    """Main dashboard view with role-specific data"""
    user = request.user
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    context = {
        'today': today,
    }
    
    # Admin/Owner Dashboard - Full overview
    if user.is_admin:
        context.update(get_admin_dashboard_data(today, month_start))
    
    # Production Manager Dashboard
    elif user.role == 'production_manager':
        context.update(get_production_dashboard_data(today))
    
    # HR Manager Dashboard
    elif user.role == 'hr_manager':
        context.update(get_hr_dashboard_data(today, month_start))
    
    # Accounts Manager Dashboard
    elif user.role == 'accounts_manager':
        context.update(get_finance_dashboard_data(today, month_start))
    
    # Inventory Manager Dashboard
    elif user.role == 'inventory_manager':
        context.update(get_inventory_dashboard_data())
    
    # Department Head Dashboards
    elif user.is_department_head:
        context.update(get_department_head_dashboard(user, today))
    
    # Order Entry Dashboard
    else:
        context.update(get_order_entry_dashboard(today))
    
    return render(request, 'dashboard/index.html', context)


def get_admin_dashboard_data(today, month_start):
    """Get dashboard data for admin/owner"""
    # Orders statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status__in=['pending', 'confirmed']).count()
    in_production = Order.objects.filter(status__in=['in_production', 'cutting', 'stitching', 'quality_check', 'ironing', 'packing']).count()
    completed_orders = Order.objects.filter(status='delivered').count()
    
    # This month's orders
    month_orders = Order.objects.filter(created_at__date__gte=month_start)
    month_order_count = month_orders.count()
    month_revenue = month_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Financial summary
    month_income = Transaction.objects.filter(
        date__gte=month_start,
        transaction_type__in=['income', 'payment_received']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    month_expenses = Transaction.objects.filter(
        date__gte=month_start,
        transaction_type__in=['expense', 'payment_made']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Pending payments
    pending_invoices = Invoice.objects.filter(status__in=['sent', 'partial', 'overdue'])
    total_receivable = pending_invoices.aggregate(total=Sum('balance_due'))['total'] or Decimal('0')
    
    # Inventory alerts
    low_stock_items = Material.objects.filter(quantity__lte=models.F('min_stock_level'), is_active=True).count()
    
    # Employee stats
    total_employees = Employee.objects.filter(status='active').count()
    today_attendance = Attendance.objects.filter(date=today, status='present').count()
    
    # Recent orders
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
    
    # Overdue orders
    overdue_orders = Order.objects.filter(
        delivery_date__lt=today,
        status__in=['pending', 'confirmed', 'in_production', 'cutting', 'stitching', 'quality_check', 'ironing', 'packing']
    ).count()
    
    return {
        'dashboard_type': 'admin',
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'in_production': in_production,
        'completed_orders': completed_orders,
        'month_order_count': month_order_count,
        'month_revenue': month_revenue,
        'month_income': month_income,
        'month_expenses': month_expenses,
        'total_receivable': total_receivable,
        'low_stock_items': low_stock_items,
        'total_employees': total_employees,
        'today_attendance': today_attendance,
        'recent_orders': recent_orders,
        'overdue_orders': overdue_orders,
    }


def get_production_dashboard_data(today):
    """Get dashboard data for production manager"""
    # Orders in each stage
    orders_by_status = Order.objects.filter(
        status__in=['in_production', 'cutting', 'stitching', 'quality_check', 'ironing', 'packing', 'dispatch']
    ).values('status').annotate(count=Count('id'))
    
    status_counts = {item['status']: item['count'] for item in orders_by_status}
    
    # Today's production batches
    today_batches = ProductionBatch.objects.filter(
        start_date=today
    ).select_related('order', 'order_item')
    
    # Pending tasks
    pending_tasks = WorkerTask.objects.filter(
        status__in=['assigned', 'in_progress']
    ).select_related('worker', 'order')[:20]
    
    # Quality issues today
    from quality.models import QualityInspection
    failed_inspections = QualityInspection.objects.filter(
        inspection_date=today,
        status='failed'
    ).count()
    
    # Overdue orders
    overdue_orders = Order.objects.filter(
        delivery_date__lt=today,
        status__in=['in_production', 'cutting', 'stitching', 'quality_check', 'ironing', 'packing']
    ).select_related('customer')[:10]
    
    return {
        'dashboard_type': 'production',
        'status_counts': status_counts,
        'today_batches': today_batches,
        'pending_tasks': pending_tasks,
        'failed_inspections': failed_inspections,
        'overdue_orders': overdue_orders,
    }


def get_hr_dashboard_data(today, month_start):
    """Get dashboard data for HR manager"""
    # Employee counts by status
    active_employees = Employee.objects.filter(status='active').count()
    on_leave = Employee.objects.filter(status='on_leave').count()
    
    # Today's attendance
    today_present = Attendance.objects.filter(date=today, status='present').count()
    today_absent = Attendance.objects.filter(date=today, status='absent').count()
    today_late = Attendance.objects.filter(date=today, status='late').count()
    
    # Pending leave requests
    from hr.models import LeaveRequest
    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    
    # Employees by department
    from hr.models import Department
    dept_counts = Employee.objects.filter(status='active').values('department__name').annotate(count=Count('id'))
    
    # Recent attendance
    recent_attendance = Attendance.objects.filter(
        date__gte=today - timedelta(days=7)
    ).select_related('employee').order_by('-date')[:20]
    
    return {
        'dashboard_type': 'hr',
        'active_employees': active_employees,
        'on_leave': on_leave,
        'today_present': today_present,
        'today_absent': today_absent,
        'today_late': today_late,
        'pending_leaves': pending_leaves,
        'dept_counts': dept_counts,
        'recent_attendance': recent_attendance,
    }


def get_finance_dashboard_data(today, month_start):
    """Get dashboard data for accounts manager"""
    # This month summary
    month_income = Transaction.objects.filter(
        date__gte=month_start,
        transaction_type__in=['income', 'payment_received']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    month_expenses = Transaction.objects.filter(
        date__gte=month_start,
        transaction_type__in=['expense', 'payment_made']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Pending invoices
    pending_invoices = Invoice.objects.filter(status__in=['sent', 'partial'])
    total_receivable = pending_invoices.aggregate(total=Sum('balance_due'))['total'] or Decimal('0')
    overdue_invoices = pending_invoices.filter(due_date__lt=today).count()
    
    # Recent transactions
    recent_transactions = Transaction.objects.select_related('customer', 'supplier').order_by('-date', '-created_at')[:15]
    
    # Today's cash flow
    today_income = Transaction.objects.filter(
        date=today,
        transaction_type__in=['income', 'payment_received']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    today_expense = Transaction.objects.filter(
        date=today,
        transaction_type__in=['expense', 'payment_made']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Customer balances
    customers_with_balance = Customer.objects.filter(balance__gt=0).order_by('-balance')[:10]
    
    return {
        'dashboard_type': 'finance',
        'month_income': month_income,
        'month_expenses': month_expenses,
        'total_receivable': total_receivable,
        'overdue_invoices': overdue_invoices,
        'recent_transactions': recent_transactions,
        'today_income': today_income,
        'today_expense': today_expense,
        'customers_with_balance': customers_with_balance,
    }


def get_inventory_dashboard_data():
    """Get dashboard data for inventory manager"""
    # Stock overview
    total_materials = Material.objects.filter(is_active=True).count()
    low_stock = Material.objects.filter(quantity__lte=models.F('min_stock_level'), is_active=True)
    out_of_stock = Material.objects.filter(quantity=0, is_active=True).count()
    
    # Stock value
    total_stock_value = sum(m.total_value for m in Material.objects.filter(is_active=True))
    
    # Recent movements
    recent_movements = StockMovement.objects.select_related('material', 'supplier').order_by('-created_at')[:20]
    
    # Category wise stock
    from inventory.models import Category
    category_stats = Category.objects.annotate(
        material_count=Count('materials'),
        total_qty=Sum('materials__quantity')
    ).filter(material_count__gt=0)
    
    return {
        'dashboard_type': 'inventory',
        'total_materials': total_materials,
        'low_stock_items': low_stock,
        'out_of_stock': out_of_stock,
        'total_stock_value': total_stock_value,
        'recent_movements': recent_movements,
        'category_stats': category_stats,
    }


def get_department_head_dashboard(user, today):
    """Get dashboard data for department heads"""
    dept_map = {
        'cutting_head': 'cutting',
        'stitching_head': 'stitching',
        'qc_head': 'quality',
        'ironing_head': 'ironing',
        'packing_head': 'packing',
        'dispatch_head': 'dispatch',
    }
    
    department = dept_map.get(user.role, '')
    
    # Tasks for this department
    tasks = WorkerTask.objects.filter(
        task_type=department,
        status__in=['assigned', 'in_progress']
    ).select_related('worker', 'order', 'order_item')
    
    # Today's completed work
    today_completed = WorkerTask.objects.filter(
        task_type=department,
        end_time__date=today,
        status='completed'
    ).aggregate(
        total_qty=Sum('quantity_completed'),
        total_earnings=Sum('total_earnings')
    )
    
    # Workers in department
    workers = Employee.objects.filter(
        department__code=department.upper(),
        status='active'
    )
    
    # Pending orders for this stage
    status_map = {
        'cutting': 'cutting',
        'stitching': 'stitching',
        'quality': 'quality_check',
        'ironing': 'ironing',
        'packing': 'packing',
        'dispatch': 'dispatch',
    }
    
    stage_status = status_map.get(department, '')
    pending_orders = Order.objects.filter(status=stage_status).select_related('customer')[:10]
    
    return {
        'dashboard_type': 'department_head',
        'department': department,
        'tasks': tasks,
        'today_completed': today_completed,
        'workers': workers,
        'pending_orders': pending_orders,
    }


def get_order_entry_dashboard(today):
    """Get dashboard data for order entry clerk"""
    # Recent orders created by this user or all pending
    pending_orders = Order.objects.filter(
        status__in=['pending', 'confirmed']
    ).select_related('customer').order_by('-created_at')[:20]
    
    # Today's orders
    today_orders = Order.objects.filter(created_at__date=today).count()
    
    # Customers
    total_customers = Customer.objects.filter(is_active=True).count()
    
    return {
        'dashboard_type': 'order_entry',
        'pending_orders': pending_orders,
        'today_orders': today_orders,
        'total_customers': total_customers,
    }


# Need to import models for F expression
from django.db import models

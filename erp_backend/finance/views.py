from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from .models import (
    Account, Transaction, Invoice, InvoiceItem,
    Payment, Expense, ExpenseCategory, Budget
)
from orders.models import Order


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
@role_required('super_admin', 'accountant', 'finance_manager')
def finance_dashboard(request):
    """Finance dashboard overview"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Revenue this month
    revenue = Payment.objects.filter(
        payment_date__gte=month_start,
        payment_date__lte=today,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Expenses this month
    expenses = Expense.objects.filter(
        expense_date__gte=month_start,
        expense_date__lte=today,
        status='approved'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending invoices
    pending_invoices = Invoice.objects.filter(
        status='sent'
    ).aggregate(
        count=Count('id'),
        total=Sum('total_amount')
    )
    
    # Overdue invoices
    overdue = Invoice.objects.filter(
        status='sent',
        due_date__lt=today
    ).count()
    
    # Recent transactions
    recent_transactions = Transaction.objects.select_related(
        'account'
    ).order_by('-created_at')[:10]
    
    # Account balances
    accounts = Account.objects.filter(is_active=True)
    
    context = {
        'revenue': revenue,
        'expenses': expenses,
        'pending_invoices': pending_invoices,
        'overdue': overdue,
        'recent_transactions': recent_transactions,
        'accounts': accounts,
        'page_title': 'Finance Dashboard'
    }
    return render(request, 'finance/dashboard.html', context)


# Invoice Management
@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def invoice_list(request):
    """List invoices"""
    status = request.GET.get('status', '')
    
    invoices = Invoice.objects.select_related('order').order_by('-created_at')
    
    if status:
        invoices = invoices.filter(status=status)
    
    paginator = Paginator(invoices, 20)
    page = request.GET.get('page', 1)
    invoices = paginator.get_page(page)
    
    context = {
        'invoices': invoices,
        'status_filter': status,
        'page_title': 'Invoices'
    }
    return render(request, 'finance/invoice_list.html', context)


@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def invoice_create(request):
    """Create invoice"""
    orders = Order.objects.filter(
        status__in=['packing', 'dispatch', 'dispatched', 'delivered']
    ).exclude(
        id__in=Invoice.objects.values_list('order_id', flat=True)
    )
    
    if request.method == 'POST':
        order_id = request.POST.get('order')
        order = get_object_or_404(Order, id=order_id)
        
        # Generate invoice number
        last_inv = Invoice.objects.order_by('-id').first()
        inv_number = f"INV-{(last_inv.id + 1) if last_inv else 1:05d}"
        
        invoice = Invoice.objects.create(
            invoice_number=inv_number,
            order=order,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            customer_phone=order.customer_phone,
            customer_address=order.shipping_address,
            subtotal=order.total_amount,
            tax_amount=order.total_amount * Decimal('0.05'),  # 5% tax
            total_amount=order.total_amount * Decimal('1.05'),
            due_date=timezone.now().date() + timedelta(days=30),
            created_by=request.user
        )
        
        # Create invoice items from order items
        for item in order.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"{item.product_name} - {item.size} ({item.color})",
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total_price
            )
        
        messages.success(request, f'Invoice {inv_number} created')
        return redirect('finance:invoice_detail', invoice_id=invoice.id)
    
    context = {
        'orders': orders,
        'page_title': 'Create Invoice'
    }
    return render(request, 'finance/invoice_form.html', context)


@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def invoice_detail(request, invoice_id):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    items = invoice.items.all()
    payments = Payment.objects.filter(invoice=invoice)
    
    context = {
        'invoice': invoice,
        'items': items,
        'payments': payments,
        'page_title': f'Invoice {invoice.invoice_number}'
    }
    return render(request, 'finance/invoice_detail.html', context)


@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def invoice_send(request, invoice_id):
    """Mark invoice as sent"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    invoice.status = 'sent'
    invoice.save()
    messages.success(request, f'Invoice {invoice.invoice_number} marked as sent')
    return redirect('finance:invoice_detail', invoice_id=invoice_id)


# Payment Management
@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def payment_list(request):
    """List payments"""
    payment_type = request.GET.get('type', '')
    
    payments = Payment.objects.select_related('invoice').order_by('-payment_date')
    
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    
    paginator = Paginator(payments, 20)
    page = request.GET.get('page', 1)
    payments = paginator.get_page(page)
    
    context = {
        'payments': payments,
        'type_filter': payment_type,
        'page_title': 'Payments'
    }
    return render(request, 'finance/payment_list.html', context)


@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def payment_record(request):
    """Record a payment"""
    invoices = Invoice.objects.filter(status__in=['draft', 'sent'])
    accounts = Account.objects.filter(is_active=True)
    
    if request.method == 'POST':
        invoice_id = request.POST.get('invoice')
        invoice = get_object_or_404(Invoice, id=invoice_id) if invoice_id else None
        
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal(request.POST.get('amount', 0)),
            payment_type=request.POST.get('payment_type', 'incoming'),
            payment_method=request.POST.get('payment_method', 'bank_transfer'),
            reference_number=request.POST.get('reference', ''),
            payment_date=request.POST.get('payment_date') or timezone.now().date(),
            notes=request.POST.get('notes', ''),
            received_by=request.user
        )
        
        # Update invoice status if fully paid
        if invoice:
            total_paid = Payment.objects.filter(
                invoice=invoice,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            if total_paid >= invoice.total_amount:
                invoice.status = 'paid'
                invoice.save()
        
        # Record transaction
        account_id = request.POST.get('account')
        if account_id:
            account = get_object_or_404(Account, id=account_id)
            Transaction.objects.create(
                account=account,
                transaction_type='credit' if payment.payment_type == 'incoming' else 'debit',
                amount=payment.amount,
                description=f'Payment - {payment.reference_number or payment.id}',
                reference_number=payment.reference_number,
                created_by=request.user
            )
            
            # Update account balance
            if payment.payment_type == 'incoming':
                account.current_balance += payment.amount
            else:
                account.current_balance -= payment.amount
            account.save()
        
        messages.success(request, 'Payment recorded successfully')
        return redirect('finance:payment_list')
    
    context = {
        'invoices': invoices,
        'accounts': accounts,
        'page_title': 'Record Payment'
    }
    return render(request, 'finance/payment_form.html', context)


# Expense Management
@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def expense_list(request):
    """List expenses"""
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    
    expenses = Expense.objects.select_related('category', 'submitted_by').order_by('-expense_date')
    
    if status:
        expenses = expenses.filter(status=status)
    if category:
        expenses = expenses.filter(category_id=category)
    
    paginator = Paginator(expenses, 20)
    page = request.GET.get('page', 1)
    expenses = paginator.get_page(page)
    
    categories = ExpenseCategory.objects.filter(is_active=True)
    
    context = {
        'expenses': expenses,
        'categories': categories,
        'status_filter': status,
        'category_filter': category,
        'page_title': 'Expenses'
    }
    return render(request, 'finance/expense_list.html', context)


@login_required
@role_required('super_admin', 'accountant', 'finance_manager')
def expense_create(request):
    """Create expense"""
    categories = ExpenseCategory.objects.filter(is_active=True)
    accounts = Account.objects.filter(is_active=True)
    
    if request.method == 'POST':
        expense = Expense.objects.create(
            category_id=request.POST.get('category'),
            amount=Decimal(request.POST.get('amount', 0)),
            description=request.POST.get('description', ''),
            expense_date=request.POST.get('expense_date') or timezone.now().date(),
            vendor_name=request.POST.get('vendor', ''),
            payment_method=request.POST.get('payment_method', 'cash'),
            reference_number=request.POST.get('reference', ''),
            submitted_by=request.user
        )
        
        # Auto-approve if submitted by finance manager or super admin
        if request.user.role in ['super_admin', 'finance_manager']:
            expense.status = 'approved'
            expense.approved_by = request.user
            expense.approved_on = timezone.now()
            expense.save()
            
            # Record transaction
            account_id = request.POST.get('account')
            if account_id:
                account = get_object_or_404(Account, id=account_id)
                Transaction.objects.create(
                    account=account,
                    transaction_type='debit',
                    amount=expense.amount,
                    description=f'Expense - {expense.description[:50]}',
                    reference_number=expense.reference_number,
                    created_by=request.user
                )
                account.current_balance -= expense.amount
                account.save()
        
        messages.success(request, 'Expense recorded')
        return redirect('finance:expense_list')
    
    context = {
        'categories': categories,
        'accounts': accounts,
        'page_title': 'Add Expense'
    }
    return render(request, 'finance/expense_form.html', context)


@login_required
@role_required('super_admin', 'finance_manager')
def expense_approve(request, expense_id):
    """Approve expense"""
    expense = get_object_or_404(Expense, id=expense_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            expense.status = 'approved'
            expense.approved_by = request.user
            expense.approved_on = timezone.now()
            messages.success(request, 'Expense approved')
        else:
            expense.status = 'rejected'
            expense.rejection_reason = request.POST.get('reason', '')
            messages.success(request, 'Expense rejected')
        
        expense.save()
    
    return redirect('finance:expense_list')


# Account Management
@login_required
@role_required('super_admin', 'finance_manager')
def account_list(request):
    """List accounts"""
    accounts = Account.objects.filter(is_active=True).order_by('name')
    
    total_balance = accounts.aggregate(total=Sum('current_balance'))['total'] or 0
    
    context = {
        'accounts': accounts,
        'total_balance': total_balance,
        'page_title': 'Accounts'
    }
    return render(request, 'finance/account_list.html', context)


@login_required
@role_required('super_admin', 'finance_manager')
def account_create(request):
    """Create account"""
    if request.method == 'POST':
        Account.objects.create(
            name=request.POST.get('name'),
            account_type=request.POST.get('account_type', 'bank'),
            account_number=request.POST.get('account_number', ''),
            bank_name=request.POST.get('bank_name', ''),
            branch=request.POST.get('branch', ''),
            opening_balance=Decimal(request.POST.get('opening_balance', 0)),
            current_balance=Decimal(request.POST.get('opening_balance', 0)),
            description=request.POST.get('description', '')
        )
        messages.success(request, 'Account created')
        return redirect('finance:account_list')
    
    return render(request, 'finance/account_form.html', {'page_title': 'Add Account'})


@login_required
@role_required('super_admin', 'finance_manager')
def account_transactions(request, account_id):
    """View account transactions"""
    account = get_object_or_404(Account, id=account_id)
    
    transactions = Transaction.objects.filter(
        account=account
    ).order_by('-created_at')
    
    paginator = Paginator(transactions, 30)
    page = request.GET.get('page', 1)
    transactions = paginator.get_page(page)
    
    context = {
        'account': account,
        'transactions': transactions,
        'page_title': f'Transactions - {account.name}'
    }
    return render(request, 'finance/account_transactions.html', context)


# Category Management
@login_required
@role_required('super_admin', 'finance_manager')
def category_list(request):
    """List expense categories"""
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('name')
    
    context = {
        'categories': categories,
        'page_title': 'Expense Categories'
    }
    return render(request, 'finance/category_list.html', context)


@login_required
@role_required('super_admin', 'finance_manager')
def category_create(request):
    """Create expense category"""
    if request.method == 'POST':
        ExpenseCategory.objects.create(
            name=request.POST.get('name'),
            description=request.POST.get('description', '')
        )
        messages.success(request, 'Category created')
        return redirect('finance:category_list')
    
    return render(request, 'finance/category_form.html', {'page_title': 'Add Category'})


# Budget Management
@login_required
@role_required('super_admin', 'finance_manager')
def budget_list(request):
    """List budgets"""
    year = request.GET.get('year', timezone.now().year)
    
    budgets = Budget.objects.filter(year=int(year)).select_related('category')
    
    context = {
        'budgets': budgets,
        'year': int(year),
        'page_title': 'Budgets'
    }
    return render(request, 'finance/budget_list.html', context)


@login_required
@role_required('super_admin', 'finance_manager')
def budget_create(request):
    """Create budget"""
    categories = ExpenseCategory.objects.filter(is_active=True)
    
    if request.method == 'POST':
        Budget.objects.create(
            category_id=request.POST.get('category'),
            year=int(request.POST.get('year', timezone.now().year)),
            month=int(request.POST.get('month', 0)) if request.POST.get('month') else None,
            amount=Decimal(request.POST.get('amount', 0)),
            notes=request.POST.get('notes', '')
        )
        messages.success(request, 'Budget created')
        return redirect('finance:budget_list')
    
    context = {
        'categories': categories,
        'page_title': 'Add Budget'
    }
    return render(request, 'finance/budget_form.html', context)


# Financial Reports
@login_required
@role_required('super_admin', 'finance_manager')
def profit_loss_report(request):
    """Profit & Loss report"""
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    
    # Revenue
    revenue = Payment.objects.filter(
        payment_date__month=int(month),
        payment_date__year=int(year),
        payment_type='incoming',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Expenses
    expenses_by_category = Expense.objects.filter(
        expense_date__month=int(month),
        expense_date__year=int(year),
        status='approved'
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    total_expenses = sum(e['total'] for e in expenses_by_category)
    
    profit = revenue - total_expenses
    
    context = {
        'revenue': revenue,
        'expenses_by_category': expenses_by_category,
        'total_expenses': total_expenses,
        'profit': profit,
        'month': int(month),
        'year': int(year),
        'page_title': 'Profit & Loss Report'
    }
    return render(request, 'finance/profit_loss_report.html', context)

from django.db import models
from django.conf import settings
from decimal import Decimal


class AccountHead(models.Model):
    """Chart of accounts"""
    ACCOUNT_TYPES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class BankAccount(models.Model):
    """Company bank accounts"""
    name = models.CharField(max_length=200)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    branch = models.CharField(max_length=100, blank=True)
    iban = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.bank_name}"


class Transaction(models.Model):
    """Financial transactions"""
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('transfer', 'Transfer'),
        ('payment_received', 'Payment Received'),
        ('payment_made', 'Payment Made'),
        ('refund', 'Refund'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('credit', 'Credit'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    account_head = models.ForeignKey(AccountHead, on_delete=models.SET_NULL, null=True, related_name='transactions')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    reference = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    
    # Related entities
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    customer = models.ForeignKey('orders.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    employee = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.transaction_number} - {self.transaction_type} - {self.amount}"


class Invoice(models.Model):
    """Customer invoices"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='invoices')
    customer = models.ForeignKey('orders.Customer', on_delete=models.CASCADE, related_name='invoices')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-invoice_date']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"
    
    def calculate_balance(self):
        self.balance_due = self.total - self.amount_paid
        if self.balance_due <= 0:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        self.save()


class Payment(models.Model):
    """Payment records for invoices"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    ]
    
    payment_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    customer = models.ForeignKey('orders.Customer', on_delete=models.CASCADE, related_name='payments')
    
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    reference = models.CharField(max_length=100, blank=True)
    
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.payment_number} - {self.customer.name} - {self.amount}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update invoice paid amount
        self.invoice.amount_paid = sum(p.amount for p in self.invoice.payments.all())
        self.invoice.calculate_balance()


class Expense(models.Model):
    """General expenses"""
    EXPENSE_CATEGORIES = [
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('salaries', 'Salaries'),
        ('materials', 'Raw Materials'),
        ('transport', 'Transport'),
        ('maintenance', 'Maintenance'),
        ('marketing', 'Marketing'),
        ('office', 'Office Supplies'),
        ('other', 'Other'),
    ]
    
    expense_number = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=30, choices=EXPENSE_CATEGORIES)
    account_head = models.ForeignKey(AccountHead, on_delete=models.SET_NULL, null=True, related_name='expenses')
    
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField()
    
    vendor_name = models.CharField(max_length=200, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    
    payment_method = models.CharField(max_length=20, default='cash')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.expense_number} - {self.category} - {self.amount}"


class DailyClosing(models.Model):
    """Daily cash/account closing"""
    date = models.DateField(unique=True)
    opening_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"Daily Closing - {self.date}"

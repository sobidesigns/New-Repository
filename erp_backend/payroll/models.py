from django.db import models
from django.conf import settings
from decimal import Decimal


class SalaryStructure(models.Model):
    """Salary components structure"""
    name = models.CharField(max_length=100)
    basic_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    housing_allowance = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    transport_allowance = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    medical_allowance = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class PayrollPeriod(models.Model):
    """Payroll periods (monthly)"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('paid', 'Paid'),
    ]
    
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_employees = models.IntegerField(default=0)
    total_gross = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return self.name


class Payslip(models.Model):
    """Individual employee payslips"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='payslips')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='payslips')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Working days
    total_days = models.IntegerField(default=0)
    days_present = models.IntegerField(default=0)
    days_absent = models.IntegerField(default=0)
    days_leave = models.IntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Earnings
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    piece_rate_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Earnings from piece-rate work')
    other_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions
    tax_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    absence_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Net
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment
    payment_method = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period__start_date']
        unique_together = ['employee', 'period']
    
    def __str__(self):
        return f"{self.employee.name} - {self.period.name}"
    
    def calculate_salary(self):
        """Calculate salary based on attendance and earnings"""
        # Calculate gross
        self.gross_salary = (
            self.basic_salary + self.housing_allowance + 
            self.transport_allowance + self.medical_allowance +
            self.overtime_pay + self.bonus + 
            self.piece_rate_earnings + self.other_earnings
        )
        
        # Calculate total deductions
        self.total_deductions = (
            self.tax_deduction + self.loan_deduction +
            self.advance_deduction + self.absence_deduction +
            self.other_deductions
        )
        
        # Calculate net
        self.net_salary = self.gross_salary - self.total_deductions
        self.save()


class EmployeeLoan(models.Model):
    """Employee loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    installments = models.IntegerField(help_text='Number of monthly installments')
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.name} - {self.loan_type} - {self.amount}"
    
    def save(self, *args, **kwargs):
        self.balance = self.amount - self.amount_paid
        super().save(*args, **kwargs)


class EmployeeAdvance(models.Model):
    """Salary advances"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('deducted', 'Deducted'),
        ('rejected', 'Rejected'),
    ]
    
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='advances')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    deduct_from_payroll = models.ForeignKey(PayrollPeriod, on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_advances')
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='paid_advances')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.name} - Advance - {self.amount}"

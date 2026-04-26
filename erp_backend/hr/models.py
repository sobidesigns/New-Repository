from django.db import models
from django.conf import settings
from decimal import Decimal


class Department(models.Model):
    """Company departments"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_departments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Designation(models.Model):
    """Job designations/positions"""
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='designations')
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.department.name}"


class Employee(models.Model):
    """Employee records"""
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    EMPLOYMENT_TYPE = [
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('daily_wage', 'Daily Wage'),
        ('piece_rate', 'Piece Rate'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('resigned', 'Resigned'),
    ]
    
    # Link to user account if applicable
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile')
    
    # Basic Info
    employee_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    date_of_birth = models.DateField(null=True, blank=True)
    cnic = models.CharField(max_length=20, blank=True, help_text='National ID Number')
    phone = models.CharField(max_length=20)
    alternate_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='employees/', blank=True, null=True)
    
    # Employment Info
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='employees')
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, related_name='employees')
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE, default='permanent')
    joining_date = models.DateField()
    termination_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Salary Info
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='For daily wage workers')
    overtime_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Bank Info
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.employee_id} - {self.name}"
    
    @property
    def years_of_service(self):
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta
        end_date = self.termination_date or timezone.now().date()
        diff = relativedelta(end_date, self.joining_date)
        return diff.years


class Attendance(models.Model):
    """Daily attendance records"""
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('late', 'Late'),
        ('on_leave', 'On Leave'),
        ('holiday', 'Holiday'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['employee', 'date']
    
    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"
    
    @property
    def working_hours(self):
        if self.check_in and self.check_out:
            from datetime import datetime, timedelta
            check_in_dt = datetime.combine(self.date, self.check_in)
            check_out_dt = datetime.combine(self.date, self.check_out)
            diff = check_out_dt - check_in_dt
            return round(diff.total_seconds() / 3600, 2)
        return 0


class LeaveType(models.Model):
    """Types of leaves"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    days_allowed = models.IntegerField(default=0, help_text='Annual days allowed')
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    """Employee leave requests"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.name} - {self.leave_type.name} - {self.start_date}"
    
    @property
    def days_count(self):
        return (self.end_date - self.start_date).days + 1


class Holiday(models.Model):
    """Company holidays"""
    name = models.CharField(max_length=100)
    date = models.DateField()
    is_recurring = models.BooleanField(default=False, help_text='Repeats every year')
    
    class Meta:
        ordering = ['date']
    
    def __str__(self):
        return f"{self.name} - {self.date}"

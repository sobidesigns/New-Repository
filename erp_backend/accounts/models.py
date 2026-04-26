from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('owner', 'Owner'),
        ('accounts_manager', 'Accounts Manager'),
        ('inventory_manager', 'Inventory Manager'),
        ('production_manager', 'Production Manager'),
        ('hr_manager', 'HR Manager'),
        ('order_entry', 'Order Entry Clerk'),
        ('cutting_head', 'Cutting Head'),
        ('stitching_head', 'Stitching Head'),
        ('qc_head', 'Quality Control Head'),
        ('ironing_head', 'Ironing Head'),
        ('packing_head', 'Packing Head'),
        ('dispatch_head', 'Dispatch Head'),
    ]
    
    DEPARTMENT_CHOICES = [
        ('management', 'Management'),
        ('accounts', 'Accounts & Finance'),
        ('inventory', 'Inventory'),
        ('production', 'Production'),
        ('hr', 'Human Resources'),
        ('cutting', 'Cutting'),
        ('stitching', 'Stitching'),
        ('quality', 'Quality Control'),
        ('ironing', 'Ironing'),
        ('packing', 'Packing'),
        ('dispatch', 'Dispatch'),
    ]
    
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='order_entry')
    department = models.CharField(max_length=30, choices=DEPARTMENT_CHOICES, default='production')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_active_employee = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
    
    @property
    def is_admin(self):
        return self.role in ['admin', 'owner']
    
    @property
    def is_manager(self):
        return self.role in ['admin', 'owner', 'accounts_manager', 'inventory_manager', 
                             'production_manager', 'hr_manager']
    
    @property
    def is_department_head(self):
        return self.role in ['cutting_head', 'stitching_head', 'qc_head', 
                             'ironing_head', 'packing_head', 'dispatch_head']
    
    def has_permission(self, permission):
        """Check if user has specific permission based on role"""
        permissions_map = {
            'admin': ['all'],
            'owner': ['all'],
            'accounts_manager': ['finance', 'payroll', 'reports', 'orders'],
            'inventory_manager': ['inventory', 'orders', 'reports'],
            'production_manager': ['production', 'orders', 'quality', 'reports'],
            'hr_manager': ['hr', 'payroll', 'employees', 'reports'],
            'order_entry': ['orders'],
            'cutting_head': ['cutting', 'production'],
            'stitching_head': ['stitching', 'production'],
            'qc_head': ['quality', 'production'],
            'ironing_head': ['ironing', 'production'],
            'packing_head': ['packing', 'production'],
            'dispatch_head': ['dispatch', 'production'],
        }
        user_perms = permissions_map.get(self.role, [])
        return 'all' in user_perms or permission in user_perms


class ActivityLog(models.Model):
    """Track user activities for audit purposes"""
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('login', 'Logged In'),
        ('logout', 'Logged Out'),
        ('export', 'Exported'),
        ('status_change', 'Status Changed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.IntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name}"


class SystemSetting(models.Model):
    """Store system-wide settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_value(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

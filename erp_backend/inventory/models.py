from django.db import models
from django.conf import settings
from decimal import Decimal


class Category(models.Model):
    """Material/Product categories"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Supplier(models.Model):
    """Material suppliers/vendors"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Material(models.Model):
    """Raw materials inventory"""
    UNIT_CHOICES = [
        ('meter', 'Meters'),
        ('yard', 'Yards'),
        ('kg', 'Kilograms'),
        ('pcs', 'Pieces'),
        ('roll', 'Rolls'),
        ('dozen', 'Dozen'),
        ('gross', 'Gross'),
        ('set', 'Set'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='materials')
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='meter')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials')
    location = models.CharField(max_length=100, blank=True, help_text='Storage location/rack')
    color = models.CharField(max_length=50, blank=True)
    width = models.CharField(max_length=50, blank=True)
    gsm = models.CharField(max_length=50, blank=True, help_text='Grams per square meter')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def total_value(self):
        return self.quantity * self.unit_price
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock_level


class StockMovement(models.Model):
    """Track all stock movements (in/out)"""
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('return', 'Return'),
    ]
    
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference = models.CharField(max_length=100, blank=True, help_text='PO number, Order number, etc.')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.material.name} - {self.movement_type} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Update material quantity based on movement type
        if not self.pk:  # Only on create
            if self.movement_type == 'in':
                self.material.quantity += self.quantity
            elif self.movement_type in ['out', 'transfer']:
                self.material.quantity -= self.quantity
            elif self.movement_type == 'adjustment':
                self.material.quantity = self.quantity
            elif self.movement_type == 'return':
                self.material.quantity += self.quantity
            self.material.save()
        super().save(*args, **kwargs)


class PurchaseOrder(models.Model):
    """Purchase orders for materials"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('partial', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_pos')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"
    
    def calculate_totals(self):
        self.subtotal = sum(item.total for item in self.items.all())
        self.total = self.subtotal + self.tax - self.discount
        self.save()


class PurchaseOrderItem(models.Model):
    """Items in a purchase order"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.material.name} - {self.quantity}"

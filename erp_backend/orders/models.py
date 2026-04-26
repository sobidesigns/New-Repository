from django.db import models
from django.conf import settings
from decimal import Decimal


class Customer(models.Model):
    """Customer/Client information"""
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail'),
    ]
    
    name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='business')
    phone = models.CharField(max_length=20)
    alternate_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.company_name or self.name


class ProductCategory(models.Model):
    """Product categories (e.g., Shirts, Pants, etc.)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = 'Product Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Products/Articles that can be manufactured"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, related_name='products')
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Order(models.Model):
    """Main order/job card"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_production', 'In Production'),
        ('cutting', 'Cutting'),
        ('stitching', 'Stitching'),
        ('quality_check', 'Quality Check'),
        ('ironing', 'Ironing'),
        ('packing', 'Packing'),
        ('dispatch', 'Ready for Dispatch'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    order_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    order_date = models.DateField()
    delivery_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tracking
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True, help_text='Internal notes not visible to customer')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_orders')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='updated_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"
    
    def calculate_totals(self):
        self.subtotal = sum(item.total for item in self.items.all())
        self.discount_amount = self.subtotal * (self.discount_percent / 100)
        taxable = self.subtotal - self.discount_amount
        self.tax_amount = taxable * (self.tax_percent / 100)
        self.total = taxable + self.tax_amount
        self.balance_due = self.total - self.advance_paid
        self.save()
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status not in ['delivered', 'cancelled']:
            return self.delivery_date < timezone.now().date()
        return False
    
    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """Individual items in an order"""
    SIZE_CHOICES = [
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', '2X Large'),
        ('XXXL', '3X Large'),
        ('custom', 'Custom'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.TextField(blank=True, help_text='Custom specifications')
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='M')
    custom_measurements = models.JSONField(default=dict, blank=True)
    color = models.CharField(max_length=50, blank=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Production tracking
    quantity_cut = models.IntegerField(default=0)
    quantity_stitched = models.IntegerField(default=0)
    quantity_qc_passed = models.IntegerField(default=0)
    quantity_qc_failed = models.IntegerField(default=0)
    quantity_ironed = models.IntegerField(default=0)
    quantity_packed = models.IntegerField(default=0)
    quantity_dispatched = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['id']
    
    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class OrderStatusHistory(models.Model):
    """Track order status changes"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} -> {self.to_status}"


class OrderAttachment(models.Model):
    """Attachments for orders (designs, references, etc.)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='order_attachments/')
    filename = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename

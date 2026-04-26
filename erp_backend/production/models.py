from django.db import models
from django.conf import settings


class ProductionBatch(models.Model):
    """Production batch/lot tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ]
    
    batch_number = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='production_batches')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='production_batches')
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Production Batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.batch_number} - {self.order.order_number}"


class CuttingRecord(models.Model):
    """Cutting department records"""
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='cutting_records')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='cutting_records')
    worker = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='cutting_work')
    quantity_assigned = models.IntegerField()
    quantity_completed = models.IntegerField(default=0)
    quantity_rejected = models.IntegerField(default=0)
    fabric_used = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Fabric used in meters')
    fabric_waste = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Cutting - {self.batch.batch_number} - {self.quantity_completed}/{self.quantity_assigned}"


class StitchingRecord(models.Model):
    """Stitching department records"""
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='stitching_records')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='stitching_records')
    worker = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='stitching_work')
    quantity_assigned = models.IntegerField()
    quantity_completed = models.IntegerField(default=0)
    quantity_rejected = models.IntegerField(default=0)
    machine_number = models.CharField(max_length=50, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Stitching - {self.batch.batch_number} - {self.quantity_completed}/{self.quantity_assigned}"


class IroningRecord(models.Model):
    """Ironing department records"""
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='ironing_records')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='ironing_records')
    worker = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='ironing_work')
    quantity_assigned = models.IntegerField()
    quantity_completed = models.IntegerField(default=0)
    quantity_rejected = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ironing - {self.batch.batch_number} - {self.quantity_completed}/{self.quantity_assigned}"


class PackingRecord(models.Model):
    """Packing department records"""
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='packing_records')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='packing_records')
    worker = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='packing_work')
    quantity_assigned = models.IntegerField()
    quantity_packed = models.IntegerField(default=0)
    packing_type = models.CharField(max_length=100, blank=True)
    carton_count = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Packing - {self.batch.batch_number} - {self.quantity_packed}/{self.quantity_assigned}"


class DispatchRecord(models.Model):
    """Dispatch records"""
    DISPATCH_STATUS = [
        ('pending', 'Pending'),
        ('ready', 'Ready for Pickup'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
    ]
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='dispatch_records')
    dispatch_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=DISPATCH_STATUS, default='pending')
    courier_name = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    total_cartons = models.IntegerField(default=0)
    total_quantity = models.IntegerField(default=0)
    dispatch_date = models.DateTimeField(null=True, blank=True)
    delivery_date = models.DateTimeField(null=True, blank=True)
    receiver_name = models.CharField(max_length=100, blank=True)
    receiver_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.dispatch_number} - {self.order.order_number}"


class WorkerTask(models.Model):
    """Track individual worker tasks/assignments"""
    TASK_TYPES = [
        ('cutting', 'Cutting'),
        ('stitching', 'Stitching'),
        ('ironing', 'Ironing'),
        ('packing', 'Packing'),
        ('quality', 'Quality Check'),
    ]
    
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ]
    
    worker = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='tasks')
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='worker_tasks')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='worker_tasks')
    quantity_assigned = models.IntegerField()
    quantity_completed = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    rate_per_piece = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        self.total_earnings = self.quantity_completed * self.rate_per_piece
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.worker.name} - {self.task_type} - {self.quantity_completed}/{self.quantity_assigned}"

from django.db import models
from django.conf import settings


class QualityCheckpoint(models.Model):
    """Quality checkpoints/criteria"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=50, blank=True)
    is_critical = models.BooleanField(default=False, help_text='Critical checkpoints must pass')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class QualityInspection(models.Model):
    """Quality inspection records"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Pass'),
    ]
    
    STAGE_CHOICES = [
        ('cutting', 'After Cutting'),
        ('stitching', 'After Stitching'),
        ('ironing', 'After Ironing'),
        ('final', 'Final Inspection'),
    ]
    
    inspection_number = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='inspections')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='inspections')
    batch = models.ForeignKey('production.ProductionBatch', on_delete=models.SET_NULL, null=True, blank=True, related_name='inspections')
    
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    quantity_inspected = models.IntegerField(default=0)
    quantity_passed = models.IntegerField(default=0)
    quantity_failed = models.IntegerField(default=0)
    quantity_rework = models.IntegerField(default=0)
    
    inspection_date = models.DateField()
    inspector = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='inspections')
    
    overall_remarks = models.TextField(blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-inspection_date', '-created_at']
    
    def __str__(self):
        return f"{self.inspection_number} - {self.order.order_number}"
    
    @property
    def pass_rate(self):
        if self.quantity_inspected > 0:
            return round((self.quantity_passed / self.quantity_inspected) * 100, 2)
        return 0


class InspectionDetail(models.Model):
    """Individual checkpoint results in an inspection"""
    RESULT_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('na', 'Not Applicable'),
    ]
    
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name='details')
    checkpoint = models.ForeignKey(QualityCheckpoint, on_delete=models.CASCADE)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='pass')
    remarks = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.checkpoint.name} - {self.result}"


class DefectType(models.Model):
    """Types of defects"""
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='minor')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.severity})"


class DefectRecord(models.Model):
    """Record of defects found"""
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name='defects')
    defect_type = models.ForeignKey(DefectType, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='defects/', blank=True, null=True)
    action_taken = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.defect_type.name} x {self.quantity}"


class ReworkRecord(models.Model):
    """Track items sent for rework"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('scrapped', 'Scrapped'),
    ]
    
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name='rework_records')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='rework_records')
    
    quantity = models.IntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    assigned_to = models.ForeignKey('hr.Employee', on_delete=models.SET_NULL, null=True, related_name='rework_assignments')
    completed_quantity = models.IntegerField(default=0)
    scrapped_quantity = models.IntegerField(default=0)
    
    start_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Rework - {self.inspection.inspection_number} - {self.quantity} pcs"

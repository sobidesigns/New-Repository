from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Q
from django.core.paginator import Paginator
from django.utils import timezone
from functools import wraps

from .models import (
    QualityCheckpoint, QualityInspection, DefectType, 
    DefectRecord, QualityReport
)
from orders.models import Order
from production.models import ProductionLog


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
@role_required('super_admin', 'qc_head', 'production_manager')
def quality_dashboard(request):
    """Quality control dashboard"""
    today = timezone.now().date()
    
    # Today's stats
    inspections_today = QualityInspection.objects.filter(
        inspection_date=today
    ).aggregate(
        count=Count('id'),
        passed=Count('id', filter=Q(result='passed')),
        failed=Count('id', filter=Q(result='failed'))
    )
    
    # Pass rate this month
    month_start = today.replace(day=1)
    month_inspections = QualityInspection.objects.filter(
        inspection_date__gte=month_start
    )
    total_month = month_inspections.count()
    passed_month = month_inspections.filter(result='passed').count()
    pass_rate = (passed_month / total_month * 100) if total_month > 0 else 0
    
    # Top defects
    top_defects = DefectRecord.objects.filter(
        created_at__gte=month_start
    ).values('defect_type__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Pending inspections
    pending_orders = Order.objects.filter(
        status='quality_check'
    ).count()
    
    # Recent inspections
    recent_inspections = QualityInspection.objects.select_related(
        'order', 'inspector'
    ).order_by('-created_at')[:10]
    
    context = {
        'inspections_today': inspections_today,
        'pass_rate': round(pass_rate, 1),
        'top_defects': top_defects,
        'pending_orders': pending_orders,
        'recent_inspections': recent_inspections,
        'page_title': 'Quality Control'
    }
    return render(request, 'quality/dashboard.html', context)


@login_required
@role_required('super_admin', 'qc_head', 'production_manager')
def inspection_list(request):
    """List quality inspections"""
    result_filter = request.GET.get('result', '')
    checkpoint_filter = request.GET.get('checkpoint', '')
    
    inspections = QualityInspection.objects.select_related(
        'order', 'checkpoint', 'inspector'
    ).order_by('-inspection_date', '-created_at')
    
    if result_filter:
        inspections = inspections.filter(result=result_filter)
    if checkpoint_filter:
        inspections = inspections.filter(checkpoint_id=checkpoint_filter)
    
    paginator = Paginator(inspections, 20)
    page = request.GET.get('page', 1)
    inspections = paginator.get_page(page)
    
    checkpoints = QualityCheckpoint.objects.filter(is_active=True)
    
    context = {
        'inspections': inspections,
        'checkpoints': checkpoints,
        'result_filter': result_filter,
        'checkpoint_filter': checkpoint_filter,
        'page_title': 'Quality Inspections'
    }
    return render(request, 'quality/inspection_list.html', context)


@login_required
@role_required('super_admin', 'qc_head')
def inspection_create(request):
    """Create quality inspection"""
    orders = Order.objects.filter(status='quality_check')
    checkpoints = QualityCheckpoint.objects.filter(is_active=True)
    defect_types = DefectType.objects.filter(is_active=True)
    
    if request.method == 'POST':
        order_id = request.POST.get('order')
        order = get_object_or_404(Order, id=order_id)
        
        inspection = QualityInspection.objects.create(
            order=order,
            checkpoint_id=request.POST.get('checkpoint'),
            inspector=request.user,
            inspection_date=timezone.now().date(),
            sample_size=int(request.POST.get('sample_size', 0)),
            passed_count=int(request.POST.get('passed_count', 0)),
            failed_count=int(request.POST.get('failed_count', 0)),
            result=request.POST.get('result', 'pending'),
            notes=request.POST.get('notes', '')
        )
        
        # Record defects if any
        defect_ids = request.POST.getlist('defect_type[]')
        defect_counts = request.POST.getlist('defect_count[]')
        
        for i, defect_id in enumerate(defect_ids):
            if defect_id and defect_counts[i]:
                DefectRecord.objects.create(
                    inspection=inspection,
                    defect_type_id=defect_id,
                    quantity=int(defect_counts[i]),
                    notes=request.POST.get(f'defect_notes_{i}', '')
                )
        
        # Log production activity
        ProductionLog.objects.create(
            order=order,
            stage='qc',
            action='inspection_completed',
            performed_by=request.user,
            notes=f'QC Inspection: {inspection.result}'
        )
        
        messages.success(request, 'Inspection recorded successfully')
        return redirect('quality:inspection_list')
    
    context = {
        'orders': orders,
        'checkpoints': checkpoints,
        'defect_types': defect_types,
        'page_title': 'New Inspection'
    }
    return render(request, 'quality/inspection_form.html', context)


@login_required
@role_required('super_admin', 'qc_head')
def inspection_detail(request, inspection_id):
    """View inspection details"""
    inspection = get_object_or_404(QualityInspection, id=inspection_id)
    defects = DefectRecord.objects.filter(inspection=inspection).select_related('defect_type')
    
    context = {
        'inspection': inspection,
        'defects': defects,
        'page_title': f'Inspection #{inspection.id}'
    }
    return render(request, 'quality/inspection_detail.html', context)


# Defect Management
@login_required
@role_required('super_admin', 'qc_head')
def defect_type_list(request):
    """List defect types"""
    defect_types = DefectType.objects.filter(is_active=True).annotate(
        occurrence_count=Count('defectrecord')
    ).order_by('name')
    
    context = {
        'defect_types': defect_types,
        'page_title': 'Defect Types'
    }
    return render(request, 'quality/defect_type_list.html', context)


@login_required
@role_required('super_admin', 'qc_head')
def defect_type_create(request):
    """Create defect type"""
    if request.method == 'POST':
        DefectType.objects.create(
            name=request.POST.get('name'),
            code=request.POST.get('code', ''),
            category=request.POST.get('category', 'other'),
            severity=request.POST.get('severity', 'minor'),
            description=request.POST.get('description', '')
        )
        messages.success(request, 'Defect type created')
        return redirect('quality:defect_type_list')
    
    return render(request, 'quality/defect_type_form.html', {'page_title': 'Add Defect Type'})


@login_required
@role_required('super_admin', 'qc_head')
def defect_analysis(request):
    """Defect analysis report"""
    days = int(request.GET.get('days', 30))
    start_date = timezone.now().date() - timezone.timedelta(days=days)
    
    # Defects by type
    by_type = DefectRecord.objects.filter(
        created_at__date__gte=start_date
    ).values('defect_type__name', 'defect_type__severity').annotate(
        count=Count('id'),
        total_qty=Sum('quantity')
    ).order_by('-count')
    
    # Defects by category
    by_category = DefectRecord.objects.filter(
        created_at__date__gte=start_date
    ).values('defect_type__category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Daily trend
    daily_trend = DefectRecord.objects.filter(
        created_at__date__gte=start_date
    ).extra(
        select={'date': 'DATE(created_at)'}
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    context = {
        'by_type': by_type,
        'by_category': by_category,
        'daily_trend': list(daily_trend),
        'days': days,
        'page_title': 'Defect Analysis'
    }
    return render(request, 'quality/defect_analysis.html', context)


# Checkpoint Management
@login_required
@role_required('super_admin', 'qc_head')
def checkpoint_list(request):
    """List quality checkpoints"""
    checkpoints = QualityCheckpoint.objects.filter(is_active=True).order_by('sequence')
    
    context = {
        'checkpoints': checkpoints,
        'page_title': 'Quality Checkpoints'
    }
    return render(request, 'quality/checkpoint_list.html', context)


@login_required
@role_required('super_admin', 'qc_head')
def checkpoint_create(request):
    """Create checkpoint"""
    if request.method == 'POST':
        QualityCheckpoint.objects.create(
            name=request.POST.get('name'),
            stage=request.POST.get('stage'),
            sequence=int(request.POST.get('sequence', 0)),
            description=request.POST.get('description', ''),
            criteria=request.POST.get('criteria', ''),
            is_mandatory=request.POST.get('is_mandatory') == 'on'
        )
        messages.success(request, 'Checkpoint created')
        return redirect('quality:checkpoint_list')
    
    return render(request, 'quality/checkpoint_form.html', {'page_title': 'Add Checkpoint'})


# Quality Reports
@login_required
@role_required('super_admin', 'qc_head', 'production_manager')
def quality_report(request):
    """Generate quality report"""
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    inspections = QualityInspection.objects.filter(
        inspection_date__month=month,
        inspection_date__year=year
    )
    
    total = inspections.count()
    passed = inspections.filter(result='passed').count()
    failed = inspections.filter(result='failed').count()
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    # By checkpoint
    by_checkpoint = inspections.values('checkpoint__name').annotate(
        total=Count('id'),
        passed=Count('id', filter=Q(result='passed')),
        failed=Count('id', filter=Q(result='failed'))
    )
    
    # Top defects
    top_defects = DefectRecord.objects.filter(
        inspection__inspection_date__month=month,
        inspection__inspection_date__year=year
    ).values('defect_type__name').annotate(
        count=Sum('quantity')
    ).order_by('-count')[:10]
    
    context = {
        'total': total,
        'passed': passed,
        'failed': failed,
        'pass_rate': round(pass_rate, 1),
        'by_checkpoint': by_checkpoint,
        'top_defects': top_defects,
        'month': month,
        'year': year,
        'page_title': 'Quality Report'
    }
    return render(request, 'quality/quality_report.html', context)


@login_required
@role_required('super_admin', 'qc_head')
def save_quality_report(request):
    """Save quality report"""
    if request.method == 'POST':
        month = int(request.POST.get('month', timezone.now().month))
        year = int(request.POST.get('year', timezone.now().year))
        
        inspections = QualityInspection.objects.filter(
            inspection_date__month=month,
            inspection_date__year=year
        )
        
        total = inspections.count()
        passed = inspections.filter(result='passed').count()
        
        QualityReport.objects.create(
            report_type='monthly',
            period_start=timezone.now().date().replace(day=1),
            period_end=timezone.now().date(),
            total_inspections=total,
            passed_inspections=passed,
            pass_rate=(passed / total * 100) if total > 0 else 0,
            summary=request.POST.get('summary', ''),
            recommendations=request.POST.get('recommendations', ''),
            generated_by=request.user
        )
        
        messages.success(request, 'Quality report saved')
        return redirect('quality:dashboard')
    
    return redirect('quality:quality_report')

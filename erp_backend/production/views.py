from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from functools import wraps

from .models import (
    CuttingTask, StitchingTask, QCTask, IroningTask, 
    PackingTask, DispatchTask, ProductionLog
)
from orders.models import Order, OrderItem
from accounts.models import User
from hr.models import Employee


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
@role_required('super_admin', 'production_manager', 'cutting_master')
def cutting_dashboard(request):
    """Dashboard for cutting department"""
    pending_tasks = CuttingTask.objects.filter(status='pending').select_related('order', 'assigned_to')
    in_progress_tasks = CuttingTask.objects.filter(status='in_progress').select_related('order', 'assigned_to')
    completed_today = CuttingTask.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).count()
    
    cutters = Employee.objects.filter(department='cutting', is_active=True)
    
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_today': completed_today,
        'cutters': cutters,
        'page_title': 'Cutting Department'
    }
    return render(request, 'production/cutting_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'cutting_master')
def cutting_task_list(request):
    """List all cutting tasks"""
    status_filter = request.GET.get('status', '')
    tasks = CuttingTask.objects.select_related('order', 'assigned_to').order_by('-created_at')
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    context = {
        'tasks': tasks,
        'status_filter': status_filter,
        'page_title': 'Cutting Tasks'
    }
    return render(request, 'production/cutting_task_list.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'cutting_master')
def create_cutting_task(request, order_id):
    """Create cutting task for an order"""
    order = get_object_or_404(Order, id=order_id)
    cutters = Employee.objects.filter(department='cutting', is_active=True)
    
    if request.method == 'POST':
        assigned_to_id = request.POST.get('assigned_to')
        notes = request.POST.get('notes', '')
        
        task = CuttingTask.objects.create(
            order=order,
            assigned_to_id=assigned_to_id if assigned_to_id else None,
            notes=notes,
            created_by=request.user
        )
        
        # Update order status
        order.status = 'cutting'
        order.save()
        
        # Log production activity
        ProductionLog.objects.create(
            order=order,
            stage='cutting',
            action='task_created',
            performed_by=request.user,
            notes=f'Cutting task created and assigned'
        )
        
        messages.success(request, f'Cutting task created for Order #{order.order_number}')
        return redirect('production:cutting_dashboard')
    
    context = {
        'order': order,
        'cutters': cutters,
        'page_title': 'Create Cutting Task'
    }
    return render(request, 'production/cutting_task_form.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'cutting_master')
def update_cutting_task(request, task_id):
    """Update cutting task status"""
    task = get_object_or_404(CuttingTask, id=task_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        pieces_cut = request.POST.get('pieces_cut')
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        if pieces_cut:
            task.pieces_cut = int(pieces_cut)
        task.notes = notes
        
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
            # Auto-create stitching task
            StitchingTask.objects.create(
                order=task.order,
                cutting_task=task,
                created_by=request.user
            )
            task.order.status = 'stitching'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='cutting',
                action='completed',
                performed_by=request.user,
                notes=f'Cutting completed. {task.pieces_cut} pieces cut.'
            )
        
        task.save()
        messages.success(request, 'Cutting task updated successfully')
        return redirect('production:cutting_dashboard')
    
    context = {
        'task': task,
        'page_title': 'Update Cutting Task'
    }
    return render(request, 'production/cutting_task_update.html', context)


# Stitching Views
@login_required
@role_required('super_admin', 'production_manager', 'stitching_supervisor')
def stitching_dashboard(request):
    """Dashboard for stitching department"""
    pending_tasks = StitchingTask.objects.filter(status='pending').select_related('order', 'assigned_to')
    in_progress_tasks = StitchingTask.objects.filter(status='in_progress').select_related('order', 'assigned_to')
    completed_today = StitchingTask.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).count()
    
    stitchers = Employee.objects.filter(department='stitching', is_active=True)
    
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_today': completed_today,
        'stitchers': stitchers,
        'page_title': 'Stitching Department'
    }
    return render(request, 'production/stitching_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'stitching_supervisor')
def update_stitching_task(request, task_id):
    """Update stitching task status"""
    task = get_object_or_404(StitchingTask, id=task_id)
    stitchers = Employee.objects.filter(department='stitching', is_active=True)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        assigned_to_id = request.POST.get('assigned_to')
        pieces_stitched = request.POST.get('pieces_stitched')
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        if assigned_to_id:
            task.assigned_to_id = assigned_to_id
        if pieces_stitched:
            task.pieces_stitched = int(pieces_stitched)
        task.notes = notes
        
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
            # Auto-create QC task
            QCTask.objects.create(
                order=task.order,
                stitching_task=task,
                created_by=request.user
            )
            task.order.status = 'quality_check'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='stitching',
                action='completed',
                performed_by=request.user,
                notes=f'Stitching completed. {task.pieces_stitched} pieces stitched.'
            )
        
        task.save()
        messages.success(request, 'Stitching task updated successfully')
        return redirect('production:stitching_dashboard')
    
    context = {
        'task': task,
        'stitchers': stitchers,
        'page_title': 'Update Stitching Task'
    }
    return render(request, 'production/stitching_task_update.html', context)


# QC Views
@login_required
@role_required('super_admin', 'production_manager', 'qc_head')
def qc_dashboard(request):
    """Dashboard for QC department"""
    pending_tasks = QCTask.objects.filter(status='pending').select_related('order')
    in_progress_tasks = QCTask.objects.filter(status='in_progress').select_related('order')
    completed_today = QCTask.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).count()
    
    qc_staff = Employee.objects.filter(department='qc', is_active=True)
    
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_today': completed_today,
        'qc_staff': qc_staff,
        'page_title': 'Quality Control'
    }
    return render(request, 'production/qc_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'qc_head')
def update_qc_task(request, task_id):
    """Update QC task status"""
    task = get_object_or_404(QCTask, id=task_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        passed_pieces = request.POST.get('passed_pieces', 0)
        rejected_pieces = request.POST.get('rejected_pieces', 0)
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        task.passed_pieces = int(passed_pieces) if passed_pieces else 0
        task.rejected_pieces = int(rejected_pieces) if rejected_pieces else 0
        task.notes = notes
        
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
            # Auto-create ironing task
            IroningTask.objects.create(
                order=task.order,
                qc_task=task,
                pieces_to_iron=task.passed_pieces,
                created_by=request.user
            )
            task.order.status = 'ironing'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='qc',
                action='completed',
                performed_by=request.user,
                notes=f'QC completed. Passed: {task.passed_pieces}, Rejected: {task.rejected_pieces}'
            )
        
        task.save()
        messages.success(request, 'QC task updated successfully')
        return redirect('production:qc_dashboard')
    
    context = {
        'task': task,
        'page_title': 'Update QC Task'
    }
    return render(request, 'production/qc_task_update.html', context)


# Ironing Views
@login_required
@role_required('super_admin', 'production_manager', 'ironing_incharge')
def ironing_dashboard(request):
    """Dashboard for ironing department"""
    pending_tasks = IroningTask.objects.filter(status='pending').select_related('order')
    in_progress_tasks = IroningTask.objects.filter(status='in_progress').select_related('order')
    completed_today = IroningTask.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).count()
    
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_today': completed_today,
        'page_title': 'Ironing Department'
    }
    return render(request, 'production/ironing_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'ironing_incharge')
def update_ironing_task(request, task_id):
    """Update ironing task status"""
    task = get_object_or_404(IroningTask, id=task_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        pieces_ironed = request.POST.get('pieces_ironed', 0)
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        task.pieces_ironed = int(pieces_ironed) if pieces_ironed else 0
        task.notes = notes
        
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
            # Auto-create packing task
            PackingTask.objects.create(
                order=task.order,
                ironing_task=task,
                pieces_to_pack=task.pieces_ironed,
                created_by=request.user
            )
            task.order.status = 'packing'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='ironing',
                action='completed',
                performed_by=request.user,
                notes=f'Ironing completed. {task.pieces_ironed} pieces ironed.'
            )
        
        task.save()
        messages.success(request, 'Ironing task updated successfully')
        return redirect('production:ironing_dashboard')
    
    context = {
        'task': task,
        'page_title': 'Update Ironing Task'
    }
    return render(request, 'production/ironing_task_update.html', context)


# Packing Views
@login_required
@role_required('super_admin', 'production_manager', 'packing_head')
def packing_dashboard(request):
    """Dashboard for packing department"""
    pending_tasks = PackingTask.objects.filter(status='pending').select_related('order')
    in_progress_tasks = PackingTask.objects.filter(status='in_progress').select_related('order')
    completed_today = PackingTask.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).count()
    
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_today': completed_today,
        'page_title': 'Packing Department'
    }
    return render(request, 'production/packing_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'packing_head')
def update_packing_task(request, task_id):
    """Update packing task status"""
    task = get_object_or_404(PackingTask, id=task_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        pieces_packed = request.POST.get('pieces_packed', 0)
        carton_count = request.POST.get('carton_count', 0)
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        task.pieces_packed = int(pieces_packed) if pieces_packed else 0
        task.carton_count = int(carton_count) if carton_count else 0
        task.notes = notes
        
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
            # Auto-create dispatch task
            DispatchTask.objects.create(
                order=task.order,
                packing_task=task,
                carton_count=task.carton_count,
                created_by=request.user
            )
            task.order.status = 'dispatch'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='packing',
                action='completed',
                performed_by=request.user,
                notes=f'Packing completed. {task.pieces_packed} pieces in {task.carton_count} cartons.'
            )
        
        task.save()
        messages.success(request, 'Packing task updated successfully')
        return redirect('production:packing_dashboard')
    
    context = {
        'task': task,
        'page_title': 'Update Packing Task'
    }
    return render(request, 'production/packing_task_update.html', context)


# Dispatch Views
@login_required
@role_required('super_admin', 'production_manager', 'dispatch_manager')
def dispatch_dashboard(request):
    """Dashboard for dispatch department"""
    pending_tasks = DispatchTask.objects.filter(status='pending').select_related('order')
    in_transit = DispatchTask.objects.filter(status='in_transit').select_related('order')
    delivered_today = DispatchTask.objects.filter(
        status='delivered',
        delivered_at__date=timezone.now().date()
    ).count()
    
    context = {
        'pending_tasks': pending_tasks,
        'in_transit': in_transit,
        'delivered_today': delivered_today,
        'page_title': 'Dispatch Department'
    }
    return render(request, 'production/dispatch_dashboard.html', context)


@login_required
@role_required('super_admin', 'production_manager', 'dispatch_manager')
def update_dispatch_task(request, task_id):
    """Update dispatch task status"""
    task = get_object_or_404(DispatchTask, id=task_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        vehicle_number = request.POST.get('vehicle_number', '')
        driver_name = request.POST.get('driver_name', '')
        driver_phone = request.POST.get('driver_phone', '')
        tracking_number = request.POST.get('tracking_number', '')
        notes = request.POST.get('notes', '')
        
        task.status = new_status
        task.vehicle_number = vehicle_number
        task.driver_name = driver_name
        task.driver_phone = driver_phone
        task.tracking_number = tracking_number
        task.notes = notes
        
        if new_status == 'in_transit' and not task.dispatched_at:
            task.dispatched_at = timezone.now()
            task.order.status = 'dispatched'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='dispatch',
                action='dispatched',
                performed_by=request.user,
                notes=f'Order dispatched. Vehicle: {vehicle_number}'
            )
        elif new_status == 'delivered':
            task.delivered_at = timezone.now()
            task.order.status = 'delivered'
            task.order.save()
            
            ProductionLog.objects.create(
                order=task.order,
                stage='dispatch',
                action='delivered',
                performed_by=request.user,
                notes='Order delivered successfully.'
            )
        
        task.save()
        messages.success(request, 'Dispatch task updated successfully')
        return redirect('production:dispatch_dashboard')
    
    context = {
        'task': task,
        'page_title': 'Update Dispatch Task'
    }
    return render(request, 'production/dispatch_task_update.html', context)


# Production Overview
@login_required
@role_required('super_admin', 'production_manager')
def production_overview(request):
    """Overall production status dashboard"""
    today = timezone.now().date()
    
    stats = {
        'cutting_pending': CuttingTask.objects.filter(status='pending').count(),
        'cutting_progress': CuttingTask.objects.filter(status='in_progress').count(),
        'stitching_pending': StitchingTask.objects.filter(status='pending').count(),
        'stitching_progress': StitchingTask.objects.filter(status='in_progress').count(),
        'qc_pending': QCTask.objects.filter(status='pending').count(),
        'qc_progress': QCTask.objects.filter(status='in_progress').count(),
        'ironing_pending': IroningTask.objects.filter(status='pending').count(),
        'ironing_progress': IroningTask.objects.filter(status='in_progress').count(),
        'packing_pending': PackingTask.objects.filter(status='pending').count(),
        'packing_progress': PackingTask.objects.filter(status='in_progress').count(),
        'dispatch_pending': DispatchTask.objects.filter(status='pending').count(),
        'dispatch_transit': DispatchTask.objects.filter(status='in_transit').count(),
    }
    
    # Recent production logs
    recent_logs = ProductionLog.objects.select_related(
        'order', 'performed_by'
    ).order_by('-created_at')[:20]
    
    context = {
        'stats': stats,
        'recent_logs': recent_logs,
        'page_title': 'Production Overview'
    }
    return render(request, 'production/overview.html', context)


# API endpoints for AJAX updates
@login_required
def api_update_task_status(request):
    """API endpoint for updating task status via AJAX"""
    if request.method == 'POST':
        task_type = request.POST.get('task_type')
        task_id = request.POST.get('task_id')
        new_status = request.POST.get('status')
        
        model_map = {
            'cutting': CuttingTask,
            'stitching': StitchingTask,
            'qc': QCTask,
            'ironing': IroningTask,
            'packing': PackingTask,
            'dispatch': DispatchTask,
        }
        
        model = model_map.get(task_type)
        if model:
            task = get_object_or_404(model, id=task_id)
            task.status = new_status
            task.save()
            return JsonResponse({'success': True, 'message': 'Status updated'})
        
        return JsonResponse({'success': False, 'message': 'Invalid task type'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

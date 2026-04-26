from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, F, Q
from django.core.paginator import Paginator
from functools import wraps

from .models import (
    MaterialCategory, Material, MaterialStock, StockMovement,
    Supplier, PurchaseOrder, PurchaseOrderItem
)


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
@role_required('super_admin', 'inventory_manager', 'store_keeper')
def inventory_dashboard(request):
    """Inventory overview dashboard"""
    low_stock_items = MaterialStock.objects.filter(
        quantity__lte=F('reorder_level')
    ).select_related('material')[:10]
    
    total_materials = Material.objects.filter(is_active=True).count()
    total_stock_value = MaterialStock.objects.aggregate(
        total=Sum(F('quantity') * F('unit_cost'))
    )['total'] or 0
    
    recent_movements = StockMovement.objects.select_related(
        'material', 'performed_by'
    ).order_by('-created_at')[:10]
    
    pending_pos = PurchaseOrder.objects.filter(
        status__in=['pending', 'approved']
    ).count()
    
    context = {
        'low_stock_items': low_stock_items,
        'total_materials': total_materials,
        'total_stock_value': total_stock_value,
        'recent_movements': recent_movements,
        'pending_pos': pending_pos,
        'page_title': 'Inventory Dashboard'
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
@role_required('super_admin', 'inventory_manager', 'store_keeper')
def material_list(request):
    """List all materials"""
    search = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    
    materials = Material.objects.filter(is_active=True).select_related('category')
    
    if search:
        materials = materials.filter(
            Q(name__icontains=search) | 
            Q(sku__icontains=search)
        )
    
    if category_id:
        materials = materials.filter(category_id=category_id)
    
    materials = materials.order_by('name')
    
    paginator = Paginator(materials, 20)
    page = request.GET.get('page', 1)
    materials = paginator.get_page(page)
    
    categories = MaterialCategory.objects.filter(is_active=True)
    
    context = {
        'materials': materials,
        'categories': categories,
        'search': search,
        'category_id': category_id,
        'page_title': 'Materials'
    }
    return render(request, 'inventory/material_list.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def material_create(request):
    """Create new material"""
    categories = MaterialCategory.objects.filter(is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        sku = request.POST.get('sku')
        category_id = request.POST.get('category')
        unit = request.POST.get('unit')
        description = request.POST.get('description', '')
        
        material = Material.objects.create(
            name=name,
            sku=sku,
            category_id=category_id if category_id else None,
            unit=unit,
            description=description
        )
        
        # Create initial stock record
        initial_qty = request.POST.get('initial_quantity', 0)
        unit_cost = request.POST.get('unit_cost', 0)
        reorder_level = request.POST.get('reorder_level', 10)
        
        MaterialStock.objects.create(
            material=material,
            quantity=float(initial_qty) if initial_qty else 0,
            unit_cost=float(unit_cost) if unit_cost else 0,
            reorder_level=float(reorder_level) if reorder_level else 10
        )
        
        messages.success(request, f'Material "{name}" created successfully')
        return redirect('inventory:material_list')
    
    context = {
        'categories': categories,
        'page_title': 'Add Material'
    }
    return render(request, 'inventory/material_form.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def material_edit(request, material_id):
    """Edit material"""
    material = get_object_or_404(Material, id=material_id)
    categories = MaterialCategory.objects.filter(is_active=True)
    stock = MaterialStock.objects.filter(material=material).first()
    
    if request.method == 'POST':
        material.name = request.POST.get('name')
        material.sku = request.POST.get('sku')
        material.category_id = request.POST.get('category') or None
        material.unit = request.POST.get('unit')
        material.description = request.POST.get('description', '')
        material.save()
        
        if stock:
            stock.unit_cost = float(request.POST.get('unit_cost', 0))
            stock.reorder_level = float(request.POST.get('reorder_level', 10))
            stock.save()
        
        messages.success(request, f'Material "{material.name}" updated successfully')
        return redirect('inventory:material_list')
    
    context = {
        'material': material,
        'stock': stock,
        'categories': categories,
        'page_title': 'Edit Material'
    }
    return render(request, 'inventory/material_form.html', context)


@login_required
@role_required('super_admin', 'inventory_manager', 'store_keeper')
def stock_movement(request):
    """Record stock movement (in/out)"""
    materials = Material.objects.filter(is_active=True)
    
    if request.method == 'POST':
        material_id = request.POST.get('material')
        movement_type = request.POST.get('movement_type')
        quantity = float(request.POST.get('quantity', 0))
        reference = request.POST.get('reference', '')
        notes = request.POST.get('notes', '')
        
        material = get_object_or_404(Material, id=material_id)
        stock, created = MaterialStock.objects.get_or_create(
            material=material,
            defaults={'quantity': 0, 'unit_cost': 0}
        )
        
        # Update stock quantity
        if movement_type == 'in':
            stock.quantity += quantity
        else:
            if stock.quantity < quantity:
                messages.error(request, 'Insufficient stock for this movement')
                return redirect('inventory:stock_movement')
            stock.quantity -= quantity
        
        stock.save()
        
        # Record movement
        StockMovement.objects.create(
            material=material,
            movement_type=movement_type,
            quantity=quantity,
            reference_number=reference,
            notes=notes,
            performed_by=request.user
        )
        
        messages.success(request, f'Stock {movement_type} recorded successfully')
        return redirect('inventory:dashboard')
    
    context = {
        'materials': materials,
        'page_title': 'Stock Movement'
    }
    return render(request, 'inventory/stock_movement.html', context)


@login_required
@role_required('super_admin', 'inventory_manager', 'store_keeper')
def stock_report(request):
    """Stock level report"""
    stocks = MaterialStock.objects.select_related('material').order_by('material__name')
    
    context = {
        'stocks': stocks,
        'page_title': 'Stock Report'
    }
    return render(request, 'inventory/stock_report.html', context)


# Category views
@login_required
@role_required('super_admin', 'inventory_manager')
def category_list(request):
    """List material categories"""
    categories = MaterialCategory.objects.filter(is_active=True).annotate(
        material_count=Sum('material__id')
    )
    
    context = {
        'categories': categories,
        'page_title': 'Material Categories'
    }
    return render(request, 'inventory/category_list.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def category_create(request):
    """Create category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        MaterialCategory.objects.create(
            name=name,
            description=description
        )
        messages.success(request, f'Category "{name}" created')
        return redirect('inventory:category_list')
    
    return render(request, 'inventory/category_form.html', {'page_title': 'Add Category'})


# Supplier views
@login_required
@role_required('super_admin', 'inventory_manager')
def supplier_list(request):
    """List suppliers"""
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    
    context = {
        'suppliers': suppliers,
        'page_title': 'Suppliers'
    }
    return render(request, 'inventory/supplier_list.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def supplier_create(request):
    """Create supplier"""
    if request.method == 'POST':
        supplier = Supplier.objects.create(
            name=request.POST.get('name'),
            contact_person=request.POST.get('contact_person', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            city=request.POST.get('city', ''),
            country=request.POST.get('country', 'Pakistan'),
            notes=request.POST.get('notes', '')
        )
        messages.success(request, f'Supplier "{supplier.name}" created')
        return redirect('inventory:supplier_list')
    
    return render(request, 'inventory/supplier_form.html', {'page_title': 'Add Supplier'})


@login_required
@role_required('super_admin', 'inventory_manager')
def supplier_edit(request, supplier_id):
    """Edit supplier"""
    supplier = get_object_or_404(Supplier, id=supplier_id)
    
    if request.method == 'POST':
        supplier.name = request.POST.get('name')
        supplier.contact_person = request.POST.get('contact_person', '')
        supplier.email = request.POST.get('email', '')
        supplier.phone = request.POST.get('phone', '')
        supplier.address = request.POST.get('address', '')
        supplier.city = request.POST.get('city', '')
        supplier.country = request.POST.get('country', 'Pakistan')
        supplier.notes = request.POST.get('notes', '')
        supplier.save()
        
        messages.success(request, f'Supplier "{supplier.name}" updated')
        return redirect('inventory:supplier_list')
    
    context = {
        'supplier': supplier,
        'page_title': 'Edit Supplier'
    }
    return render(request, 'inventory/supplier_form.html', context)


# Purchase Order views
@login_required
@role_required('super_admin', 'inventory_manager')
def po_list(request):
    """List purchase orders"""
    status_filter = request.GET.get('status', '')
    pos = PurchaseOrder.objects.select_related('supplier', 'created_by').order_by('-created_at')
    
    if status_filter:
        pos = pos.filter(status=status_filter)
    
    paginator = Paginator(pos, 20)
    page = request.GET.get('page', 1)
    pos = paginator.get_page(page)
    
    context = {
        'purchase_orders': pos,
        'status_filter': status_filter,
        'page_title': 'Purchase Orders'
    }
    return render(request, 'inventory/po_list.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def po_create(request):
    """Create purchase order"""
    suppliers = Supplier.objects.filter(is_active=True)
    materials = Material.objects.filter(is_active=True)
    
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        expected_date = request.POST.get('expected_delivery_date')
        notes = request.POST.get('notes', '')
        
        # Generate PO number
        last_po = PurchaseOrder.objects.order_by('-id').first()
        po_number = f"PO-{(last_po.id + 1) if last_po else 1:05d}"
        
        po = PurchaseOrder.objects.create(
            po_number=po_number,
            supplier_id=supplier_id,
            expected_delivery_date=expected_date if expected_date else None,
            notes=notes,
            created_by=request.user
        )
        
        # Add items
        material_ids = request.POST.getlist('material_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_costs = request.POST.getlist('unit_cost[]')
        
        for i, mat_id in enumerate(material_ids):
            if mat_id and quantities[i]:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    material_id=mat_id,
                    quantity=float(quantities[i]),
                    unit_cost=float(unit_costs[i]) if unit_costs[i] else 0
                )
        
        # Calculate total
        po.total_amount = po.items.aggregate(
            total=Sum(F('quantity') * F('unit_cost'))
        )['total'] or 0
        po.save()
        
        messages.success(request, f'Purchase Order {po_number} created')
        return redirect('inventory:po_list')
    
    context = {
        'suppliers': suppliers,
        'materials': materials,
        'page_title': 'Create Purchase Order'
    }
    return render(request, 'inventory/po_form.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def po_detail(request, po_id):
    """View purchase order details"""
    po = get_object_or_404(PurchaseOrder, id=po_id)
    items = po.items.select_related('material')
    
    context = {
        'po': po,
        'items': items,
        'page_title': f'PO {po.po_number}'
    }
    return render(request, 'inventory/po_detail.html', context)


@login_required
@role_required('super_admin', 'inventory_manager')
def po_receive(request, po_id):
    """Receive purchase order items into stock"""
    po = get_object_or_404(PurchaseOrder, id=po_id)
    
    if request.method == 'POST':
        for item in po.items.all():
            received_qty = float(request.POST.get(f'received_{item.id}', 0))
            if received_qty > 0:
                item.received_quantity = received_qty
                item.save()
                
                # Update stock
                stock, created = MaterialStock.objects.get_or_create(
                    material=item.material,
                    defaults={'quantity': 0, 'unit_cost': item.unit_cost}
                )
                stock.quantity += received_qty
                stock.unit_cost = item.unit_cost
                stock.save()
                
                # Record movement
                StockMovement.objects.create(
                    material=item.material,
                    movement_type='in',
                    quantity=received_qty,
                    reference_number=po.po_number,
                    notes=f'Received from PO {po.po_number}',
                    performed_by=request.user
                )
        
        po.status = 'received'
        po.save()
        
        messages.success(request, f'PO {po.po_number} received into stock')
        return redirect('inventory:po_list')
    
    context = {
        'po': po,
        'items': po.items.select_related('material'),
        'page_title': f'Receive PO {po.po_number}'
    }
    return render(request, 'inventory/po_receive.html', context)


# API endpoints
@login_required
def api_material_search(request):
    """API for material search autocomplete"""
    query = request.GET.get('q', '')
    materials = Material.objects.filter(
        Q(name__icontains=query) | Q(sku__icontains=query),
        is_active=True
    )[:10]
    
    data = [{'id': m.id, 'name': m.name, 'sku': m.sku, 'unit': m.unit} for m in materials]
    return JsonResponse({'results': data})


@login_required
def api_stock_check(request, material_id):
    """API to check stock level"""
    stock = MaterialStock.objects.filter(material_id=material_id).first()
    if stock:
        return JsonResponse({
            'quantity': stock.quantity,
            'unit_cost': float(stock.unit_cost),
            'reorder_level': stock.reorder_level
        })
    return JsonResponse({'quantity': 0, 'unit_cost': 0, 'reorder_level': 0})

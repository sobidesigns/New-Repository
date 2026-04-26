from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal
import json

from .models import Order, OrderItem, Customer, Product, ProductCategory, OrderStatusHistory, OrderAttachment
from accounts.models import ActivityLog


@login_required
def order_list(request):
    orders = Order.objects.select_related('customer', 'created_by').all()
    
    # Filters
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    customer = request.GET.get('customer')
    search = request.GET.get('search')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        orders = orders.filter(status=status)
    if priority:
        orders = orders.filter(priority=priority)
    if customer:
        orders = orders.filter(customer_id=customer)
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) | 
            Q(customer__name__icontains=search) |
            Q(customer__company_name__icontains=search)
        )
    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)
    
    # Sorting
    sort = request.GET.get('sort', '-created_at')
    orders = orders.order_by(sort)
    
    paginator = Paginator(orders, 20)
    page = request.GET.get('page', 1)
    orders = paginator.get_page(page)
    
    context = {
        'orders': orders,
        'statuses': Order.STATUS_CHOICES,
        'priorities': Order.PRIORITY_CHOICES,
        'customers': Customer.objects.filter(is_active=True),
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('customer', 'created_by')
        .prefetch_related('items__product', 'status_history__changed_by', 'attachments'),
        pk=pk
    )
    
    context = {
        'order': order,
        'statuses': Order.STATUS_CHOICES,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def order_create(request):
    if request.method == 'POST':
        # Generate order number
        today = timezone.now()
        prefix = f"ORD-{today.strftime('%Y%m')}"
        last_order = Order.objects.filter(order_number__startswith=prefix).order_by('-order_number').first()
        if last_order:
            last_num = int(last_order.order_number.split('-')[-1])
            order_number = f"{prefix}-{last_num + 1:04d}"
        else:
            order_number = f"{prefix}-0001"
        
        # Create order
        order = Order.objects.create(
            order_number=order_number,
            customer_id=request.POST.get('customer'),
            order_date=request.POST.get('order_date'),
            delivery_date=request.POST.get('delivery_date'),
            priority=request.POST.get('priority', 'normal'),
            status='pending',
            notes=request.POST.get('notes', ''),
            internal_notes=request.POST.get('internal_notes', ''),
            discount_percent=Decimal(request.POST.get('discount_percent', '0') or '0'),
            tax_percent=Decimal(request.POST.get('tax_percent', '0') or '0'),
            advance_paid=Decimal(request.POST.get('advance_paid', '0') or '0'),
            created_by=request.user,
            updated_by=request.user,
        )
        
        # Add order items
        items_data = request.POST.getlist('items')
        if items_data:
            for item_json in items_data:
                try:
                    item = json.loads(item_json)
                    OrderItem.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        description=item.get('description', ''),
                        size=item.get('size', 'M'),
                        color=item.get('color', ''),
                        quantity=item['quantity'],
                        unit_price=Decimal(item['unit_price']),
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Calculate totals
        order.calculate_totals()
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action='create',
            model_name='Order',
            object_id=order.id,
            object_repr=str(order),
        )
        
        # Create initial status history
        OrderStatusHistory.objects.create(
            order=order,
            from_status='',
            to_status='pending',
            changed_by=request.user,
            notes='Order created'
        )
        
        messages.success(request, f'Order {order_number} created successfully.')
        return redirect('orders:detail', pk=order.pk)
    
    context = {
        'customers': Customer.objects.filter(is_active=True),
        'products': Product.objects.filter(is_active=True),
        'categories': ProductCategory.objects.filter(is_active=True),
        'priorities': Order.PRIORITY_CHOICES,
        'sizes': OrderItem.SIZE_CHOICES,
    }
    return render(request, 'orders/order_form.html', context)


@login_required
def order_edit(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if order.status in ['delivered', 'cancelled']:
        messages.error(request, 'Cannot edit a delivered or cancelled order.')
        return redirect('orders:detail', pk=pk)
    
    if request.method == 'POST':
        order.customer_id = request.POST.get('customer')
        order.delivery_date = request.POST.get('delivery_date')
        order.priority = request.POST.get('priority', 'normal')
        order.notes = request.POST.get('notes', '')
        order.internal_notes = request.POST.get('internal_notes', '')
        order.discount_percent = Decimal(request.POST.get('discount_percent', '0') or '0')
        order.tax_percent = Decimal(request.POST.get('tax_percent', '0') or '0')
        order.advance_paid = Decimal(request.POST.get('advance_paid', '0') or '0')
        order.updated_by = request.user
        order.save()
        
        # Update items if provided
        if request.POST.get('update_items'):
            order.items.all().delete()
            items_data = request.POST.getlist('items')
            for item_json in items_data:
                try:
                    item = json.loads(item_json)
                    OrderItem.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        description=item.get('description', ''),
                        size=item.get('size', 'M'),
                        color=item.get('color', ''),
                        quantity=item['quantity'],
                        unit_price=Decimal(item['unit_price']),
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
        
        order.calculate_totals()
        
        ActivityLog.objects.create(
            user=request.user,
            action='update',
            model_name='Order',
            object_id=order.id,
            object_repr=str(order),
        )
        
        messages.success(request, f'Order {order.order_number} updated successfully.')
        return redirect('orders:detail', pk=order.pk)
    
    context = {
        'order': order,
        'customers': Customer.objects.filter(is_active=True),
        'products': Product.objects.filter(is_active=True),
        'categories': ProductCategory.objects.filter(is_active=True),
        'priorities': Order.PRIORITY_CHOICES,
        'sizes': OrderItem.SIZE_CHOICES,
    }
    return render(request, 'orders/order_form.html', context)


@login_required
def order_change_status(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    
    if new_status not in dict(Order.STATUS_CHOICES):
        messages.error(request, 'Invalid status.')
        return redirect('orders:detail', pk=pk)
    
    old_status = order.status
    order.status = new_status
    order.updated_by = request.user
    
    if new_status == 'delivered':
        order.actual_delivery_date = timezone.now().date()
    
    order.save()
    
    # Record status change
    OrderStatusHistory.objects.create(
        order=order,
        from_status=old_status,
        to_status=new_status,
        changed_by=request.user,
        notes=notes
    )
    
    ActivityLog.objects.create(
        user=request.user,
        action='status_change',
        model_name='Order',
        object_id=order.id,
        object_repr=str(order),
        details={'from': old_status, 'to': new_status}
    )
    
    messages.success(request, f'Order status changed to {order.get_status_display()}.')
    return redirect('orders:detail', pk=pk)


# Customer Views
@login_required
def customer_list(request):
    customers = Customer.objects.all()
    
    search = request.GET.get('search')
    customer_type = request.GET.get('type')
    
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(company_name__icontains=search) |
            Q(phone__icontains=search)
        )
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    paginator = Paginator(customers, 20)
    page = request.GET.get('page', 1)
    customers = paginator.get_page(page)
    
    context = {
        'customers': customers,
        'customer_types': Customer.CUSTOMER_TYPE_CHOICES,
    }
    return render(request, 'orders/customer_list.html', context)


@login_required
def customer_create(request):
    if request.method == 'POST':
        customer = Customer.objects.create(
            name=request.POST.get('name'),
            company_name=request.POST.get('company_name', ''),
            customer_type=request.POST.get('customer_type', 'business'),
            phone=request.POST.get('phone'),
            alternate_phone=request.POST.get('alternate_phone', ''),
            email=request.POST.get('email', ''),
            address=request.POST.get('address', ''),
            city=request.POST.get('city', ''),
            credit_limit=Decimal(request.POST.get('credit_limit', '0') or '0'),
            notes=request.POST.get('notes', ''),
        )
        
        ActivityLog.objects.create(
            user=request.user,
            action='create',
            model_name='Customer',
            object_id=customer.id,
            object_repr=str(customer),
        )
        
        messages.success(request, f'Customer {customer.name} created successfully.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'id': customer.id, 'name': str(customer)})
        
        return redirect('orders:customers')
    
    context = {
        'customer_types': Customer.CUSTOMER_TYPE_CHOICES,
    }
    return render(request, 'orders/customer_form.html', context)


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.company_name = request.POST.get('company_name', '')
        customer.customer_type = request.POST.get('customer_type', 'business')
        customer.phone = request.POST.get('phone')
        customer.alternate_phone = request.POST.get('alternate_phone', '')
        customer.email = request.POST.get('email', '')
        customer.address = request.POST.get('address', '')
        customer.city = request.POST.get('city', '')
        customer.credit_limit = Decimal(request.POST.get('credit_limit', '0') or '0')
        customer.notes = request.POST.get('notes', '')
        customer.is_active = request.POST.get('is_active') == 'on'
        customer.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action='update',
            model_name='Customer',
            object_id=customer.id,
            object_repr=str(customer),
        )
        
        messages.success(request, f'Customer {customer.name} updated successfully.')
        return redirect('orders:customers')
    
    context = {
        'customer': customer,
        'customer_types': Customer.CUSTOMER_TYPE_CHOICES,
    }
    return render(request, 'orders/customer_form.html', context)


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = Order.objects.filter(customer=customer).order_by('-created_at')[:20]
    
    # Calculate stats
    total_orders = orders.count()
    total_value = orders.aggregate(total=Sum('total'))['total'] or 0
    
    context = {
        'customer': customer,
        'orders': orders,
        'total_orders': total_orders,
        'total_value': total_value,
    }
    return render(request, 'orders/customer_detail.html', context)


# Product Views
@login_required
def product_list(request):
    products = Product.objects.select_related('category').all()
    
    search = request.GET.get('search')
    category = request.GET.get('category')
    
    if search:
        products = products.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search)
        )
    if category:
        products = products.filter(category_id=category)
    
    paginator = Paginator(products, 20)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)
    
    context = {
        'products': products,
        'categories': ProductCategory.objects.filter(is_active=True),
    }
    return render(request, 'orders/product_list.html', context)


@login_required
def product_create(request):
    if request.method == 'POST':
        # Generate product code
        prefix = "PRD"
        last_product = Product.objects.filter(code__startswith=prefix).order_by('-code').first()
        if last_product:
            last_num = int(last_product.code.split('-')[-1])
            code = f"{prefix}-{last_num + 1:04d}"
        else:
            code = f"{prefix}-0001"
        
        product = Product.objects.create(
            code=code,
            name=request.POST.get('name'),
            category_id=request.POST.get('category') or None,
            description=request.POST.get('description', ''),
            base_price=Decimal(request.POST.get('base_price', '0') or '0'),
        )
        
        if request.FILES.get('image'):
            product.image = request.FILES['image']
            product.save()
        
        messages.success(request, f'Product {product.name} created successfully.')
        return redirect('orders:products')
    
    context = {
        'categories': ProductCategory.objects.filter(is_active=True),
    }
    return render(request, 'orders/product_form.html', context)


@login_required 
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.category_id = request.POST.get('category') or None
        product.description = request.POST.get('description', '')
        product.base_price = Decimal(request.POST.get('base_price', '0') or '0')
        product.is_active = request.POST.get('is_active') == 'on'
        
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        
        product.save()
        
        messages.success(request, f'Product {product.name} updated successfully.')
        return redirect('orders:products')
    
    context = {
        'product': product,
        'categories': ProductCategory.objects.filter(is_active=True),
    }
    return render(request, 'orders/product_form.html', context)


# API endpoints for AJAX
@login_required
def api_products(request):
    """Get products for order form"""
    products = Product.objects.filter(is_active=True).values('id', 'code', 'name', 'base_price', 'category__name')
    return JsonResponse(list(products), safe=False)


@login_required
def api_customer_orders(request, customer_id):
    """Get customer's order history"""
    orders = Order.objects.filter(customer_id=customer_id).values(
        'id', 'order_number', 'status', 'total', 'order_date'
    )[:10]
    return JsonResponse(list(orders), safe=False)

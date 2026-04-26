from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import User, ActivityLog, SystemSetting


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Log the login activity
            ActivityLog.objects.create(
                user=user,
                action='login',
                model_name='User',
                object_id=user.id,
                object_repr=str(user),
                ip_address=get_client_ip(request)
            )
            
            if not remember:
                request.session.set_expiry(0)
            
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            
            # Redirect based on role
            next_url = request.GET.get('next', 'dashboard:index')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    ActivityLog.objects.create(
        user=request.user,
        action='logout',
        model_name='User',
        object_id=request.user.id,
        object_repr=str(request.user),
        ip_address=get_client_ip(request)
    )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        
        if request.FILES.get('profile_image'):
            user.profile_image = request.FILES['profile_image']
        
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile.html')


@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Password changed successfully. Please login again.')
            return redirect('accounts:login')
    
    return render(request, 'accounts/change_password.html')


@login_required
def users_list(request):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:index')
    
    users = User.objects.all()
    
    # Filters
    role = request.GET.get('role')
    department = request.GET.get('department')
    search = request.GET.get('search')
    
    if role:
        users = users.filter(role=role)
    if department:
        users = users.filter(department=department)
    if search:
        users = users.filter(username__icontains=search) | users.filter(first_name__icontains=search) | users.filter(last_name__icontains=search)
    
    paginator = Paginator(users, 20)
    page = request.GET.get('page', 1)
    users = paginator.get_page(page)
    
    context = {
        'users': users,
        'roles': User.ROLE_CHOICES,
        'departments': User.DEPARTMENT_CHOICES,
    }
    return render(request, 'accounts/users_list.html', context)


@login_required
def user_create(request):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        department = request.POST.get('department')
        phone = request.POST.get('phone')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                department=department,
                phone=phone
            )
            
            ActivityLog.objects.create(
                user=request.user,
                action='create',
                model_name='User',
                object_id=user.id,
                object_repr=str(user),
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'User {username} created successfully.')
            return redirect('accounts:users')
    
    context = {
        'roles': User.ROLE_CHOICES,
        'departments': User.DEPARTMENT_CHOICES,
    }
    return render(request, 'accounts/user_form.html', context)


@login_required
def user_edit(request, pk):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:index')
    
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.role = request.POST.get('role')
        user.department = request.POST.get('department')
        user.phone = request.POST.get('phone')
        user.is_active = request.POST.get('is_active') == 'on'
        
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        user.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action='update',
            model_name='User',
            object_id=user.id,
            object_repr=str(user),
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'User {user.username} updated successfully.')
        return redirect('accounts:users')
    
    context = {
        'edit_user': user,
        'roles': User.ROLE_CHOICES,
        'departments': User.DEPARTMENT_CHOICES,
    }
    return render(request, 'accounts/user_form.html', context)


@login_required
def settings_view(request):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        # Update settings
        settings_to_update = [
            'company_name', 'company_address', 'company_phone', 'company_email',
            'currency_symbol', 'tax_rate', 'invoice_prefix', 'order_prefix'
        ]
        
        for key in settings_to_update:
            value = request.POST.get(key, '')
            setting, created = SystemSetting.objects.update_or_create(
                key=key,
                defaults={'value': value, 'updated_by': request.user}
            )
        
        messages.success(request, 'Settings updated successfully.')
        return redirect('accounts:settings')
    
    # Get current settings
    settings = {}
    for setting in SystemSetting.objects.all():
        settings[setting.key] = setting.value
    
    return render(request, 'accounts/settings.html', {'settings': settings})


@login_required
def activity_log(request):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:index')
    
    logs = ActivityLog.objects.select_related('user').all()
    
    # Filters
    user_id = request.GET.get('user')
    action = request.GET.get('action')
    model = request.GET.get('model')
    
    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    if model:
        logs = logs.filter(model_name=model)
    
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs = paginator.get_page(page)
    
    context = {
        'logs': logs,
        'users': User.objects.all(),
        'actions': ActivityLog.ACTION_CHOICES,
    }
    return render(request, 'accounts/activity_log.html', context)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

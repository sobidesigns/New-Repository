from django.conf import settings


def user_context(request):
    """Add user-related context to all templates"""
    context = {
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', 'PKR'),
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'PKR'),
    }
    
    if request.user.is_authenticated:
        context.update({
            'user_role': request.user.role,
            'user_role_display': request.user.get_role_display(),
            'user_department': request.user.department,
            'is_admin': request.user.is_admin,
            'is_manager': request.user.is_manager,
            'is_department_head': request.user.is_department_head,
        })
    
    return context

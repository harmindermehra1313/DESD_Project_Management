from functools import wraps
from django.core.exceptions import PermissionDenied

def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
                # return HttpResponseForbidden("Login required.")
            if request.user.role != role:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

admin_required = role_required("ADMIN")
producer_required = role_required("PRODUCER")
business_required = role_required("BUSINESS")
community_required = role_required("COMMUNITY")
customer_required = role_required("CUSTOMER")
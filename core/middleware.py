from django.shortcuts import redirect
from django.contrib import messages

class AdminAccessMiddleware:
    """
    Middleware to redirect non-staff users away from Django admin.
    If a non-staff user tries to access admin, they are redirected to dashboard.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if the request is for Django admin
        if request.path.startswith('/admin/'):
            # Check if user is authenticated and not staff
            if request.user.is_authenticated and not request.user.is_staff:
                # Redirect non-staff users to dashboard
                messages.warning(request, 'You do not have permission to access Django admin.')
                return redirect('dashboard')
        
        response = self.get_response(request)
        return response


class SemesterMiddleware:
    """
    Optional middleware to inject the current semester into request object.
    This allows templates and views to access request.semester directly.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Inject current semester into request
        try:
            from core.models import Semester
            request.semester = Semester.get_current()
        except Exception:
            request.semester = None
        
        response = self.get_response(request)
        return response
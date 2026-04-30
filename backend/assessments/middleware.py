from django.http import HttpResponse

from .rate_limits import ADMIN_LOGIN_PATH, check_admin_login_rate_limit, clear_admin_login_rate_limit


class AdminLoginRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        should_limit = request.method == "POST" and request.path_info == ADMIN_LOGIN_PATH

        if should_limit:
            rate_limit = check_admin_login_rate_limit(request)
            if rate_limit.limited:
                response = HttpResponse("Too many admin login attempts. Try again later.", status=429)
                response["Retry-After"] = str(rate_limit.retry_after_seconds)
                return response

        response = self.get_response(request)

        if should_limit and getattr(request, "user", None) and request.user.is_authenticated and 300 <= response.status_code < 400:
            clear_admin_login_rate_limit(request)

        return response

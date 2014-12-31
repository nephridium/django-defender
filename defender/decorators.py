import logging
from django.conf import settings

from .models import AccessAttempt
from . import utils

# use a specific username field to retrieve from login POST data
USERNAME_FORM_FIELD = getattr(settings,
                              'DEFENDER_USERNAME_FORM_FIELD',
                              'username')

log = logging.getLogger(__name__)


def watch_login(func):
    """
    Used to decorate the django.contrib.admin.site.login method.
    """

    def decorated_login(request, *args, **kwargs):
        # if the request is currently under lockout, do not proceed to the
        # login function, go directly to lockout url, do not pass go, do not
        # collect messages about this login attempt
        if utils.is_already_locked(request):
            return utils.lockout_response(request)

        # call the login function
        response = func(request, *args, **kwargs)

        if func.__name__ == 'decorated_login':
            # if we're dealing with this function itself, don't bother checking
            # for invalid login attempts.  I suppose there's a bunch of
            # recursion going on here that used to cause one failed login
            # attempt to generate 10+ failed access attempt records (with 3
            # failed attempts each supposedly)
            return response

        if request.method == 'POST':
            # see if the login was successful
            login_unsuccessful = (
                response and
                not response.has_header('location') and
                response.status_code != 302
            )

            AccessAttempt.objects.create(
                user_agent=request.META.get('HTTP_USER_AGENT',
                                            '<unknown>')[:255],
                ip_address=utils.get_ip(request),
                username=request.POST.get(USERNAME_FORM_FIELD, None),
                http_accept=request.META.get('HTTP_ACCEPT', '<unknown>'),
                path_info=request.META.get('PATH_INFO', '<unknown>'),
                login_valid=not login_unsuccessful,
            )
            if utils.check_request(request, login_unsuccessful):
                return response

            return utils.lockout_response(request)

        return response

    return decorated_login

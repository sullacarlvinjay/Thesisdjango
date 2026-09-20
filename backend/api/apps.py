"""Application configuration.

``ready`` registers the system checks and connects the cache invalidation.
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """The single application holding the whole system.

    ``ready`` registers the system checks and the cache invalidation; there
    is no second app to split them across.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Wire up the system checks and the cache invalidation.

        ``checks`` is imported only for the side effect of registering its
        checks with Django; nothing here calls it, which is why ``api/apps.py``
        is exempted from the unused-import rule in ``pyproject.toml``.
        """
        from django.db.models.signals import post_save

        from . import checks  # noqa: F401
        from .context_processors import forget_active_term
        from .models import SystemSettings

        post_save.connect(forget_active_term, sender=SystemSettings,
                          dispatch_uid='srms.forget_active_term')

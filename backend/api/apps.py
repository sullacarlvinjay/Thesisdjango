from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # Registers the deploy-time configuration checks. Imported for the
        # side effect of the @register() decorators — see api/checks.py.
        from . import checks           # noqa: F401

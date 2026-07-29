def system_settings(request):
    from .models import SystemSettings
    try:
        s = SystemSettings.objects.get(pk=1)
        return {'active_semester': s.active_semester, 'academic_year': s.academic_year}
    except Exception:
        return {'active_semester': '', 'academic_year': ''}

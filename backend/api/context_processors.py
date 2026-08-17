def system_settings(request):
    from .models import SystemSettings
    try:
        s = SystemSettings.objects.get(pk=1)
        parsed = SystemSettings.parse_label(s.academic_year)
        return {'active_semester': parsed['semester'], 'academic_year': parsed['sy']}
    except Exception:
        return {'active_semester': '', 'academic_year': ''}

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .models import StudentProfile, Scholarship, Application, Notification, Announcement, User, AffirmativeNSUApplication


SCHOLARSHIP_DETAILS = {
    'academic': {
        'name': 'Academic Scholarship', 'category': 'Merit-Based',
        'color': 'linear-gradient(135deg,#3b5bdb,#4c6ef5)',
        'badge_bg': '#edf2ff', 'badge_color': '#3b5bdb',
        'background': 'The Academic Scholarship is BiPSU\'s flagship merit-based program established to recognize and reward students with outstanding academic performance. It has been a cornerstone of the university\'s commitment to academic excellence since its founding, providing full tuition coverage to top-performing students each semester.',
        'eligibility': ['University Scholar: GWA of 1.29 or better', 'College Scholar: GWA of 1.30 to 1.50', 'No grade above 2.5 in any subject', 'Must be a regular student (full load)'],
        'benefits': ['Full tuition fee coverage', 'Miscellaneous fee exemption', 'Priority in university activities', 'Certificate of recognition each semester'],
        'apply_url': '/login/', 'apply_label': 'Sign In to Apply',
    },
    'tdp': {
        'name': 'TDP Scholarship', 'category': 'Needs-Based',
        'color': 'linear-gradient(135deg,#1971c2,#339af0)',
        'badge_bg': '#eff6ff', 'badge_color': '#1971c2',
        'background': 'The Tertiary Development Program (TDP) is a government scholarship under UniFAST providing financial subsidy to qualified students from low-income families enrolled in state universities and colleges. It aims to ensure that financial constraints do not hinder deserving students from accessing higher education.',
        'eligibility': ['Filipino citizen enrolled in a state university', 'From a low-income family (combined annual income threshold)', 'Not a recipient of other government subsidies', 'Maintaining satisfactory academic performance'],
        'benefits': ['Monthly stipend for living expenses', 'Tuition and miscellaneous fee subsidy', 'Book and supplies allowance', 'Renewable each semester subject to conditions'],
        'apply_url': None, 'apply_label': 'Processed by UniFAST',
    },
    'staff': {
        'name': 'NSU Staff Scholarship', 'category': 'Institutional',
        'color': 'linear-gradient(135deg,#2f9e44,#51cf66)',
        'badge_bg': '#f0fdf4', 'badge_color': '#2f9e44',
        'background': 'The NSU Staff Scholarship is an institutional benefit established by Biliran Province State University to support its permanent faculty, employees, and their qualified dependents. Recognizing the dedication of its academic community, the university provides this scholarship as a tangible expression of its commitment to the welfare of its personnel and their families.',
        'eligibility': ['Permanent NSU faculty or employee, OR', 'Legitimate dependent of a permanent NSU faculty/staff', 'Dependent must not have already earned a baccalaureate degree', 'Must be enrolled in BiPSU'],
        'benefits': ['Full tuition fee coverage', 'Miscellaneous fee exemption', 'Renewable each semester', 'Applicable to all undergraduate programs'],
        'apply_url': '/apply/register/', 'apply_label': 'Register to Apply',
    },
    'affirmative': {
        'name': 'Affirmative Scholarship', 'category': 'Affirmative Action',
        'color': 'linear-gradient(135deg,#f59f00,#fcc419)',
        'badge_bg': '#fffbeb', 'badge_color': '#92400e',
        'background': 'The Affirmative Action Scholarship at BiPSU promotes equal access to quality education for students who demonstrate strong academic potential in Senior High School and perform well in the university admission examination. It bridges the gap for deserving students who may not qualify for traditional merit-based programs but show clear potential for academic success.',
        'eligibility': ['SHS GPA of at least 75% certified by SHS principal', 'At least 50% passing score in SUC-administered admission exam', 'Must NOT be a TES (Tertiary Education Subsidy) beneficiary', 'Must be enrolled as a regular student at BiPSU'],
        'benefits': ['Tuition fee coverage', 'Monthly educational allowance', 'Access to university academic support programs', 'Renewable subject to satisfactory academic performance'],
        'apply_url': '/apply/register/', 'apply_label': 'Register to Apply',
    },
    'dost': {
        'name': 'DOST Scholarship', 'category': 'Science & Tech',
        'color': 'linear-gradient(135deg,#7048e8,#9775fa)',
        'badge_bg': '#f3f0ff', 'badge_color': '#7048e8',
        'background': 'The Department of Science and Technology (DOST) Scholarship is a prestigious government program supporting outstanding students pursuing science, technology, engineering, and mathematics (STEM) courses. Administered nationally, it aims to build a strong pool of Filipino scientists, engineers, and technologists to drive national development.',
        'eligibility': ['Enrolled in a STEM-related course', 'GWA of at least 85% in high school', 'Must pass the DOST qualifying examination', 'Filipino citizen with financial need'],
        'benefits': ['Full tuition and fees', 'Monthly stipend', 'Book allowance', 'Thesis/dissertation allowance for graduate scholars'],
        'apply_url': None, 'apply_label': 'Apply via DOST Office',
    },
    'ched': {
        'name': 'CHED Scholarship', 'category': 'Government',
        'color': 'linear-gradient(135deg,#e64980,#f783ac)',
        'badge_bg': '#fff0f6', 'badge_color': '#c2255c',
        'background': 'The Commission on Higher Education (CHED) Scholarship provides financial assistance to deserving and qualified students in higher education institutions. Established under Republic Act 7722, it represents the government\'s investment in human capital development through accessible higher education for all Filipinos.',
        'eligibility': ['Filipino citizen with demonstrated financial need', 'GWA of 80% or higher in the previous school year', 'Not a recipient of other CHED scholarships', 'Enrolled in CHED-recognized programs'],
        'benefits': ['Tuition and miscellaneous fees', 'Monthly living allowance', 'Book allowance per semester', 'Thesis support grant'],
        'apply_url': None, 'apply_label': 'Apply via CHED Office',
    },
    'coscho': {
        'name': 'CoScho Scholarship', 'category': 'Agricultural',
        'color': 'linear-gradient(135deg,#0ca678,#20c997)',
        'badge_bg': '#e6fcf5', 'badge_color': '#0ca678',
        'background': 'The Coconut Farmers Scholar (CoScho) Program is a scholarship initiative for children and dependents of registered coconut farmers. Funded through the Philippine Coconut Authority, it aims to uplift coconut farming communities by investing in the education of the next generation.',
        'eligibility': ['Child or legal dependent of a registered coconut farmer', 'Farmer must be registered with PCIC', 'Good academic standing (passing all subjects)', 'Must submit proof of coconut farm registration'],
        'benefits': ['Tuition fee subsidy', 'Monthly allowance', 'Book and supplies grant', 'Annual clothing allowance'],
        'apply_url': None, 'apply_label': 'Apply via PCIC Office',
    },
    'sports': {
        'name': 'Sports Scholarship', 'category': 'Athletics',
        'color': 'linear-gradient(135deg,#f76707,#ff922b)',
        'badge_bg': '#fff4e6', 'badge_color': '#d9480f',
        'background': 'The Sports Scholarship at BiPSU honors student athletes who represent the university in regional and national competitions. The university supports its athletes with this scholarship to ensure they can pursue both their academic and athletic goals without financial burden.',
        'eligibility': ['Must be a recognized university athlete', 'Actively competing in university-sanctioned athletic events', 'Maintaining passing grades in all enrolled subjects', 'Endorsed by the university coach and sports office'],
        'benefits': ['Full tuition fee coverage', 'Athletic allowance', 'Sports equipment and uniform support', 'Travel allowance for competitions'],
        'apply_url': None, 'apply_label': 'Coach Endorsement Required',
    },
}


# ── Landing ───────────────────────────────────────────────────────────────────

def landing_view(request):
    return render(request, 'landing.html', {'scholarship_details': SCHOLARSHIP_DETAILS})


# ── Affirmative / NSU Staff flows ─────────────────────────────────────────────

def apply_register_view(request):
    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        errors = []
        if AffirmativeNSUApplication.objects.filter(email=p.get('email')).exists():
            errors.append('This email is already registered.')
        if p.get('password') != p.get('password_confirm'):
            errors.append('Passwords do not match.')
        if errors:
            return render(request, 'apply_register.html', {'errors': errors, 'form_data': p})

        app = AffirmativeNSUApplication(
            full_name=p.get('full_name'),
            email=p.get('email'),
            contact_number=p.get('contact_number'),
            date_of_birth=p.get('date_of_birth'),
            gender=p.get('gender'),
            address=p.get('address'),
            course=p.get('course'),
            year_level=int(p.get('year_level', 1)),
            school_id=p.get('school_id', ''),
            is_nsu_staff=p.get('is_nsu_staff') == 'yes',
            is_nsu_dependent=p.get('is_nsu_dependent') == 'yes',
            staff_name=p.get('staff_name', ''),
            staff_employee_id=p.get('staff_employee_id', ''),
            relationship_to_staff=p.get('relationship_to_staff', ''),
            has_baccalaureate=p.get('has_baccalaureate') == 'yes',
            shs_gpa=float(p.get('shs_gpa')) if p.get('shs_gpa') else None,
            suc_exam_score=float(p.get('suc_exam_score')) if p.get('suc_exam_score') else None,
            is_tes_beneficiary=p.get('is_tes_beneficiary') == 'yes',
        )
        app.set_password(p.get('password'))
        if f.get('shs_certificate'):
            app.shs_certificate = f.get('shs_certificate')
        if f.get('suc_exam_certificate'):
            app.suc_exam_certificate = f.get('suc_exam_certificate')
        app.qualified_for = app.determine_qualification()
        app.save()
        request.session['apply_app_id'] = app.id
        return redirect('/apply/result/')

    return render(request, 'apply_register.html')


def apply_result_view(request):
    app_id = request.session.get('apply_app_id')
    if not app_id:
        return redirect('/apply/register/')
    try:
        application = AffirmativeNSUApplication.objects.get(id=app_id)
    except AffirmativeNSUApplication.DoesNotExist:
        return redirect('/apply/register/')
    if request.method == 'POST':
        application.status = 'Draft' if request.POST.get('action') == 'draft' else 'Pending Validation'
        application.save()
        return redirect('/apply/submitted/')
    return render(request, 'apply_result.html', {'application': application, 'qualified_for': application.qualified_for})


def apply_login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            app = AffirmativeNSUApplication.objects.get(email=email)
            if app.check_password(password):
                request.session['apply_app_id'] = app.id
                return redirect('/apply/portal/')
            return render(request, 'apply_login.html', {'error': 'Invalid credentials'})
        except AffirmativeNSUApplication.DoesNotExist:
            return render(request, 'apply_login.html', {'error': 'No account found with that email'})
    return render(request, 'apply_login.html')


def apply_portal_view(request):
    app_id = request.session.get('apply_app_id')
    if not app_id:
        return redirect('/apply/login/')
    try:
        application = AffirmativeNSUApplication.objects.get(id=app_id)
    except AffirmativeNSUApplication.DoesNotExist:
        return redirect('/apply/login/')
    return render(request, 'apply_portal.html', {'application': application, 'qualified_for': application.qualified_for})


def apply_submit_view(request):
    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        try:
            application = AffirmativeNSUApplication.objects.get(id=app_id)
            application.status = 'Draft' if request.POST.get('action') == 'draft' else 'Pending Validation'
            application.save()
        except AffirmativeNSUApplication.DoesNotExist:
            pass
        return redirect('/apply/submitted/')
    return redirect('/apply/portal/')


def apply_logout_view(request):
    request.session.pop('apply_app_id', None)
    return redirect('/apply/login/')


def apply_submitted_view(request):
    app_id = request.session.get('apply_app_id')
    application = AffirmativeNSUApplication.objects.filter(id=app_id).first() if app_id else None
    return render(request, 'apply_submitted.html', {'application': application})


# ── Academic auth ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            if user.role == 'student':
                return redirect('/student/apply/academic/')
            elif user.role == 'super':
                return redirect('/super/')
            elif user.role == 'vpsea':
                return redirect('/vpsea/')
            elif user.role == 'unifast':
                return redirect('/unifast/')
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('/')


def register_view(request):
    if request.method == 'POST':
        p = request.POST
        errors = []
        if User.objects.filter(email=p.get('email')).exists():
            errors.append('Email already registered.')
        if StudentProfile.objects.filter(student_id=p.get('student_id')).exists():
            errors.append('Student ID already registered.')
        if errors:
            return render(request, 'register.html', {'errors': errors})
        user = User.objects.create_user(
            username=p.get('email'),
            email=p.get('email'),
            password=p.get('password'),
            first_name=p.get('first_name', ''),
            last_name=p.get('last_name', ''),
            role='student',
        )
        StudentProfile.objects.create(
            user=user,
            student_id=p.get('student_id'),
            course=p.get('course'),
            year_level=int(p.get('year_level', 1)),
            gwa=float(p.get('gwa', 0)),
            contact_number=p.get('contact_number', ''),
            address=p.get('address', ''),
            date_of_birth=p.get('date_of_birth') or None,
            gender=p.get('gender', ''),
            family_income=float(p.get('family_income', 0)),
            indigenous_group=p.get('indigenous_group', ''),
            parent_employment=p.get('parent_employment', ''),
            is_pwd='is_pwd' in p,
            is_athlete='is_athlete' in p,
            is_coconut_farmer_family='is_coconut_farmer_family' in p,
            has_other_scholarship='has_other_scholarship' in p,
        )
        login(request, user)
        return redirect('/student/apply/academic/')
    return render(request, 'register.html')


# ── Academic student pages ────────────────────────────────────────────────────

@login_required(login_url='/login/')
def student_apply_academic(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Academic').first()
        if scholarship and profile:
            Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Draft' if request.POST.get('action') == 'draft' else 'Pending Validation',
                form_data=request.POST.dict()
            )
        return redirect('/student/applications/')
    gwa = profile.gwa if profile else 0
    if gwa <= 1.29:
        classification = 'University Scholar'
    elif gwa <= 1.50:
        classification = 'College Scholar'
    else:
        classification = 'Not Eligible'
    return render(request, 'student/apply_academic.html', {
        'profile': profile,
        'classification': classification,
        'eligible': gwa <= 1.50,
    })


@login_required(login_url='/login/')
def student_applications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = Application.objects.filter(student=profile).select_related('scholarship') if profile else Application.objects.none()
    return render(request, 'student/applications.html', {'applications': applications})


@login_required(login_url='/login/')
def student_notifications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    notifications = Notification.objects.filter(student=profile).order_by('-created_at') if profile else Notification.objects.none()
    return render(request, 'student/notifications.html', {'notifications': notifications})


# ── VPSEA portal pages ─────────────────────────────────────────────────────────────────────

def _vpsea_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'vpsea':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_vpsea_required
def vpsea_dashboard(request):
    from .models import Application, Renewal
    from django.db.models import Count
    apps = Application.objects.all()
    ctx = {
        'total_applicants': apps.count(),
        'approved': apps.filter(status='Approved').count(),
        'rejected': apps.filter(status='Rejected').count(),
        'pending': apps.filter(status='Pending Validation').count(),
        'renewals': Renewal.objects.filter(status='Renewal Pending').count(),
    }
    return render(request, 'vpsea/dashboard.html', ctx)


@_vpsea_required
def vpsea_applications(request):
    from .models import Application
    applications = Application.objects.select_related('student__user', 'scholarship').all().order_by('-submitted_at')
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        Application.objects.filter(id=app_id).update(status=new_status, remarks=remarks)
        return redirect('/vpsea/applications/')
    return render(request, 'vpsea/applications.html', {'applications': applications})


@_vpsea_required
def vpsea_renewals(request):
    from .models import Renewal
    renewals = Renewal.objects.select_related('student__user', 'scholarship').all().order_by('-created_at')
    return render(request, 'vpsea/renewals.html', {'renewals': renewals})


@_vpsea_required
def vpsea_archives(request):
    from .models import Application, AffirmativeNSUApplication, ScholarshipRollover
    from django.utils import timezone
    stype = request.GET.get('type', 'Academic')
    archive_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    now = timezone.now()
    current_sy = f'{now.year}-{now.year + 1}' if now.month >= 6 else f'{now.year - 1}-{now.year}'
    next_sy_start = (now.year + 1) if now.month >= 6 else now.year
    next_sy = f'{next_sy_start}-{next_sy_start + 1}'
    history = ScholarshipRollover.objects.filter(scholarship_type=stype).order_by('-created_at')

    # Affirmative and Staff come from AffirmativeNSUApplication
    if stype in ('Affirmative', 'Staff'):
        aff_scholars = AffirmativeNSUApplication.objects.filter(
            status='Approved', qualified_for=stype
        ).order_by('full_name')
        total = aff_scholars.count()
        return render(request, 'vpsea/archives.html', {
            'aff_scholars': aff_scholars,
            'scholars': None,
            'archive_types': archive_types,
            'active_type': stype,
            'total': total,
            'current_sy': current_sy,
            'next_sy': next_sy,
            'history': history,
        })

    # CHED only: split into full and half blocks
    if stype == 'CHED':
        all_scholars = Application.objects.filter(
            status='Approved', scholarship__type='CHED'
        ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        full_scholars = [a for a in all_scholars if 'full' in (a.scholarship.name or '').lower() or 'full' in (a.form_data.get('scholar_type', '')).lower()]
        half_scholars = [a for a in all_scholars if a not in full_scholars]
        if not full_scholars and not half_scholars:
            full_scholars = list(all_scholars)
        total = all_scholars.count()
        return render(request, 'vpsea/archives.html', {
            'full_scholars': full_scholars,
            'half_scholars': half_scholars,
            'scholars': None,
            'archive_types': archive_types,
            'active_type': stype,
            'total': total,
            'current_sy': current_sy,
            'next_sy': next_sy,
            'history': history,
        })

    scholars = Application.objects.filter(
        status='Approved', scholarship__type=stype
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
    return render(request, 'vpsea/archives.html', {
        'scholars': scholars,
        'archive_types': archive_types,
        'active_type': stype,
        'total': scholars.count(),
        'current_sy': current_sy,
        'next_sy': next_sy,
        'history': history,
    })


@_vpsea_required
def vpsea_archive_rollover(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.core.files.base import ContentFile
    from io import BytesIO
    from .models import Application, AffirmativeNSUApplication, ActivityLog, ScholarshipRollover
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    school_year = request.POST.get('school_year', '')
    next_school_year = request.POST.get('next_school_year', '').strip()
    if not school_year:
        return redirect(f'/vpsea/archives/?type={stype}')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{stype} Scholars'

    # ── Styling helpers ──────────────────────────────────────────────────────
    header_font = Font(bold=True)
    header_fill = PatternFill('solid', fgColor='D9E1F2')
    section_fill = PatternFill('solid', fgColor='BDD7EE')
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def style_header_row(ws, row_num, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row_num, column=c)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center

    def style_section_title(ws, row_num, ncols, title):
        ws.cell(row=row_num, column=1, value=title)
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=ncols)
        cell = ws.cell(row=row_num, column=1)
        cell.font = Font(bold=True, size=11)
        cell.fill = section_fill
        cell.alignment = center
        cell.border = border

    def write_rows(ws, start_row, rows_data, ncols):
        for i, row in enumerate(rows_data):
            for j, val in enumerate(row):
                cell = ws.cell(row=start_row + i, column=j + 1, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
        return start_row + len(rows_data)

    # ── Per-scholarship export logic ─────────────────────────────────────────

    def _split_name(full_name):
        """Returns (last, first, middle_initial) from 'First Middle Last' or best-effort."""
        parts = full_name.strip().split()
        if len(parts) == 0:
            return ('', '', '')
        if len(parts) == 1:
            return (parts[0], '', '')
        if len(parts) == 2:
            return (parts[-1], parts[0], '')
        # Assume: First [Middle...] Last
        last = parts[-1]
        first = parts[0]
        middle = ' '.join(parts[1:-1])
        middle_initial = middle[0] + '.' if middle else ''
        return (last, first, middle_initial)

    def _full_name_parts(user):
        """Returns (last, first, middle_initial) from Django User."""
        last = user.last_name or ''
        first = user.first_name or ''
        # middle not stored separately on User; leave blank
        return (last, first, '')

    count = 0

    if stype == 'Academic':
        scholars = Application.objects.filter(
            status='Approved', scholarship__type='Academic'
        ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        count = scholars.count()
        headers = ['No.', 'Last Name', 'First', 'Middle Name', 'Sex',
                   'Address: Brgy/St., Muni, Prov', 'Course', 'Year', 'GWA',
                   '% / Type of Academic Scholarship', 'Scholarship']
        ws.append(headers)
        style_header_row(ws, 1, len(headers))
        rows = []
        for i, app in enumerate(scholars, 1):
            p = app.student
            u = p.user
            last, first, mi = _full_name_parts(u)
            # Determine scholarship type label
            if p.gwa <= 1.29:
                pct_type = 'University Scholar'
            elif p.gwa <= 1.50:
                pct_type = 'College Scholar'
            else:
                pct_type = ''
            rows.append([i, last, first, mi, p.gender, p.address, p.course,
                         p.year_level, p.gwa, pct_type, app.scholarship.name])
        write_rows(ws, 2, rows, len(headers))
        scholars.delete()

    elif stype == 'Staff':
        scholars = AffirmativeNSUApplication.objects.filter(
            status='Approved', qualified_for='Staff'
        ).order_by('full_name')
        count = scholars.count()
        headers = ['No.', 'Last', 'First', 'Middle Initial', 'Sex', 'Course',
                   'Year Level', 'Student Number', '%', 'Scholarship Program']
        ws.append(headers)
        style_header_row(ws, 1, len(headers))
        rows = []
        for i, app in enumerate(scholars, 1):
            last, first, mi = _split_name(app.full_name)
            pct = '100%' if app.is_nsu_staff else '75%'
            rows.append([i, last, first, mi, app.gender, app.course,
                         app.year_level, app.school_id, pct, 'NSU Staff Scholarship'])
        write_rows(ws, 2, rows, len(headers))
        scholars.delete()

    elif stype in ('CHED', 'TDP', 'DOST'):
        # Two blocks: Full Merit / Full Scholar  then  Half Merit / Half Scholar
        # For TDP/DOST the block titles differ slightly
        if stype == 'CHED':
            block1_title = 'Full Merit / Full Scholar'
            block2_title = 'Half Merit / Half Scholar'
        elif stype == 'TDP':
            block1_title = 'TDP — Full Subsidy'
            block2_title = 'TDP — Half Subsidy'
        else:  # DOST
            block1_title = 'DOST — Full Scholar'
            block2_title = 'DOST — Half Scholar'

        scholars = Application.objects.filter(
            status='Approved', scholarship__type=stype
        ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        count = scholars.count()

        headers = ['No.', 'Award Number', 'Last Name', 'First Name', 'Middle Name',
                   'Sex', 'Address: Brgy/St., Mun. Prov', 'Congress District',
                   'Course', 'Yr.', 'Scholarship Program']
        ncols = len(headers)

        # Split into full vs half based on scholarship name containing 'Full' or 'Half'
        full_scholars = [a for a in scholars if 'full' in (a.scholarship.name or '').lower() or 'full' in (a.form_data.get('scholar_type', '')).lower()]
        half_scholars = [a for a in scholars if a not in full_scholars]
        # If no name-based split, put all in block1
        if not full_scholars and not half_scholars:
            full_scholars = list(scholars)

        current_row = 1
        # Block 1
        style_section_title(ws, current_row, ncols, block1_title)
        current_row += 1
        for j, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=j, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center
        current_row += 1
        for i, app in enumerate(full_scholars, 1):
            p = app.student
            u = p.user
            last, first, mi = _full_name_parts(u)
            award_no = app.form_data.get('award_number', '')
            congress = app.form_data.get('congress_district', '')
            for j, val in enumerate([i, award_no, last, first, mi, p.gender,
                                      p.address, congress, p.course,
                                      p.year_level, app.scholarship.name], 1):
                cell = ws.cell(row=current_row, column=j, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
            current_row += 1

        current_row += 1  # blank separator row

        # Block 2
        style_section_title(ws, current_row, ncols, block2_title)
        current_row += 1
        for j, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=j, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center
        current_row += 1
        for i, app in enumerate(half_scholars, 1):
            p = app.student
            u = p.user
            last, first, mi = _full_name_parts(u)
            award_no = app.form_data.get('award_number', '')
            congress = app.form_data.get('congress_district', '')
            for j, val in enumerate([i, award_no, last, first, mi, p.gender,
                                      p.address, congress, p.course,
                                      p.year_level, app.scholarship.name], 1):
                cell = ws.cell(row=current_row, column=j, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
            current_row += 1

        scholars.delete()

    elif stype == 'GSIS':
        scholars = Application.objects.filter(
            status='Approved', scholarship__type='GSIS'
        ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        count = scholars.count()
        headers = ['No.', 'Last', 'First', 'Middle Initial',
                   'Address: Brgy/ St. Municipality, Province',
                   'Sex', 'Course', 'Year Level', 'Student Number', 'Scholarship Program']
        ws.append(headers)
        style_header_row(ws, 1, len(headers))
        rows = []
        for i, app in enumerate(scholars, 1):
            p = app.student
            u = p.user
            last, first, mi = _full_name_parts(u)
            rows.append([i, last, first, mi, p.address, p.gender,
                         p.course, p.year_level, p.student_id, app.scholarship.name])
        write_rows(ws, 2, rows, len(headers))
        scholars.delete()

    elif stype == 'Affirmative':
        scholars = AffirmativeNSUApplication.objects.filter(
            status='Approved', qualified_for='Affirmative'
        ).order_by('full_name')
        count = scholars.count()
        headers = ['No.', 'Award Number', 'Last Name', 'First Name', 'Middle Name',
                   'Sex', 'Address: Brgy/St., Mun. Prov', 'Congress District',
                   'Course', 'Yr.', 'Scholarship Program']
        ws.append(headers)
        style_header_row(ws, 1, len(headers))
        rows = []
        for i, app in enumerate(scholars, 1):
            last, first, mi = _split_name(app.full_name)
            rows.append([i, '', last, first, mi, app.gender, app.address,
                         '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        write_rows(ws, 2, rows, len(headers))
        scholars.delete()

    else:
        # CoScho, Sports — generic fallback
        scholars = Application.objects.filter(
            status='Approved', scholarship__type=stype
        ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        count = scholars.count()
        headers = ['No.', 'Last Name', 'First Name', 'Middle Initial', 'Sex',
                   'Address', 'Course', 'Year Level', 'Student Number', 'Scholarship Program']
        ws.append(headers)
        style_header_row(ws, 1, len(headers))
        rows = []
        for i, app in enumerate(scholars, 1):
            p = app.student
            u = p.user
            last, first, mi = _full_name_parts(u)
            rows.append([i, last, first, mi, p.gender, p.address,
                         p.course, p.year_level, p.student_id, app.scholarship.name])
        write_rows(ws, 2, rows, len(headers))
        scholars.delete()

    # ── Auto-fit column widths ────────────────────────────────────────────────
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    # ── Save file ─────────────────────────────────────────────────────────────
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f'{stype}_scholars_{school_year}.xlsx'
    rollover = ScholarshipRollover(
        scholarship_type=stype,
        school_year=school_year,
        scholar_count=count,
        rolled_over_by=request.user,
    )
    rollover.excel_file.save(filename, ContentFile(buffer.read()), save=True)
    ActivityLog.objects.create(
        user=request.user,
        action=f'Rolled over {count} {stype} scholars for A.Y. {school_year} — saved as {filename}. Next A.Y.: {next_school_year}.'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


@_vpsea_required
def vpsea_uploads(request):
    from .models import ArchiveRecord, ActivityLog
    import openpyxl
    message = None
    error = None

    # Column maps: position index → field name (0-based, skipping the No. column at index 0)
    COLUMN_MAPS = {
        'Academic': [
            # No., Last Name, First, Middle Name, Sex, Address, Course, Year, GWA, % / Type, Scholarship
            (1, 'last_name'), (2, 'first_name'), (3, 'middle_name'), (4, 'sex'),
            (5, 'address'), (6, 'course'), (7, 'year'), (8, 'gwa'),
            (9, 'pct_type'), (10, 'scholarship'),
        ],
        'Staff': [
            # No., Last, First, Middle Initial, Sex, Course, Year Level, Student Number, %, Scholarship Program
            (1, 'last_name'), (2, 'first_name'), (3, 'middle_initial'), (4, 'sex'),
            (5, 'course'), (6, 'year'), (7, 'student_number'), (8, 'pct'),
            (9, 'scholarship_program'),
        ],
        'CHED': [
            # No., Award Number, Last Name, First Name, Middle Name, Sex, Address, Congress District, Course, Yr., Scholarship Program
            (1, 'award_number'), (2, 'last_name'), (3, 'first_name'), (4, 'middle_name'),
            (5, 'sex'), (6, 'address'), (7, 'congress_district'), (8, 'course'),
            (9, 'year'), (10, 'scholarship_program'),
        ],
        'TDP': [
            (1, 'award_number'), (2, 'last_name'), (3, 'first_name'), (4, 'middle_name'),
            (5, 'sex'), (6, 'address'), (7, 'congress_district'), (8, 'course'),
            (9, 'year'), (10, 'scholarship_program'),
        ],
        'DOST': [
            (1, 'award_number'), (2, 'last_name'), (3, 'first_name'), (4, 'middle_name'),
            (5, 'sex'), (6, 'address'), (7, 'congress_district'), (8, 'course'),
            (9, 'year'), (10, 'scholarship_program'),
        ],
        'GSIS': [
            # No., Last, First, Middle Initial, Address, Sex, Course, Year Level, Student Number, Scholarship Program
            (1, 'last_name'), (2, 'first_name'), (3, 'middle_initial'), (4, 'address'),
            (5, 'sex'), (6, 'course'), (7, 'year'), (8, 'student_number'),
            (9, 'scholarship_program'),
        ],
        'Affirmative': [
            # No., Award Number, Last Name, First Name, Middle Name, Sex, Address, Congress District, Course, Yr., Scholarship Program
            (1, 'award_number'), (2, 'last_name'), (3, 'first_name'), (4, 'middle_name'),
            (5, 'sex'), (6, 'address'), (7, 'congress_district'), (8, 'course'),
            (9, 'year'), (10, 'scholarship_program'),
        ],
        # CoScho / Sports fallback
        'CoScho': [
            (1, 'last_name'), (2, 'first_name'), (3, 'middle_initial'), (4, 'sex'),
            (5, 'address'), (6, 'course'), (7, 'year'), (8, 'student_number'),
            (9, 'scholarship_program'),
        ],
        'Sports': [
            (1, 'last_name'), (2, 'first_name'), (3, 'middle_initial'), (4, 'sex'),
            (5, 'address'), (6, 'course'), (7, 'year'), (8, 'student_number'),
            (9, 'scholarship_program'),
        ],
    }

    if request.method == 'POST':
        stype = request.POST.get('scholarship_type', 'Academic')
        file = request.FILES.get('file')
        if file:
            try:
                wb = openpyxl.load_workbook(file)
                ws = wb.active
                col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])
                created = 0
                for row in ws.iter_rows(min_row=2, values_only=True):
                    # Skip blank rows and section-title rows (merged header rows have no No. value)
                    if not row or row[0] is None:
                        continue
                    # Skip rows where col 0 is not a number (section title rows in CHED)
                    try:
                        int(row[0])
                    except (ValueError, TypeError):
                        continue
                    extra = {}
                    for idx, field in col_map:
                        val = row[idx] if idx < len(row) else None
                        extra[field] = str(val).strip() if val is not None else ''
                    # Derive scholar_name, course, gwa, year for the core fields
                    last = extra.get('last_name', '')
                    first = extra.get('first_name', '')
                    scholar_name = f'{last}, {first}'.strip(', ')
                    course = extra.get('course', '')
                    gwa = 0.0
                    try:
                        gwa = float(extra.get('gwa', 0) or 0)
                    except (ValueError, TypeError):
                        pass
                    year = 0
                    try:
                        year = int(extra.get('year', 0) or 0)
                    except (ValueError, TypeError):
                        pass
                    ArchiveRecord.objects.create(
                        scholarship_type=stype,
                        scholar_name=scholar_name,
                        course=course,
                        gwa=gwa,
                        year=year,
                        imported_from=file.name,
                        extra_data=extra,
                    )
                    created += 1
                ActivityLog.objects.create(
                    user=request.user,
                    action=f'Imported {file.name} ({created} rows) for {stype}'
                )
                message = f'Successfully imported {created} records from {file.name}.'
            except Exception as e:
                error = f'Import failed: {e}'

    recent = ActivityLog.objects.filter(action__icontains='Imported').order_by('-created_at')[:10]
    return render(request, 'vpsea/uploads.html', {
        'recent': recent,
        'message': message,
        'error': error,
        'column_maps': {
            'Academic':    'No. | Last Name | First | Middle Name | Sex | Address | Course | Year | GWA | % / Type | Scholarship',
            'Staff':       'No. | Last | First | Middle Initial | Sex | Course | Year Level | Student Number | % | Scholarship Program',
            'CHED':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Address | Congress District | Course | Yr. | Scholarship Program',
            'TDP':         'No. | Award Number | Last Name | First Name | Middle Name | Sex | Address | Congress District | Course | Yr. | Scholarship Program',
            'DOST':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Address | Congress District | Course | Yr. | Scholarship Program',
            'GSIS':        'No. | Last | First | Middle Initial | Address | Sex | Course | Year Level | Student Number | Scholarship Program',
            'Affirmative': 'No. | Award Number | Last Name | First Name | Middle Name | Sex | Address | Congress District | Course | Yr. | Scholarship Program',
            'CoScho':      'No. | Last Name | First Name | Middle Initial | Sex | Address | Course | Year Level | Student Number | Scholarship Program',
            'Sports':      'No. | Last Name | First Name | Middle Initial | Sex | Address | Course | Year Level | Student Number | Scholarship Program',
        },
    })


@_vpsea_required
def vpsea_analytics(request):
    from .models import Application, StudentProfile
    from django.db.models import Count
    import calendar
    from django.utils import timezone
    now = timezone.now()
    trend = []
    for i in range(5, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year if now.month - i > 0 else now.year - 1
        trend.append({
            'month': calendar.month_abbr[m],
            'approved': Application.objects.filter(submitted_at__month=m, submitted_at__year=y, status='Approved').count(),
            'rejected': Application.objects.filter(submitted_at__month=m, submitted_at__year=y, status='Rejected').count(),
        })
    course_dist = list(StudentProfile.objects.filter(applications__status='Approved').values('course').annotate(scholars=Count('id')))
    gpa_ranges = [
        {'range': '1.00-1.25', 'count': StudentProfile.objects.filter(gwa__gte=1.0, gwa__lte=1.25).count()},
        {'range': '1.26-1.50', 'count': StudentProfile.objects.filter(gwa__gt=1.25, gwa__lte=1.50).count()},
        {'range': '1.51-1.75', 'count': StudentProfile.objects.filter(gwa__gt=1.50, gwa__lte=1.75).count()},
        {'range': '1.76-2.00', 'count': StudentProfile.objects.filter(gwa__gt=1.75, gwa__lte=2.00).count()},
        {'range': '2.01-2.50', 'count': StudentProfile.objects.filter(gwa__gt=2.00, gwa__lte=2.50).count()},
    ]
    return render(request, 'vpsea/analytics.html', {'trend': trend, 'course_dist': course_dist, 'gpa_ranges': gpa_ranges})


@_vpsea_required
def vpsea_announcements(request):
    from .models import Announcement
    if request.method == 'POST':
        Announcement.objects.create(
            title=request.POST.get('title'),
            body=request.POST.get('body'),
            published_by=request.user,
        )
        return redirect('/vpsea/announcements/')
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'vpsea/announcements.html', {'announcements': announcements})


@_vpsea_required
def vpsea_reports(request):
    reports = [
        {'name': 'Scholarship Master List A.Y. 2024-2025', 'desc': 'Consolidated list of all active scholars across programs.', 'size': '2.4 MB'},
        {'name': 'Academic Scholarship Approval Report Q2', 'desc': 'Approval, rejection and renewal statistics.', 'size': '812 KB'},
        {'name': 'GWA Distribution Report', 'desc': 'Cohort-wise grade weighted average breakdown.', 'size': '640 KB'},
        {'name': 'TDP Recipients Report', 'desc': 'List of TDP recipients with subsidy amounts.', 'size': '1.1 MB'},
    ]
    return render(request, 'vpsea/reports.html', {'reports': reports})


@_vpsea_required
def vpsea_ranking(request):
    from .models import AffirmativeNSUApplication
    scholarship_type = request.GET.get('type', 'Affirmative')
    scholarship_types = ['Affirmative', 'Staff']
    if scholarship_type not in scholarship_types:
        scholarship_type = 'Affirmative'

    # Exclude already approved applicants
    applicants = AffirmativeNSUApplication.objects.exclude(status='Approved').filter(
        qualified_for=scholarship_type
    )

    def score(a):
        if scholarship_type == 'Affirmative':
            s = 0
            if a.shs_gpa is not None:
                s += min((a.shs_gpa / 100) * 50, 50)  # up to 50 pts
            if a.suc_exam_score is not None:
                s += min((a.suc_exam_score / 100) * 50, 50)  # up to 50 pts
            return round(s)
        else:  # Staff
            # NSU staff themselves rank higher than dependents
            return 100 if a.is_nsu_staff else 75

    ranked = sorted(applicants, key=score, reverse=True)
    students = [{'rank': i + 1, 'applicant': a, 'score': score(a)} for i, a in enumerate(ranked)]
    return render(request, 'vpsea/ranking.html', {
        'students': students,
        'scholarship_types': scholarship_types,
        'active_type': scholarship_type,
    })

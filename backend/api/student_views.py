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

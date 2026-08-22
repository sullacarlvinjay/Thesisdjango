from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import StudentProfile, Scholarship, Application, Notification, Announcement, User, AffirmativeNSUApplication, AcademicRenewal, ScholarshipLinkRequest, TESApplication, BIPSU_SCHOOLS, BIPSU_COURSES
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.core.files.base import ContentFile
from django.http import HttpResponse
from io import BytesIO

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


# — Landing ——————————————————————————————————

def landing_view(request):
    qs = Scholarship.objects.filter(is_active=True).order_by('type')
    return render(request, 'landing.html', {
        'scholarships': qs,
        'internal': qs.filter(group='internal'),
        'external': qs.filter(group='external'),
        'institutional': qs.filter(group='institutional'),
    })


# — Academic auth ———————————————————————————————————

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            if user.role == 'student':
                return redirect('/student/applications/')
            elif user.role == 'super':
                return redirect('/super/')
            elif user.role == 'vpsea':
                return redirect('/vpsea/')
            elif user.role == 'unifast':
                return redirect('/unifast/')
            elif user.role == 'nsu_staff':
                return redirect('/nsu-staff/')
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('/')


def register_view(request):
    if request.method == 'POST':
        p = request.POST
        errors = []
        account_type = p.get('account_type', 'student')

        if p.get('password') != p.get('confirm_password'):
            errors.append('Passwords do not match.')
        if User.objects.filter(email=p.get('email')).exists():
            errors.append('Email already registered.')

        if account_type == 'student':
            if not p.get('student_id'):
                errors.append('Student ID is required.')
            elif StudentProfile.objects.filter(student_id=p.get('student_id')).exists():
                errors.append('Student ID already registered.')

        if errors:
            return render(request, 'register.html', {'errors': errors, 'post': p})

        # ── Create the Django user ──────────────────────────────────────────
        user = User.objects.create_user(
            username=p.get('email'),
            email=p.get('email'),
            password=p.get('password'),
            first_name=p.get('first_name', '').strip(),
            last_name=p.get('last_name', '').strip(),
            role=account_type,
        )

        if account_type == 'student':
            # ── Student: create a StudentProfile ───────────────────────────
            StudentProfile.objects.create(
                user=user,
                student_id=p.get('student_id'),
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1) or 1),
                contact_number=p.get('contact_number', ''),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
            )
            login(request, user)
            return redirect('/student/profile/')

        else:
            # ── NSU Staff: no StudentProfile needed — store extra info on
            #    the User directly (first/last name already set above).
            #    employee_id, department, position are stored in a light
            #    JSON blob on ActivityLog as an audit entry so no new model
            #    is required. The VPSEA office links the account to their
            #    AffirmativeNSUApplication record.
            from .models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                action=(
                    f"Staff account created — "
                    f"Employee ID: {p.get('employee_id','—')} | "
                    f"Department: {p.get('department','—')} | "
                    f"Position: {p.get('position','—')} | "
                    f"Contact: {p.get('contact_number','—')}"
                ),
            )
            login(request, user)
            return redirect('/nsu-staff/')

    return render(request, 'register.html', {'post': {}})


# — Academic student pages ——————————————————————————

def _is_enrolled(profile):
    """True only when the student has an APPROVED application or approved linked scholarship.
    Pending/Needs Revision applications do not count as enrolled — the student
    should still be able to see their other apply options while waiting for a decision.
    """
    if not profile:
        return False
    if Application.objects.filter(student=profile, status='Approved').exists():
        return True
    return ScholarshipLinkRequest.objects.filter(student=profile, status='Approved').exists()


@login_required(login_url='/login/')
def student_dashboard(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    scholarships = Scholarship.objects.filter(is_active=True)
    matched = []
    for s in scholarships:
        score = s.match_score(profile)
        matched.append({'name': s.name, 'description': s.description, 'match': score})
    matched.sort(key=lambda x: x['match'], reverse=True)
    applications = Application.objects.filter(student=profile) if profile else Application.objects.none()
    announcements = Announcement.objects.order_by('-created_at')[:3]
    top_match = matched[0]['match'] if matched else 0
    top_match_offset = round(314 * (1 - top_match / 100))
    timeline = [
        {'date': a.submitted_at, 'title': f"{a.scholarship.name} — {a.status}", 'status': 'done' if a.status == 'Approved' else 'pending'}
        for a in applications.select_related('scholarship').order_by('-submitted_at')[:5]
    ]
    ctx = {
        'profile': profile,
        'enrolled': _is_enrolled(profile),
        'scholarships': matched,
        'announcements': announcements,
        'top_match': top_match,
        'top_match_offset': top_match_offset,
        'timeline': timeline,
        'dashboard': {
            'recommended_count': len([s for s in matched if s['match'] >= 50]),
            'pending_count': applications.filter(status='Pending Validation').count(),
            'approved_count': applications.filter(status='Approved').count(),
            'notification_count': Notification.objects.filter(student=profile, is_read=False).count() if profile else 0,
        },
    }
    return render(request, 'student/dashboard.html', ctx)


@login_required(login_url='/login/')
def student_apply_staff(request):
    from .models import ApplicationDocument
    profile = StudentProfile.objects.filter(user=request.user).first()
    # Block if already has an active (non-rejected, non-draft) application for any scholarship
    existing = Application.objects.filter(
        student=profile, status__in=['Pending Validation', 'Approved', 'Needs Revision']
    ).select_related('scholarship').first() if profile else None
    if not existing:
        # Also block if student has an approved linked scholarship
        existing_link = ScholarshipLinkRequest.objects.filter(
            student=profile, status='Approved'
        ).first() if profile else None
        if existing_link:
            return render(request, 'student/apply_staff.html', {
                'profile': profile, 'blocked': True,
                'blocked_reason': f'You are already enrolled in the {existing_link.scholarship_type} scholarship program. You cannot apply to another scholarship while enrolled in a program.',
            })
    if existing:
        return render(request, 'student/apply_staff.html', {
            'profile': profile, 'blocked': True,
            'blocked_reason': f'You already have an active {existing.scholarship.name} application ({existing.status}). You cannot apply to another scholarship while enrolled in a program.',
        })
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Staff').first()
        if scholarship and profile:
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Draft' if request.POST.get('action') == 'draft' else 'Pending Validation',
                form_data={
                    'employment_status': request.POST.get('employment_status', ''),
                    'designation': request.POST.get('designation', ''),
                    'years_of_service': request.POST.get('years_of_service', ''),
                    'date_of_regularization': request.POST.get('date_of_regularization', ''),
                }
            )
            uploaded = request.FILES.get('doc_appointment')
            if uploaded:
                ApplicationDocument.objects.create(application=app, name='Appointment Paper', file=uploaded)
        return redirect('/student/apply/staff/?submitted=1')
    return render(request, 'student/apply_staff.html', {
        'profile': profile,
        'submitted': request.GET.get('submitted'),
        'enrolled': _is_enrolled(profile),
    })


@login_required(login_url='/login/')
def student_apply_academic(request):
    from .models import ApplicationDocument
    profile = StudentProfile.objects.filter(user=request.user).first()
    # Block if already has an active (non-rejected, non-draft) application for any scholarship
    existing = Application.objects.filter(
        student=profile, status__in=['Pending Validation', 'Approved', 'Needs Revision']
    ).select_related('scholarship').first() if profile else None
    if not existing:
        # Also block if student has an approved linked scholarship
        existing_link = ScholarshipLinkRequest.objects.filter(
            student=profile, status='Approved'
        ).first() if profile else None
        if existing_link:
            return render(request, 'student/apply_academic.html', {
                'profile': profile, 'blocked': True,
                'blocked_reason': f'You are already enrolled in the {existing_link.scholarship_type} scholarship program. You cannot apply to another scholarship while enrolled in a program.',
                'classification': '', 'eligible': False,
            })
    if existing:
        return render(request, 'student/apply_academic.html', {
            'profile': profile, 'blocked': True,
            'blocked_reason': f'You already have an active {existing.scholarship.name} application ({existing.status}). You cannot apply to another scholarship while enrolled in a program.',
            'classification': '', 'eligible': False,
        })
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Academic').first()
        if scholarship and profile:
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Draft' if request.POST.get('action') == 'draft' else 'Pending Validation',
                form_data=request.POST.dict()
            )
            for field, label in [
                ('doc_certificate_of_grades', 'Certificate Of Grades'),
                ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
                ('doc_prospectus', 'Prospectus'),
                ('doc_id_photo', 'Id Photo'),
                ('doc_application_form', 'Application Form'),
            ]:
                uploaded = request.FILES.get(field)
                if uploaded:
                    ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
        return redirect('/student/applications/')
    gwa = profile.gwa if profile else 0
    if gwa <= 1.00:
        classification = 'University Scholar'
    elif gwa <= 1.50:
        classification = 'College Scholar'
    else:
        classification = 'Not Eligible'
    return render(request, 'student/apply_academic.html', {
        'profile': profile,
        'classification': classification,
        'eligible': gwa <= 1.50,
        'enrolled': _is_enrolled(profile),
    })
    


@login_required(login_url='/login/')
def student_applications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = Application.objects.filter(student=profile).select_related('scholarship') if profile else Application.objects.none()
    tes_applications = TESApplication.objects.filter(student=profile) if profile else TESApplication.objects.none()
    return render(request, 'student/applications.html', {
        'applications': applications,
        'tes_applications': tes_applications,
        'enrolled': _is_enrolled(profile),
    })


@login_required(login_url='/login/')
def student_notifications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    notifications = Notification.objects.filter(student=profile).order_by('-created_at') if profile else Notification.objects.none()
    return render(request, 'student/notifications.html', {'notifications': notifications, 'enrolled': _is_enrolled(profile)})


@login_required(login_url='/login/')
def student_renewal_academic(request):
    from .models import SystemSettings
    profile = StudentProfile.objects.filter(user=request.user).first()
    has_academic = Application.objects.filter(student=profile, scholarship__type='Academic', status='Approved').exists() if profile else False
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    if request.method == 'POST' and profile:
        cog = request.FILES.get('certificate_of_grades')
        coe = request.FILES.get('certificate_of_enrollment')
        errors = []
        if not cog:
            errors.append('Certificate of Grades is required.')
        if not coe:
            errors.append('Certificate of Enrollment is required.')
        if errors:
            renewals = AcademicRenewal.objects.filter(student=profile).order_by('-submitted_at')
            return render(request, 'student/renewal_academic.html', {
                'profile': profile, 'has_academic': has_academic,
                'renewals': renewals, 'errors': errors,
                'semester': settings_obj.active_semester, 'academic_year': settings_obj.academic_year,
                'enrolled': _is_enrolled(profile),
            })
        AcademicRenewal.objects.create(student=profile, certificate_of_grades=cog, certificate_of_enrollment=coe)
        return redirect('/student/renewal/academic/?submitted=1')
    renewals = AcademicRenewal.objects.filter(student=profile).order_by('-submitted_at') if profile else []
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'student/renewal_academic.html', {
        'profile': profile, 'has_academic': has_academic,
        'renewals': renewals, 'submitted': request.GET.get('submitted'),
        'semester': parsed['semester'], 'academic_year': parsed['sy'],
        'enrolled': _is_enrolled(profile),
    })


@login_required(login_url='/login/')
@login_required(login_url='/login/')
def student_profile(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    errors = []
    saved = False
    if request.method == 'POST' and profile:
        p = request.POST
        u = profile.user
        u.save()
        profile.family_income = float(p.get('family_income', profile.family_income) or profile.family_income)
        profile.indigenous_group = p.get('indigenous_group', profile.indigenous_group)
        profile.is_pwd = 'is_pwd' in p
        profile.is_athlete = 'is_athlete' in p
        profile.is_coconut_farmer_family = 'is_coconut_farmer_family' in p
        profile.has_other_scholarship = 'has_other_scholarship' in p
        profile.elementary = p.get('elementary', profile.elementary)
        profile.highschool = p.get('highschool', profile.highschool)
        profile.last_school = p.get('last_school', profile.last_school)
        profile.father_name = p.get('father_name', profile.father_name)
        profile.father_occupation = p.get('father_occupation', profile.father_occupation)
        profile.mother_name = p.get('mother_name', profile.mother_name)
        profile.mother_occupation = p.get('mother_occupation', profile.mother_occupation)
        # Affirmative eligibility
        raw_shs = p.get('shs_gpa', '').strip()
        if raw_shs:
            try: profile.shs_gpa = float(raw_shs)
            except ValueError: pass
        raw_suc = p.get('suc_exam_score', '').strip()
        if raw_suc:
            try: profile.suc_exam_score = float(raw_suc)
            except ValueError: pass
        profile.is_tes_beneficiary = 'is_tes_beneficiary' in p
        if request.FILES.get('shs_gpa_cert'):
            profile.shs_gpa_cert = request.FILES['shs_gpa_cert']
        if request.FILES.get('suc_exam_cert'):
            profile.suc_exam_cert = request.FILES['suc_exam_cert']
        # Address: only update if not yet locked (all three empty)
        if not (profile.barangay and profile.municipality and profile.province):
            profile.barangay = p.get('barangay', profile.barangay)
            profile.municipality = p.get('municipality', profile.municipality)
            profile.province = p.get('province', profile.province)
        profile.save()
        saved = True
    import json
    address_locked = bool(profile and profile.barangay and profile.municipality and profile.province)
    return render(request, 'student/profile.html', {
        'profile': profile, 'errors': errors, 'saved': saved,
        'enrolled': _is_enrolled(profile),
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'address_locked': address_locked,
    })


@login_required(login_url='/login/')
def student_link_scholarship(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    SCHOLARSHIP_TYPES = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'GSIS', 'Affirmative', 'NSU Staff']
    if request.method == 'POST' and profile:
        stype = request.POST.get('scholarship_type', '')
        notes = request.POST.get('notes', '')
        proof = request.FILES.get('proof_document')
        errors = []
        if not stype:
            errors.append('Please select a scholarship type.')
        if not proof:
            errors.append('Proof document is required.')
        if errors:
            link_requests = ScholarshipLinkRequest.objects.filter(student=profile).order_by('-submitted_at')
            return render(request, 'student/link_scholarship.html', {
                'profile': profile, 'scholarship_types': SCHOLARSHIP_TYPES,
                'link_requests': link_requests, 'errors': errors,
            })
        ScholarshipLinkRequest.objects.create(student=profile, scholarship_type=stype, proof_document=proof, notes=notes)
        return redirect('/student/link-scholarship/?submitted=1')
    link_requests = ScholarshipLinkRequest.objects.filter(student=profile).order_by('-submitted_at') if profile else []
    return render(request, 'student/link_scholarship.html', {
        'profile': profile, 'scholarship_types': SCHOLARSHIP_TYPES,
        'link_requests': link_requests, 'submitted': request.GET.get('submitted'),
        'enrolled': _is_enrolled(profile),
    })


# — UniFAST portal pages ———————————————————————————

def _unifast_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'unifast':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_unifast_required
def unifast_dashboard(request):
    from .models import TDPApplication
    ctx = {
        'tes_beneficiaries': TDPApplication.objects.filter(status='Approved').count(),
        'tdp_scholars': TDPApplication.objects.count(),
        'billing_approved_pct': 92,
        'pending_liquidation': 0,
        'released_funds': 'â‚±3.45M',
    }
    return render(request, 'unifast/dashboard.html', ctx)



# — VPSEA portal pages ———————————————————————————————————

def _vpsea_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'vpsea':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_vpsea_required
def vpsea_affirmative_applications(request):
    from .models import AffirmativeNSUApplication
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        try:
            aff_app = AffirmativeNSUApplication.objects.get(id=app_id)
            aff_app.status = new_status
            aff_app.remarks = remarks
            aff_app.save()
            # On approval: create Django User + StudentProfile + Application
            if new_status == 'Approved' and not User.objects.filter(email=aff_app.email).exists():
                name_parts = aff_app.full_name.strip().split()
                first_name = name_parts[0] if name_parts else ''
                last_name = name_parts[-1] if len(name_parts) > 1 else ''
                raw_password = aff_app.school_id or aff_app.email.split('@')[0]
                new_user = User.objects.create_user(
                    username=aff_app.email,
                    email=aff_app.email,
                    password=raw_password,
                    first_name=first_name,
                    last_name=last_name,
                    role='student',
                )
                profile = StudentProfile.objects.create(
                    user=new_user,
                    student_id=aff_app.school_id or f'AFF-{aff_app.id}',
                    school=aff_app.school,
                    course=aff_app.course,
                    year_level=aff_app.year_level,
                    contact_number=aff_app.contact_number,
                    barangay=aff_app.barangay,
                    municipality=aff_app.municipality,
                    province=aff_app.province,
                    date_of_birth=aff_app.date_of_birth,
                    gender=aff_app.gender,
                )
                scholarship = Scholarship.objects.filter(type=aff_app.qualified_for).first()
                if scholarship:
                    Application.objects.create(
                        student=profile,
                        scholarship=scholarship,
                        status='Approved',
                        remarks=remarks,
                        form_data={},
                    )
        except AffirmativeNSUApplication.DoesNotExist:
            pass
        return redirect('/vpsea/affirmative/')
    stype = request.GET.get('type', '')
    qs = AffirmativeNSUApplication.objects.all().order_by('-submitted_at')
    if stype in ('Affirmative', 'Staff'):
        qs = qs.filter(qualified_for=stype)
    return render(request, 'vpsea/affirmative.html', {'applications': qs, 'active_type': stype})


@_vpsea_required
def vpsea_dashboard(request):
    from .models import Application, Renewal, AffirmativeNSUApplication, SystemSettings
    from django.db.models import Q
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    apps = Application.objects.filter(
        Q(form_data__academic_year=active_sy) | Q(form_data__academic_year=settings_obj.academic_year),
        form_data__semester=active_semester,
    )
    ctx = {
        'total_applicants': apps.count(),
        'approved': apps.filter(status='Approved').count(),
        'rejected': apps.filter(status='Rejected').count(),
        'pending': apps.filter(status='Pending Validation').count(),
        'renewals': Renewal.objects.filter(status='Renewal Pending').count(),
        'pending_staff': AffirmativeNSUApplication.objects.filter(qualified_for='Staff', status='Pending Validation').count(),
        'pending_affirmative': AffirmativeNSUApplication.objects.filter(qualified_for='Affirmative', status='Pending Validation').count(),
        'active_sy_display': f"{active_sy} — {active_semester}",
    }
    return render(request, 'vpsea/dashboard.html', ctx)


@_vpsea_required
def vpsea_applications(request):
    from .models import Application, AffirmativeNSUApplication
    if request.method == 'POST':
        tab = request.POST.get('tab', 'academic')
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        if tab == 'affirmative':
            AffirmativeNSUApplication.objects.filter(id=app_id).update(status=new_status, remarks=remarks)
        else:
            Application.objects.filter(id=app_id).update(status=new_status, remarks=remarks)
        return redirect(f'/vpsea/applications/?tab={tab}')
    tab = request.GET.get('tab', 'academic')
    academic_apps = Application.objects.select_related('student__user', 'scholarship').prefetch_related('documents').exclude(scholarship__type='Staff').order_by('-submitted_at')
    staff_apps = Application.objects.select_related('student__user', 'scholarship').prefetch_related('documents').filter(scholarship__type='Staff').order_by('-submitted_at')
    affirmative_apps = AffirmativeNSUApplication.objects.filter(qualified_for='Affirmative').order_by('-submitted_at')
    return render(request, 'vpsea/applications.html', {
        'applications': academic_apps,
        'academic_apps': academic_apps,
        'staff_apps': staff_apps,
        'affirmative_apps': affirmative_apps,
        'active_tab': tab,
    })


@_vpsea_required
def vpsea_renewals(request):
    if request.method == 'POST':
        from .models import SystemSettings
        from django.utils import timezone
        renewal_id = request.POST.get('renewal_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        AcademicRenewal.objects.filter(id=renewal_id).update(status=new_status, remarks=remarks)
        # On approval: create a new Application for the current semester so the
        # student appears in the current-SY archives.
        if new_status == 'Approved':
            try:
                renewal = AcademicRenewal.objects.select_related('student').get(id=renewal_id)
                scholarship = Scholarship.objects.filter(type='Academic').first()
                if scholarship:
                    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
                    parsed = SystemSettings.parse_label(settings_obj.academic_year)
                    already = Application.objects.filter(
                        student=renewal.student, scholarship=scholarship,
                        form_data__academic_year=parsed['sy'],
                        form_data__semester=parsed['semester'],
                    ).exists()
                    if not already:
                        Application.objects.create(
                            student=renewal.student,
                            scholarship=scholarship,
                            status='Approved',
                            remarks=remarks,
                            form_data={'source': 'renewal', 'renewal_id': renewal_id,
                                       'academic_year': parsed['sy'],
                                       'semester': parsed['semester']},
                        )
            except AcademicRenewal.DoesNotExist:
                pass
        return redirect('/vpsea/renewals/')
    renewals = AcademicRenewal.objects.select_related('student__user').order_by('-submitted_at')
    return render(request, 'vpsea/renewals.html', {
        'renewals': renewals,
        'approved_count': renewals.filter(status='Approved').count(),
        'pending_count': renewals.filter(status='Pending').count(),
    })


@_vpsea_required
def vpsea_archives(request):
    from .models import Application, AffirmativeNSUApplication, ScholarshipRollover, SystemSettings, AcademicRenewal, ActivityLog
    stype = request.GET.get('type', 'Academic')
    # Build archive_types dynamically from DB so newly added scholarship types appear
    base_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    db_types = list(Scholarship.objects.values_list('type', flat=True).distinct())
    archive_types = base_types + [t for t in db_types if t not in base_types]
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year  # e.g. '26-1'
    parsed = SystemSettings.parse_label(active_label)
    active_sy = parsed['sy']           # '2025-2026'
    active_semester = parsed['semester']  # '1st Semester'

    history = ScholarshipRollover.objects.filter(scholarship_type=stype).order_by('-created_at')
    all_labels = list(
    ScholarshipRollover.objects.filter(scholarship_type=stype)
    .values_list('label', flat=True).distinct().order_by('-label')
)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label

    selected_parsed = SystemSettings.parse_label(selected_label)
    selected_sy = selected_parsed['sy']   # e.g. '2025-2026'
    sy_start = selected_parsed['sy_start']
    sy_end = selected_parsed['sy_end']

    next_label = settings_obj.next_label()
    # Human-readable label for display: '2025-2026 — 1st Semester'
    active_display = f"{active_sy} — {active_semester}"
    # Build (label, display) pairs for the SY dropdown
    all_sy_display = []
    for lbl in all_labels:
        p = SystemSettings.parse_label(lbl)
        all_sy_display.append((lbl, f"{p['sy']} — {p['semester']}"))

    # Previous label = one step back from active
    yy, s = active_label.split('-')
    if s == '2':
        prev_label = f'{yy}-1'
    else:
        prev_label = f'{int(yy)-1}-2'
    prev_parsed = SystemSettings.parse_label(prev_label)
    prev_display = f"{prev_parsed['sy']} — {prev_parsed['semester']}"

    base_ctx = {
        'archive_types': archive_types,
        'active_type': stype,
        'history': history,
        'all_sy': all_labels,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'active_sy': active_label,
        'active_sy_display': active_display,
        'active_semester': active_semester,
        'next_sy': next_label,
        'prev_sy': prev_label,
        'prev_sy_display': prev_display,
        'add_docs': [
            (1, 'Certificate of Grades', 'Official COG from the Registrar for the previous semester.', 'doc_certificate_of_grades'),
            (2, 'Certificate of Enrollment', 'Official COE from the Registrar for the current semester.', 'doc_certificate_of_enrollment'),
            (3, 'Prospectus / Subject Checklist', 'Program prospectus or subject checklist showing enrolled subjects.', 'doc_prospectus'),
            (4, '2Ã—2 ID Photo', 'Recent 2Ã—2 ID photo with white background.', 'doc_id_photo'),
            (5, 'Application Form', 'Signed and accomplished scholarship application form.', 'doc_application_form'),
        ],
        'col_hint': COLUMN_HINTS.get(stype, ''),
        'recent_imports': ActivityLog.objects.filter(action__icontains='Imported').order_by('-created_at')[:5],
        'import_message': f"Successfully imported {request.GET.get('import_ok')} records." if request.GET.get('import_ok') else None,
        'import_error': request.GET.get('import_error'),
    }

    # Renewal-gated: only scholars with an Approved AcademicRenewal are shown
    # For Affirmative/Staff there is no AcademicRenewal flow — show all approved
    from .models import ArchiveRecord
    imported_rows = ArchiveRecord.objects.filter(
        scholarship_type=stype, rollover_label=selected_label
    ).order_by('last_name', 'first_name')

    if stype in ('Affirmative', 'Staff'):
        aff_scholars = AffirmativeNSUApplication.objects.filter(
            status='Approved', qualified_for=stype
        ).order_by('full_name')
        return render(request, 'vpsea/archives.html', {
            **base_ctx,
            'aff_scholars': aff_scholars,
            'imported_rows': imported_rows,
            'scholars': None,
            'total': aff_scholars.count() + imported_rows.count(),
        })

    def sy_filter(qs):
        from django.db.models import Q
        # For the active/current semester, show all approved apps regardless of
        # what SY is stored in form_data (student-submitted apps store school_year
        # from the form, not the system active_label)
        if selected_label == active_label:
            return qs
        selected_sy = SystemSettings.parse_label(selected_label)['sy']
        return qs.filter(
            Q(form_data__academic_year=selected_sy) |
            Q(form_data__school_year=selected_sy) |
            Q(form_data__academic_year=selected_label) |
            Q(form_data__school_year=selected_label)
        )

    if stype == 'CHED':
        all_scholars = sy_filter(Application.objects.filter(
            status='Approved', scholarship__type='CHED',
        )).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        full_scholars = [a for a in all_scholars if 'full' in (a.scholarship.name or '').lower() or 'full' in (a.form_data.get('scholar_type', '')).lower()]
        half_scholars = [a for a in all_scholars if a not in full_scholars]
        if not full_scholars and not half_scholars:
            full_scholars = list(all_scholars)
        return render(request, 'vpsea/archives.html', {
            **base_ctx,
            'full_scholars': full_scholars,
            'half_scholars': half_scholars,
            'imported_rows': imported_rows,
            'scholars': None,
            'total': all_scholars.count() + imported_rows.count(),
        })

    scholars = sy_filter(Application.objects.filter(
        status='Approved', scholarship__type=stype,
    )).select_related('student__user', 'scholarship').order_by('student__user__last_name').distinct()
    return render(request, 'vpsea/archives.html', {
        **base_ctx,
        'scholars': scholars,
        'imported_rows': imported_rows,
        'total': scholars.count() + imported_rows.count(),
    })


@_vpsea_required
def vpsea_archive_add(request):
    from .models import Application, Scholarship, StudentProfile, User, AffirmativeNSUApplication, SystemSettings, ApplicationDocument
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    f = request.FILES
    stype = p.get('scholarship_type', 'Academic')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']

    if stype in ('Affirmative', 'Staff'):
        full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
        fake_email = f"{p.get('student_id','').strip() or full_name.replace(' ','_').lower()}_{stype.lower()}@bipsu.edu.ph"
        base = fake_email
        counter = 1
        while AffirmativeNSUApplication.objects.filter(email=fake_email).exists():
            fake_email = f"{base.split('@')[0]}_{counter}@bipsu.edu.ph"
            counter += 1
        AffirmativeNSUApplication.objects.create(
            full_name=full_name,
            email=fake_email,
            contact_number=p.get('contact_number', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            date_of_birth=p.get('date_of_birth') or '2000-01-01',
            gender=p.get('gender', ''),
            course=p.get('course', ''),
            year_level=int(p.get('year_level', 1) or 1),
            school_id=p.get('student_id', ''),
            qualified_for=stype,
            status='Approved',
            is_nsu_staff=(stype == 'Staff'),
        )
    else:
        email = p.get('email', '').strip()
        student_id = p.get('student_id', '').strip()
        if not email:
            email = f"{student_id}@bipsu.edu.ph"
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(
                username=email, email=email,
                password=student_id or 'bipsu1234',
                first_name=p.get('first_name', ''),
                last_name=p.get('last_name', ''),
                role='student',
            )
        profile = StudentProfile.objects.filter(user=user).first()
        if not profile:
            profile = StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1) or 1),
                gwa=float(p.get('gwa', 0) or 0),
                gender=p.get('gender', ''),
                barangay=p.get('barangay', ''),
                municipality=p.get('municipality', ''),
                province=p.get('province', ''),
                contact_number=p.get('contact_number', ''),
                date_of_birth=p.get('date_of_birth') or None,
            )
        else:
            profile.course = p.get('course', profile.course)
            profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
            profile.gwa = float(p.get('gwa', profile.gwa) or profile.gwa)
            profile.gender = p.get('gender', profile.gender)
            profile.barangay = p.get('barangay', profile.barangay)
            profile.municipality = p.get('municipality', profile.municipality)
            profile.province = p.get('province', profile.province)
            profile.save()
        scholarship = Scholarship.objects.filter(type=stype).first()
        if scholarship:
            form_data = {
                'academic_year': active_sy,
                'semester': active_semester,
                'award_number': p.get('award_number', ''),
                'congress_district': p.get('congress_district', ''),
                'source': 'manual',
            }
            if stype == 'Academic':
                form_data.update({
                    'elementary': p.get('elementary', ''),
                    'highschool': p.get('highschool', ''),
                    'last_school': p.get('last_school', ''),
                    'father_name': p.get('father_name', ''),
                    'father_occupation': p.get('father_occupation', ''),
                    'mother_name': p.get('mother_name', ''),
                    'mother_occupation': p.get('mother_occupation', ''),
                })
            already = Application.objects.filter(
                student=profile, scholarship=scholarship,
                form_data__academic_year=active_sy,
                form_data__semester=active_semester,
            ).exists()
            if not already:
                app = Application.objects.create(
                    student=profile,
                    scholarship=scholarship,
                    status='Approved',
                    form_data=form_data,
                )
            else:
                app = Application.objects.filter(
                    student=profile, scholarship=scholarship,
                    form_data__academic_year=active_sy,
                    form_data__semester=active_semester,
                ).first()
            # Save uploaded documents
            doc_fields = [
                ('doc_certificate_of_grades', 'Certificate Of Grades'),
                ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
                ('doc_prospectus', 'Prospectus'),
                ('doc_id_photo', 'Id Photo'),
                ('doc_application_form', 'Application Form'),
                ('proof_document', 'Proof Document'),
            ]
            for field, label in doc_fields:
                uploaded = f.get(field)
                if uploaded:
                    ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
    return redirect(f'/vpsea/archives/?type={stype}&added=1')


@_vpsea_required
def vpsea_archive_edit(request, pk):
    from .models import Application, AffirmativeNSUApplication, StudentProfile, SystemSettings
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'Academic')
    is_aff = stype in ('Affirmative', 'Staff')

    if is_aff:
        try:
            obj = AffirmativeNSUApplication.objects.get(pk=pk)
        except AffirmativeNSUApplication.DoesNotExist:
            return redirect(f'/vpsea/archives/?type={stype}')
        obj.full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
        obj.gender = p.get('gender', obj.gender)
        obj.course = p.get('course', obj.course)
        obj.year_level = int(p.get('year_level', obj.year_level) or obj.year_level)
        obj.barangay = p.get('barangay', obj.barangay)
        obj.municipality = p.get('municipality', obj.municipality)
        obj.province = p.get('province', obj.province)
        obj.school_id = p.get('student_id', obj.school_id)
        if p.get('contact_number'):
            obj.contact_number = p.get('contact_number')
        if p.get('date_of_birth'):
            obj.date_of_birth = p.get('date_of_birth')
        # Password reset for AffirmativeNSUApplication scholars
        new_pw = p.get('new_password', '').strip()
        if new_pw:
            obj.set_password(new_pw)
        obj.save()
    else:
        try:
            app = Application.objects.select_related('student__user').get(pk=pk)
        except Application.DoesNotExist:
            return redirect(f'/vpsea/archives/?type={stype}')
        profile = app.student
        user = profile.user
        user.first_name = p.get('first_name', user.first_name)
        user.last_name = p.get('last_name', user.last_name)
        # Password reset for enrolled students (Django User)
        new_pw = p.get('new_password', '').strip()
        if new_pw:
            user.set_password(new_pw)
        user.save()
        profile.course = p.get('course', profile.course)
        profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
        profile.gender = p.get('gender', profile.gender)
        profile.barangay = p.get('barangay', profile.barangay)
        profile.municipality = p.get('municipality', profile.municipality)
        profile.province = p.get('province', profile.province)
        if p.get('student_id'):
            profile.student_id = p.get('student_id')
        if p.get('gwa'):
            profile.gwa = float(p.get('gwa'))
        profile.save()
        fd = dict(app.form_data)
        if p.get('award_number') is not None:
            fd['award_number'] = p.get('award_number')
        if p.get('congress_district') is not None:
            fd['congress_district'] = p.get('congress_district')
        app.form_data = fd
        app.save()
    return redirect(f'/vpsea/archives/?type={stype}&edited=1')


@_vpsea_required
def vpsea_archive_delete(request, pk):
    from .models import Application, AffirmativeNSUApplication
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    if stype in ('Affirmative', 'Staff'):
        AffirmativeNSUApplication.objects.filter(pk=pk).delete()
    else:
        Application.objects.filter(pk=pk).delete()
    return redirect(f'/vpsea/archives/?type={stype}&deleted=1')


@_vpsea_required
def vpsea_new_semester(request):
    from .models import SystemSettings, ScholarshipRollover, ActivityLog, Application, AffirmativeNSUApplication
    from django.core.files.base import ContentFile
    import openpyxl
    from io import BytesIO
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    label = request.POST.get('school_year', '').strip()
    stype = request.POST.get('type', 'Academic')
    if not label or '-' not in label:
        return redirect(f'/vpsea/archives/?type={stype}')

    parsed = SystemSettings.parse_label(label)
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    settings_obj.academic_year = label
    settings_obj.active_semester = parsed['semester']
    settings_obj.save()

    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    ALL_TYPES = _base + [t for t in Scholarship.objects.values_list('type', flat=True).distinct() if t not in _base]

    def _build_excel(scholarship_type):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Scholars'
        if scholarship_type in ('Affirmative', 'Staff'):
            ws.append(['No.', 'Full Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'Address'])
            qs = AffirmativeNSUApplication.objects.filter(
                status='Approved', qualified_for=scholarship_type
            ).order_by('full_name')
            for i, s in enumerate(qs, 1):
                ws.append([i, s.full_name, s.gender, s.course, s.year_level, s.school_id, s.address])
        else:
            ws.append(['No.', 'Last Name', 'First Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'GWA', 'Barangay', 'Municipality', 'Province'])
            qs = Application.objects.filter(
                status='Approved', scholarship__type=scholarship_type
            ).select_related('student__user').order_by('student__user__last_name')
            for i, app in enumerate(qs, 1):
                p = app.student
                ws.append([i, p.user.last_name, p.user.first_name, p.gender, p.course, p.year_level, p.student_id, p.gwa, p.barangay, p.municipality, p.province])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf, qs.count()

    created = 0
    for t in ALL_TYPES:
        if ScholarshipRollover.objects.filter(label=label, scholarship_type=t).exists():
            continue
        buf, count = _build_excel(t)
        rollover = ScholarshipRollover(
            scholarship_type=t,
            school_year=parsed['sy'],
            semester=parsed['semester'],
            label=label,
            scholar_count=count,
            rolled_over_by=request.user,
        )
        rollover.excel_file.save(f'{t}_{label}.xlsx', ContentFile(buf.read()), save=True)
        created += 1

    ActivityLog.objects.create(
        user=request.user,
        action=f'New semester started: {label} ({parsed["sy"]} {parsed["semester"]}). Saved lists for {created} scholarship types.'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


@_vpsea_required
def vpsea_undo_semester(request):
    from .models import SystemSettings, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    prev_label = request.POST.get('prev_label', '').strip()
    stype = request.POST.get('type', 'Academic')
    if not prev_label or '-' not in prev_label:
        return redirect(f'/vpsea/archives/?type={stype}')
    parsed = SystemSettings.parse_label(prev_label)
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    old_label = settings_obj.academic_year
    settings_obj.academic_year = prev_label
    settings_obj.active_semester = parsed['semester']
    settings_obj.save()
    ActivityLog.objects.create(
        user=request.user,
        action=f'Semester undone from {old_label} back to {prev_label} ({parsed["sy"]} {parsed["semester"]}).'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


COLUMN_HINTS = {
    'Academic':    'No. | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Course | Year | GWA | % / Type | Scholarship',
    'Staff':       'No. | Last Name | First Name | Middle Initial | Sex | Course | Year Level | Student Number | % | Scholarship Program',
    'CHED':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'TDP':         'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'DOST':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'GSIS':        'No. | Last Name | First Name | Middle Initial | Brgy./St. | Municipality | Province | Sex | Course | Year Level | Student Number | Scholarship Program',
    'Affirmative': 'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'CoScho':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
    'Sports':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
}

COLUMN_MAPS = {
    'Academic':    [(1,'last_name'),(2,'first_name'),(3,'middle_name'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'gwa'),(11,'pct_type'),(12,'scholarship')],
    'Staff':       [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'course'),(6,'year'),(7,'student_number'),(8,'pct'),(9,'scholarship_program')],
    'CHED':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'TDP':         [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'DOST':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'GSIS':        [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'barangay'),(5,'municipality'),(6,'province'),(7,'sex'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Affirmative': [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'CoScho':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Sports':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
}


@_vpsea_required
def vpsea_rollover_delete(request, pk):
    from .models import ScholarshipRollover
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    try:
        r = ScholarshipRollover.objects.get(pk=pk)
        r.excel_file.delete(save=False)
        r.delete()
    except ScholarshipRollover.DoesNotExist:
        pass
    return redirect(f'/vpsea/archives/?type={stype}')


@_vpsea_required
def vpsea_archive_import(request):
    import openpyxl
    from django.core.files.base import ContentFile
    from .models import ScholarshipRollover, ActivityLog, SystemSettings, ArchiveRecord
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    rollover_label = request.POST.get('rollover_label', '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'/vpsea/archives/?type={stype}&import_error=No+file+provided')
    if not rollover_label:
        return redirect(f'/vpsea/archives/?type={stype}&import_error=Rollover+name+is+required')
    try:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        parsed = SystemSettings.parse_label(settings_obj.academic_year)
        active_semester = parsed['semester']
        rollover_parsed = SystemSettings.parse_label(rollover_label) if '-' in rollover_label else {'sy': rollover_label, 'semester': active_semester}

        wb = openpyxl.load_workbook(file)
        ws = wb.active
        col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])

        # Delete existing rows for this label+type so re-import is clean
        ArchiveRecord.objects.filter(scholarship_type=stype, rollover_label=rollover_label).delete()

        records = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            try:
                int(row[0])
            except (ValueError, TypeError):
                continue

            extra = {}
            for idx, field in col_map:
                val = row[idx] if idx < len(row) else None
                extra[field] = str(val).strip() if val is not None else ''

            last = extra.get('last_name', '').strip()
            first = extra.get('first_name', '').strip()
            if not last and not first:
                continue

            try:
                year_level = int(extra.get('year', 0) or 0)
            except (ValueError, TypeError):
                year_level = 0
            try:
                gwa = float(extra.get('gwa', 0) or 0)
            except (ValueError, TypeError):
                gwa = 0.0

            address = extra.get('address', '')
            addr_parts = [x.strip() for x in address.split(',')] if address else []

            records.append(ArchiveRecord(
                scholarship_type=stype,
                rollover_label=rollover_label,
                last_name=last,
                first_name=first,
                middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
                scholar_name=f'{first} {last}'.strip(),
                gender=extra.get('sex', ''),
                course=extra.get('course', ''),
                year=year_level,
                gwa=gwa,
                barangay=extra.get('barangay', addr_parts[0] if len(addr_parts) > 0 else ''),
                municipality=extra.get('municipality', addr_parts[1] if len(addr_parts) > 1 else ''),
                province=extra.get('province', addr_parts[2] if len(addr_parts) > 2 else ''),
                student_number=extra.get('student_number', extra.get('student_id', '')),
                award_number=extra.get('award_number', ''),
                congress_district=extra.get('congress_district', ''),
                imported_from=file.name,
            ))

        ArchiveRecord.objects.bulk_create(records)
        created = len(records)

        # Save the uploaded file as a rollover record for download history
        file.seek(0)
        if not ScholarshipRollover.objects.filter(label=rollover_label, scholarship_type=stype).exists():
            rollover = ScholarshipRollover(
                scholarship_type=stype,
                school_year=rollover_parsed['sy'],
                semester=rollover_parsed.get('semester', active_semester),
                label=rollover_label,
                scholar_count=created,
                rolled_over_by=request.user,
            )
            rollover.excel_file.save(f'{stype}_{rollover_label}.xlsx', ContentFile(file.read()), save=True)
        else:
            ScholarshipRollover.objects.filter(label=rollover_label, scholarship_type=stype).update(scholar_count=created)

        ActivityLog.objects.create(
            user=request.user,
            action=f'Imported {file.name} ({created} rows) for {stype} as "{rollover_label}"'
        )
    except Exception as e:
        return redirect(f'/vpsea/archives/?type={stype}&import_error={e}')
    return redirect(f'/vpsea/archives/?type={stype}&import_ok={created}')



@_vpsea_required
def vpsea_archive_download(request):
    from .models import Application, AffirmativeNSUApplication, SystemSettings, AcademicRenewal
    stype = request.GET.get('type', 'Academic')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    school_year = settings_obj.academic_year
    semester = settings_obj.active_semester

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{stype} Scholars'
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    hfont = Font(bold=True)
    hfill = PatternFill('solid', fgColor='D9E1F2')

    def hrow(ws, r, n):
        for c in range(1, n+1):
            cell = ws.cell(row=r, column=c)
            cell.font = hfont; cell.fill = hfill; cell.border = border; cell.alignment = center

    def drow(ws, r, vals):
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
            cell.alignment = Alignment(vertical='center', wrap_text=True)

    def name_parts(user):
        return user.last_name or '', user.first_name or '', ''

    def split_name(full):
        p = full.strip().split()
        if len(p) == 0: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        return p[-1], p[0], ' '.join(p[1:-1])[0] + '.'

    renewed_ids = AcademicRenewal.objects.filter(status='Approved').values_list('student_id', flat=True)

    row = 1
    if stype in ('Affirmative', 'Staff'):
        scholars = AffirmativeNSUApplication.objects.filter(status='Approved', qualified_for=stype).order_by('full_name')
        if stype == 'Staff':
            headers = ['No.', 'Last', 'First', 'M.I.', 'Sex', 'Course', 'Year Level', 'Student No.', '%', 'Scholarship Program']
        else:
            headers = ['No.', 'Last Name', 'First Name', 'Middle Name', 'Sex', 'Address', 'Course', 'Yr.', 'Scholarship Program']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            last, first, mi = split_name(app.full_name)
            if stype == 'Staff':
                drow(ws, row, [i, last, first, mi, app.gender, app.course, app.year_level, app.school_id, '100%' if app.is_nsu_staff else '75%', 'NSU Staff Scholarship'])
            else:
                drow(ws, row, [i, last, first, mi, app.gender, app.address, app.course, app.year_level, 'Affirmative Action Scholarship'])
            row += 1
    elif stype == 'Academic':
        scholars = Application.objects.filter(status='Approved', scholarship__type='Academic', student_id__in=renewed_ids).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        headers = ['No.', 'Last Name', 'First', 'Middle Name', 'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Course', 'Yr', 'GWA', '% / Type', 'Scholarship']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            p = app.student; last, first, mi = name_parts(p.user)
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else '')
            drow(ws, row, [i, last, first, mi, p.gender, p.barangay, p.municipality, p.province, p.course, p.year_level, p.gwa, pct, app.scholarship.name]); row += 1
    else:
        scholars = Application.objects.filter(status='Approved', scholarship__type=stype, student_id__in=renewed_ids).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        headers = ['No.', 'Last Name', 'First Name', 'Middle Name', 'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Course', 'Year', 'Student No.', 'Scholarship Program']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            p = app.student; last, first, mi = name_parts(p.user)
            drow(ws, row, [i, last, first, mi, p.gender, p.barangay, p.municipality, p.province, p.course, p.year_level, p.student_id, app.scholarship.name]); row += 1

    for col in ws.columns:
        ml = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(ml + 4, 40)

    buf = BytesIO(); wb.save(buf); buf.seek(0)
    filename = f'{stype}_scholars_{school_year}_{semester.replace(" ", "_")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



@_vpsea_required
def vpsea_analytics(request):
    from .models import ScholarshipRollover, SystemSettings
    import openpyxl
    from collections import defaultdict

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    ALL_TYPES = _base + [t for t in Scholarship.objects.values_list('type', flat=True).distinct() if t not in _base]

    from .models import ArchiveRecord
    all_labels = list(
        ScholarshipRollover.objects.values_list('label', flat=True)
        .distinct().order_by('-label')
    )
    # Also include labels that only exist in ArchiveRecord (import-only semesters)
    ar_labels = list(
        ArchiveRecord.objects.exclude(rollover_label='')
        .values_list('rollover_label', flat=True).distinct()
    )
    for lbl in ar_labels:
        if lbl not in all_labels:
            all_labels.append(lbl)
    all_labels = sorted(set(all_labels), reverse=True)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    all_sy_display = [(lbl, f"{SystemSettings.parse_label(lbl)['sy']} — {SystemSettings.parse_label(lbl)['semester']}") for lbl in all_labels]

    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label
    selected_parsed = SystemSettings.parse_label(selected_label)
    selected_sy = selected_parsed['sy']
    selected_semester = selected_parsed['semester']
    selected_type = request.GET.get('stype', '')

    # Scholar count per type: rollover records + ArchiveRecord imports
    from .models import ArchiveRecord
    # Scholar count per type: if selected = active semester, use live DB counts
    # otherwise use ArchiveRecord imports or ScholarshipRollover snapshot
    rollover_counts = {}
    for t in ALL_TYPES:
        if selected_label == active_label:
            # Current semester — no rollover yet, count from live approved records
            if t in ('Affirmative', 'Staff'):
                from .models import AffirmativeNSUApplication
                rollover_counts[t] = AffirmativeNSUApplication.objects.filter(
                    status='Approved', qualified_for=t
                ).count()
            else:
                rollover_counts[t] = Application.objects.filter(
                    status='Approved', scholarship__type=t
                ).count()
        else:
            # Past semester — prefer ArchiveRecord rows, fall back to rollover snapshot
            import_count = ArchiveRecord.objects.filter(scholarship_type=t, rollover_label=selected_label).count()
            if import_count:
                rollover_counts[t] = import_count
            else:
                r = ScholarshipRollover.objects.filter(scholarship_type=t, label=selected_label).first()
                rollover_counts[t] = r.scholar_count if r else 0

    def _course_counts_from_rollover(stype):
        # Current semester — pull from live approved records
        if selected_label == active_label:
            from django.db.models import Count as DCount
            if stype in ('Affirmative', 'Staff'):
                from .models import AffirmativeNSUApplication
                qs = AffirmativeNSUApplication.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('course').annotate(n=DCount('id'))
                return {r['course'] or 'Unknown': r['n'] for r in qs}
            else:
                qs = Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__course').annotate(n=DCount('id'))
                return {r['student__course'] or 'Unknown': r['n'] for r in qs}
        # Past semester — first try ArchiveRecord (imported rows)
        ar_counts = {}
        for rec in ArchiveRecord.objects.filter(scholarship_type=stype, rollover_label=selected_label).values('course'):
            c = rec['course'] or 'Unknown'
            ar_counts[c] = ar_counts.get(c, 0) + 1
        if ar_counts:
            return ar_counts
        # Fall back to rollover excel file
        r = ScholarshipRollover.objects.filter(scholarship_type=stype, label=selected_label).first()
        if not r or not r.excel_file:
            return {}
        try:
            wb = openpyxl.load_workbook(r.excel_file.path)
            ws = wb.active
            course_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'course' in str(cell.value).lower()), None)
            if course_col is None:
                return {}
            counts = defaultdict(int)
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0] is not None and course_col < len(row) and row[course_col]:
                    counts[str(row[course_col]).strip()] += 1
            return dict(counts)
        except Exception:
            return {}

    # Course distribution
    if selected_type and selected_type in ALL_TYPES:
        raw = _course_counts_from_rollover(selected_type)
    else:
        raw = defaultdict(int)
        for t in ALL_TYPES:
            for k, v in _course_counts_from_rollover(t).items():
                raw[k] += v
    course_dist = [{'course': k, 'scholars': v} for k, v in sorted(raw.items(), key=lambda x: -x[1])]

    # GWA distribution — current sem: live DB; past sem: ArchiveRecord or rollover excel
    gpa_ranges = [{'range': r, 'count': 0} for r in ['1.00-1.25', '1.26-1.50', '1.51-1.75', '1.76-2.00', '2.01-2.50']]
    if selected_label == active_label:
        buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
        for p in Application.objects.filter(
            status='Approved', scholarship__type='Academic'
        ).values('student__gwa'):
            g = p['student__gwa'] or 0
            if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
            elif g <= 1.50: buckets['1.26-1.50'] += 1
            elif g <= 1.75: buckets['1.51-1.75'] += 1
            elif g <= 2.00: buckets['1.76-2.00'] += 1
            elif g <= 2.50: buckets['2.01-2.50'] += 1
        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
    else:
        ar_academic = ArchiveRecord.objects.filter(scholarship_type='Academic', rollover_label=selected_label)
        if ar_academic.exists():
            buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
            for rec in ar_academic.values('gwa'):
                g = rec['gwa'] or 0
                if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
                elif g <= 1.50: buckets['1.26-1.50'] += 1
                elif g <= 1.75: buckets['1.51-1.75'] += 1
                elif g <= 2.00: buckets['1.76-2.00'] += 1
                elif g <= 2.50: buckets['2.01-2.50'] += 1
            gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
        else:
            acad_r = ScholarshipRollover.objects.filter(scholarship_type='Academic', label=selected_label).first()
            if acad_r and acad_r.excel_file:
                try:
                    wb = openpyxl.load_workbook(acad_r.excel_file.path)
                    ws = wb.active
                    gwa_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'gwa' in str(cell.value).lower()), None)
                    if gwa_col is not None:
                        buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            if row and row[0] is not None:
                                try:
                                    g = float(row[gwa_col]) if gwa_col < len(row) and row[gwa_col] else 0
                                    if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
                                    elif g <= 1.50: buckets['1.26-1.50'] += 1
                                    elif g <= 1.75: buckets['1.51-1.75'] += 1
                                    elif g <= 2.00: buckets['1.76-2.00'] += 1
                                    elif g <= 2.50: buckets['2.01-2.50'] += 1
                                except (ValueError, TypeError):
                                    pass
                        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
                except Exception:
                    pass

    # ── Scholars-over-time trend ──────────────────────────────────────────────
    # Build a chronological list of (label, display, total_scholars) covering
    # every known semester so the line chart spans the full history.
    # Labels use the compact format "YY-S" (e.g. "25-1") — sort numerically.
    def _label_sort_key(lbl):
        try:
            yy, s = lbl.split('-')
            return int(yy) * 10 + int(s)
        except Exception:
            return 0

    trend_labels_sorted = sorted(set(all_labels), key=_label_sort_key)

    trend_data = []
    for lbl in trend_labels_sorted:
        parsed = SystemSettings.parse_label(lbl)
        display = f"{parsed['sy']}\n{parsed['semester']}"   # two-line label for x-axis
        short   = f"{parsed['sy']} S{parsed['sy_start'] and lbl.split('-')[1] or '?'}"

        total = 0
        for t in ALL_TYPES:
            if lbl == active_label:
                if t in ('Affirmative', 'Staff'):
                    from .models import AffirmativeNSUApplication
                    total += AffirmativeNSUApplication.objects.filter(
                        status='Approved', qualified_for=t
                    ).count()
                else:
                    total += Application.objects.filter(
                        status='Approved', scholarship__type=t
                    ).count()
            else:
                # Prefer ArchiveRecord row count, fall back to rollover snapshot
                cnt = ArchiveRecord.objects.filter(
                    scholarship_type=t, rollover_label=lbl
                ).count()
                if not cnt:
                    r = ScholarshipRollover.objects.filter(
                        scholarship_type=t, label=lbl
                    ).first()
                    cnt = r.scholar_count if r else 0
                total += cnt

        # Build a per-type breakdown for the tooltip
        per_type = {}
        for t in ALL_TYPES:
            if lbl == active_label:
                if t in ('Affirmative', 'Staff'):
                    from .models import AffirmativeNSUApplication
                    c = AffirmativeNSUApplication.objects.filter(
                        status='Approved', qualified_for=t
                    ).count()
                else:
                    c = Application.objects.filter(
                        status='Approved', scholarship__type=t
                    ).count()
            else:
                c = ArchiveRecord.objects.filter(
                    scholarship_type=t, rollover_label=lbl
                ).count()
                if not c:
                    r = ScholarshipRollover.objects.filter(
                        scholarship_type=t, label=lbl
                    ).first()
                    c = r.scholar_count if r else 0
            if c:
                per_type[t] = c

        parsed_display = f"{parsed['sy']} — {parsed['semester']}"
        trend_data.append({
            'label': lbl,
            'display': parsed_display,
            'total': total,
            'per_type': per_type,
        })

    return render(request, 'vpsea/analytics.html', {
        'rollover_counts': rollover_counts,
        'all_types': ALL_TYPES,
        'course_dist': course_dist,
        'gpa_ranges': gpa_ranges,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'selected_type': selected_type,
        'selected_sy_display': f"{selected_sy} — {selected_semester}",
        'active_sy': active_label,
        'trend_data': trend_data,
    })


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
    from .models import Application, AffirmativeNSUApplication, SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    def _split(full):
        p = full.strip().split()
        if not p: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        return p[-1], p[0], p[1][0] + '.'

    def _app_row(app):
        p = app.student; u = p.user
        return {
            'last': u.last_name, 'first': u.first_name, 'mi': '',
            'sex': p.gender, 'brgy': p.barangay, 'mun': p.municipality,
            'prov': p.province, 'course': p.course, 'yr': p.year_level,
            'gwa': p.gwa,
            'pct': 'Univ. Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else ''),
            'scholarship': app.scholarship.name,
            'award': app.form_data.get('award_number', ''),
            'cong': app.form_data.get('congress_district', ''),
        }

    def _aff_row(app):
        last, first, mi = _split(app.full_name)
        return {
            'last': last, 'first': first, 'mi': mi,
            'sex': app.gender, 'brgy': app.barangay, 'mun': app.municipality,
            'prov': app.province, 'course': app.course, 'yr': app.year_level,
            'gwa': '', 'pct': '100' if app.is_nsu_staff else '75',
            'scholarship': 'NSU Staff Scholarship' if app.is_nsu_staff else 'Affirmative Action Scholarship',
            'award': '', 'cong': '', 'student_no': app.school_id,
        }

    academic_all = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))

    staff_all = list(AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).order_by('full_name'))

    affirmative_all = list(AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).order_by('full_name'))

    ched_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    ched_full = [a for a in ched_all if 'full' in (a.scholarship.name or '').lower()]
    ched_half = [a for a in ched_all if a not in ched_full]
    if not ched_full and not ched_half:
        ched_full = list(ched_all)

    dost_all = list(Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    gsis_all = list(Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    tdp_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    tes_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TES'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    coscho_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CoScho'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    sports_all = list(Application.objects.filter(
        status='Approved', scholarship__type='Sports'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))

    def split_gender(lst, is_aff=False):
        if is_aff:
            f = [_aff_row(a) for a in lst if a.gender and a.gender.upper() in ('F','FEMALE')]
            m = [_aff_row(a) for a in lst if not (a.gender and a.gender.upper() in ('F','FEMALE'))]
        else:
            f = [_app_row(a) for a in lst if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
            m = [_app_row(a) for a in lst if not (a.student.gender and a.student.gender.upper() in ('F','FEMALE'))]
        return f, m

    acad_f, acad_m     = split_gender(academic_all)
    aff_f,  aff_m      = split_gender(affirmative_all, is_aff=True)
    ched_full_f, ched_full_m = split_gender(ched_full)
    ched_half_f, ched_half_m = split_gender(ched_half)
    dost_f, dost_m     = split_gender(dost_all)
    gsis_f, gsis_m     = split_gender(gsis_all)
    tdp_f,  tdp_m      = split_gender(tdp_all)
    tes_f,  tes_m      = split_gender(tes_all)
    coscho_f, coscho_m = split_gender(coscho_all)
    sports_f, sports_m = split_gender(sports_all)
    staff_rows         = [_aff_row(a) for a in staff_all]

    hdrs_academic  = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','COURSE','YR.','GWA','%','SCHOLARSHIP PROGRAM']
    hdrs_staff     = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','COURSE','YEAR LEVEL','STUDENT NO.','%','SCHOLARSHIP PROGRAM']
    hdrs_standard  = ['NO.','AWARD NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']
    hdrs_no_award  = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    sections = [
        ('ACADEMIC (@)',          hdrs_academic,  acad_f,      acad_m,      True,  'academic'),
        ('NSU STAFF (@)',         hdrs_staff,     staff_rows,  [],          False, 'staff'),
        ('AFFIRMATIVE (*)',       hdrs_standard,  aff_f,       aff_m,       True,  'affirmative'),
        ('CHED FULL MERIT (*)',   hdrs_standard,  ched_full_f, ched_full_m, True,  'ched_full'),
        ('CHED HALF MERIT (*)',   hdrs_standard,  ched_half_f, ched_half_m, True,  'ched_half'),
        ('DOST (*)',              hdrs_standard,  dost_f,      dost_m,      True,  'dost'),
        ('GSIS (*)',              hdrs_no_award,  gsis_f,      gsis_m,      True,  'gsis'),
        ('TDP (*)',               hdrs_standard,  tdp_f,       tdp_m,       True,  'tdp'),
        ('TES — TERTIARY EDUCATION SUBSIDY (*)', hdrs_standard, tes_f, tes_m, True, 'tes'),
        ('CoScho — COCONUT FARMERS SCHOLAR (*)', hdrs_no_award, coscho_f, coscho_m, True, 'coscho'),
        ('SPORTS (*)',            hdrs_no_award,  sports_f,    sports_m,    True,  'sports'),
    ]

    return render(request, 'vpsea/reports.html', {
        'semester': semester, 'ay': ay,
        'sections': sections,
    })


@_vpsea_required
@xframe_options_exempt
def vpsea_report_preview_pdf(request):
    from reportlab.lib.pagesizes import landscape, legal
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    from django.http import HttpResponse
    from .models import Application, AffirmativeNSUApplication, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(legal),
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.7*inch, bottomMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Normal'], fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=2)
    sub_style   = ParagraphStyle('sub',   parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=2)
    sec_style   = ParagraphStyle('sec',   parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=4, spaceBefore=8)
    lbl_style   = ParagraphStyle('lbl',   parent=styles['Normal'], fontSize=9,  alignment=TA_LEFT,   fontName='Helvetica-Bold')
    cell_style  = ParagraphStyle('cell',  parent=styles['Normal'], fontSize=7)

    HDR_BG  = colors.HexColor('#D9E1F2')
    SEC_BG  = colors.HexColor('#BDD7EE')
    TITLE_BG = colors.HexColor('#1F4E79')
    TITLE_FG = colors.white

    def _split(full):
        p = full.strip().split()
        if not p: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        mi = p[1][0] + '.' if len(p) > 2 else ''
        return p[-1], p[0], mi

    def _addr(profile):
        return profile.barangay, profile.municipality, profile.province

    def make_table(headers, rows):
        data = [headers] + (rows if rows else [['—'] * len(headers)])
        col_w = (landscape(legal)[0] - inch) / len(headers)
        t = Table(data, colWidths=[col_w] * len(headers), repeatRows=1)
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HDR_BG),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 7),
            ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('GRID',       (0,0), (-1,-1), 0.4, colors.black),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F7FF')]),
        ])
        t.setStyle(style)
        return t

    story = []
    story.append(Paragraph('Republic of the Philippines', sub_style))
    story.append(Paragraph('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', title_style))
    story.append(Paragraph(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', title_style))
    story.append(Spacer(1, 8))

    # ── ACADEMIC ──────────────────────────────────────────────────────────────
    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user').order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    males_a   = [a for a in academic if a not in females_a]

    hdrs_acad = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','COURSE','YR.','GWA','%','SCHOLARSHIP']

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            pct = 'Univ. Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else '')
            rows.append([i, u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    story.append(Paragraph(f'ACADEMIC (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_acad, acad_rows(females_a)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_acad, acad_rows(males_a)))
    story.append(Spacer(1, 10))

    # ── NSU STAFF ─────────────────────────────────────────────────────────────
    staff = list(AffirmativeNSUApplication.objects.filter(status='Approved', qualified_for='Staff').order_by('full_name'))
    hdrs_staff = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','COURSE','YEAR LEVEL','STUDENT NO.','%','SCHOLARSHIP PROGRAM']
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split(app.full_name)
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.school_id or '', '100' if app.is_nsu_staff else '75', 'NSU STAFF'])
    story.append(Paragraph(f'NSU STAFF (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(make_table(hdrs_staff, staff_rows))
    story.append(Spacer(1, 10))

    # ── AFFIRMATIVE ───────────────────────────────────────────────────────────
    affirmative = list(AffirmativeNSUApplication.objects.filter(status='Approved', qualified_for='Affirmative').order_by('full_name'))
    aff_f = [a for a in affirmative if a.gender and a.gender.upper() in ('F','FEMALE')]
    aff_m = [a for a in affirmative if a not in aff_f]
    hdrs_aff = ['NO.','AWARD NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split(app.full_name)
            rows.append([i, '', last, first, mi, app.gender or '', app.barangay, app.municipality, app.province, '', app.course, app.year_level, 'Affirmative Action'])
        return rows

    story.append(Paragraph(f'AN WARAY (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_aff, aff_rows(aff_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_aff, aff_rows(aff_m)))
    story.append(Spacer(1, 10))

    # ── CHED ──────────────────────────────────────────────────────────────────
    ched_all = list(Application.objects.filter(status='Approved', scholarship__type='CHED').select_related('student__user','scholarship').order_by('student__user__last_name'))
    ched_full = [a for a in ched_all if 'full' in (a.scholarship.name or '').lower()]
    ched_half = [a for a in ched_all if a not in ched_full]
    if not ched_full and not ched_half:
        ched_full = list(ched_all)
    hdrs_ched = ['NO.','AWARD NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            rows.append([i, app.form_data.get('award_number',''), u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, app.form_data.get('congress_district',''), p.course, p.year_level, app.scholarship.name])
        return rows

    for title, block in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        story.append(Paragraph(f'{title} — {semester} SY: {ay}', sec_style))
        bf = [a for a in block if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
        bm = [a for a in block if a not in bf]
        story.append(Paragraph('FEMALE', lbl_style))
        story.append(make_table(hdrs_ched, ched_rows(bf)))
        story.append(Paragraph('MALE', lbl_style))
        story.append(make_table(hdrs_ched, ched_rows(bm)))
        story.append(Spacer(1, 10))

    # ── DOST ──────────────────────────────────────────────────────────────────
    dost_all = list(Application.objects.filter(status='Approved', scholarship__type='DOST').select_related('student__user','scholarship').order_by('student__user__last_name'))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    story.append(Paragraph(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(dost_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(dost_m)))
    story.append(Spacer(1, 10))

    # ── GSIS ──────────────────────────────────────────────────────────────────
    gsis_all = list(Application.objects.filter(status='Approved', scholarship__type='GSIS').select_related('student__user','scholarship').order_by('student__user__last_name'))
    hdrs_gsis = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            rows.append([i, u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, app.form_data.get('congress_district',''), p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    story.append(Paragraph(f'GSIS (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_gsis, gsis_rows(gsis_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_gsis, gsis_rows(gsis_m)))
    story.append(Spacer(1, 10))

    # ── TDP/TES ───────────────────────────────────────────────────────────────
    tes_all = list(Application.objects.filter(status='Approved', scholarship__type='TDP').select_related('student__user','scholarship').order_by('student__user__last_name'))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    story.append(Paragraph(f'TERTIARY EDUCATION SUBSIDY - TES (*) — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(tes_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(tes_m)))

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="masterlist_preview.pdf"'
    return response


@_vpsea_required
def vpsea_report_download(request):
    from docxtpl import DocxTemplate
    from io import BytesIO
    from django.http import HttpResponse
    import os
    from .models import Application, AffirmativeNSUApplication, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    def _split(full):
        p = full.strip().split()
        if not p: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        return p[-1], p[0], p[1][0] + '.'

    def _app_row(app):
        p = app.student; u = p.user
        return {
            'last': u.last_name, 'first': u.first_name, 'mi': '',
            'sex': p.gender or '', 'brgy': p.barangay, 'mun': p.municipality,
            'prov': p.province, 'course': p.course, 'yr': p.year_level,
            'gwa': p.gwa,
            'pct': 'Univ. Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else ''),
            'scholarship': app.scholarship.name,
            'award': app.form_data.get('award_number', ''),
            'cong': app.form_data.get('congress_district', ''),
            'student_no': p.student_id,
        }

    def _aff_row(app):
        last, first, mi = _split(app.full_name)
        return {
            'last': last, 'first': first, 'mi': mi,
            'sex': app.gender or '', 'brgy': app.barangay, 'mun': app.municipality,
            'prov': app.province, 'course': app.course, 'yr': app.year_level,
            'gwa': '', 'pct': '100' if app.is_nsu_staff else '75',
            'scholarship': 'NSU Staff Scholarship' if app.is_nsu_staff else 'Affirmative Action Scholarship',
            'award': '', 'cong': '', 'student_no': app.school_id or '',
        }

    def split_gender(lst, is_aff=False):
        fn = _aff_row if is_aff else _app_row
        gf = lambda a: (a.gender if is_aff else a.student.gender) or ''
        female = [fn(a) for a in lst if gf(a).upper() in ('F', 'FEMALE')]
        male   = [fn(a) for a in lst if gf(a).upper() not in ('F', 'FEMALE')]
        return female, male

    academic   = list(Application.objects.filter(status='Approved', scholarship__type='Academic').select_related('student__user','scholarship').order_by('student__user__last_name'))
    staff_qs   = list(AffirmativeNSUApplication.objects.filter(status='Approved', qualified_for='Staff').order_by('full_name'))
    aff_qs     = list(AffirmativeNSUApplication.objects.filter(status='Approved', qualified_for='Affirmative').order_by('full_name'))
    ched_all   = list(Application.objects.filter(status='Approved', scholarship__type='CHED').select_related('student__user','scholarship').order_by('student__user__last_name'))
    ched_full  = [a for a in ched_all if 'full' in (a.scholarship.name or '').lower()] or ched_all
    ched_half  = [a for a in ched_all if a not in ched_full]
    dost_qs    = list(Application.objects.filter(status='Approved', scholarship__type='DOST').select_related('student__user','scholarship').order_by('student__user__last_name'))
    gsis_qs    = list(Application.objects.filter(status='Approved', scholarship__type='GSIS').select_related('student__user','scholarship').order_by('student__user__last_name'))
    tdp_qs     = list(Application.objects.filter(status='Approved', scholarship__type='TDP').select_related('student__user','scholarship').order_by('student__user__last_name'))
    tes_qs     = list(Application.objects.filter(status='Approved', scholarship__type='TES').select_related('student__user','scholarship').order_by('student__user__last_name'))
    coscho_qs  = list(Application.objects.filter(status='Approved', scholarship__type='CoScho').select_related('student__user','scholarship').order_by('student__user__last_name'))
    sports_qs  = list(Application.objects.filter(status='Approved', scholarship__type='Sports').select_related('student__user','scholarship').order_by('student__user__last_name'))

    acad_f,      acad_m      = split_gender(academic)
    aff_f,       aff_m       = split_gender(aff_qs,    is_aff=True)
    ched_full_f, ched_full_m = split_gender(ched_full)
    ched_half_f, ched_half_m = split_gender(ched_half)
    dost_f,      dost_m      = split_gender(dost_qs)
    gsis_f,      gsis_m      = split_gender(gsis_qs)
    tdp_f,       tdp_m       = split_gender(tdp_qs)
    tes_f,       tes_m       = split_gender(tes_qs)
    coscho_f,    coscho_m    = split_gender(coscho_qs)
    sports_f,    sports_m    = split_gender(sports_qs)

    context = {
        'semester': semester, 'ay': ay,
        'academic_female': acad_f,      'academic_male': acad_m,
        'staff':           [_aff_row(a) for a in staff_qs],
        'affirmative_female': aff_f,    'affirmative_male': aff_m,
        'ched_full_female': ched_full_f,'ched_full_male': ched_full_m,
        'ched_half_female': ched_half_f,'ched_half_male': ched_half_m,
        'dost_female': dost_f,          'dost_male': dost_m,
        'gsis_female': gsis_f,          'gsis_male': gsis_m,
        'tdp_female':  tdp_f,           'tdp_male':  tdp_m,
        'tes_female':  tes_f,           'tes_male':  tes_m,
        'coscho_female': coscho_f,      'coscho_male': coscho_m,
        'sports_female': sports_f,      'sports_male': sports_m,
    }

    tpl_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'docx', 'masterlist_template.docx')
    tpl = DocxTemplate(tpl_path)
    tpl.render(context)

    buffer = BytesIO()
    tpl.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{ay.replace("-","_")}_{semester.replace(" ","_")}.docx'
    response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

    # — Page layout: landscape, legal-ish wide ————————————————
    section = doc.sections[0]
    section.orientation = 1  # LANDSCAPE
    section.page_width = Inches(13.0)
    section.page_height = Inches(8.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.4)

    # — Helpers ————————————————————————————————
    def add_heading(text, bold=False, size=11, align=WD_ALIGN_PARAGRAPH.CENTER):
        p = doc.add_paragraph()
        p.alignment = align
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        return p

    def add_blank():
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

    def set_cell_border(cell):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        for edge in ('top', 'left', 'bottom', 'right'):
            tag = OxmlElement(f'w:{edge}')
            tag.set(qn('w:val'), 'single')
            tag.set(qn('w:sz'), '4')
            tag.set(qn('w:space'), '0')
            tag.set(qn('w:color'), '000000')
            tcPr.append(tag)

    def style_header_row(row, bold=True, bg='D9E1F2'):
        for cell in row.cells:
            set_cell_border(cell)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), bg)
            tcPr.append(shd)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.bold = bold
                    run.font.size = Pt(8)

    def style_data_row(row):
        for cell in row.cells:
            set_cell_border(cell)
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(8)

    def add_scholar_table(headers, sub_headers, rows_data):
        ncols = len(headers)
        table = doc.add_table(rows=0, cols=ncols)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Header row 1
        hrow1 = table.add_row()
        for i, h in enumerate(headers):
            hrow1.cells[i].text = h
        style_header_row(hrow1)
        # Header row 2 (sub-headers)
        if sub_headers:
            hrow2 = table.add_row()
            for i, h in enumerate(sub_headers):
                hrow2.cells[i].text = h
            style_header_row(hrow2)
        # Data rows
        for row_vals in rows_data:
            drow = table.add_row()
            for i, val in enumerate(row_vals):
                drow.cells[i].text = str(val) if val is not None else ''
            style_data_row(drow)
        return table

    def _split_name(full_name):
        parts = full_name.strip().split()
        if len(parts) == 0: return ('', '', '')
        if len(parts) == 1: return (parts[0], '', '')
        if len(parts) == 2: return (parts[-1], parts[0], '')
        last = parts[-1]
        first = parts[0]
        middle = ' '.join(parts[1:-1])
        mi = middle[0] + '.' if middle else ''
        return (last, first, mi)

    def _name_parts(user):
        return (user.last_name or '', user.first_name or '', '')

    # — Document header ————————————————————————————
    add_heading('Republic of the Philippines', bold=False, size=11)
    add_heading('BILIRAN PROVINCE STATE UNIVERSITY', bold=True, size=11)
    add_heading('Naval, Biliran', bold=False, size=11)
    add_blank()
    add_heading(f'LIST OF SCHOLARS FOR {sem_label}', bold=True, size=16)
    add_blank()

    # — ACADEMIC ———————————————————————————————
    academic = Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    females = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    males   = [a for a in academic if a not in females]

    add_heading('ACADEMIC (@)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_acad = ['NO.', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']
    sub_acad     = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholars' if p.gwa <= 1.50 else '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    p_label = doc.add_paragraph('FEMALE')
    p_label.paragraph_format.space_before = Pt(0)
    p_label.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_acad, sub_acad, acad_rows(females))
    add_blank()
    p_label2 = doc.add_paragraph('MALE')
    p_label2.paragraph_format.space_before = Pt(0)
    p_label2.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_acad, sub_acad, acad_rows(males))
    add_blank()

    # — NSU STAFF ———————————————————————————————
    staff = AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).order_by('full_name')

    add_heading('NSU STAFF (@)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_staff = ['NO. ', 'NAME ', 'NAME ', 'NAME ', 'SEX', 'COURSE ', 'YEAR LEVEL ', 'STUDENT ', '% ', 'SCHOLARSHIP ']
    sub_staff     = ['NO. ', 'LAST NAME ', 'FIRST NAME ', 'M.I. ', 'SEX', 'COURSE ', 'YEAR LEVEL ', 'NUMBER ', '% ', 'PROGRAM ']
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split_name(app.full_name)
        pct = '100' if app.is_nsu_staff else '75'
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.school_id or '', pct, 'NSU STAFF SCHOLARSHIP'])
    add_scholar_table(headers_staff, sub_staff, staff_rows)
    add_blank()

    # — AFFIRMATIVE (AN WARAY) ————————————————————————
    affirmative = AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).order_by('full_name')

    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    aff_males   = [a for a in affirmative if a not in aff_females]

    add_heading('AN WARAY (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_aff = ['NO.', 'AWARD NUMBER', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_aff     = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split_name(app.full_name)
            addr = app.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            rows.append([i, '', last, first, mi, app.gender or '', brgy, mun, prov, '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        return rows

    p_f = doc.add_paragraph('FEMALE')
    p_f.paragraph_format.space_before = Pt(0)
    p_f.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_aff, sub_aff, aff_rows(aff_females))
    add_blank()
    p_m = doc.add_paragraph('MALE')
    p_m.paragraph_format.space_before = Pt(0)
    p_m.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_aff, sub_aff, aff_rows(aff_males))
    add_blank()

    # — CHED (FULL MERIT / HALF MERIT) ————————————————————
    ched_all = Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    ched_full = [a for a in ched_all if 'full' in (a.scholarship.name or '').lower()]
    ched_half = [a for a in ched_all if a not in ched_full]
    if not ched_full and not ched_half:
        ched_full = list(ched_all)

    headers_ched = ['NO.', 'AWARD NUMBER', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_ched     = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            award = app.form_data.get('award_number', '')
            cong  = app.form_data.get('congress_district', '')
            rows.append([i, award, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    for block_title, block_apps in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        add_heading(block_title, bold=True, size=11)
        add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
        add_heading(f'{semester} SY: {ay}', bold=False, size=11)
        add_blank()
        ched_f = [a for a in block_apps if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
        ched_m = [a for a in block_apps if a not in ched_f]
        pf = doc.add_paragraph('FEMALE')
        pf.paragraph_format.space_before = Pt(0)
        pf.paragraph_format.space_after = Pt(0)
        add_scholar_table(headers_ched, sub_ched, ched_rows(ched_f))
        add_blank()
        pm = doc.add_paragraph('MALE')
        pm.paragraph_format.space_before = Pt(0)
        pm.paragraph_format.space_after = Pt(0)
        add_scholar_table(headers_ched, sub_ched, ched_rows(ched_m))
        add_blank()

    # — DOST —————————————————————————————————
    dost_all = Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('DOST (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(dost_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(dost_m))
    add_blank()

    # — GSIS —————————————————————————————————
    gsis_all = Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('GSIS (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_gsis = ['NO.', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_gsis     = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            cong = app.form_data.get('congress_district', '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_gsis, sub_gsis, gsis_rows(gsis_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_gsis, sub_gsis, gsis_rows(gsis_m))
    add_blank()

    # — TES (TDP) ———————————————————————————————
    tes_all = Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('TERTIARY EDUCATION SUBSIDY -TES (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(tes_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(tes_m))
    add_blank()

    # — Page footer with signatories (appears on every page) —————————
    footer = section.footer
    footer.is_linked_to_previous = False
    # Clear default empty paragraph
    for para in footer.paragraphs:
        p_elem = para._p
        p_elem.getparent().remove(p_elem)

    footer_table = footer.add_table(rows=2, cols=4, width=Inches(12.0))
    footer_table.style = 'Table Grid'

    sig_labels = [
        ('Prepared by:', 'Noted:', 'Recommending approval:', 'Approved:'),
        (
            'MARICEL S. SAULAN\nScholarship in charge',
            'NORMA M. DUALLO, Ph.D.TM\nSDSO Director',
            'ERWIN G. SALVATIERRA, Ph. D.\nVP for Extension Services,\nStudent and External Affairs',
            'VICTOR C. CAÃ‘EZO, JR., Ed. D.\nUniversity President',
        ),
    ]
    for ri, row_vals in enumerate(sig_labels):
        for ci, val in enumerate(row_vals):
            cell = footer_table.rows[ri].cells[ci]
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # remove cell borders
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            for edge in ('top', 'left', 'bottom', 'right'):
                tag = OxmlElement(f'w:{edge}')
                tag.set(qn('w:val'), 'none')
                tcPr.append(tag)
            if ri == 0:
                run = para.add_run(val)
                run.bold = True
                run.font.size = Pt(8)
            else:
                lines = val.split('\n')
                r1 = para.add_run(lines[0])
                r1.bold = True
                r1.font.size = Pt(8)
                for line in lines[1:]:
                    para.add_run('\n' + line).font.size = Pt(8)

    # — Save & return —————————————————————————————
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{ay.replace("-","_")}_{semester.replace(" ","_")}.docx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_vpsea_required
def vpsea_report_download_excel(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from django.http import HttpResponse
    from .models import Application, AffirmativeNSUApplication, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Scholars'

    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    header_font = Font(bold=True, size=9)
    header_fill = PatternFill('solid', fgColor='D9E1F2')
    section_fill = PatternFill('solid', fgColor='BDD7EE')
    title_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=11, color='FFFFFF')

    current_row = [1]  # mutable so nested helpers can update it

    def write_title(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        cell.border = border
        ws.row_dimensions[r].height = 18
        current_row[0] += 1

    def write_section(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=10)
        cell.fill = section_fill
        cell.alignment = center
        cell.border = border
        current_row[0] += 1

    def write_gender_label(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal='left', vertical='center')
        current_row[0] += 1

    def write_headers(headers):
        r = current_row[0]
        for ci, h in enumerate(headers, 1):
            cell = ws.cell(row=r, column=ci, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center
        current_row[0] += 1

    def write_rows(rows_data):
        for row_vals in rows_data:
            r = current_row[0]
            for ci, val in enumerate(row_vals, 1):
                cell = ws.cell(row=r, column=ci, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                cell.font = Font(size=9)
            current_row[0] += 1

    def blank_row():
        current_row[0] += 1

    def _split_name(full_name):
        parts = full_name.strip().split()
        if len(parts) == 0: return ('', '', '')
        if len(parts) == 1: return (parts[0], '', '')
        if len(parts) == 2: return (parts[-1], parts[0], '')
        last = parts[-1]; first = parts[0]
        middle = ' '.join(parts[1:-1])
        return (last, first, middle[0] + '.' if middle else '')

    def _name_parts(user):
        return (user.last_name or '', user.first_name or '', '')

    def addr_parts(addr):
        parts = [x.strip() for x in (addr or '').split(',')]
        return (parts[0] if len(parts) > 0 else '',
                parts[1] if len(parts) > 1 else '',
                parts[2] if len(parts) > 2 else '')

    MAX_COLS = 13  # widest table

    # — Document title ————————————————————————————
    write_title('Republic of the Philippines', MAX_COLS)
    write_title('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', MAX_COLS)
    write_title(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', MAX_COLS)
    blank_row()

    # — ACADEMIC ———————————————————————————————
    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    males_a   = [a for a in academic if a not in females_a]

    headers_acad = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'ACADEMIC (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_acad))

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholars' if p.gwa <= 1.50 else '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    write_gender_label('FEMALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(females_a))
    write_gender_label('MALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(males_a))
    blank_row()

    # — NSU STAFF ———————————————————————————————
    staff = list(AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).order_by('full_name'))
    headers_staff = ['NO.', 'LAST NAME', 'FIRST NAME', 'M.I.', 'SEX', 'COURSE', 'YEAR LEVEL', 'STUDENT NUMBER', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'NSU STAFF (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_staff))
    write_headers(headers_staff)
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split_name(app.full_name)
        pct = '100' if app.is_nsu_staff else '75'
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.school_id or '', pct, 'NSU STAFF SCHOLARSHIP'])
    write_rows(staff_rows)
    blank_row()

    # — AFFIRMATIVE ——————————————————————————————
    affirmative = list(AffirmativeNSUApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).order_by('full_name'))
    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    aff_males   = [a for a in affirmative if a not in aff_females]
    headers_aff = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'AN WARAY (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_aff))

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split_name(app.full_name)
            brgy, mun, prov = addr_parts(app.address)
            rows.append([i, '', last, first, mi, app.gender or '', brgy, mun, prov, '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        return rows

    write_gender_label('FEMALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_females))
    write_gender_label('MALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_males))
    blank_row()

    # — CHED —————————————————————————————————
    ched_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    ched_full = [a for a in ched_all if 'full' in (a.scholarship.name or '').lower()]
    ched_half = [a for a in ched_all if a not in ched_full]
    if not ched_full and not ched_half:
        ched_full = list(ched_all)
    headers_ched = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            award = app.form_data.get('award_number', '')
            cong  = app.form_data.get('congress_district', '')
            rows.append([i, award, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    for block_title, block_apps in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        write_section(f'{block_title} SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
        bf = [a for a in block_apps if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
        bm = [a for a in block_apps if a not in bf]
        write_gender_label('FEMALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bf))
        write_gender_label('MALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bm))
        blank_row()

    # — DOST —————————————————————————————————
    dost_all = list(Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    write_section(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_m))
    blank_row()

    # — GSIS —————————————————————————————————
    gsis_all = list(Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    headers_gsis = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'GSIS (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_gsis))

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            cong = app.form_data.get('congress_district', '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    write_gender_label('FEMALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_f))
    write_gender_label('MALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_m))
    blank_row()

    # — TES (TDP) ———————————————————————————————
    tes_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    write_section(f'TERTIARY EDUCATION SUBSIDY -TES (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_m))
    blank_row()
    blank_row()

    # — Page footer with signatories (appears on every printed page) —————
    footer_text = (
        'Prepared by:\t\t\t\t\tNoted:\t\t\t\t\t\tRecommending approval:\t\t\t\t\t\tApproved:\n'
        'MARICEL S. SAULAN\t\t\t\tNORMA M. DUALLO, Ph.D.TM\t\t\tERWIN G. SALVATIERRA, Ph. D.\t\t\tVICTOR C. CAÃ‘EZO, JR., Ed. D.\n'
        'Scholarship in charge\t\t\t\tSDSO Director\t\t\t\t\tVP for Extension Services, Student and External Affairs\t\tUniversity President'
    )
    ws.oddFooter.center.text = footer_text
    ws.oddFooter.center.size = 8
    ws.evenFooter.center.text = footer_text
    ws.evenFooter.center.size = 8

    # — Auto-fit columns (skip MergedCell objects) ——————————————
    from openpyxl.utils import get_column_letter
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 3, 35)

    # — Save & return —————————————————————————————
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{ay.replace("-","_")}_{semester.replace(" ","_")}.xlsx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_vpsea_required
def vpsea_students(request):
    from .models import StudentProfile, Application, Scholarship, SystemSettings
    from django.db.models import Q

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    current_sy = settings_obj.academic_year      # e.g. '2025-2026'
    current_sem = settings_obj.active_semester   # e.g. '1st Semester'

    q = request.GET.get('q', '').strip()
    stype = request.GET.get('stype', '').strip()

    scholarship_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']

    # Base: only students with an Approved application in the current active SY
    try:
        start_year = int(current_sy.split('-')[0])
    except (ValueError, IndexError):
        start_year = None

    students = StudentProfile.objects.select_related('user').order_by('user__last_name')
    if start_year:
        students = students.filter(
            applications__status='Approved',
            applications__submitted_at__year=start_year,
        ).distinct()
    else:
        students = students.filter(applications__status='Approved').distinct()

    if q:
        students = students.filter(
            Q(user__last_name__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(student_id__icontains=q)
        )

    if stype:
        if stype in ('Affirmative', 'Staff'):
            from .models import AffirmativeNSUApplication
            aff_emails = AffirmativeNSUApplication.objects.filter(
                qualified_for=stype, status='Approved'
            ).values_list('email', flat=True)
            students = students.filter(user__email__in=aff_emails)
        else:
            students = students.filter(
                applications__scholarship__type=stype
            ).distinct()

    return render(request, 'vpsea/students.html', {
        'students': students,
        'q': q,
        'stype': stype,
        'scholarship_types': scholarship_types,
        'current_sy': current_sy,
        'current_sem': current_sem,
    })


@_vpsea_required
def vpsea_student_add(request):
    from .models import StudentProfile, Scholarship, Application, ApplicationDocument
    errors = []
    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        email = p.get('email', '').strip()
        student_id = p.get('student_id', '').strip()
        if User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        if StudentProfile.objects.filter(student_id=student_id).exists():
            errors.append('Student ID already registered.')
        if not errors:
            user = User.objects.create_user(
                username=email, email=email,
                password=p.get('password') or student_id,
                first_name=p.get('first_name', ''),
                last_name=p.get('last_name', ''),
                role='student',
            )
            profile = StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1)),
                gwa=float(p.get('gwa', 0) or 0),
                contact_number=p.get('contact_number', ''),
                barangay=p.get('barangay', ''),
                municipality=p.get('municipality', ''),
                province=p.get('province', ''),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
                family_income=float(p.get('family_income', 0) or 0),
            )
            # Build form_data from all extra fields
            form_data = {
                k: v for k, v in p.items()
                if k not in ('csrfmiddlewaretoken', 'password', 'first_name', 'last_name',
                             'email', 'student_id', 'course', 'year_level', 'gwa',
                             'contact_number', 'barangay', 'municipality', 'province',
                             'date_of_birth', 'gender', 'family_income')
            }
            scholarship = Scholarship.objects.filter(type='Academic').first()
            if scholarship:
                app = Application.objects.create(
                    student=profile, scholarship=scholarship,
                    status='Approved', form_data=form_data,
                )
                doc_fields = ['doc_certificate_of_grades', 'doc_certificate_of_enrollment',
                              'doc_prospectus', 'doc_id_photo', 'doc_application_form']
                for field in doc_fields:
                    uploaded = f.get(field)
                    if uploaded:
                        ApplicationDocument.objects.create(
                            application=app, name=field.replace('doc_', '').replace('_', ' ').title(),
                            file=uploaded,
                        )
            return redirect('/vpsea/students/?added=1')
    import json

    return render(request, 'vpsea/student_form.html', {'errors': errors, 'action': 'Add', 'form_data': request.POST, 'doc_list': _doc_list(),

        'bipsu_schools': BIPSU_SCHOOLS, 'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'v_first_name': request.POST.get('first_name', ''),
        'v_last_name': request.POST.get('last_name', ''),
        'v_email': request.POST.get('email', ''),
        'v_student_id': request.POST.get('student_id', ''),
        'v_course': request.POST.get('course', ''),
        'v_year_level': request.POST.get('year_level', '1'),
        'v_gwa': request.POST.get('gwa', ''),
        'v_gender': request.POST.get('gender', ''),
        'v_date_of_birth': request.POST.get('date_of_birth', ''),
        'v_contact_number': request.POST.get('contact_number', ''),
        'v_barangay': request.POST.get('barangay', ''),
        'v_municipality': request.POST.get('municipality', ''),
        'v_province': request.POST.get('province', ''),
        'v_family_income': request.POST.get('family_income', ''),
        'v_elementary': request.POST.get('elementary', ''),
        'v_highschool': request.POST.get('highschool', ''),
        'v_last_school': request.POST.get('last_school', ''),
        'v_father_name': request.POST.get('father_name', ''),
        'v_father_occupation': request.POST.get('father_occupation', ''),
        'v_mother_name': request.POST.get('mother_name', ''),
        'v_mother_occupation': request.POST.get('mother_occupation', ''),
        'v_semester': request.POST.get('semester', '1st Semester'),
        'v_school_year': request.POST.get('school_year', '2025-2026'),
    })


@_vpsea_required
def vpsea_student_edit(request, pk):
    from .models import StudentProfile, Application, ApplicationDocument
    try:
        profile = StudentProfile.objects.select_related('user').get(pk=pk)
    except StudentProfile.DoesNotExist:
        return redirect('/vpsea/students/')

    # Get the latest Academic application for this student (for form_data + documents)
    app = Application.objects.filter(
        student=profile, scholarship__type='Academic'
    ).prefetch_related('documents').order_by('-submitted_at').first()

    errors = []
    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        u = profile.user
        new_email = p.get('email', '').strip()
        if new_email != u.email and User.objects.filter(email=new_email).exists():
            errors.append('Email already in use by another account.')
        new_sid = p.get('student_id', '').strip()
        if new_sid != profile.student_id and StudentProfile.objects.filter(student_id=new_sid).exists():
            errors.append('Student ID already in use.')
        if not errors:
            u.first_name = p.get('first_name', '')
            u.last_name = p.get('last_name', '')
            u.email = new_email
            u.username = new_email
            if p.get('password'):
                u.set_password(p.get('password'))
            u.save()
            profile.student_id = new_sid
            profile.course = p.get('course', '')
            profile.year_level = int(p.get('year_level', 1))
            profile.gwa = float(p.get('gwa', 0) or 0)
            profile.contact_number = p.get('contact_number', '')
            profile.barangay = p.get('barangay', '')
            profile.municipality = p.get('municipality', '')
            profile.province = p.get('province', '')
            profile.date_of_birth = p.get('date_of_birth') or None
            profile.gender = p.get('gender', '')
            profile.family_income = float(p.get('family_income', 0) or 0)
            profile.save()
            # Update form_data on the application
            if app:
                form_data = dict(app.form_data)
                for k, v in p.items():
                    if k not in ('csrfmiddlewaretoken', 'password', 'first_name', 'last_name',
                                 'email', 'student_id', 'course', 'year_level', 'gwa',
                                 'contact_number', 'barangay', 'municipality', 'province',
                                 'date_of_birth', 'gender', 'family_income'):
                        form_data[k] = v
                app.form_data = form_data
                app.save()
                # Replace documents if new files uploaded
                doc_fields = ['doc_certificate_of_grades', 'doc_certificate_of_enrollment',
                              'doc_prospectus', 'doc_id_photo', 'doc_application_form']
                for field in doc_fields:
                    uploaded = f.get(field)
                    if uploaded:
                        label = field.replace('doc_', '').replace('_', ' ').title()
                        app.documents.filter(name=label).delete()
                        ApplicationDocument.objects.create(
                            application=app, name=label, file=uploaded,
                        )
            return redirect('/vpsea/students/?edited=1')
    fd = request.POST if request.method == 'POST' else {}
    afd = (app.form_data or {}) if app else {}
    return render(request, 'vpsea/student_form.html', {
        'errors': errors, 'action': 'Edit',
        'profile': profile, 'app': app,
        'form_data': fd,
        'doc_list': _doc_list(),
        'v_first_name': fd.get('first_name', profile.user.first_name),
        'v_last_name': fd.get('last_name', profile.user.last_name),
        'v_email': fd.get('email', profile.user.email),
        'v_student_id': fd.get('student_id', profile.student_id),
        'v_course': fd.get('course', profile.course),
        'v_year_level': fd.get('year_level', str(profile.year_level)),
        'v_gwa': fd.get('gwa', str(profile.gwa)),
        'v_gender': fd.get('gender', profile.gender),
        'v_date_of_birth': fd.get('date_of_birth', profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else ''),
        'v_contact_number': fd.get('contact_number', profile.contact_number),
        'v_barangay': fd.get('barangay', profile.barangay),

        'v_municipality': fd.get('municipality', profile.municipality),

        'v_province': fd.get('province', profile.province),
        'v_family_income': fd.get('family_income', str(profile.family_income)),
        'v_elementary': fd.get('elementary', afd.get('elementary', '')),
        'v_highschool': fd.get('highschool', afd.get('highschool', '')),
        'v_last_school': fd.get('last_school', afd.get('last_school', '')),
        'v_father_name': fd.get('father_name', afd.get('father_name', '')),
        'v_father_occupation': fd.get('father_occupation', afd.get('father_occupation', '')),
        'v_mother_name': fd.get('mother_name', afd.get('mother_name', '')),
        'v_mother_occupation': fd.get('mother_occupation', afd.get('mother_occupation', '')),
        'v_semester': fd.get('semester', afd.get('semester', '1st Semester')),
        'v_school_year': fd.get('school_year', afd.get('school_year', '2025-2026')),
    })


def _doc_list():
    return [
        ('doc_certificate_of_grades',   'Certificate Of Grades',   'Official COG from the Registrar for the previous semester.'),
        ('doc_certificate_of_enrollment', 'Certificate Of Enrollment', 'Official COE from the Registrar for the current semester.'),
        ('doc_prospectus',              'Prospectus',              'Program prospectus or subject checklist showing enrolled subjects.'),
        ('doc_id_photo',                'Id Photo',                'Recent 2Ã—2 ID photo with white background.'),
        ('doc_application_form',        'Application Form',        'Signed and accomplished scholarship application form.'),
    ]


@_vpsea_required
def vpsea_student_delete(request, pk):
    from .models import StudentProfile
    if request.method == 'POST':
        try:
            profile = StudentProfile.objects.select_related('user').get(pk=pk)
            profile.user.delete()  # cascades to profile
        except StudentProfile.DoesNotExist:
            pass
        return redirect('/vpsea/students/?deleted=1')
    return redirect('/vpsea/students/')


@_vpsea_required
def vpsea_scholarships(request):
    scholarships = Scholarship.objects.all().order_by('type')
    return render(request, 'vpsea/scholarships.html', {
        'scholarships': scholarships,
        'added': request.GET.get('added'),
        'saved': request.GET.get('saved'),
    })


@_vpsea_required
def vpsea_scholarship_add(request):
    errors = []
    if request.method == 'POST':
        p = request.POST
        name = p.get('name','').strip()
        stype = p.get('type','').strip()
        description = p.get('description','').strip()
        background = p.get('background','').strip()
        eligibility_list = [l.strip() for l in p.get('eligibility_list','').splitlines() if l.strip()]
        benefits = [l.strip() for l in p.get('benefits','').splitlines() if l.strip()]
        if not name: errors.append('Name is required.')
        if not stype: errors.append('Type is required.')
        if not errors:
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description=description, eligibility='',
                background=background, eligibility_list=eligibility_list,
                benefits=benefits, group=p.get('group','internal'), is_active=True,
            )
            return redirect('/vpsea/scholarships/?added=1')
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Add', 'errors': errors, 'form': request.POST,
    })


@_vpsea_required
def vpsea_scholarship_edit(request, pk):
    try:
        s = Scholarship.objects.get(pk=pk)
    except Scholarship.DoesNotExist:
        return redirect('/vpsea/scholarships/')
    errors = []
    if request.method == 'POST':
        p = request.POST
        s.name = p.get('name','').strip()
        s.type = p.get('type','').strip()
        s.description = p.get('description','').strip()
        s.background = p.get('background','').strip()
        s.group = p.get('group', 'internal')
        s.eligibility_list = [l.strip() for l in p.get('eligibility_list','').splitlines() if l.strip()]
        s.benefits = [l.strip() for l in p.get('benefits','').splitlines() if l.strip()]
        if not s.name: errors.append('Name is required.')
        if not s.type: errors.append('Type is required.')
        if not errors:
            s.save()
            return redirect('/vpsea/scholarships/?saved=1')
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Edit', 'errors': errors, 's': s,
    })


@_vpsea_required
def vpsea_scholarship_toggle(request, pk):
    if request.method == 'POST':
        Scholarship.objects.filter(pk=pk).update(
            is_active=not Scholarship.objects.get(pk=pk).is_active
        )
    return redirect('/vpsea/scholarships/')


@_vpsea_required
def vpsea_ranking(request):
    from .models import AffirmativeRecommendation, SystemSettings

    scholarship_type = request.GET.get('type', 'Affirmative')
    scholarship_types = ['Affirmative', 'Staff']
    if scholarship_type not in scholarship_types:
        scholarship_type = 'Affirmative'

    # Recommended tab is Affirmative-only — Staff always stays on applicants
    tab = request.GET.get('tab', 'applicants')   # 'applicants' | 'recommended'
    if scholarship_type == 'Staff':
        tab = 'applicants'

    # ── Passing threshold (can be tweaked via GET param for VPSEA, default 75) ──
    try:
        passing_threshold = float(request.GET.get('passing', 75.0))
    except (TypeError, ValueError):
        passing_threshold = 75.0

    # ── Handle POST: endorse / disqualify a recommendation ───────────────────
    if request.method == 'POST':
        rec_id = request.POST.get('rec_id')
        action = request.POST.get('action')
        if rec_id and action in ('endorse', 'disqualify'):
            try:
                rec = AffirmativeRecommendation.objects.get(pk=rec_id)
                rec.status = 'Endorsed' if action == 'endorse' else 'Disqualified'
                rec.notes = request.POST.get('notes', rec.notes)
                rec.save()
            except AffirmativeRecommendation.DoesNotExist:
                pass
        # Re-sync all profiles when admin clicks "Re-evaluate"
        elif action == 'resync':
            AffirmativeRecommendation.evaluate_and_sync(passing_threshold)
        return redirect(f'/vpsea/ranking/?tab={tab}&type={scholarship_type}&passing={passing_threshold}')

    # ── TAB 1: Applicants (AffirmativeNSUApplication) ────────────────────────
    def _aff_score(a):
        s = 0.0
        if a.shs_gpa is not None:
            s += min((a.shs_gpa / 100.0) * 50.0, 50.0)
        if a.suc_exam_score is not None:
            s += min((a.suc_exam_score / 100.0) * 50.0, 50.0)
        return round(s)

    def _staff_score(a):
        return 100 if a.is_nsu_staff else 75

    applicants_qs = AffirmativeNSUApplication.objects.exclude(status='Approved').filter(
        qualified_for=scholarship_type
    )

    def _applicant_rules(a):
        """Return per-rule pass/fail dict for Affirmative applicants."""
        if scholarship_type != 'Affirmative':
            return None
        return {
            'gpa_pass': a.shs_gpa is not None and a.shs_gpa >= passing_threshold,
            'exam_pass': a.suc_exam_score is not None and a.suc_exam_score >= 50.0,
            'not_tes': not a.is_tes_beneficiary,
            'eligible': (
                a.shs_gpa is not None and a.shs_gpa >= passing_threshold and
                a.suc_exam_score is not None and a.suc_exam_score >= 50.0 and
                not a.is_tes_beneficiary
            ),
        }

    raw_score = _aff_score if scholarship_type == 'Affirmative' else _staff_score
    ranked_applicants = sorted(applicants_qs, key=raw_score, reverse=True)
    applicant_rows = [
        {
            'rank': i + 1,
            'applicant': a,
            'score': raw_score(a),
            'rules': _applicant_rules(a),
        }
        for i, a in enumerate(ranked_applicants)
    ]

    # ── TAB 2: Enrolled students evaluated by rule-based engine ──────────────
    # Sync first so the table is always current
    if scholarship_type == 'Affirmative':
        AffirmativeRecommendation.evaluate_and_sync(passing_threshold)

    recommendations = (
        AffirmativeRecommendation.objects
        .select_related('student__user')
        .order_by('-fit_score', 'student__user__last_name')
    )

    # Build per-row rule breakdown from live profile data
    rec_rows = []
    for i, rec in enumerate(recommendations):
        p = rec.student
        gpa_pass   = p.shs_gpa is not None and p.shs_gpa >= passing_threshold
        exam_pass  = p.suc_exam_score is not None and p.suc_exam_score >= 50.0
        not_tes    = not p.is_tes_beneficiary
        eligible   = gpa_pass and exam_pass and not_tes
        rec_rows.append({
            'rank': i + 1 if eligible else None,
            'rec': rec,
            'profile': p,
            'gpa_pass': gpa_pass,
            'exam_pass': exam_pass,
            'not_tes': not_tes,
            'eligible': eligible,
        })

    # Sort: eligible first (by fit_score desc), then ineligible
    rec_rows.sort(key=lambda r: (0 if r['eligible'] else 1, -r['rec'].fit_score))
    # Re-assign ranks only to eligible rows
    rank_counter = 1
    for row in rec_rows:
        if row['eligible']:
            row['rank'] = rank_counter
            rank_counter += 1
        else:
            row['rank'] = None

    eligible_count   = sum(1 for r in rec_rows if r['eligible'])
    ineligible_count = sum(1 for r in rec_rows if not r['eligible'])

    return render(request, 'vpsea/ranking.html', {
        'applicant_rows': applicant_rows,
        'rec_rows': rec_rows,
        'scholarship_types': scholarship_types,
        'active_type': scholarship_type,
        'tab': tab,
        'passing_threshold': passing_threshold,
        'eligible_count': eligible_count,
        'ineligible_count': ineligible_count,
        'total_applicants': len(ranked_applicants),
    })


@login_required(login_url='/login/')
def student_apply_tes(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    existing = TESApplication.objects.filter(student=profile).first() if profile else None
    if request.method == 'POST' and profile and not existing:
        p = request.POST
        TESApplication.objects.create(
            student=profile,
            lrn=p.get('lrn', ''),
            middle_name=p.get('middle_name', ''),
            birthdate=p.get('birthdate') or None,
            complete_program=p.get('complete_program', ''),
            father_last_name=p.get('father_last_name', ''),
            father_first_name=p.get('father_first_name', ''),
            father_middle_name=p.get('father_middle_name', ''),
            mother_last_name=p.get('mother_last_name', ''),
            mother_first_name=p.get('mother_first_name', ''),
            mother_middle_name=p.get('mother_middle_name', ''),
            street_barangay=p.get('street_barangay', ''),
            city_municipality=p.get('city_municipality', ''),
            province=p.get('province', ''),
            region=p.get('region', ''),
            zip_code=p.get('zip_code', ''),
            contact_number=p.get('contact_number', ''),
            email_address=p.get('email_address', ''),
            disability_type=p.get('disability_type', 'N/A'),
            is_solo_parent_dependent=p.get('is_solo_parent_dependent') == '1',
            is_first_gen_college=p.get('is_first_gen_college') == '1',
            indigenous_people_group=p.get('indigenous_people_group', 'Not Applicable'),
        )
        return redirect('/student/apply/tes/?submitted=1')
    return render(request, 'student/apply_tes.html', {
        'profile': profile,
        'existing': existing,
        'submitted': request.GET.get('submitted'),
        'enrolled': _is_enrolled(profile),
        'post': request.POST if request.method == 'POST' else (
            {
                'lrn': existing.lrn,
                'middle_name': existing.middle_name,
                'birthdate': existing.birthdate.strftime('%Y-%m-%d') if existing.birthdate else '',
                'complete_program': existing.complete_program,
                'father_last_name': existing.father_last_name,
                'father_first_name': existing.father_first_name,
                'father_middle_name': existing.father_middle_name,
                'mother_last_name': existing.mother_last_name,
                'mother_first_name': existing.mother_first_name,
                'mother_middle_name': existing.mother_middle_name,
                'street_barangay': existing.street_barangay,
                'city_municipality': existing.city_municipality,
                'province': existing.province,
                'region': existing.region,
                'zip_code': existing.zip_code,
                'contact_number': existing.contact_number,
                'email_address': existing.email_address,
                'disability_type': existing.disability_type,
                'is_solo_parent_dependent': '1' if existing.is_solo_parent_dependent else '0',
                'is_first_gen_college': '1' if existing.is_first_gen_college else '0',
                'indigenous_people_group': existing.indigenous_people_group,
            } if existing else {}
        ),
    })


@_unifast_required
def unifast_tes_applications(request):
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        TESApplication.objects.filter(id=app_id).update(status=new_status, remarks=remarks)
        return redirect('/unifast/tes-applications/?saved=1')
    apps = TESApplication.objects.select_related('student__user').order_by('-submitted_at')
    return render(request, 'unifast/tes_applications.html', {
        'applications': apps,
        'total': apps.count(),
        'pending_count': apps.filter(status='Pending').count(),
        'approved_count': apps.filter(status='Approved').count(),
    })


@_unifast_required
def unifast_tes_review(request, pk):
    if request.method == 'POST':
        new_status = request.POST.get('status', 'Pending')
        remarks = request.POST.get('remarks', '')
        TESApplication.objects.filter(pk=pk).update(status=new_status, remarks=remarks)
        if new_status == 'Approved':
            from .models import SystemSettings
            try:
                tes_app = TESApplication.objects.select_related('student').get(pk=pk)
                scholarship = Scholarship.objects.filter(type='TES').first()
                if scholarship:
                    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
                    parsed = SystemSettings.parse_label(settings_obj.academic_year)
                    already = Application.objects.filter(
                        student=tes_app.student, scholarship=scholarship,
                        form_data__academic_year=parsed['sy'],
                        form_data__semester=parsed['semester'],
                    ).exists()
                    if not already:
                        Application.objects.create(
                            student=tes_app.student,
                            scholarship=scholarship,
                            status='Approved',
                            remarks=remarks,
                            form_data={
                                'source': 'tes_application',
                                'tes_application_id': pk,
                                'academic_year': parsed['sy'],
                                'semester': parsed['semester'],
                            },
                        )
            except TESApplication.DoesNotExist:
                pass
    return redirect('/unifast/tes-applications/?saved=1')


@_unifast_required
def unifast_archives(request):
    from .models import ScholarshipRollover, SystemSettings, ArchiveRecord
    UNIFAST_TYPES = ['TDP', 'TES']
    db_types = list(Scholarship.objects.values_list('type', flat=True).distinct())
    archive_types = UNIFAST_TYPES + [t for t in db_types if t not in UNIFAST_TYPES and t not in ['Academic','DOST','CHED','CoScho','Sports','Affirmative','Staff','GSIS']]
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    stype = request.GET.get('type', 'TDP')
    if stype not in archive_types:
        stype = archive_types[0]
    history = ScholarshipRollover.objects.filter(scholarship_type=stype).order_by('-created_at')
    all_labels = list(ScholarshipRollover.objects.filter(scholarship_type=stype).values_list('label', flat=True).distinct().order_by('-label'))
    ar_labels = list(ArchiveRecord.objects.exclude(rollover_label='').filter(scholarship_type=stype).values_list('rollover_label', flat=True).distinct())
    for lbl in ar_labels:
        if lbl not in all_labels:
            all_labels.append(lbl)
    all_labels = sorted(set(all_labels), reverse=True)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    all_sy_display = [(lbl, SystemSettings.parse_label(lbl)['sy'] + ' - ' + SystemSettings.parse_label(lbl)['semester']) for lbl in all_labels]
    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label
    yy, s = active_label.split('-')
    prev_label = f'{yy}-1' if s == '2' else f'{int(yy)-1}-2'
    prev_parsed = SystemSettings.parse_label(prev_label)
    next_label = settings_obj.next_label()
    imported_rows = ArchiveRecord.objects.filter(scholarship_type=stype, rollover_label=selected_label).order_by('last_name', 'first_name')

    def sy_filter(qs):
        from django.db.models import Q
        if selected_label == active_label:
            return qs
        sel_sy = SystemSettings.parse_label(selected_label)['sy']
        return qs.filter(
            Q(form_data__academic_year=sel_sy) |
            Q(form_data__school_year=sel_sy) |
            Q(form_data__academic_year=selected_label) |
            Q(form_data__school_year=selected_label)
        )

    scholars = sy_filter(
        Application.objects.filter(status='Approved', scholarship__type=stype)
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name').distinct()
    return render(request, 'unifast/archives.html', {
        'archive_types': archive_types,
        'active_type': stype,
        'scholars': scholars,
        'imported_rows': imported_rows,
        'total': scholars.count() + imported_rows.count(),
        'history': history,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'active_sy': active_label,
        'active_sy_display': active_sy + ' - ' + active_semester,
        'active_semester': active_semester,
        'next_sy': next_label,
        'prev_sy': prev_label,
        'prev_sy_display': prev_parsed['sy'] + ' - ' + prev_parsed['semester'],
    })


@_unifast_required
def unifast_archive_add(request):
    from .models import Application, Scholarship, StudentProfile, User, SystemSettings, ApplicationDocument
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    p = request.POST
    f = request.FILES
    stype = p.get('scholarship_type', 'TDP')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    email = p.get('email', '').strip()
    student_id = p.get('student_id', '').strip()
    if not email:
        email = f"{student_id}@bipsu.edu.ph"
    user = User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create_user(
            username=email, email=email,
            password=student_id or 'bipsu1234',
            first_name=p.get('first_name', ''),
            last_name=p.get('last_name', ''),
            role='student',
        )
    profile = StudentProfile.objects.filter(user=user).first()
    if not profile:
        profile = StudentProfile.objects.create(
            user=user,
            student_id=student_id,
            course=p.get('course', ''),
            year_level=int(p.get('year_level', 1) or 1),
            gwa=float(p.get('gwa', 0) or 0),
            gender=p.get('gender', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            contact_number=p.get('contact_number', ''),
            date_of_birth=p.get('date_of_birth') or None,
        )
    else:
        profile.course = p.get('course', profile.course)
        profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
        profile.gender = p.get('gender', profile.gender)
        profile.barangay = p.get('barangay', profile.barangay)
        profile.municipality = p.get('municipality', profile.municipality)
        profile.province = p.get('province', profile.province)
        profile.save()
    scholarship = Scholarship.objects.filter(type=stype).first()
    if scholarship:
        form_data = {
            'academic_year': active_sy,
            'semester': active_semester,
            'award_number': p.get('award_number', ''),
            'congress_district': p.get('congress_district', ''),
            'source': 'manual',
        }
        already = Application.objects.filter(
            student=profile, scholarship=scholarship,
            form_data__academic_year=active_sy,
            form_data__semester=active_semester,
        ).exists()
        if not already:
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Approved', form_data=form_data,
            )
        else:
            app = Application.objects.filter(
                student=profile, scholarship=scholarship,
                form_data__academic_year=active_sy,
                form_data__semester=active_semester,
            ).first()
        for field, label in [
            ('doc_certificate_of_grades', 'Certificate Of Grades'),
            ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
            ('doc_prospectus', 'Prospectus'),
            ('doc_id_photo', 'Id Photo'),
            ('doc_application_form', 'Application Form'),
            ('proof_document', 'Proof Document'),
        ]:
            uploaded = f.get(field)
            if uploaded:
                ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
    return redirect(f'/unifast/archives/?type={stype}&added=1')


@_unifast_required
def unifast_archive_edit(request, pk):
    from .models import Application
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'TDP')
    try:
        app = Application.objects.select_related('student__user').get(pk=pk)
    except Application.DoesNotExist:
        return redirect(f'/unifast/archives/?type={stype}')
    profile = app.student
    user = profile.user
    user.first_name = p.get('first_name', user.first_name)
    user.last_name = p.get('last_name', user.last_name)
    user.save()
    profile.course = p.get('course', profile.course)
    profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
    profile.gender = p.get('gender', profile.gender)
    profile.barangay = p.get('barangay', profile.barangay)
    profile.municipality = p.get('municipality', profile.municipality)
    profile.province = p.get('province', profile.province)
    if p.get('student_id'):
        profile.student_id = p.get('student_id')
    profile.save()
    fd = dict(app.form_data)
    if p.get('award_number') is not None:
        fd['award_number'] = p.get('award_number')
    if p.get('congress_district') is not None:
        fd['congress_district'] = p.get('congress_district')
    app.form_data = fd
    app.save()
    return redirect(f'/unifast/archives/?type={stype}&edited=1')


@_unifast_required
def unifast_archive_delete(request, pk):
    from .models import Application
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('scholarship_type', 'TDP')
    Application.objects.filter(pk=pk).delete()
    return redirect(f'/unifast/archives/?type={stype}&deleted=1')


@_unifast_required
def unifast_archive_import(request):
    from django.core.files.base import ContentFile
    from .models import ScholarshipRollover, ActivityLog, SystemSettings, ArchiveRecord
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('type', 'TDP')
    rollover_label = request.POST.get('rollover_label', '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'/unifast/archives/?type={stype}&import_error=No+file+provided')
    if not rollover_label:
        return redirect(f'/unifast/archives/?type={stype}&import_error=Rollover+name+is+required')
    try:
        import openpyxl
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        parsed = SystemSettings.parse_label(settings_obj.academic_year)
        active_semester = parsed['semester']
        rollover_parsed = SystemSettings.parse_label(rollover_label) if '-' in rollover_label else {'sy': rollover_label, 'semester': active_semester}
        wb = openpyxl.load_workbook(file)
        ws = wb.active
        col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])
        ArchiveRecord.objects.filter(scholarship_type=stype, rollover_label=rollover_label).delete()
        records = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            try:
                int(row[0])
            except (ValueError, TypeError):
                continue
            extra = {}
            for idx, field in col_map:
                val = row[idx] if idx < len(row) else None
                extra[field] = str(val).strip() if val is not None else ''
            last = extra.get('last_name', '').strip()
            first = extra.get('first_name', '').strip()
            if not last and not first:
                continue
            try:
                year_level = int(extra.get('year', 0) or 0)
            except (ValueError, TypeError):
                year_level = 0
            try:
                gwa = float(extra.get('gwa', 0) or 0)
            except (ValueError, TypeError):
                gwa = 0.0
            records.append(ArchiveRecord(
                scholarship_type=stype,
                rollover_label=rollover_label,
                last_name=last,
                first_name=first,
                middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
                scholar_name=f'{first} {last}'.strip(),
                gender=extra.get('sex', ''),
                course=extra.get('course', ''),
                year=year_level,
                gwa=gwa,
                barangay=extra.get('barangay', ''),
                municipality=extra.get('municipality', ''),
                province=extra.get('province', ''),
                student_number=extra.get('student_number', extra.get('student_id', '')),
                award_number=extra.get('award_number', ''),
                congress_district=extra.get('congress_district', ''),
                imported_from=file.name,
            ))
        ArchiveRecord.objects.bulk_create(records)
        created = len(records)
        file.seek(0)
        if not ScholarshipRollover.objects.filter(label=rollover_label, scholarship_type=stype).exists():
            rollover = ScholarshipRollover(
                scholarship_type=stype,
                school_year=rollover_parsed['sy'],
                semester=rollover_parsed.get('semester', active_semester),
                label=rollover_label,
                scholar_count=created,
                rolled_over_by=request.user,
            )
            rollover.excel_file.save(f'{stype}_{rollover_label}.xlsx', ContentFile(file.read()), save=True)
        else:
            ScholarshipRollover.objects.filter(label=rollover_label, scholarship_type=stype).update(scholar_count=created)
        ActivityLog.objects.create(
            user=request.user,
            action=f'Imported {file.name} ({created} rows) for {stype} as "{rollover_label}"'
        )
    except Exception as e:
        return redirect(f'/unifast/archives/?type={stype}&import_error={e}')
    return redirect(f'/unifast/archives/?type={stype}&import_ok={created}')


@_unifast_required
def unifast_rollover_delete(request, pk):
    from .models import ScholarshipRollover
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('type', 'TDP')
    try:
        r = ScholarshipRollover.objects.get(pk=pk)
        r.excel_file.delete(save=False)
        r.delete()
    except ScholarshipRollover.DoesNotExist:
        pass
    return redirect(f'/unifast/archives/?type={stype}')


@_unifast_required
def unifast_archive_download(request):
    from django.http import HttpResponse
    from io import BytesIO
    from .models import SystemSettings
    from django.db.models import Q
    stype = request.GET.get('type', 'TDP')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    semester = settings_obj.active_semester
    scholars = Application.objects.filter(
        status='Approved', scholarship__type=stype
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{stype} Scholars'
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hfont = Font(bold=True)
    hfill = PatternFill('solid', fgColor='D9E1F2')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    headers = ['No.', 'Last Name', 'First Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'Award No.', 'Congress District', 'Barangay', 'Municipality', 'Province']
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = hfont; cell.fill = hfill; cell.border = border; cell.alignment = center
    for i, app in enumerate(scholars, 1):
        p = app.student
        ws.append([i, p.user.last_name, p.user.first_name, p.gender, p.course, p.year_level,
                   p.student_id, app.form_data.get('award_number', ''),
                   app.form_data.get('congress_district', ''),
                   p.barangay, p.municipality, p.province])
    for col in ws.columns:
        ml = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(ml + 4, 40)
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    filename = f'{stype}_scholars_{settings_obj.academic_year}_{semester.replace(" ", "_")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── NSU Staff portal ─────────────────────────────────────────────────────────

def _nsu_staff_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'nsu_staff':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_nsu_staff_required
def nsu_staff_dashboard(request):
    from .models import StaffRenewal, Notification, Announcement, AffirmativeNSUApplication
    user = request.user
    # Try to find the matching AffirmativeNSUApplication record for this staff member
    aff_app = AffirmativeNSUApplication.objects.filter(
        email=user.email, qualified_for='Staff', status='Approved'
    ).first()
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    announcements = Announcement.objects.order_by('-created_at')[:3]
    unread_count = Notification.objects.filter(
        student__user=user, is_read=False
    ).count() if hasattr(user, 'profile') else 0
    return render(request, 'nsu_staff/dashboard.html', {
        'aff_app': aff_app,
        'renewals': renewals,
        'announcements': announcements,
        'unread_count': unread_count,
        'pending_renewals': renewals.filter(status='Pending').count(),
        'approved_renewals': renewals.filter(status='Approved').count(),
    })


@_nsu_staff_required
def nsu_staff_profile(request):
    from .models import AffirmativeNSUApplication
    user = request.user
    aff_app = AffirmativeNSUApplication.objects.filter(
        email=user.email, qualified_for='Staff', status='Approved'
    ).first()
    saved = False
    errors = []
    if request.method == 'POST':
        p = request.POST
        # Update Django user name fields
        user.first_name = p.get('first_name', user.first_name).strip()
        user.last_name  = p.get('last_name',  user.last_name).strip()
        user.save()
        # Update the AffirmativeNSUApplication record if linked
        if aff_app:
            aff_app.contact_number = p.get('contact_number', aff_app.contact_number)
            aff_app.barangay       = p.get('barangay', aff_app.barangay)
            aff_app.municipality   = p.get('municipality', aff_app.municipality)
            aff_app.province       = p.get('province', aff_app.province)
            aff_app.course         = p.get('course', aff_app.course)
            try:
                aff_app.year_level = int(p.get('year_level', aff_app.year_level) or aff_app.year_level)
            except (ValueError, TypeError):
                pass
            aff_app.save()
        saved = True
    return render(request, 'nsu_staff/profile.html', {
        'aff_app': aff_app,
        'saved': saved,
        'errors': errors,
        'bipsu_schools': BIPSU_SCHOOLS,
    })


@_nsu_staff_required
def nsu_staff_notifications(request):
    from .models import Notification
    user = request.user
    # Notifications are tied to StudentProfile; staff may not have one — guard gracefully
    notifications = []
    if hasattr(user, 'profile'):
        notifications = Notification.objects.filter(
            student=user.profile
        ).order_by('-created_at')
        if request.method == 'POST' and request.POST.get('mark_all_read'):
            notifications.update(is_read=True)
            return redirect('/nsu-staff/notifications/')
    return render(request, 'nsu_staff/notifications.html', {
        'notifications': notifications,
    })


@_nsu_staff_required
def nsu_staff_renewal(request):
    from .models import StaffRenewal, SystemSettings
    user = request.user
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    errors = []
    submitted = False

    if request.method == 'POST':
        sup = request.FILES.get('supporting_document')
        if not errors:
            StaffRenewal.objects.create(
                staff_user=user,
                supporting_document=sup or None,
            )
            return redirect('/nsu-staff/renewal/?submitted=1')
        return render(request, 'nsu_staff/renewal.html', {
            'renewals': renewals, 'errors': errors,
            'semester': parsed['semester'], 'academic_year': parsed['sy'],
        })

    return render(request, 'nsu_staff/renewal.html', {
        'renewals': renewals,
        'submitted': request.GET.get('submitted'),
        'semester': parsed['semester'],
        'academic_year': parsed['sy'],
        'errors': errors,
    })

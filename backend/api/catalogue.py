"""The scholarship programmes BiPSU actually runs.

Kept apart from any one command because two of them need it and they must not
drift: ``seed`` builds a demo database on a laptop, ``bootstrap`` prepares a
real deployment. A programme missing from one and present in the other shows up
as a scholarship students can see in testing and not in production -- which is
exactly what happened before this list was taken from the real catalogue.

``group`` is the field to be careful with. It decides which office reviews the
programme and which report a scholar appears in, and it defaults to
``internal``, so a row that simply omits it is quietly filed as a BiPSU-funded
programme. Most of these are not: TDP, DOST, CHED, CoScho, GSIS and TES are all
externally funded.
"""

# Generated from the working catalogue rather than written by hand. ``type`` is
# the key the approval routes look a programme up by, so it is what
# ensure_scholarships() matches on; a missing type does not raise, it just
# produces no award, and the scholar never reaches the masterlist.
SCHOLARSHIPS = [   {   'name': 'Academic Scholarship',
        'type': 'Academic',
        'category': 'application',
        'group': 'internal',
        'description': "BiPSU's flagship merit scholarship for outstanding students "
                       'with exemplary GWA.',
        'eligibility': 'GWA 1.00–1.50, no grade above 2.5',
        'eligibility_list': [   'University Scholar: GWA of 1.00',
                                'College Scholar: GWA of 1.30 to 1.50',
                                'Must be a regular student (full load)'],
        'requirements': [   'Certificate of Grades',
                            'Certificate of Enrollment',
                            'Prospectus',
                            'Good Moral',
                            '2x2 ID',
                            'Study Load'],
        'benefits': [   'Full tuition fee coverage',
                        'Miscellaneous fee exemption',
                        'Priority in university activities',
                        'Certificate of recognition each semester'],
        'background': 'The Academic Scholarship is BiPSU flagship merit-based program '
                      'recognizing students with outstanding academic performance, '
                      'providing full tuition coverage to top-performing students each '
                      'semester.',
        'is_active': True},
    {   'name': 'Tulong Dunong Program Scholarship',
        'type': 'TDP',
        'category': 'application',
        'group': 'external',
        'description': 'Tertiary Education Subsidy & TDP grant for indigent but '
                       'deserving students.',
        'eligibility': 'Indigent family, enrolled BiPSU student',
        'eligibility_list': [   'Filipino citizen enrolled in a state university',
                                'From a low-income family (combined annual income not '
                                'exceeding PHP 400,000)',
                                'Not a recipient of other government subsidies',
                                'Maintaining satisfactory academic performance'],
        'requirements': ['COR/COE', 'Certificate of Indigency'],
        'benefits': [   'Monthly stipend for living expenses',
                        'Tuition and miscellaneous fee subsidy',
                        'Book and supplies allowance',
                        'Renewable each semester subject to conditions'],
        'background': 'The Tertiary Development Program (TDP) is a government '
                      'scholarship under UniFAST providing financial subsidy to '
                      'qualified students from low-income families enrolled in state '
                      'universities and colleges.',
        'is_active': True},
    {   'name': 'DOST Merit Scholarship',
        'type': 'DOST',
        'category': 'recommendation',
        'group': 'external',
        'description': 'DOST-SEI scholarship for STEM students with academic '
                       'excellence.',
        'eligibility': 'STEM course, high GWA, passed DOST exam',
        'eligibility_list': [   'Enrolled in a STEM-related course',
                                'GWA of at least 85% in high school',
                                'Must pass the DOST qualifying examination',
                                'Filipino citizen with financial need'],
        'requirements': ['DOST application form', 'HS Card', 'Income Tax Return'],
        'benefits': [   'Full tuition and fees',
                        'Monthly stipend',
                        'Book allowance',
                        'Thesis/dissertation allowance for graduate scholars'],
        'background': 'The DOST Scholarship is a prestigious government program '
                      'supporting outstanding students pursuing science, technology, '
                      'engineering, and mathematics (STEM) courses to drive national '
                      'development.',
        'is_active': True},
    {   'name': 'CHED Merit',
        'type': 'CHED',
        'category': 'recommendation',
        'group': 'external',
        'description': 'CHED-funded merit scholarship for qualified college students.',
        'eligibility': 'GWA ≥ 1.75, family income ≤ ₱300k',
        'eligibility_list': [   'Filipino citizen with demonstrated financial need',
                                'GWA of 80% or higher in the previous school year',
                                'Not a recipient of other CHED scholarships',
                                'Enrolled in CHED-recognized programs'],
        'requirements': ['CHED form', 'Income proof', 'Grades'],
        'benefits': [   'Tuition and miscellaneous fees',
                        'Monthly living allowance',
                        'Book allowance per semester',
                        'Thesis support grant'],
        'background': 'The CHED Scholarship provides financial assistance to deserving '
                      'and qualified students in higher education institutions under '
                      'Republic Act 7722.',
        'is_active': True},
    {   'name': 'CoScho (Coconut Farmers)',
        'type': 'CoScho',
        'category': 'recommendation',
        'group': 'external',
        'description': 'Scholarship for children of registered coconut farmers.',
        'eligibility': 'Child of registered coconut farmer',
        'eligibility_list': [   'Child or legal dependent of a registered coconut '
                                'farmer',
                                'Farmer must be registered with PCIC',
                                'Good academic standing (passing all subjects)',
                                'Must submit proof of coconut farm registration'],
        'requirements': ['PCA Certification', 'Birth Certificate'],
        'benefits': [   'Tuition fee subsidy',
                        'Monthly allowance',
                        'Book and supplies grant',
                        'Annual clothing allowance'],
        'background': 'The Coconut Farmers Scholar (CoScho) Program is for children '
                      'and dependents of registered coconut farmers funded through the '
                      'Philippine Coconut Authority.',
        'is_active': True},
    {   'name': 'Sports Scholarship',
        'type': 'Sports',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Grant for varsity athletes representing BiPSU.',
        'eligibility': 'Active varsity athlete',
        'eligibility_list': [   'Must be a recognized university athlete',
                                'Actively competing in university-sanctioned athletic '
                                'events',
                                'Maintaining passing grades in all enrolled subjects',
                                'Endorsed by the university coach and sports office'],
        'requirements': ['Athlete Certification', 'Coach endorsement'],
        'benefits': [   'Full tuition fee coverage',
                        'Athletic allowance',
                        'Sports equipment and uniform support',
                        'Travel allowance for competitions'],
        'background': 'The Sports Scholarship honors student athletes who represent '
                      'BiPSU in regional and national competitions, ensuring they can '
                      'pursue both academic and athletic goals without financial '
                      'burden.',
        'is_active': True},
    {   'name': 'Affirmative Action',
        'type': 'Affirmative',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Support for Indigenous Peoples and students with disabilities.',
        'eligibility': 'IP member or PWD',
        'eligibility_list': [   'SHS GPA of at least 75% certified by SHS principal',
                                'At least 50% passing score in SUC-administered '
                                'admission exam',
                                'Must NOT be a TES beneficiary',
                                'Must be enrolled as a regular student at BiPSU'],
        'requirements': ['IP Certification or PWD ID'],
        'benefits': [   'Tuition fee coverage',
                        'Monthly educational allowance',
                        'Access to university academic support programs',
                        'Renewable subject to satisfactory academic performance'],
        'background': 'The Affirmative Action Scholarship promotes equal access to '
                      'quality education for students who demonstrate strong academic '
                      'potential in Senior High School and perform well in the '
                      'university admission examination.',
        'is_active': True},
    {   'name': 'Staff Scholarship',
        'type': 'Staff',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Tuition support for dependents of BiPSU employees.',
        'eligibility': 'Dependent of BiPSU employee',
        'eligibility_list': [   'Permanent NSU faculty or employee, OR',
                                'Legitimate dependent of a permanent NSU faculty/staff',
                                'Dependent must not have already earned a '
                                'baccalaureate degree'],
        'requirements': ['HR Certification'],
        'benefits': [   'Full tuition fee coverage',
                        'Miscellaneous fee exemption',
                        'Renewable each semester',
                        'Applicable to all undergraduate programs'],
        'background': 'The NSU Staff Scholarship is an institutional benefit for '
                      'permanent faculty, employees, and their qualified dependents as '
                      'a benefit of university employment at BiPSU.',
        'is_active': True},
    {   'name': 'GSIS Scholarship',
        'type': 'GSIS',
        'category': 'application',
        'group': 'external',
        'description': 'Dev seed for GSIS',
        'eligibility': 'Dev only',
        'eligibility_list': [   'Child or dependent of an active GSIS member',
                                'Good academic standing',
                                'Must not be a recipient of other government '
                                'scholarships',
                                'Enrolled in an accredited higher education '
                                'institution'],
        'requirements': [],
        'benefits': [   'Tuition fee coverage',
                        'Annual book allowance',
                        'Monthly stipend',
                        'Renewable each semester'],
        'background': 'The GSIS Scholarship Program supports dependents of GSIS '
                      'members, providing educational assistance to qualified children '
                      'of government employees.',
        'is_active': True},
    {   'name': 'Tertiary Education Subsidy',
        'type': 'TES',
        'category': 'application',
        'group': 'external',
        'description': 'provides financial assistance to qualified undergraduate '
                       'students enrolled in public and private higher education '
                       'institutions. Grantees can receive support for tuition, books, '
                       'and living costs.',
        'eligibility': '',
        'eligibility_list': [   'Filipino Citizen',
                                'enrolled in CHED-recognized undergraduate programs'],
        'requirements': [],
        'benefits': [   'Grant Amounts: Up to ₱20,000 per academic year for SUCs and '
                        'LUCs, and up to ₱27,000 per academic year for private higher '
                        'education institutions.'],
        'background': 'Tertiary Education Subsidy (TES) in the Philippines is a '
                      'grants-in-aid program under Republic Act 10931 that provides '
                      'financial assistance to qualified undergraduate students '
                      'enrolled in public and private higher education institutions. '
                      'Grantees can receive support for tuition, books, and living '
                      'costs.',
        'is_active': True}]


def ensure_scholarships():
    """Make the database agree with the catalogue above. Returns (added, updated).

    Matched on ``type``, not name: the name is the part most likely to be
    reworded, while the type is what the code looks programmes up by.

    Existing rows are brought back into line rather than left alone. This list
    is the definition of the programmes, so wording is changed here and shipped;
    the alternative -- creating only what is missing -- is how a deployment ends
    up with programmes filed under the wrong office and no way to correct them
    without a shell.
    """
    from .models import Scholarship

    added, updated = [], []
    for row in SCHOLARSHIPS:
        fields = {k: v for k, v in row.items() if k != 'type'}
        obj, created = Scholarship.objects.get_or_create(
            type=row['type'], defaults=fields)
        if created:
            added.append(row['name'])
            continue
        changed = [k for k, v in fields.items() if getattr(obj, k) != v]
        if changed:
            for k in changed:
                setattr(obj, k, fields[k])
            obj.save(update_fields=changed)
            updated.append(f"{row['name']} ({', '.join(changed)})")
    return added, updated

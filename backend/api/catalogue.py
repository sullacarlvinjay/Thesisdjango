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
# ── Benefit figures below are quoted from the UniFAST 2026 guidelines
#    (Board Resolution No. 2026-012, 08 July 2026, effective 1st Semester
#    AY 2026-2027) for TES, TDP and FHE. They are the amounts a student reads
#    on the landing page, so they are revisited whenever the Board revises a
#    rate — both decks say the amounts "may be increased as determined and
#    approved by the UniFAST Board".
#
#    BiPSU is a state university, so the SUC rate is the one quoted. The
#    private-HEI rate in the same section (₱13,500 a semester) is deliberately
#    left out: no BiPSU student is paid on it, and printing both invites a
#    grantee to expect the larger one.
#
# ── Academic, Sports, Staff, DOST, JLSS, CHED and CoScho are taken from
#    BiPSU's own "Scholarship Flow" charter (supplied 2026-09-12), which sets
#    out the citizens-charter checklists for the internal programmes and
#    reproduces the external agencies' own published terms.
#
#    Two figures in it are load-bearing and come from named instruments:
#    Sports is Board Resolution No. 14, s. 2023 (₱5,000-₱10,000 a semester),
#    and CHED Merit is the CMSP's ₱80,000 Full / ₱40,000 Half annual package.
#    CoScho's ₱195,000 splits ₱80,000 in regular allowances (stipend + books,
#    both per semester) against ₱115,000 in one-off allowances (thesis/OJT,
#    one conference, a laptop).
#
#    The charter also carries TES and TDP sections, and they are NOT the
#    source for those two entries -- it predates the 2026 guidelines above and
#    quotes the older rates (TES by academic year, plus a PHEI rate; no SARDO
#    and no solo-parent/IP top-up). Where the two disagree the deck wins.
#
#    Two gaps the decks left are filled from the charter, on Juniel's word
#    (2026-09-12) and only because neither contradicts a figure the decks
#    stated: TES `requirements`, which was empty and rendered a blank card,
#    and TDP's ₱400,000 household income ceiling. Nothing else in those two
#    entries is the charter's to touch.
#
#    Still unsourced: GSIS and SUC-TDP, which the charter does not mention,
#    and the benefit lists for DOST, JLSS and Staff, which it describes
#    without ever pricing. Those remain the office's to confirm.
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
        'requirements': [   'Certificate of Grades (COG) — Registrar',
                            'Certificate of Enrollment (COE) — Registrar',
                            'Prospectus / Subject Checklist — School',
                            'Good Moral — Guidance and Counselling Office',
                            '2x2 ID Picture — Student',
                            'Brown Envelope — Student',
                            'Application Form — VPSEA Office'],
        'benefits': [   'Full tuition fee coverage',
                        'Miscellaneous fee exemption',
                        'Priority in university activities',
                        'Certificate of recognition each semester'],
        'background': 'The Academic Scholarship is BiPSU flagship merit-based program '
                      'recognizing students with outstanding academic performance, '
                      'providing full tuition coverage to top-performing students each '
                      'semester. The checklist above is the one the citizens charter '
                      'sets for a new applicant; a renewal is assessed on the first '
                      'three alone — the Certificate of Grades, the Certificate of '
                      'Enrollment and the prospectus.',
        'is_active': True},
    {   'name': 'Tulong Dunong Program Scholarship',
        'type': 'TDP',
        'category': 'application',
        'group': 'external',
        'description': 'Tertiary Education Subsidy & TDP grant for indigent but '
                       'deserving students.',
        'eligibility': 'First undergraduate degree, indigent household, no '
                       'other national grant',
        'eligibility_list': ['Enrolled in a first undergraduate degree at a '
                             'state university, a CHED-recognised LUC, or a '
                             'private HEI on the CHED registry',
                             'Combined gross household income of the parents or '
                             'guardians not exceeding ₱400,000',
                             'Continuing grantees hold a TDP award number from '
                             'a term before AY 2026-2027',
                             'Meets the university’s own admission and '
                             'retention policy',
                             'Holds no other national government grant — Free '
                             'Higher Education does not count against this, '
                             'nor does one-off aid such as DSWD AICS',
                             'Enrolled for at least two terms in the academic '
                             'year, with no term missed without an approved '
                             'leave of absence',
                             'Completes the degree within the maximum '
                             'residency rule plus one year',
                             'Tells the CHED Regional Office about dropping '
                             'out, deferring or transferring'],
        'requirements': ['COR/COE', 'Certificate of Indigency'],
        'benefits': [   '₱7,500 per semester — ₱15,000 for the academic year, '
                        'paid to the grantee',
                        'The UniFAST Board may raise the amount for a later '
                        'term',
                        'Held alongside Free Higher Education, which the '
                        'guidelines name as an exception to the bar on holding '
                        'more than one government grant',
                        'Paid to the grantee directly by bank credit or '
                        'cheque; coursed through the university only where '
                        'neither is possible',
                        'Released within 15 working days of the university '
                        'receiving the funds'],
        'background': 'Tulong Dunong is a UniFAST grant-in-aid under the UAQTE '
                      'Act, paid on top of Free Higher Education rather than '
                      'instead of it. It is appropriated a year at a time, and '
                      'the guidelines are plain about what that means: a new '
                      'grantee for AY 2026-2027 becomes a continuing grantee '
                      'only if similar funding is provided in the following '
                      'fiscal years, so a first award is not a promise of '
                      'support to graduation. These terms are the 2026 '
                      'guidelines, UniFAST Board Resolution No. 2026-012, '
                      'effective 1st Semester AY 2026-2027.',
        'is_active': True},
    {   'name': 'DOST S&T Undergraduate Scholarship',
        'type': 'DOST',
        'category': 'recommendation',
        'group': 'external',
        'description': 'DOST-SEI scholarship for STEM students, awarded under '
                       'either the RA 7687 or the Merit track.',
        'eligibility': 'STEM course, high GWA, passed DOST exam',
        'eligibility_list': [   'Enrolled in a STEM-related course',
                                'GWA of at least 85% in high school',
                                'Must pass the DOST qualifying examination',
                                'RA 7687 track (Science and Technology Scholarship '
                                'Act of 1994): the family’s socio-economic status '
                                'must not exceed the set cut-off values, and the '
                                'course must be a priority field — the basic '
                                'sciences, engineering, the other applied sciences, '
                                'or science and mathematics teaching',
                                'Merit track (DOST-SEI): awarded on high aptitude in '
                                'science and mathematics and a willingness to pursue '
                                'a career in science and technology',
                                'Filipino citizen',
                                'BiPSU’s DOST priority courses are BSCE, BSCS, BSCpE, BSEE, BSIS, '
                                'BSME, BSEd Mathematics and BSEd Science'],
        'requirements': ['DOST application form', 'HS Card', 'Income Tax Return'],
        'benefits': [   'Full tuition and fees',
                        'Monthly stipend',
                        'Book allowance',
                        'Thesis/dissertation allowance for graduate scholars'],
        'background': 'The S&T Undergraduate Scholarships Program exists to entice '
                      'talented Filipino youth into lifetime productive careers in '
                      'science and technology, and to keep a steady, adequate supply '
                      'of qualified S&T people who can steer the country towards '
                      'national progress. Application is through DOST-SEI in four '
                      'steps: registration; an eligibility check, made up of an '
                      'eligibility questionnaire and a student information '
                      'questionnaire; the application form itself, with personal, '
                      'contact, family, financial contribution, household, and '
                      'school and grades sections, and the documentary requirements '
                      'uploaded; and finally the choice of test centre.',
        'is_active': True},
    {   'name': 'CHED Merit',
        'type': 'CHED',
        'category': 'recommendation',
        'group': 'external',
        'description': 'CHED Merit Scholarship Program — a full or a half '
                       'scholarship for academically excellent students from '
                       'underprivileged families.',
        'eligibility': 'Full Merit: GWA 96% and above; Half Merit: GWA 93–95%; '
                       'household income ≤ ₱400,000',
        'eligibility_list': [   'Filipino citizen',
                                'Full Merit: a general weighted average of at least '
                                '96% in Grade 11 and the first semester of Grade 12',
                                'Half Merit: a general weighted average of 93% to '
                                '95%',
                                'Combined annual household income not exceeding '
                                '₱400,000 — a household slightly above the ceiling '
                                'may still be considered with a valid justification',
                                'Certification of good moral character from the '
                                'school or the barangay',
                                'Physically and mentally fit'],
        'requirements': [   'Birth Certificate (PSA)',
                            'High school report card or Transcript of Records',
                            'Certificate of Good Moral Character',
                            'Proof of income — Income Tax Return, Certificate of '
                            'Indigency, or a 4Ps ID',
                            'Recent 2x2 ID photographs'],
        'benefits': [   'Full Merit: ₱80,000 for the academic year — tuition and '
                        'miscellaneous fees up to ₱40,000, a stipend of ₱35,000, '
                        'and ₱5,000 for books and connectivity',
                        'Half Merit: ₱40,000 for the academic year — tuition and '
                        'miscellaneous fees up to ₱20,000, a stipend of ₱17,500, '
                        'and ₱2,500 for books and connectivity',
                        'Tenable in a wide range of programmes at any '
                        'CHED-recognised higher education institution'],
        'background': 'The CHED Merit Scholarship Program (CMSP) is a '
                      'government-funded programme that awards a full or a half '
                      'scholarship to students who excel academically but come from '
                      'underprivileged families, so that equitable access to quality '
                      'higher education does not turn on what a family can pay. '
                      'Applications are filed through the CHED Scholarship Portal or '
                      'the CHED Regional Office, which screens the academic records '
                      'and the financial documents before the qualifiers are posted.',
        'is_active': True},
    {   'name': 'CoScho (Coconut Farmers)',
        'type': 'CoScho',
        'category': 'recommendation',
        'group': 'external',
        'description': 'CHED scholarship for coconut farmers registered in the '
                       'NCFRS and their dependents.',
        'eligibility': 'Registered coconut farmer or dependent, GWA 80%, parents’ '
                       'combined gross income ≤ ₱300,000',
        'eligibility_list': [   'Filipino citizen',
                                'A coconut farmer duly registered in the NCFRS, or '
                                'a dependent of one',
                                'Graduating high school student or high school '
                                'graduate with a GWA of 80% or its equivalent',
                                'Or a college student with earned academic units '
                                'relevant to a degree programme identified by the '
                                'PCA, with a GWA of 80% the previous semester or '
                                'its equivalent',
                                'Passes the entry-level requirements of the '
                                'identified state university or college',
                                'Not a recipient of any government-funded financial '
                                'assistance programme',
                                'Combined annual gross income of the parents does '
                                'not exceed ₱300,000'],
        'requirements': [   'Birth Certificate from the Local Civil Registry or '
                            'the PSA',
                            'Senior high school student: certified copy of the '
                            'grades for Grade 11 and the first semester of Grade 12',
                            'Senior high school graduate: Form 138',
                            'With earned units or already in college: certified '
                            'copy of the grades for the latest semester or term '
                            'attended',
                            'PCA Certification — only one member of a family may '
                            'apply',
                            'Certificate of Good Moral Character from the last '
                            'school attended',
                            'Proof of income — any one of: the latest ITR of the '
                            'applicant, spouse, parents or guardians if employed; a '
                            'Certificate of Tax Exemption from the BIR; a '
                            'Certificate of No Income from the BIR; a Certificate '
                            'of Indigency from the barangay; or a certificate or '
                            'case study from the DSWD',
                            'Notice of admission from an HEI with collegiate degree '
                            'offerings',
                            'Proof of belonging to a special group, if applicable',
                            'Original barangay certification that the parents or '
                            'guardians and the siblings never attended college or '
                            'university, if applicable'],
        'benefits': [   '₱195,000 in total — ₱80,000 in regular allowances and '
                        '₱115,000 in other allowances',
                        'Stipend of ₱35,000 per semester — ₱70,000 for the '
                        'academic year — covering food, smaller projects, '
                        'educational tours, transportation, medical insurance, '
                        'internet use and communication expenses',
                        'Books and learning materials allowance of ₱5,000 per '
                        'semester — ₱10,000 for the academic year',
                        '₱75,000 thesis and/or OJT allowance',
                        '₱10,000 once for attendance at a local conference or '
                        'forum during junior or senior standing — it must relate '
                        'to the undergraduate programme, and must not be held at '
                        'the HEI where the grantee is enrolled',
                        '₱30,000 once towards the purchase of a laptop, given '
                        'during the first year of the grant'],
        'background': 'The Coconut Farmers Scholarship (CoScho) is CHED’s programme '
                      'for coconut farmers registered in the NCFRS and their '
                      'dependents, taking a degree programme identified by the '
                      'Philippine Coconut Authority at an identified state '
                      'university or college. It carries ₱195,000 in allowances: a '
                      'stipend and a book allowance each semester, plus thesis or '
                      'OJT support, one local conference, and a laptop in the first '
                      'year.',
        'is_active': True},
    {   'name': 'Sports, Athletics and Cultural Scholarship',
        'type': 'Sports',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Grant for student-athletes and cultural performers '
                       'representing BiPSU, under Board Resolution No. 14, s. 2023.',
        'eligibility': '₱5,000–₱10,000 a semester for a qualified student-athlete',
        'eligibility_list': [   'Qualifies as a student-athlete under Board '
                                'Resolution No. 14, series of 2023',
                                'Actively competing in university-sanctioned '
                                'athletic or cultural events',
                                'Maintaining passing grades in all enrolled subjects',
                                'Endorsed by the Sports and Athletics Services '
                                'Office'],
        'requirements': [   'Certificate of Enrollment (COE) — Registrar',
                            'School ID — Registrar',
                            'Certificate of Award — Student',
                            'Medals, plaques or trophies — Student',
                            'Pictures — Student'],
        'benefits': [   'A grant of ₱5,000 to ₱10,000 per semester, the range set '
                        'by Board Resolution No. 14, series of 2023'],
        'background': 'The Sports and Athletics Services Office offers scholarship '
                      'grants to student-athletes who qualify under Board Resolution '
                      'No. 14, series of 2023, which sets the grant at ₱5,000 to '
                      '₱10,000 per semester. The application is assessed on proof of '
                      'competition — the certificate of award, the medals, plaques or '
                      'trophies won, and pictures — rather than on a coach’s '
                      'endorsement alone.',
        'is_active': True},
    # ── Affirmative Action ──────────────────────────────────────────────────
    #    Taken from the PASUC-8 proposal "Affirmative Action Program for State
    #    Colleges and Universities in Region 8 (SUCs-8) To Provide Access to
    #    Quality Education for Underprivileged / Marginalized Students" —
    #    proponents CHED R8, PASUC 8, DSWD 8 and DepEd 8 — which commenced 1st
    #    Semester SY 2021-2022. Criteria are its section 2, benefits its
    #    section 4, the mentor and the retention waiver its section 7.
    #
    #    The ₱2,500 living allowance is that document's own figure. It dates
    #    from 2021, so it carries the same caveat as the UniFAST rates above:
    #    it is the office's to confirm against any later Board revision.
    #
    #    Two things this entry had backwards, written down because a later
    #    reader would otherwise put them back:
    #
    #    * **The four groups are who the programme is for, not a document
    #      gate.** It read 'IP member or PWD', asking for an IP certificate or
    #      a PWD ID — which turned away the other half of the mandate, students
    #      from public schools and from depressed areas, over a document the
    #      criteria never mention. What is actually required is the two
    #      certifications in 2a and 2b.
    #    * **Tuition is not what this programme pays.** Benefit 4b is precisely
    #      what UniFAST does *not* cover — RLE, OJT, internship, the rest.
    #      Listing tuition credited this programme with what free higher
    #      education already gives every qualified SUC student.
    {   'name': 'Affirmative Action',
        'type': 'Affirmative',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Access to college for underprivileged and marginalized '
                       'students — those from indigenous groups, persons with '
                       'disabilities, students from public schools, and students '
                       'from depressed areas.',
        'eligibility': 'SHS GPA of 75%, at least 50% in the admission exam, and not '
                       'a TES beneficiary',
        'eligibility_list': [   'A passing grade point average of 75% in Senior High '
                                'School, as certified by the High School principal',
                                'At least a 50% passing score in the SUC-administered '
                                'admission examination, as certified by the BiPSU '
                                'Admission Office',
                                'Must NOT be a TES beneficiary',
                                'For underprivileged or marginalized students: those '
                                'from indigenous groups, persons with disabilities, '
                                'students from public schools, and students from '
                                'depressed areas',
                                'Grades are not the only factor. A qualifier need be '
                                'neither indigent nor an excellent academic performer, '
                                'and may be outside the DSWD 4Ps'],
        'requirements': [   'Certification of the Senior High School grade point '
                            'average, signed by the High School principal',
                            'Certification of the admission examination score from '
                            'the BiPSU Admission Office'],
        'benefits': [   'A living allowance of ₱2,500 a month, covering meals, '
                        'transportation and other incidental expenses',
                        'Every expense UniFAST does not cover — RLE, OJT fees, '
                        'internship and the other required fees of the programme '
                        'enrolled in — shouldered by the university',
                        'Ready-made uniforms prescribed by the programme, shouldered '
                        'by the university',
                        'Free accommodation in a campus dormitory, or boarding '
                        'expenses paid by the university where no dormitory is '
                        'available',
                        'A mentor assigned to supervise academic performance and '
                        'progress through the programme',
                        'The retention policy still applies, but may be waived for a '
                        'recipient with the approval of the Board of Regents, duly '
                        'endorsed by PASUC-8'],
        'background': 'RA 10687 (UniFAST) declares quality education an inalienable '
                      'right, and state universities and CHED-recognised local '
                      'colleges are mandated to advance affirmative action '
                      'programmes that widen the chance to study for underprivileged '
                      'and marginalized students. BiPSU runs this one under the '
                      'PASUC-8 regional programme, with CHED, DepEd and DSWD Region '
                      '8. It is not a merit award: the criteria are a floor, not a '
                      'ranking, and the office identifies beneficiaries who meet '
                      'them for endorsement to PASUC-8.',
        'is_active': True},
    {   'name': 'Staff Scholarship',
        'type': 'Staff',
        'category': 'recommendation',
        'group': 'internal',
        'description': 'Tuition support for BiPSU employees with a permanent '
                       'appointment and their legitimate dependents.',
        'eligibility': 'Permanent BiPSU employee, or a legitimate dependent of one',
        'eligibility_list': [   'A faculty member or employee of the university '
                                'with a permanent appointment, OR',
                                'A qualified and legitimate dependent of one',
                                'A dependent who has already graduated with a '
                                'baccalaureate degree is disqualified'],
        'requirements': ['HR Certification'],
        'benefits': [   'Full tuition fee coverage',
                        'Miscellaneous fee exemption',
                        'Renewable each semester',
                        'Applicable to all undergraduate programs'],
        'background': 'The Staff Scholarship is a specialised programme of the '
                      'university that gives the privilege to faculty and staff and '
                      'their legitimate dependents, as approved by the Board of '
                      'Regents. It turns on the appointment being a permanent one, '
                      'and a dependent who already holds a baccalaureate degree is '
                      'outside it.',
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
        'eligibility': 'Listahanan household or a DSWD-listed priority group; '
                       'no other national grant',
        'eligibility_list': ['Filipino citizen enrolled in a first '
                             'undergraduate degree',
                             'Priority 1: part of a household in the most '
                             'recent DSWD Listahanan',
                             'Priority 2, and only while funds last: a '
                             'dependent of a solo parent on the DSWD registry '
                             '— unmarried, unemployed and 22 or under, or '
                             'older with a disability',
                             'Priority 2, and only while funds last: a member '
                             'of a household the NCIP recognises as an ICC/IP '
                             'under RA 8371',
                             'Should the Listahanan be discontinued, the '
                             'DSWD-certified 4Ps list stands in its place, '
                             'ranked by household per capita income',
                             'Not already receiving TDP, CSP or another '
                             'national student financial assistance programme',
                             'Enrolled on a programme covered by a COPC — or '
                             'an RRPA where the programme is new',
                             'Higher education only: TES for TVET follows '
                             'separate TESDA guidelines'],
        'requirements': [   'Certificate of Registration (COR) or Certificate of '
                            'Enrolment (COE)',
                            'PWD ID, if applicable',
                            'Certificate of Residency — required only of the '
                            'private-HEI category in an area with no SUC or LUC, so '
                            'never of a BiPSU grantee'],
        'benefits': [   '₱10,000 per semester — ₱20,000 for the academic '
                        'year — as a grantee of a state university',
                        'TES-3A: a further ₱5,000 per semester (₱10,000 for '
                        'the academic year) for a grantee with a disability',
                        'A further ₱5,000 per semester (₱10,000 for the '
                        'academic year) for a dependent of a solo parent, or a '
                        'member of an ICC/IP community',
                        'TES-3B: up to ₱8,000 reimbursed once towards '
                        'licensure examination costs, where the programme '
                        'requires a professional licence — claimable within '
                        'two fiscal years of graduating',
                        'SARDO: a one-off ₱10,000 where a sudden disruption '
                        "— the death or serious illness of the family's "
                        'earner, a calamity — puts a grantee at risk of '
                        'dropping out',
                        'Paid to the grantee directly by bank credit or '
                        'cheque; coursed through the university only where '
                        'neither is possible'],
        'background': 'The Tertiary Education Subsidy is the cash grant RA '
                      '10931 pairs with free tuition — for the costs that '
                      'remain once tuition is gone, and aimed at the poorest '
                      'households. It is administered by UniFAST, created '
                      'under RA 10687 as an attached agency of CHED. Places '
                      'are ranked rather than granted on request: the DSWD '
                      'Listahanan decides Priority 1, and the guidelines are '
                      'explicit that applying is in no way automatic '
                      'eligibility — every application is subject to '
                      'validation and to the funds available. These terms are '
                      'the 2026 guidelines, UniFAST Board Resolution No. '
                      '2026-012, effective 1st Semester AY 2026-2027.',
        'is_active': True},
    {   'name': 'Free Higher Education (FHE)',
        'type': 'FHE',
        'category': 'application',
        'group': 'external',
        'description': 'Free tuition and other school fees at state universities '
                       'under RA 10931.',
        'eligibility': 'Enrolled at a state university in a first '
                       'undergraduate degree',
        'eligibility_list': ['Filipino citizen enrolled at a state university '
                             'or a CHED-recognised LUC',
                             'Has not already earned a bachelor’s degree',
                             'Meets the university’s own admission and '
                             'retention policy',
                             'A student who does not qualify is charged '
                             'tuition and other school fees as the Governing '
                             'Board sets them'],
        'requirements': ['Certificate of Enrollment'],
        'benefits': [   'No tuition at a state university',
                        'No miscellaneous or other school fees',
                        'First copy of the school ID, library ID and student '
                        'handbook free — repeat copies are charged the usual '
                        'fee',
                        'Held alongside any other grant: the Tulong Dunong '
                        'guidelines name Free Higher Education as an explicit '
                        'exception to the bar on holding more than one '
                        'government grant'],
        'background': 'Free Higher Education is the universal benefit created '
                      'by RA 10931, the Universal Access to Quality Tertiary '
                      'Education Act. It is not awarded to a shortlist: every '
                      'qualified student enrolled at a state university '
                      'already has it, which is why there is nothing here to '
                      'apply for and nothing for the office to verify. It is '
                      'also the one grant the Tulong Dunong guidelines name as '
                      'an exception to the bar on holding more than one '
                      'government grant, so it sits alongside whatever else a '
                      'student is awarded. The eligibility conditions the 2026 '
                      'deck sets out in full are on slides the office should '
                      'read beside this — what is listed here is the part '
                      'stated in text.',
        'is_active': True},
    {   'name': 'SUC-TDP (Tulong Dunong for SUCs)',
        'type': 'SUC-TDP',
        'category': 'application',
        'group': 'external',
        'description': 'The Tulong Dunong grant-in-aid as administered for state '
                       'universities and colleges.',
        'eligibility': 'First undergraduate degree at a state university; no '
                       'other national grant',
        'eligibility_list': ['Enrolled in a first undergraduate degree at a '
                             'state university',
                             'Continuing grantees hold a TDP award number from '
                             'a term before AY 2026-2027',
                             'Meets the university’s own admission and '
                             'retention policy',
                             'Holds no other national government grant — Free '
                             'Higher Education does not count against this, '
                             'nor does one-off aid such as DSWD AICS',
                             'Enrolled for at least two terms in the academic '
                             'year, with no term missed without an approved '
                             'leave of absence',
                             'Completes the degree within the maximum '
                             'residency rule plus one year'],
        'requirements': ['COR/COE', 'Certificate of Indigency'],
        'benefits': [   '₱7,500 per semester — ₱15,000 for the academic year, '
                        'at the same rate as Tulong Dunong, which these '
                        'guidelines cover state universities under',
                        'Held alongside Free Higher Education, which the '
                        'guidelines name as an exception to the bar on holding '
                        'more than one government grant',
                        'Paid to the grantee directly by bank credit or '
                        'cheque; coursed through the university only where '
                        'neither is possible',
                        'Released within 15 working days of the university '
                        'receiving the funds'],
        'background': 'The state-university line of Tulong Dunong, governed by '
                      'the same 2026 guidelines as TDP — UniFAST Board '
                      'Resolution No. 2026-012, effective 1st Semester AY '
                      '2026-2027 — which cover SUCs, CHED-recognised LUCs and '
                      'private HEIs together. It is reported and billed on its '
                      'own line, and like TDP it is appropriated a year at a '
                      'time rather than guaranteed to graduation.',
        'is_active': True},
    {   'name': 'Junior Level Science Scholarship (JLSS)',
        'type': 'JLSS',
        'category': 'recommendation',
        'group': 'external',
        'description': 'DOST-SEI scholarship taken up on entry to the third year '
                       'of an S&T degree.',
        'eligibility': 'Entering 3rd year of an S&T course, passed the JLSS exam',
        'eligibility_list': [   'Entering the third year of a science or '
                                'technology degree',
                                'Must pass the JLSS qualifying examination',
                                'Filipino citizen',
                                'RA 10612 track: fast-tracks graduates in the '
                                'sciences, mathematics and engineering who will go '
                                'on to teach science and mathematics in a secondary '
                                'school',
                                'RA 7687 track (Science and Technology Scholarship '
                                'Act of 1994): the family’s socio-economic status '
                                'must not exceed the set cut-off values, and the '
                                'course must be a priority field',
                                'Merit track (DOST-SEI): awarded on high aptitude in '
                                'science and mathematics',
                                'BiPSU’s DOST priority courses are BSCE, BSCS, BSCpE, BSEE, BSIS, '
                                'BSME, BSEd Mathematics and BSEd Science'],
        'requirements': ['JLSS application form', 'Certificate of Grades',
                         'Certificate of Enrollment'],
        'benefits': [   'Tuition and fees',
                        'Monthly stipend',
                        'Book allowance'],
        'background': 'The Junior Level Science Scholarship is DOST-SEI\u2019s '
                      'entry point for students who reach the third year of an '
                      'S&T degree without an undergraduate DOST scholarship. It '
                      'is a separate programme from the S&T Undergraduate '
                      'Scholarships, which is why it is listed on its own. It '
                      'finances talented and deserving students in their third year '
                      'so that the country keeps an adequate supply of qualified '
                      'S&T people. It runs under three tracks — RA 10612, RA 7687 '
                      'and Merit — and is applied for in the same four DOST-SEI '
                      'steps as the undergraduate scholarship, ending in the choice '
                      'of a test centre.',
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

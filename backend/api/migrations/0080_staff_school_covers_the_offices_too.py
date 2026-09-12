"""An employee's School may be an office that teaches nobody.

A choices-only change, so nothing in the database moves: ``choices`` is
validation and a dropdown, not a column type. Every school already recorded
stays exactly as it reads.

``StaffProfile.school`` was validated against BIPSU_SCHOOLS, which is the list a
*student* enrols in. Non-teaching personnel are assigned to the
vice-presidential clusters, the two lifelong-learning offices and the library,
and none of those is a school; the graduate and professional schools, the
Biliran campus's teacher-education unit and NSTP are not on the student list
either, because none of them grants an undergraduate degree through
BIPSU_COURSES and the Course dropdown is built from that.

So the staff side gets its own list — BIPSU_STAFF_UNITS — which is the student
list plus both of those groups. See api/constants.py.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0079_application_and_renewal_windows'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staffemployment',
            name='school',
            field=models.CharField(blank=True, choices=[('School of Technologies and Computer Studies', 'School of Technologies and Computer Studies'), ('School of Engineering', 'School of Engineering'), ('School of Nursing and Health Sciences', 'School of Nursing and Health Sciences'), ('School of Criminal Justice Education', 'School of Criminal Justice Education'), ('School of Tourism and Hospitality Management', 'School of Tourism and Hospitality Management'), ('School of Arts and Sciences', 'School of Arts and Sciences'), ('School of Teacher Education', 'School of Teacher Education'), ('School of Business and Management', 'School of Business and Management'), ('School of Law and Governance', 'School of Law and Governance'), ('School of Graduate Studies', 'School of Graduate Studies'), ('School of Agri-Industries and Natural Resource Management', 'School of Agri-Industries and Natural Resource Management'), ('School of Teacher Education Biliran Campus', 'School of Teacher Education Biliran Campus'), ('National Service Training Program', 'National Service Training Program'), ('Academic Affairs & Lifelong Learning', 'Academic Affairs & Lifelong Learning'), ('Research, Innovation, and Social Impact', 'Research, Innovation, and Social Impact'), ('Student, Internationalization & Strategic Partner', 'Student, Internationalization & Strategic Partner'), ('Administration, Finance, & Sustainable Management', 'Administration, Finance, & Sustainable Management'), ('Office of Advance and Accessible Lifelong Learning', 'Office of Advance and Accessible Lifelong Learning'), ('Office of Teaching, Learning, and Curriculum Effectiveness', 'Office of Teaching, Learning, and Curriculum Effectiveness'), ('Center for Learning Resources', 'Center for Learning Resources')], max_length=100),
        ),
    ]

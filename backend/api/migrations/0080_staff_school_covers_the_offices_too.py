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

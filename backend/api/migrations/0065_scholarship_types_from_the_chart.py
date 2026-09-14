from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0064_tes_liquidation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='importedscholar',
            name='scholarship_type',
            field=models.CharField(choices=[('Academic', 'Academic Scholarship'), ('TDP', 'TDP Scholarship'), ('SUC-TDP', 'SUC-TDP Scholarship'), ('DOST', 'DOST S&T Undergraduate Scholarship'), ('JLSS', 'DOST Junior Level Science Scholarship'), ('CHED', 'CHED Scholarship'), ('CoScho', 'CoScho Scholarship'), ('Sports', 'Sports Scholarship'), ('GSIS', 'GSIS Scholarship'), ('Affirmative', 'Affirmative Scholarship'), ('Staff', 'BiPSU Staff Scholarship')], max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarlistimport',
            name='scholarship_type',
            field=models.CharField(choices=[('Academic', 'Academic Scholarship'), ('TDP', 'TDP Scholarship'), ('SUC-TDP', 'SUC-TDP Scholarship'), ('DOST', 'DOST S&T Undergraduate Scholarship'), ('JLSS', 'DOST Junior Level Science Scholarship'), ('CHED', 'CHED Scholarship'), ('CoScho', 'CoScho Scholarship'), ('Sports', 'Sports Scholarship'), ('GSIS', 'GSIS Scholarship'), ('Affirmative', 'Affirmative Scholarship'), ('Staff', 'BiPSU Staff Scholarship')], max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarshiplinkrequest',
            name='scholarship_type',
            field=models.CharField(choices=[('Academic', 'Academic Scholarship'), ('TDP', 'TDP Scholarship'), ('SUC-TDP', 'SUC-TDP Scholarship'), ('DOST', 'DOST S&T Undergraduate Scholarship'), ('JLSS', 'DOST Junior Level Science Scholarship'), ('CHED', 'CHED Scholarship'), ('CoScho', 'CoScho Scholarship'), ('Sports', 'Sports Scholarship'), ('GSIS', 'GSIS Scholarship'), ('Affirmative', 'Affirmative Scholarship'), ('Staff', 'BiPSU Staff Scholarship')], max_length=50),
        ),
    ]

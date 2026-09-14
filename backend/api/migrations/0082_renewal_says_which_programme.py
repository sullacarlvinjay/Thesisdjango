from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0081_staff_unit_is_typed_not_picked'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicrenewal',
            name='scholarship_type',
            field=models.CharField(choices=[('Academic', 'Academic Scholarship'), ('TDP', 'TDP Scholarship'), ('SUC-TDP', 'SUC-TDP Scholarship'), ('DOST', 'DOST S&T Undergraduate Scholarship'), ('JLSS', 'DOST Junior Level Science Scholarship'), ('CHED', 'CHED Scholarship'), ('CoScho', 'CoScho Scholarship'), ('Sports', 'Sports Scholarship'), ('GSIS', 'GSIS Scholarship'), ('Affirmative', 'Affirmative Scholarship'), ('Staff', 'BiPSU Staff Scholarship')], default='Academic', help_text='Which programme this submission renews.', max_length=50),
        ),
    ]

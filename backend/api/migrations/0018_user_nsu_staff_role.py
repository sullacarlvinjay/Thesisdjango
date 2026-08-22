from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_affirmativerecommendation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('student', 'Student'),
                    ('nsu_staff', 'NSU Staff'),
                    ('vpsea', 'VPSEA Admin'),
                    ('unifast', 'UniFAST Admin'),
                    ('super', 'Super Admin'),
                ],
                default='student',
                max_length=20,
            ),
        ),
    ]

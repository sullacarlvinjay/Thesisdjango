from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0080_staff_school_covers_the_offices_too'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staffemployment',
            name='school',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]

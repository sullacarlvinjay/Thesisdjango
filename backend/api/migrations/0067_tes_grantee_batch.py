from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0066_scholarship_logo_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='tesapplication',
            name='batch',
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
    ]

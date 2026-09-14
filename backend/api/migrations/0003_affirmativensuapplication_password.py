from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_affirmativensuapplication'),
    ]

    operations = [
        migrations.AddField(
            model_name='affirmativensuapplication',
            name='password',
            field=models.CharField(default='', max_length=255),
        ),
    ]

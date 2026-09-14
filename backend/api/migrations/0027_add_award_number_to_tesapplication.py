from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_move_staff_fields_to_affirmativensuapplication'),
    ]

    operations = [
        migrations.AddField(
            model_name='tesapplication',
            name='award_number',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]

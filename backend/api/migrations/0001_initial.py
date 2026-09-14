import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Application',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('Pending Validation', 'Pending Validation'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Needs Revision', 'Needs Revision'), ('Draft', 'Draft')], default='Pending Validation', max_length=30)),
                ('remarks', models.TextField(blank=True)),
                ('submitted_at', models.DateField(auto_now_add=True)),
                ('updated_at', models.DateField(auto_now=True)),
                ('form_data', models.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name='ArchiveRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scholarship_type', models.CharField(max_length=20)),
                ('scholar_name', models.CharField(max_length=100)),
                ('course', models.CharField(max_length=50)),
                ('gwa', models.FloatField()),
                ('year', models.IntegerField()),
                ('imported_from', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='BillingRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('semester', models.CharField(max_length=20)),
                ('amount', models.FloatField()),
                ('submitted_at', models.DateField()),
                ('status', models.CharField(choices=[('Approved', 'Approved'), ('Pending Validation', 'Pending Validation'), ('Needs Revision', 'Needs Revision')], default='Pending Validation', max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='LiquidationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch', models.CharField(max_length=50)),
                ('amount', models.FloatField()),
                ('submitted_at', models.DateField()),
                ('status', models.CharField(choices=[('Approved', 'Approved'), ('Pending Validation', 'Pending Validation'), ('Needs Revision', 'Needs Revision')], default='Pending Validation', max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='Office',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=20, unique=True)),
                ('manages', models.JSONField(default=list)),
            ],
        ),
        migrations.CreateModel(
            name='Scholarship',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('type', models.CharField(choices=[('Academic', 'Academic'), ('TDP', 'TDP'), ('DOST', 'DOST'), ('CHED', 'CHED'), ('CoScho', 'CoScho'), ('Sports', 'Sports'), ('Affirmative', 'Affirmative'), ('Staff', 'Staff')], max_length=20)),
                ('category', models.CharField(choices=[('application', 'Application'), ('recommendation', 'Recommendation')], max_length=20)),
                ('description', models.TextField()),
                ('eligibility', models.TextField()),
                ('requirements', models.JSONField(default=list)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(default='2025-2026', max_length=20)),
                ('active_semester', models.CharField(default='1st Semester', max_length=20)),
                ('email_notifications', models.BooleanField(default=True)),
                ('sms_alerts', models.BooleanField(default=False)),
                ('inapp_push', models.BooleanField(default=True)),
                ('max_file_size_mb', models.IntegerField(default=5)),
                ('allowed_formats', models.CharField(default='PDF, JPG, PNG', max_length=50)),
                ('show_match_scores', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'System Settings',
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(choices=[('student', 'Student'), ('vpsea', 'VPSEA Admin'), ('unifast', 'UniFAST Admin'), ('super', 'Super Admin')], default='student', max_length=20)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ApplicationDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('file', models.FileField(upload_to='documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='api.application')),
            ],
        ),
        migrations.AddField(
            model_name='application',
            name='scholarship',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.scholarship'),
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_id', models.CharField(max_length=20, unique=True)),
                ('course', models.CharField(max_length=100)),
                ('year_level', models.IntegerField(default=1)),
                ('gwa', models.FloatField(default=0.0)),
                ('contact_number', models.CharField(blank=True, max_length=20)),
                ('address', models.CharField(blank=True, max_length=200)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, max_length=10)),
                ('family_income', models.FloatField(default=0.0)),
                ('indigenous_group', models.CharField(blank=True, max_length=100)),
                ('parent_employment', models.CharField(blank=True, max_length=100)),
                ('is_pwd', models.BooleanField(default=False)),
                ('is_athlete', models.BooleanField(default=False)),
                ('is_coconut_farmer_family', models.BooleanField(default=False)),
                ('has_other_scholarship', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Renewal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('previous_gwa', models.FloatField()),
                ('current_gwa', models.FloatField()),
                ('status', models.CharField(choices=[('Renewal Pending', 'Renewal Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Renewal Pending', max_length=20)),
                ('report_card', models.FileField(blank=True, null=True, upload_to='renewals/')),
                ('created_at', models.DateField(auto_now_add=True)),
                ('scholarship', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.scholarship')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='renewals', to='api.studentprofile')),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('success', 'Success'), ('warning', 'Warning'), ('info', 'Info')], default='info', max_length=10)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='api.studentprofile')),
            ],
        ),
        migrations.AddField(
            model_name='application',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='api.studentprofile'),
        ),
        migrations.CreateModel(
            name='TDPApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subsidy_amount', models.FloatField(default=20000)),
                ('status', models.CharField(choices=[('Pending Validation', 'Pending Validation'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Needs Revision', 'Needs Revision')], default='Pending Validation', max_length=30)),
                ('created_at', models.DateField(auto_now_add=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tdp_applications', to='api.studentprofile')),
            ],
        ),
    ]

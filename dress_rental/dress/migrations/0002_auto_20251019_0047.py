from django.db import migrations, models
import django.db.models.deletion
from django.contrib.auth.models import User

class Migration(migrations.Migration):

    dependencies = [
        ('dress', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gender', models.CharField(max_length=10, blank=True, null=True)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('phone', models.CharField(max_length=20, blank=True, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('profile_image', models.ImageField(upload_to='profile_images/', blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
        ),
    ]

# Generated by Django 4.2.11 on 2024-11-20 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='total_copies',
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
    ]
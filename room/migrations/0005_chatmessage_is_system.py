# Generated by Django 4.2.20 on 2025-06-02 08:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('room', '0004_chatmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='is_system',
            field=models.BooleanField(default=False),
        ),
    ]

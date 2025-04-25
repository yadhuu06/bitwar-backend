from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from room.models import generate_join_code  # Updated import
import uuid

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Room',
            fields=[
                ('room_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('join_code', models.CharField(default=generate_join_code, editable=False, max_length=8, unique=True)),  # Fixed default
                ('name', models.CharField(max_length=100)),
                ('topic', models.CharField(max_length=50)),
                ('difficulty', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], max_length=10)),
                ('time_limit', models.PositiveIntegerField(help_text='Time limit in minutes')),
                ('capacity', models.PositiveIntegerField(default=2)),
                ('participant_count', models.PositiveIntegerField(default=1)),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private')], default='public', max_length=10)),
                ('password', models.CharField(blank=True, max_length=128, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('archived', 'Archived')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_rooms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [  # Moved indexes here for consistency
                    models.Index(fields=['join_code'], name='room_room_join_co_a606a6_idx'),
                    models.Index(fields=['owner'], name='room_room_owner_i_d2ecca_idx'),
                    models.Index(fields=['visibility'], name='room_room_visibil_e77d70_idx'),
                    models.Index(fields=['status'], name='room_room_status_6f53d2_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='RoomParticipant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('host', 'Host'), ('participant', 'Participant')], default='participant', max_length=20)),
                ('status', models.CharField(choices=[('waiting', 'Waiting'), ('joined', 'Joined'), ('left', 'Left'), ('kicked', 'Kicked')], default='waiting', max_length=20)),
                ('ready', models.BooleanField(default=False)),
                ('ready_at', models.DateTimeField(blank=True, null=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('left_at', models.DateTimeField(blank=True, null=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participants', to='room.room')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='room_participations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['joined_at'],
                'indexes': [
                    models.Index(fields=['room', 'status'], name='room_roompa_room_id_59a1e6_idx'),
                    models.Index(fields=['room', 'user'], name='room_roompa_room_id_b398de_idx'),
                    models.Index(fields=['status'], name='room_roompa_status_fd4d3c_idx'),
                ],
                'unique_together': {('room', 'user')},
            },
        ),
    ]
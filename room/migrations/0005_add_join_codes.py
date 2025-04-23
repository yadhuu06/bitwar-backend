from django.db import migrations
import string
import random

def generate_unique_join_code(apps, schema_editor):
    Room = apps.get_model('room', 'Room')
    characters = string.ascii_uppercase + string.digits
    for room in Room.objects.all():
        while True:
            code = ''.join(random.choice(characters) for _ in range(6))
            if not Room.objects.filter(join_code=code).exists():
                room.join_code = code
                room.save()
                break

class Migration(migrations.Migration):
    dependencies = [
        ('room', '0003_alter_room_options_remove_room_id_room_join_code_and_more'),
    ]
    operations = [
        migrations.RunPython(generate_unique_join_code, reverse_code=migrations.RunPython.noop),
    ]
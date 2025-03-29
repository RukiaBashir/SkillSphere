from django.core.management.base import BaseCommand
from django.utils.timezone import now
from classes.models import Class


class Command(BaseCommand):
    help = 'Update class status based on schedule'

    def handle(self, *args, **kwargs):
        classes = Class.objects.all()
        for class_obj in classes:
            class_obj.update_status()
        self.stdout.write(self.style.SUCCESS('Successfully updated class statuses.'))

from django.db.models.signals import post_save
from django.dispatch import receiver
from books.models import CustomUser, Badge

@receiver(post_save, sender=CustomUser)
def create_user_badge(sender, instance, created, **kwargs):
    if created:
        Badge.objects.create(user=instance)

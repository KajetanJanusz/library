from django.core.management.base import BaseCommand
from books.ai import generate_and_save_image
from books.models import Book


class Command(BaseCommand):
    help = "Resave all Book instances (trigger signals/updates)"

    def handle(self, *args, **options):
        for book in Book.objects.all():
            result = generate_and_save_image(
                book.title,
                book.author
            )
            if result:
                file_name, image_content = result
                if file_name and image_content:
                    book.ai_image.save(file_name, image_content)
                    self.stdout.write(self.style.SUCCESS("All books have been re-saved."))
            else:
                self.stdout.write(self.style.ERROR("No image."))

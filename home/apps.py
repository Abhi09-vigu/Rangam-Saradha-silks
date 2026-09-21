from django.apps import AppConfig


class HomeConfig(AppConfig):
    name = 'home'

    def ready(self):
        from shop.image_utils import setup_universal_image_handling
        setup_universal_image_handling()

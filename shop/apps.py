from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = 'shop'

    def ready(self):
        import shop.signals
        from shop.image_utils import setup_universal_image_handling
        setup_universal_image_handling()


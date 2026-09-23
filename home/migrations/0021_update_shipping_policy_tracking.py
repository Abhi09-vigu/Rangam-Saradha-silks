from django.db import migrations


def update_shipping_policy_tracking(apps, schema_editor):
    CMSPage = apps.get_model('home', 'CMSPage')
    page = CMSPage.objects.filter(slug='shipping-policy').first()
    if page:
        content = page.content
        old_sentence = 'Once dispatched, a tracking ID and carrier link will be sent to your registered email and SMS.'
        new_sentence = 'Once dispatched, a tracking ID will be sent to your registered email.'
        if old_sentence in content:
            page.content = content.replace(old_sentence, new_sentence)
            page.save()


def reverse_shipping_policy_tracking(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0020_websitesetting_hero_display_mode'),
    ]

    operations = [
        migrations.RunPython(update_shipping_policy_tracking, reverse_shipping_policy_tracking),
    ]

from django.db import migrations


def update_refund_policy_content(apps, schema_editor):
    CMSPage = apps.get_model('home', 'CMSPage')
    page = CMSPage.objects.filter(slug='refund-policy').first()
    if page:
        content = page.content
        content = content.replace('within 48 hours of delivery', 'within 24 hours of delivery')
        content = content.replace('within 48 hours of receipt', 'within 24 hours of receipt')
        content = content.replace('48 hours', '24 hours')
        content = content.replace('every handcrafted pure silk saree', 'every handcrafted saree')
        content = content.replace('handcrafted pure silk saree', 'handcrafted saree')
        page.content = content
        page.save()


def reverse_refund_policy_content(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0018_alter_popup_popup_type_and_more'),
    ]

    operations = [
        migrations.RunPython(update_refund_policy_content, reverse_refund_policy_content),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_alter_product_video_file_alter_product_video_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='video_file',
            field=models.FileField(blank=True, help_text='Direct video file upload (MP4, WebM, MOV)', max_length=500, null=True, upload_to='product_videos/'),
        ),
    ]

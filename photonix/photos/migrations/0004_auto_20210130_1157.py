# Generated by Django 3.0.7 on 2021-01-30 11:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('photos', '0003_auto_20201229_1329'),
    ]

    operations = [
        migrations.AlterField(
            model_name='phototag',
            name='photo',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='photo_tags', to='photos.Photo'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='type',
            field=models.CharField(choices=[('L', 'Location'), ('O', 'Object'), ('F', 'Face'), ('C', 'Color'), ('S', 'Style'), ('G', 'Generic')], max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(choices=[('L', 'Location'), ('O', 'Object'), ('F', 'Face'), ('C', 'Color'), ('S', 'Style'), ('G', 'Generic')], db_index=True, default='P', max_length=1),
        ),
    ]

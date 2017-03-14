# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-14 23:43
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('timezone', models.CharField(max_length=64)),
                ('lon', models.FloatField()),
                ('lat', models.FloatField()),
                ('population', models.PositiveIntegerField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='WorldBorder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('area', models.IntegerField()),
                ('pop2005', models.IntegerField(verbose_name=b'Population 2005')),
                ('fips', models.CharField(max_length=2, verbose_name=b'FIPS Code')),
                ('iso2', models.CharField(max_length=2, verbose_name=b'2 Digit ISO')),
                ('iso3', models.CharField(max_length=3, verbose_name=b'3 Digit ISO')),
                ('un', models.IntegerField(verbose_name=b'United Nations Code')),
                ('region', models.IntegerField(verbose_name=b'Region Code')),
                ('subregion', models.IntegerField(verbose_name=b'Sub-Region Code')),
                ('lon', models.FloatField()),
                ('lat', models.FloatField()),
                ('mpoly', django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='city',
            name='country',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cities', to='world.WorldBorder'),
        ),
    ]

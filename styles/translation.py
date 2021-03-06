# -*- coding: utf-8 -*-

# Global imports
import csv
import logging

# Django imports
from django.conf import settings

# Local imports
from styles.models import LegendItemName

LANG_CODES = [code for code, name in settings.LANGUAGES]

logger = logging.getLogger(__name__)


def dump_translation_file(lang_code):
    filename = _get_locale_filename(lang_code)
    fields = ['slug', 'name_en', 'name_%s' % lang_code]
    _write_csv(filename, fields)


def load_translation_file(lang_code):
    filename = _get_locale_filename(lang_code)
    name_field = 'name_%s' % lang_code
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        line = 2
        for row_dict in reader:
            new_value = row_dict[name_field]
            if new_value:
                try:
                    lin = LegendItemName.objects.get(slug=row_dict['slug'])
                    if getattr(lin, name_field) != new_value:
                        setattr(lin, name_field, new_value)
                        lin.save()
                        logger.info('Updating LegendItemName(slug=%s), %s = %s' % (row_dict['slug'], name_field, new_value))
                except LegendItemName.DoesNotExist:
                    logger.warn('Slug %s not found in the db, but on line %i in the input file.' % (row_dict['slug'], line), exc_info=True)
            line += 1


def _get_locale_filename(lang_code):
    return 'styles/locale/%s/names.csv' % lang_code


def dump_default_names(filename='styles/fixtures/default_names.csv'):
    fields = ['slug', 'group', 'order', 'name_en']
    _write_csv(filename, fields)


def load_default_names(filename='styles/fixtures/default_names.csv'):
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            slug = row_dict['slug']
            lins = LegendItemName.objects.filter(slug=slug)
            if lins.count():
                row_dict.pop('slug')
                changed = {}
                for key, value in row_dict.iteritems():
                    if value and str(value) != str(getattr(lins[0], key)):
                            changed[key] = value
                if changed != {}:
                    lins.update(**changed)
                    logger.info('Updating LegendItemName(slug=%s): %s' % (slug, changed))
            else:
                logger.info('Creating LegendItemName(slug=%s)' % slug)
                data = {}
                for key, value in row_dict.iteritems():
                    if value:
                        data[key] = value
                LegendItemName(**data).save()


def _write_csv(filename, fields):
    with open(filename, 'wb') as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for row in LegendItemName.objects.order_by('slug').values_list(*fields):
            writer.writerow(row)

from __future__ import unicode_literals

from collections import defaultdict
import csv
import glob
import os

DATA_FILE = 'zipgun.db'


class FIELDS(object):
    # iso country code, 2 characters
    COUNTRY_CODE = 0
    # varchar(20)
    POSTAL_CODE = 1
    # City - varchar(180)
    PLACE_NAME = 2
    # 1. order subdivision (state) varchar(100)
    ADMIN_NAME1 = 3
    # 1. order subdivision (state) varchar(20)
    ADMIN_CODE1 = 4
    # 2. order subdivision (county/province) varchar(100)
    ADMIN_NAME2 = 5
    # 2. order subdivision (county/province) varchar(20)
    ADMIN_CODE2 = 6
    # 3. order subdivision (community) varchar(100)
    ADMIN_NAME3 = 7
    # 3. order subdivision (community) varchar(20)
    ADMIN_CODE3 = 8
    # estimated latitude (wgs84)
    LATITUDE = 9
    # estimated longitude (wgs84)
    LONGITUDE = 10
    # accuracy of lat/lng from 1=estimated to 6=centroid
    ACCURACY = 11


def _import_text_data(data_dir):
    country_postal_codes = defaultdict(lambda: dict())  # pylint: disable=W0108

    fieldnames = sorted([k for k in FIELDS.__dict__ if k.upper() == k],
                        key=lambda x: FIELDS.__dict__[x])
    for filename in glob.glob(os.path.join(data_dir, '*')):
        with open(filename) as f:
            reader = csv.DictReader(f, fieldnames=fieldnames,
                                    delimiter=str('\t'))
            for line in reader:
                postal_codes = (
                    country_postal_codes[line['COUNTRY_CODE']])
                postal_code = line['POSTAL_CODE']
                data = {
                    'region': line['ADMIN_CODE1'],
                    'city': line['PLACE_NAME'],
                    'lat': line['LATITUDE'],
                    'lon': line['LONGITUDE'],
                    'country_code': line['COUNTRY_CODE'],
                    'postal_code': postal_code,
                }
                if postal_code in postal_codes:
                    postal_codes[postal_code].update(data)
                else:
                    postal_codes[postal_code] = data
        return dict(country_postal_codes)


def _import_sql_data(data_dir):
    import sqlite3
    from sqlitedict import SqliteDict

    file_path = os.path.join(data_dir, DATA_FILE)

    # Find out what format we have
    with sqlite3.connect(file_path) as conn:
        try:
            conn.execute('select count(*) from zipgun_info')
            zipgun_info = SqliteDict(file_path, tablename='zipgun_info')
            version = zipgun_info.get('version', 0)
        except sqlite3.OperationalError:
            version = 0

    if version == 0:
        country_postal_codes = SqliteDict(file_path)
    elif version == 1:
        country_postal_codes = {}
        for country_code in zipgun_info['country_codes']:
            if country_code in country_postal_codes:
                raise ValueError('Duplicate entry found for {}'.format(
                    country_code))
            country_postal_codes[country_code] = SqliteDict(
                file_path, tablename='zg_{}'.format(country_code),
                journal_mode='OFF')
        zipgun_info.close()
    else:
        raise ValueError('Unknown data file version {}'.format(version))
    return country_postal_codes


class Zipgun(object):

    def __init__(self, data_dir, force_text=False):
        if (force_text or
                not os.path.exists(os.path.join(data_dir, DATA_FILE))):
            country_postal_codes = _import_text_data(data_dir)
        else:
            country_postal_codes = _import_sql_data(data_dir)
        self.country_postal_codes = country_postal_codes

    def lookup(self, postal_code, country_code='US'):
        postal_codes = self.country_postal_codes.get(country_code, {})
        return postal_codes.get(postal_code, {})

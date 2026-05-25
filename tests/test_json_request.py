import unittest as ut
import sqlite3 as sqlite

from autoinject import injector
import zirconium


class TestJSONUpsertDataset(ut.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @injector.inject
    def test_upsert(self, app_config: zirconium.ApplicationConfig = None):
        print(app_config.d)

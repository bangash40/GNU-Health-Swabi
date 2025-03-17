import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class HealthProcTestCase(ModuleTestCase):
    '''
    Test Health Proc module.
    '''
    module = 'health_proc'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        HealthProcTestCase))
    return suite

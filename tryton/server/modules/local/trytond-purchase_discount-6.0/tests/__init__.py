# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.purchase_discount.tests.test_purchase_discount import suite
except ImportError:
    from .test_purchase_discount import suite

__all__ = ['suite']

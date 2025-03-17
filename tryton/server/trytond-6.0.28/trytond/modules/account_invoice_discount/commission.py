# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import PoolMeta

__all__ = ['Commission']


class Commission(metaclass=PoolMeta):
    __name__ = 'commission'

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        invoice_line = super(Commission, cls)._get_invoice_line(
            key, invoice, commissions)
        # set gross_unit_price from unit_price
        invoice_line.gross_unit_price = invoice_line.unit_price
        invoice_line.discount = Decimal(0)
        return invoice_line

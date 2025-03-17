# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.config import config as config_
from trytond.modules.product import price_digits, round_price

__all__ = ['InvoiceLine', 'discount_digits']

STATES = {
    'invisible': Eval('type') != 'line',
    'required': Eval('type') == 'line',
    'readonly': Eval('invoice_state') != 'draft',
    }
DEPENDS = ['type', 'invoice_state']
discount_digits = (16, config_.getint('product', 'discount_decimal',
    default=4))


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    gross_unit_price = fields.Numeric('Gross Price', digits=price_digits,
        states=STATES, depends=DEPENDS)
    gross_unit_price_wo_round = fields.Numeric('Gross Price without rounding',
        digits=(16, price_digits[1] + discount_digits[1]), readonly=True)
    discount = fields.Numeric('Discount', digits=discount_digits,
        states=STATES, depends=DEPENDS)

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.unit_price.states['readonly'] = True
        cls.unit_price.digits = (20, price_digits[1] + discount_digits[1])

    @classmethod
    def default_discount(cls):
        return Decimal(0)

    @fields.depends('gross_unit_price', 'discount', 'unit_price')
    def update_prices(self):
        unit_price = self.unit_price
        digits = self.__class__.gross_unit_price.digits[1]
        gross_unit_price = gross_unit_price_wo_round = self.gross_unit_price

        if self.gross_unit_price is not None and self.discount is not None:
            unit_price = self.gross_unit_price * (1 - self.discount)
            unit_price = round_price(unit_price)

            if self.discount != 1:
                gross_unit_price_wo_round = unit_price / (1 - self.discount)
            gross_unit_price = round_price(gross_unit_price_wo_round)
        elif self.unit_price and self.discount:
            gross_unit_price_wo_round = self.unit_price / (1 - self.discount)
            gross_unit_price = round_price(gross_unit_price_wo_round)

        if gross_unit_price_wo_round:
            gross_unit_price_wo_round = round_price(gross_unit_price_wo_round)

        self.gross_unit_price = gross_unit_price
        self.gross_unit_price_wo_round = gross_unit_price_wo_round
        self.unit_price = unit_price

    @fields.depends(methods=['update_prices'])
    def on_change_gross_unit_price(self):
        self.update_prices()

    @fields.depends(methods=['update_prices'])
    def on_change_discount(self):
        self.update_prices()

    @fields.depends('discount', 'gross_unit_price')
    def on_change_with_amount(self):
        return super(InvoiceLine, self).on_change_with_amount()

    @fields.depends('unit_price', 'gross_unit_price', 'discount',
        methods=['update_prices'])
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()
        if self.unit_price:
            self.gross_unit_price = self.unit_price
            self.discount = Decimal(0)
            self.update_prices()
        if not self.discount:
            self.discount = Decimal(0)

    @fields.depends('unit_price', 'gross_unit_price', methods=['update_prices'])
    def on_change_quantity(self):
        try:
            super(InvoiceLine, self).on_change_quantity()
        except:
            pass
        if self.unit_price:
            self.update_prices()

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('type') != 'line':
                continue

            if vals.get('unit_price') is None:
                vals['gross_unit_price'] = Decimal(0)
                continue

            if vals.get('gross_unit_price', None) == None:
                gross_unit_price = vals.get('unit_price', Decimal('0.0'))
                if vals.get('discount') not in (None, 1):
                    gross_unit_price = gross_unit_price / (1 - vals['discount'])
                vals['gross_unit_price'] = gross_unit_price

            vals['gross_unit_price'] = round_price(Decimal(vals['gross_unit_price']))

            if not vals.get('discount'):
                vals['discount'] = Decimal(0)
        return super(InvoiceLine, cls).create(vlist)

    def _credit(self):
        line = super(InvoiceLine, self)._credit()
        for field in ('gross_unit_price', 'discount'):
            setattr(line, field, getattr(self, field))
        return line

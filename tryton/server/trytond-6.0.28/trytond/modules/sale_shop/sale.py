# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval

__all__ = ['Sale']


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    shop = fields.Many2One('sale.shop', 'Shop', required=True, domain=[
            ('id', 'in', Eval('context', {}).get('shops', [])),
            ('company', '=', Eval('company')),
            ],
        states={
            'readonly': (Eval('state') != 'draft') | Bool(Eval('number')),
        }, depends=['number', 'state', 'company'])
    shop_address = fields.Function(fields.Many2One('party.address',
            'Shop Address'), 'on_change_with_shop_address')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        shipment_addr_domain = cls.shipment_address.domain[:]
        if shipment_addr_domain:
            cls.shipment_address.domain = [
                'OR',
                shipment_addr_domain,
                [('id', '=', Eval('shop_address', 0))],
                ]
        else:
            cls.shipment_address.domain = [('id', '=', Eval('shop_address'))]
        cls.shipment_address.depends.append('shop_address')
        cls.party.on_change.add('shop')

    @classmethod
    def __register__(cls, module_name):
        table = backend.TableHandler(cls, module_name)
        # Migration from 3.8: remove reference constraint
        if not table.column_exist('number'):
            table.drop_constraint('reference_uniq')
        # Migration from 5.2: remove number constraint
        table.drop_constraint('number_uniq')

        super(Sale, cls).__register__(module_name)

    @classmethod
    def current_shop(cls):
        User = Pool().get('res.user')

        user = User(Transaction().user)
        return user.shop

    @classmethod
    def default_company(cls):
        shop = cls.current_shop()
        if shop:
            return shop.company.id
        return super().default_company()

    @classmethod
    def default_shop(cls):
        shop = cls.current_shop()
        return shop.id if shop else None

    @classmethod
    def default_invoice_method(cls, **pattern):
        shop = cls.current_shop()
        if shop and shop.sale_invoice_method:
            return shop.sale_invoice_method
        return super().default_invoice_method(**pattern)

    @classmethod
    def default_shipment_method(cls, **pattern):
        shop = cls.current_shop()
        if shop and shop.sale_shipment_method:
            return shop.sale_shipment_method
        return super().default_shipment_method(**pattern)

    @classmethod
    def default_warehouse(cls):
        shop = cls.current_shop()
        warehouse = None
        if shop and shop.warehouse:
            warehouse = shop.warehouse.id
        if not warehouse:
            warehouse = super().default_warehouse()
        return warehouse

    @classmethod
    def default_price_list(cls):
        shop = cls.current_shop()
        if not shop or not shop.price_list:
            return
        return shop.price_list.id

    @classmethod
    def default_payment_term(cls, **pattern):
        shop = cls.current_shop()
        if shop and shop.payment_term:
            return shop.payment_term.id
        return super().default_payment_term(**pattern)

    @classmethod
    def default_shop_address(cls):
        shop = cls.current_shop()
        if not shop or not shop.address:
            return
        return shop.address.id

    @fields.depends('shop', 'party')
    def on_change_shop(self):
        if not self.shop:
            return
        for fname in ('company', 'warehouse', 'currency', 'payment_term'):
            fvalue = getattr(self.shop, fname)
            if fvalue:
                setattr(self, fname, fvalue)
        if not self.party or not self.party.sale_price_list:
            self.price_list = self.shop.price_list
        if self.shop.sale_invoice_method:
            self.invoice_method = self.shop.sale_invoice_method
        if self.shop.sale_shipment_method:
            self.shipment_method = self.shop.sale_shipment_method

    @fields.depends('shop')
    def on_change_with_shop_address(self, name=None):
        return (self.shop and self.shop.address and
            self.shop.address.id or None)

    @fields.depends('shop')
    def on_change_party(self):
        super(Sale, self).on_change_party()
        if self.shop:
            if not self.price_list:
                self.price_list = self.shop.price_list
            if not self.payment_term:
                self.payment_term = self.shop.payment_term

    @classmethod
    def set_number(cls, sales):
        '''
        Fill the reference field with the sale shop or sale config sequence
        '''
        for sale in sales:
            if sale.number:
                continue
            if sale.shop and sale.shop.sale_sequence:
                sale.number = sale.shop.sale_sequence.get()
        # super() saves all sales, so we don't need to do it here
        super().set_number(sales)

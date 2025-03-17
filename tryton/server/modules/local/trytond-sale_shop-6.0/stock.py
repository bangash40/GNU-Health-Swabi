# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__all__ = ['ShipmentOut', 'ShipmentOutReturn']


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    shop_addresses = fields.Function(fields.Many2Many('party.address', None,
            None, 'Shop Addresses'),
        'on_change_with_shop_addresses')

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        delivery_addr_domain = cls.delivery_address.domain[:]
        if delivery_addr_domain:
            cls.delivery_address.domain = [
                'OR',
                delivery_addr_domain,
                [('id', 'in', Eval('shop_addresses'))],
                ]
        else:
            cls.delivery_address.domain = [
                ('id', 'in', Eval('shop_addresses')),
                ]
        if 'shop_addresses' not in cls.delivery_address.depends:
            cls.delivery_address.depends.append('shop_addresses')

    @fields.depends('warehouse')
    def on_change_with_shop_addresses(self, name=None):
        Shop = Pool().get('sale.shop')
        if not self.warehouse:
            return []
        warehouse_shops = Shop.search([
                ('warehouse', '=', self.warehouse.id),
                ])
        return [s.address.id for s in warehouse_shops if s.address]


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    shop_addresses = fields.Function(fields.Many2Many('party.address', None,
            None, 'Shop Addresses'),
        'on_change_with_shop_addresses')

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        delivery_addr_domain = cls.delivery_address.domain[:]
        if delivery_addr_domain:
            cls.delivery_address.domain = [
                'OR',
                delivery_addr_domain,
                [('id', 'in', Eval('shop_addresses'))],
                ]
        else:
            cls.delivery_address.domain = [
                ('id', 'in', Eval('shop_addresses')),
                ]
        if 'shop_addresses' not in cls.delivery_address.depends:
            cls.delivery_address.depends.append('shop_addresses')

    @fields.depends('warehouse')
    def on_change_with_shop_addresses(self, name=None):
        Shop = Pool().get('sale.shop')
        if not self.warehouse:
            return []
        warehouse_shops = Shop.search([
                ('warehouse', '=', self.warehouse.id),
                ])
        return [s.address.id for s in warehouse_shops if s.address]

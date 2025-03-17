# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from proteus import Model

__all__ = ['create_shop']


def create_shop(payment_term, product_price_list, name=None, warehouse=None,
        sequence=None, config=None):
    "Create a sale shop"
    Shop = Model.get('sale.shop', config=config)
    Sequence = Model.get('ir.sequence', config=config)
    Location = Model.get('stock.location', config=config)

    shop = Shop()
    if not name:
        name = 'My Shop'
    shop.name = name
    if not warehouse:
        warehouse, = Location.find([
            ('type', '=', 'warehouse'),
            ])
    shop.warehouse = warehouse
    shop.price_list = product_price_list
    shop.payment_term = payment_term
    if not sequence:
        sequence, = Sequence.find([
            ('name', '=', 'Sale'),
            ])
    shop.sale_sequence = sequence
    shop.sale_invoice_method = 'shipment'
    shop.sale_shipment_method = 'order'
    return shop

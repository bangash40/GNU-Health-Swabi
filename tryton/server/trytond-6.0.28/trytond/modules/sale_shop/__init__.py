# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import shop
from . import sale
from . import user
from . import stock


def register():
    Pool.register(
        shop.SaleShop,
        shop.SaleShopResUser,
        user.User,
        sale.Sale,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        module='sale_shop', type_='model')

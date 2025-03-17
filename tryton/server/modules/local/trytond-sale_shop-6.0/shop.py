# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from sql import Null, Table

from trytond.model import ModelView, ModelSQL, DeactivableMixin, fields
from trytond.pyson import If, Eval, Id
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['SaleShop', 'SaleShopResUser']


class SaleShop(DeactivableMixin, ModelSQL, ModelView):
    'Sale Shop'
    __name__ = 'sale.shop'

    name = fields.Char('Shop Name', required=True, select=True)
    users = fields.Many2Many('sale.shop-res.user', 'shop', 'user', 'Users')
    address = fields.Many2One('party.address', 'Address', domain=[
            ('party', '=', Eval('company_party')),
            ], depends=['company_party'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        domain=[('type', '=', 'warehouse')])
    currency = fields.Many2One('currency.currency', 'Currency',)
    price_list = fields.Many2One('product.price_list', "Price List",
        domain=[
            ('company', '=', Eval('company')),
        ], depends=['company'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term')
    sale_sequence = fields.Many2One(
        'ir.sequence', 'Sale Sequence', domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=', Id('sale', 'sequence_type_sale')),
            ],
        depends=['company'])
    sale_invoice_method = fields.Selection([
            (None, ''),
            ('manual', 'Manual'),
            ('order', 'On Order Processed'),
            ('shipment', 'On Shipment Sent')
            ], 'Sale Invoice Method')
    sale_shipment_method = fields.Selection([
            (None, ''),
            ('manual', 'Manual'),
            ('order', 'On Order Processed'),
            ('invoice', 'On Invoice Paid'),
            ], 'Sale Shipment Method')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ], select=True)
    company_party = fields.Function(fields.Many2One('party.party',
        "Company Party",
        context={
            'company': Eval('company'),
        }, depends=['company']),
        'on_change_with_company_party')

    @classmethod
    def __register__(cls, module_name):
        connection = Transaction().connection
        pool = Pool()
        Company = pool.get('company.company')
        Field = pool.get('ir.model.field')
        Model = pool.get('ir.model')
        shop_table = cls.__table__()
        company_table = Company.__table__()
        table_h = backend.TableHandler(cls, module_name)
        table = cls.__table__()
        field = Field.__table__()
        model = Model.__table__()
        cursor = connection.cursor()
        update = connection.cursor()

        property_exist = backend.TableHandler.table_exist('ir_property')
        if property_exist:
            property_ = Table('ir_property')
        sale_sequence_exist = table_h.column_exist('sale_sequence')
        sale_invoice_method_exist = table_h.column_exist('sale_invoice_method')
        sale_shipment_method_exist = table_h.column_exist(
            'sale_shipment_method')

        super(SaleShop, cls).__register__(module_name)
        if backend.name != 'sqlite':
            # SQLite doesn't support this query as it generates and update
            # with an alias (AS) which is not valid on SQLite
            query = shop_table.update(columns=[shop_table.currency],
                values=[company_table.currency],
                from_=[company_table],
                where=((shop_table.company == company_table.id)
                    & (shop_table.currency == Null)))
            cursor.execute(*query)

        # Migration to remove Property
        if not sale_sequence_exist and property_exist:
            cursor.execute(*property_
                .join(field, condition=property_.field == field.id)
                .join(model, condition=field.model == model.id)
                .select(
                    property_.res,
                    property_.value,
                    where=property_.res.like(cls.__name__ + ',%')
                    & (field.name == 'sale_sequence')
                    & (model.model == cls.__name__)))
            for res, value in cursor:
                id_ = int(res.split(',')[1])
                value = int(value.split(',')[1]) if value else None
                update.execute(*table.update(
                        [table.sale_sequence],
                        [value],
                        where=table.id == id_))
        if not sale_invoice_method_exist and property_exist:
            cursor.execute(*property_
                .join(field, condition=property_.field == field.id)
                .join(model, condition=field.model == model.id)
                .select(
                    property_.res,
                    property_.value,
                    where=property_.res.like(cls.__name__ + ',%')
                    & (field.name == 'sale_invoice_method')
                    & (model.model == cls.__name__)))
            for res, value in cursor:
                id_ = int(res.split(',')[1])
                value = value.split(',')[1] if value else None
                update.execute(*table.update(
                        [table.sale_invoice_method],
                        [value],
                        where=table.id == id_))
        if not sale_shipment_method_exist and property_exist:
            cursor.execute(*property_
                .join(field, condition=property_.field == field.id)
                .join(model, condition=field.model == model.id)
                .select(
                    property_.res,
                    property_.value,
                    where=property_.res.like(cls.__name__ + ',%')
                    & (field.name == 'sale_shipment_method')
                    & (model.model == cls.__name__)))
            for res, value in cursor:
                id_ = int(res.split(',')[1])
                value = value.split(',')[1] if value else None
                update.execute(*table.update(
                        [table.sale_shipment_method],
                        [value],
                        where=table.id == id_))

        # Migration from 5.2: do not require price_list
        table_h.not_null_action('price_list', action='remove')
        # Migration from 5.2: do not require payment_term
        table_h.not_null_action('payment_term', action='remove')
        # Migration from 5.2: do not require sale_invoice_method
        table_h.not_null_action('sale_invoice_method', action='remove')
        # Migration from 5.2: do not require sale_shipment_method
        table_h.not_null_action('sale_shipment_method', action='remove')
        # Migration from 5.2: do not require currency
        table_h.not_null_action('currency', action='remove')

    @staticmethod
    def default_currency():
        pool = Pool()
        Company = pool.get('company.company')
        Shop = pool.get('sale.shop')

        company_id = Shop.default_company()
        return company_id and Company(company_id).currency.id or None

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def sale_configuration():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company and self.company.party:
            return self.company.party.id
        return None


class SaleShopResUser(ModelSQL):
    'Sale Shop - Res User'
    __name__ = 'sale.shop-res.user'
    _table = 'sale_shop_res_user'

    shop = fields.Many2One('sale.shop', 'Shop', ondelete='CASCADE',
        select=True, required=True)
    user = fields.Many2One('res.user', 'User', ondelete='RESTRICT',
        required=True)

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.model import sequence_ordered
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Get
from trytond.transaction import Transaction
import logging


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    def get_multivalue(self, name, **pattern):
        pool = Pool()
        AccountRule = pool.get('account.account.rule')
        transaction = Transaction()
        context = transaction.context
        value = super().get_multivalue(name, **pattern)
        account2type = {
            'default_account_receivable': 'receivable',
            'default_account_payable': 'payable',
            'default_category_account_expense': 'expense',
            'default_category_account_revenue': 'revenue',
            'gift_card_account_expense': 'expense',
            'gift_card_account_revenue': 'revenue',
            }
        if name in account2type:
            with transaction.set_context(
                    account_type=account2type[name],
                    company=pattern.get('company', context.get('company'))):
                value = AccountRule.apply(value)
        return value


class AccountRule(sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    "Account Rule"
    __name__ = 'account.account.rule'

    company = fields.Many2One('company.company', "Company", required=True)
    start_date = fields.Date("Starting Date")
    end_date = fields.Date("Ending Date")
    type = fields.Selection([
            ('receivable', "Receivable"),
            ('stock', "Stock"),
            ('payable', "Payable"),
            ('revenue', "Revenue"),
            ('expense', "Expense"),
            ], "Type", required=True)

    origin_account = fields.Many2One('account.account', "Original Account")
    return_ = fields.Boolean(
        "Return",
        help="Check to limit to return operation.")
    tax = fields.Many2One(
        'account.tax', "Tax",
        domain=[
            ('parent', '=', None),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('type').in_(['revenue', 'expense']),
            },
        depends=['company', 'type'])

    account = fields.Many2One(
        'account.account', "Substitution Account", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        account_domain = cls._account_domain_per_type()
        for field in [cls.origin_account, cls.account]:
            field.domain = [
                ('company', '=', Eval('company', -1)),
                Get(account_domain, Eval('type'), []),
                ]
            field.depends = ['company', 'type']

    @classmethod
    def _account_domain_per_type(cls):
        return {
            'receivable': [('type.receivable', '=', True)],
            'stock': [('type.stock', '=', True)],
            'payable': [('type.payable', '=', True)],
            'revenue': [('type.revenue', '=', True)],
            'expense': [('type.expense', '=', True)],
            }

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_return_(cls):
        return False

    @classmethod
    def apply(cls, origin_account=None):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        today = Date.today()
        pattern = {
            'origin_account': origin_account.id if origin_account else None,
            'type': context.get('account_type'),
            'return_': context.get('return_', False),
            }
        date = context.get('date') or today
        rules = cls.search([
                ('company', '=', context.get('company', -1)),
                ['OR',
                    ('start_date', '=', None),
                    ('start_date', '>=', date),
                    ],
                ['OR',
                    ('end_date', '=', None),
                    ('end_date', '<=', date),
                    ],
                ])
        taxes = context.get('taxes', [])
        for rule in rules:
            if rule.tax and rule.tax.id not in taxes:
                continue
            if rule.match(pattern):
                return rule.account.current()
        return origin_account


class AccountRuleStock(metaclass=PoolMeta):
    __name__ = 'account.account.rule'

    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'invisible': Eval('type') != 'stock',
            },
        depends=['type'])


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

class InvoiceLineStock(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['warehouse'] = Eval('warehouse', -1)
        if 'warehouse' not in cls.product.depends:
            cls.product.depends.append('warehouse')
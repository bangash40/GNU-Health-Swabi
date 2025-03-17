=============
Sale Scenario
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install sale_discount Module::

    >>> config = activate_modules('sale_discount')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')

Create sale user::

    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create account user::

    >>> account_user = User()
    >>> account_user.name = 'Account'
    >>> account_user.login = 'account'
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> account_user.groups.append(account_group)
    >>> account_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name='Category')
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.account_category = account_category
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an Inventory::

    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> inventory_line = InventoryLine(product=product, inventory=inventory)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory_line.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    'done'

Sale 5 products testing several on_change calls and avoiding division by zero::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale_line.discount = Decimal('1')
    >>> sale_line.unit_price == Decimal('0.00')
    True
    >>> sale_line.discount = Decimal('0.12')
    >>> sale_line.unit_price == Decimal('8.80')
    True
    >>> sale_line.quantity = 2.0
    >>> sale_line.amount == Decimal('17.60')
    True
    >>> sale_line = sale.lines.new()
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Comment'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale_line.amount == Decimal('30.00')
    True
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('47.60')
    >>> sale_line_w_discount = sale.lines[0]
    >>> sale_line_w_discount.amount
    Decimal('17.60')
    >>> sale_line_wo_discount = sale.lines[2]
    >>> sale_line_wo_discount.amount
    Decimal('30.00')

Applying global sale discount::

    >>> sale.sale_discount = Decimal('0.15')
    >>> sale.save()
    >>> sale.reload()
    >>> sale.untaxed_amount
    Decimal('40.46')
    >>> sale_line_w_discount.reload()
    >>> sale_line_w_discount.amount
    Decimal('14.96')
    >>> sale_line_wo_discount.reload()
    >>> sale_line_wo_discount.amount
    Decimal('25.50')

Remove global sale discount::

    >>> sale.sale_discount = Decimal(0)
    >>> sale.save()
    >>> sale.reload()
    >>> sale.untaxed_amount
    Decimal('47.60')
    >>> sale_line_w_discount.reload()
    >>> sale_line_w_discount.amount
    Decimal('17.60')
    >>> sale_line_wo_discount.reload()
    >>> sale_line_wo_discount.amount
    Decimal('30.00')

Applying global sale discount::

    >>> sale.sale_discount = Decimal('0.10')
    >>> sale.save()
    >>> sale.reload()
    >>> sale.untaxed_amount
    Decimal('42.84')
    >>> sale_line_w_discount.reload()
    >>> sale_line_w_discount.amount
    Decimal('15.84')
    >>> sale_line_wo_discount.reload()
    >>> sale_line_wo_discount.amount
    Decimal('27.00')

Process sale::

    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)
    >>> invoice, = sale.invoices
    >>> invoice.origins == sale.rec_name
    True
    >>> invoice.untaxed_amount
    Decimal('42.84')

Check invoice discounts::

    >>> sale_line_w_discount.reload()
    >>> invoice_line_w_discount, = sale_line_w_discount.invoice_lines
    >>> invoice_line_w_discount.gross_unit_price
    Decimal('10.0000')
    >>> invoice_line_w_discount.discount
    Decimal('0.2080')
    >>> invoice_line_w_discount.amount
    Decimal('15.84')
    >>> invoice_line_w_discount.amount == sale_line_w_discount.amount
    True
    >>> sale_line_wo_discount.reload()
    >>> invoice_line_wo_discount, = sale_line_wo_discount.invoice_lines
    >>> invoice_line_wo_discount.gross_unit_price
    Decimal('10.0000')
    >>> invoice_line_wo_discount.discount
    Decimal('0.1000')
    >>> invoice_line_wo_discount.amount
    Decimal('27.00')
    >>> invoice_line_wo_discount.amount == sale_line_wo_discount.amount
    True
    >>> invoice.untaxed_amount
    Decimal('42.84')

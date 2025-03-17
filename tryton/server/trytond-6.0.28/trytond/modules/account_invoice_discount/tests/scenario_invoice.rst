================
Invoice Scenario
================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.product import price_digits
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install account_invoice_discount module::

    >>> config = activate_modules('account_invoice_discount')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> account_tax = accounts['tax']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta = line.relativedeltas.new(days=20)
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term

Add line defining Gross Unit Price and Discount (Unit Price is calculated)::

    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.discount = Decimal('0.2577')
    >>> line.gross_unit_price = Decimal('25.153')
    >>> line.unit_price == Decimal('18.6711')
    True
    >>> line.amount
    Decimal('18.67')

Add line defining Unit Price and Discount, Gross Unit Price is calculated::

    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('17.60')
    >>> line.discount = Decimal('0.12')
    >>> line.gross_unit_price
    Decimal('20.0000')
    >>> line.amount
    Decimal('88.00')

Add line defining a discount of 100%. Despite of the List Price of product,
after set the Discount the Unit Price is recomputed to 0.::

    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 2
    >>> line.unit_price = Decimal('20.00000000')
    >>> line.gross_unit_price = Decimal('25.153')
    >>> line.discount = Decimal('1.0')
    >>> line.unit_price == Decimal(0)
    True
    >>> invoice.save()
    >>> line = invoice.lines.pop()
    >>> invoice.lines.append(line)
    >>> abs(line.gross_unit_price.as_tuple().exponent) == price_digits[1]
    True
    >>> line.gross_unit_price
    Decimal('25.1530')
    >>> line.discount
    Decimal('1.0')
    >>> line.unit_price == Decimal(0)
    True

Check invoice totals::

    >>> invoice.untaxed_amount
    Decimal('106.67')
    >>> invoice.tax_amount
    Decimal('8.80')
    >>> invoice.total_amount
    Decimal('115.47')

Post invoice and check again invoice totals and taxes::

    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.untaxed_amount
    Decimal('106.67')
    >>> invoice.tax_amount
    Decimal('8.80')
    >>> invoice.total_amount
    Decimal('115.47')
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit)
    (Decimal('115.47'), Decimal('0.00'))
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit)
    (Decimal('0.00'), Decimal('106.67'))
    >>> account_tax.reload()
    >>> (account_tax.debit, account_tax.credit)
    (Decimal('0.00'), Decimal('8.80'))

Discounts are copied when crediting the invoice::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> credit_invoice, = credit.actions[0]
    >>> tuple(l.discount for l in credit_invoice.lines)
    (Decimal('0.2577'), Decimal('0.12'), Decimal('1.0'))
    >>> credit_invoice.untaxed_amount
    Decimal('-106.67')
    >>> credit_invoice.tax_amount
    Decimal('-8.80')
    >>> credit_invoice.total_amount
    Decimal('-115.47')

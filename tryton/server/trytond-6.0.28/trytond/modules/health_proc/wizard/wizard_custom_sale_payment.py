# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnusolidario.org>
#    Copyright (C) 2011-2016 GNU Solidario <health@gnusolidario.org>
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from datetime import datetime, timedelta
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal, And, Or, If
import logging
from trytond.config import config
from trytond.model.exceptions import ValidationError
from trytond.modules.health.core  import (get_institution, compute_age_from_dates,
                   estimated_date_from_years,
                   get_health_professional)
import requests
import traceback
from trytond.wizard.wizard import StateReport
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['CustomSalePaymentWizard']

class CustomSalePaymentWizard(Wizard):
    'Custom Sale Payment'
    __name__ = 'health.proc.sale.payment.wizard'

    start = StateView('health.proc.confirm.pos.payment.start',
        'health_proc.health_proc_confirm_pos_payment_start_form_view', [
            Button('Pay Now', 'pay_now', 'tryton-ok', default=True),
            Button('Cancel', 'end', 'tryton-ok'),
            ])

    pay_now = StateTransition()
    show_ticket_ = StateReport('sale_pos.sale_ticket')      
    other_sale_print_ = StateReport('sale_ticket_other_sale')      
    lab_sale_print_ = StateReport('sale_ticket_lab_sale')        

    def do_show_ticket_(self, action):
        data = {}
        data['id'] = self.start.sale.id
        data['ids'] = [data['id']]
        return action, data 

    def default_start(self, fields):
        Sale = Pool().get('sale.sale')
        sale = None
        discount_request = None

        if Transaction().context.get('active_model') == 'sale.sale':
            sale = Sale(Transaction().context.get('active_id'))

            if(sale):
                if sale.is_return_sale:
                    main_sale = sale.origin
                    DiscountRequest = Pool().get("anth.proc.discount.request")
                    discounts = DiscountRequest.search([
                                ('sale', '=', main_sale.id),('state', '=', 'utilized')				
                    ])

                    if(len(discounts) == 1):
                        discount_request = discounts[0]

                else:
                    DiscountRequest = Pool().get("anth.proc.discount.request")
                    discounts = DiscountRequest.search([
                                ('sale', '=', sale.id),('state', '=', 'approved')				
                    ])

                    if(len(discounts) == 1):
                        discount_request = discounts[0]

        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)        
        sale_device = user.sale_device or False
        if not sale_device:
            raise UserError(gettext('sale_payment.not_sale_device'))
        welfare_discount = 0

        if discount_request and discount_request.discount_value:
             welfare_discount = discount_request.discount_value 
        
        if sale.is_return_sale:
            if sale.welfare_discount_value:
                welfare_discount = -1 * sale.welfare_discount_value

            
        net_amount = sale.total_amount - welfare_discount

        return {
            'sale': sale.id,
            'device':sale_device.id,
            'total_amount': sale.total_amount,
            'user': user.id,
            'welfare':discount_request.id if discount_request else None,
            'welfare_discount': welfare_discount,
            'net_amount': net_amount,
            'sale_id': sale.id,
            }
        
    def transition_pay_now(self):
        Sale = Pool().get('sale.sale')
        sale = Sale(self.start.sale.id)
        pool = Pool()
        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)        
        Date = Pool().get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        StatementLine = Pool().get('account.statement.line')
        SystemConfig = Pool().get('anth.proc.system.config')
        DiscountRequest = Pool().get("anth.proc.discount.request")

        if(self.start.sale.state != 'draft'):
             raise ValidationError("The Sale is not in draft state, so it can't be paid. Plz contact I.T")
        
        advance_amount = None
        if self.start.welfare and self.start.welfare.discount_value:
             advance_amount = self.start.welfare.discount_value

        if self.start.sale.is_return_sale and self.start.sale.welfare_discount_value:
             advance_amount = -1 * self.start.sale.welfare_discount_value;
        
        if(advance_amount):
            SystemConfig = Pool().get('anth.proc.system.config')
            statement_id = -1
            AccountStatement = Pool().get('account.statement')

            discount_request = self.start.welfare
            if self.start.sale.is_return_sale:
                DiscountRequest.write([discount_request],{'state': 'returned'})
            else:
                DiscountRequest.write([discount_request],{'state': 'utilized'})

            device = user.sale_device
            if not device:
                    raise ValidationError("No Sale Device is attached to this user; advance can not be recorded.")

            journals = [j.id for j in device.journals]
            stmts = AccountStatement.search([
                        ('journal', 'in', journals),
                        ('state', '=', 'draft'),
                        ], order=[
                        ('date', 'ASC'),
                        ])
            if len(stmts) == 1:
                    logging.info(stmts[0].id)
                    statement_id = stmts[0].id
            else:
                    raise ValidationError('The statement for the user is not opened yet')

            sysConfig = SystemConfig(1);
            description = ""
        
            Sale.write([sale], {'sale_date': Date.today(),'is_welfare_sale': True,'welfare_discount_value': self.start.welfare_discount})

            sale = Sale(self.start.sale.id)
            p = Sale.quote([sale])
            
            sale = Sale(self.start.sale.id)
            p = Sale.confirm([sale])

            sale = Sale(self.start.sale.id)
            p = Sale.process([sale])

            # adding advance line in the draft invoice created for this sale
            final_invoice_id = -1
            SaleLine = Pool().get('sale.line')
            the_sale_lines = SaleLine.search([
                            ('sale', '=', sale.id),		
                        ])

            InvoiceLine = Pool().get('account.invoice.line')
            invoice_line = None
            invoice_line = InvoiceLine.search(['origin', '=', "sale.line," + str(the_sale_lines[0].id)])

            logging.info(invoice_line)
            final_invoice_id = invoice_line[0].invoice.id
            # setting the invoice field patient - its not working
            Invoice = Pool().get("account.invoice")
            final_invoice_obj = Invoice(final_invoice_id)            

            donation_exp_journal = 9
            company_id = Transaction().context.get('company')

            period_id = Period.find(company_id, date=Date.today())
            move = Move(
                period=period_id,
                journal=sysConfig.donation_journal_id,
                date=Date.today(),
                origin=final_invoice_obj,
                company=company_id,
                description='Moved funds from donation to patient depoist account',
            )
            Move.save([move])
            MoveLine = pool.get('account.move.line')

            second_currency = None
            amount_second_currency = None

            description = ''
            donation_exp_account = 19
            dep_move_line =  MoveLine(
                debit=advance_amount,
                credit=0,
                account=sysConfig.donation_expense_account_id,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                description=description,
                move=move.id,
            )
            MoveLine.save([dep_move_line])

            description = ''
            donation_as_patient_advance = 20
            dep_move_line =  MoveLine(
                debit=0,
                credit=advance_amount,
                account=sysConfig.donation_as_patient_advance_account_id,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                description=description,
                party=sale.party.id,
                move=move.id,
            )
            MoveLine.save([dep_move_line])

            Move.post([move])

            InvoiceLine = Pool().get('account.invoice.line')
            invoiceLine = [{'type':'line', 
                    'description':'Less welfare discount forpatient MRNO:' + sale.party.ref , 
                    'quantity':1, 
                    'unit_price':advance_amount * -1,
                    'invoice': final_invoice_id,
                    'account': sysConfig.donation_as_patient_advance_account_id,
                    'party': sale.party.id,}]
            InvoiceLine.create(invoiceLine)

        SalePaymentWizard = pool.get('sale.payment', type='wizard')
        sale_device = user.sale_device or False
        if not sale_device:
            raise UserError("No Sale Device found for this user. Contact I.T.")
        
        if advance_amount and sale.total_amount < advance_amount:
             if not sale.is_return_sale:
                raise UserError("The amaount payable is found less than the approved welfare discount. Contact I.T")

        #amount_charged = sale.total_amount - sale.paid_amount if sale.paid_amount else sale.total_amount
        fields =  {
            'journal': sale_device.journal.id if sale_device.journal else None,
            'journals': [j.id for j in sale_device.journals],
            'payment_amount': sale.total_amount - advance_amount if advance_amount else sale.total_amount,
            'currency_digits': sale.currency_digits,
            'party': sale.party.id,
            }

        session_id, _, _ = SalePaymentWizard.create()
        context = {
                'active_ids': [self.start.sale.id],
                'active_id': self.start.sale.id,
                'active_model': 'sale.sale',
                }

        with Transaction().set_context(**context):
            SalePaymentWizard.execute(session_id, {'start': fields}, 'pay_')

        try:
            SalePaymentWizard.delete(session_id)
        except:
             logging.error("some error while deleting wizard------------------")
 
        Sale.workflow_to_end([sale])

        if sale.sale_report == 'other_sales':
            return 'other_sale_print_'
        else:
            if sale.sale_report == 'lab_sales':
                return 'lab_sale_print_'
            else:
                return 'show_ticket_'

    def do_other_sale_print_(self, action):
        data = {}
        data['id'] = self.start.sale.id
        data['ids'] = [data['id']]
        return action, data            

    def do_lab_sale_print_(self, action):
        data = {}
        data['id'] = self.start.sale.id
        data['ids'] = [data['id']]
        return action, data     
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
from datetime import datetime
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.pool import Pool
import logging
from trytond.model.exceptions import ValidationError



__all__ = ['GetPatientAdvanceStart', 'GetPatientAdvance']

class GetPatientAdvanceStart(ModelView):
    'Create Patient Sale Start'
    __name__ = 'gnuhealth.patient.sale.create.start'

    amount = fields.Numeric('Advance Amount', help='Amount for which invoice will be created')

class GetPatientAdvance(Wizard):
    'Create Patient Sale'
    __name__ = 'gnuhealth.patient.advance.get'

    start = StateView('gnuhealth.patient.sale.create.start',
        'health_proc.patient_sale_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Invoice for Advance', 'request', 'tryton-ok', default=True),
            ])
    request = StateTransition()

    @classmethod
    @ModelView.button_action('account_invoice.report_invoice')
    def printInvoiceAdvance(cls, invoices):
        pass

    def transition_request(self):

	#creating sale and sale lines for the imagaing tests in this request
        Patient = Pool().get('gnuhealth.patient')
        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')

        SystemConfig = Pool().get('anth.proc.system.config')
        StatementLine = Pool().get('account.statement.line')
        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)
        statement_id = -1
        AccountStatement = Pool().get('account.statement')

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
        #if not statement_journal:
        #        raise ValidationError('No statement jounral found for the user. Contact IT department for configuration.')

        #stmts = AccountStatement.search([('journal', '=', user.statement_journal.id) ,( 'state', '=', 'draft'),])
        if len(stmts) == 1:
                logging.info(stmts[0].id)
                statement_id = stmts[0].id
        else:
                raise ValidationError('The statement for the user is not opened yet')

        sysConfig = SystemConfig(1);
        description = ""

        pp = Patient(self.start.patient)
        if self.start.inpatient_registration_code:
                inpatient = InpatientRegistration(self.start.inpatient_registration_code)
                if inpatient.final_invoice_id:
                        raise ValidationError('The Final invoice for this inpatient record is already created. No more advance can be booked from here.')
                description = 'advance from patient MRNO:' + pp.name.ref + ", Inpatient Code: " + inpatient.name

        Date = Pool().get('ir.date')			
        Invoice = Pool().get('account.invoice')
        InvoiceLine = Pool().get('account.invoice.line')
        invoiceLine = [{'type':'line', 
		        'description':description, 
		        'quantity':1, 
		        'unit_price':self.start.amount,
		        'account': sysConfig.patient_advance_account_id,
		        'party': pp.name.id,}]
        invoices = Invoice.create([{'company':1,
	        'payment_term':sysConfig.advance_payment_term_id, 
	        'invoice_date': Date.today(),
	        'accounting_date': Date.today(),
	        'currency':1,
	        'party':pp.name.id,
	        'invoice_address':pp.name.addresses[0],
	        'journal':sysConfig.advance_invoice_journal_id,
	        'account':sysConfig.invoice_account_id,
	        'lines': [('create', invoiceLine)],	
	

	        }])

        Invoice.post(invoices)
        #Invoice.paid(invoices)

        logging.info("============================== invice id generated")
        logging.info(invoices[0].id)

        #StatementLine.create([{'statement':7,'date':Date.today(),'amount':self.start.amount,'party':pp.name.id,'account':5, 'invoice':invoices[0].id-40}])
        stmtLine = {'statement':statement_id,'date':Date.today(),'amount':self.start.amount,'party':pp.name.id, 'line_type': 'ipd_advance', 'sale_type': 'ipd',
		        'account':sysConfig.advance_account_for_statement, 'invoice':invoices[0].id, 'description': 'advance from patient MRNO:' + pp.name.ref + ", Inpatient Code: " + inpatient.name}
        logging.info(stmtLine)
        StatementLine.create([stmtLine])

        if self.start.inpatient_registration_code:
                InpatientAdvanceInvoice = Pool().get('gnuhealth.inpatient.advance.invoice')
                invoices = InpatientAdvanceInvoice.create([{'name':self.start.inpatient_registration_code,'invoice':invoices[0].id,}])

        #self.printInvoiceAdvance(invoices)
        return 'end'

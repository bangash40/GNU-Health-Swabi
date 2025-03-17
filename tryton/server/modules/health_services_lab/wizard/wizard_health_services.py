# Copyright (C) 2008-2023 Luis Falcon <lfalcon@gnusolidario.org>
# Copyright (C) 2011-2023 GNU Solidario <health@gnusolidario.org>
# SPDX-FileCopyrightText: 2008-2023 Luis Falcón <falcon@gnuhealth.org>
# SPDX-FileCopyrightText: 2011-2023 GNU Solidario <health@gnusolidario.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from trytond.model import ModelView, fields
from trytond.pyson import Eval, Equal
from trytond.wizard import Wizard, StateAction
from trytond.wizard import Wizard, StateTransition, StateView, Button, StateAction

from trytond.pool import Pool
import logging
from trytond.transaction import Transaction
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal, And, Or, If

from trytond.wizard.wizard import StateReport
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['RequestPatientLabTestStart', 'RequestPatientLabTest']


# Include services in the wizard
class RequestPatientLabTestStart(ModelView):
    'Request Patient Lab Test Start'
    __name__ = 'gnuhealth.patient.lab.test.request.start'

    ungroup_tests = fields.Boolean(
        'Ungroup',
        help="Check if you DO NOT want to include each individual lab test"
             " from this order in the lab test generation step."
             " This is useful when some services are not provided in"
             " the same institution.\n"
             "In this case, you need to individually update the service"
             " document from each individual test")

    service = fields.Many2One(
        'gnuhealth.health_service', 'Service',
        domain=[('patient', '=', Eval('patient'))], depends=['patient'],
        states={'readonly': Equal(Eval('state'), 'done')},
        help="Service document associated to this Lab Request")



class RequestPatientLabTest(Wizard):
    'Request Patient Lab Test'
    __name__ = 'gnuhealth.patient.lab.test.request'

    open_ = StateAction('sale_pos.act_sale_form')

    confirm_payment = StateView('health.proc.confirm.pos.payment.start',
        'health_proc.health_proc_confirm_pos_payment_start_form_view', [
            Button('Pay Now', 'pay_now', 'tryton-ok', default=True),
            Button('Open Sale', 'open_', 'tryton-ok'),
            Button('Close', 'end', 'tryton-ok'),
            ])
                
    
    pay_now = StateTransition()
    open_ = StateAction('sale_pos.act_sale_form')
    show_ticket_ = StateReport('sale_ticket_lab_sale')      

    def do_show_ticket_(self, action):
        data = {}
        data['id'] = self.start.sale_id
        data['ids'] = [data['id']]
        return action, data     

    def default_confirm_payment(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(self.start.sale_id)

        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)        
        sale_device = user.sale_device or False
        if not sale_device:
            raise UserError(gettext('sale_payment.not_sale_device'))
        
        return {
            'sale': self.start.sale_id,
            'device':sale_device.id,
            'total_amount': sale.total_amount,
            'user': user.id,
            'welfare':None,
            'welfare_discount': 0,
            'net_amount': sale.total_amount,
            }
        
    def transition_pay_now(self):
        Sale = Pool().get('sale.sale')
        sale = Sale(self.start.sale_id)
        pool = Pool()
        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)        
        Date = Pool().get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        StatementLine = Pool().get('account.statement.line')
        SystemConfig = Pool().get('anth.proc.system.config')

        advance_amount = None

        if(advance_amount):
            logging.info("Advance Managemnt section")

        SalePaymentWizard = pool.get('sale.payment', type='wizard')
        sale_device = user.sale_device or False
        if not sale_device:
            raise UserError("No Sale Device found for this user. Contact I.T.")

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
                'active_ids': [self.start.sale_id],
                'active_id': self.start.sale_id,
                'active_model': 'sale.sale',
                }

        with Transaction().set_context(**context):
            SalePaymentWizard.execute(session_id, {'start': fields}, 'pay_')

        try:
            SalePaymentWizard.delete(session_id)
        except:
             logging.error("some error while deleting wizard------------------")
 
        return 'show_ticket_'


    def generate_code(self, **pattern):
        Config = Pool().get('gnuhealth.sequences')
        config = Config(1)
        sequence = config.get_multivalue(
            'lab_request_sequence', **pattern)
        if sequence:
            return sequence.get()

    def append_services(self, labtest, service):
        """ If the ungroup flag is not set, append the lab test
            to the associated health service
        """
        HealthService = Pool().get('gnuhealth.health_service')

        hservice = []

        service_data = {}
        service_lines = []

        # Add the labtest to the service document

        service_lines.append(('create', [{
            'product': labtest.product_id.id,
            'desc': labtest.product_id.rec_name,
            'qty': 1
            }]))

        hservice.append(service)
        service_data['service_line'] = service_lines

        HealthService.write(hservice, service_data)

    def transition_request(self):
        PatientLabTest = Pool().get('gnuhealth.patient.lab.test')
        request_number = self.generate_code()
        lab_tests = []
        for test in self.start.tests:
            lab_test = {}
            lab_test['request'] = request_number
            lab_test['name'] = test.id
            lab_test['patient_id'] = self.start.patient.id
            if self.start.doctor:
                lab_test['doctor_id'] = self.start.doctor.id
            if self.start.context:
                lab_test['context'] = self.start.context.id
            lab_test['date'] = self.start.date
            lab_test['urgent'] = self.start.urgent
            
            logging.warning("================= inpatient reg code received in health_services module: " + str(self.start.inpatient_registration_code))
            lab_test['inpatient_registration_code'] = self.start.inpatient_registration_code.id if self.start.inpatient_registration_code else None

            lab_test['payment_mode'] = self.start.payment_mode if self.start.payment_mode else None
            lab_test['insurance_company'] = self.start.insurance_company.id if self.start.insurance_company else None
            lab_test['insurance_plan'] = self.start.insurance_plan.id if self.start.insurance_plan else None

            User = Pool().get('res.user')
            user = User(Transaction().user)	        
            if user.health_center:
                lab_test['health_center'] = user.health_center.id

            if self.start.service:
                lab_test['service'] = self.start.service.id
                # Append the test directly to the health service document
                # if the Ungroup flag is not set (default).
                if not self.start.ungroup_tests:
                    self.append_services(test, self.start.service)
            lab_tests.append(lab_test)

        created_requests = PatientLabTest.create(lab_tests)
        #set sale_id
        if(created_requests and len(created_requests) >= 1):
            SaleLine = Pool().get("sale.line")
            for test_req in created_requests:
                if test_req.sale_line:
                    foundSaleLine = SaleLine(test_req.sale_line)
                    if foundSaleLine.sale.sale_type in ['opd', 'er']:
                        self.start.sale_id = foundSaleLine.sale.id        

        #if it is an OPD sale then, open the Sale in the End
        try:
            if self.start.sale_id:
                return 'confirm_payment'
        except:
            logging.info("there is some error while finishing Lab test request")

        return 'end'
    

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([('id', '=', self.start.sale_id)])

        return action, {}
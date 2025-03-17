# Copyright (C) 2008-2023 Luis Falcon <lfalcon@gnusolidario.org>
# Copyright (C) 2011-2023 GNU Solidario <health@gnusolidario.org>
# SPDX-FileCopyrightText: 2008-2023 Luis Falcón <falcon@gnuhealth.org>
# SPDX-FileCopyrightText: 2011-2023 GNU Solidario <health@gnusolidario.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from trytond.model import ModelView, fields
from trytond.pyson import Eval, Equal
from trytond.wizard import Wizard, StateAction
from trytond.pool import Pool
import logging
from trytond.model.exceptions import ValidationError
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal, And, Or, If

__all__ = ['RequestPatientImagingTestStart', 'RequestPatientImagingTest']


# Include services in the wizard
class RequestPatientImagingTestStart(ModelView):
    'Request Patient Imaging Test Start'
    __name__ = 'gnuhealth.patient.imaging.test.request.start'

    ungroup_tests = fields.Boolean(
        'Ungroup',
        help="Check if you DO NOT want to include each individual Dx"
             " imaging test from this order in the lab test generation step."
             " This is useful when some services are not provided in"
             " the same institution.\n"
             "In this case, you need to individually update the service"
             " document from each individual test")

    service = fields.Many2One(
        'gnuhealth.health_service', 'Service',
        domain=[('patient', '=', Eval('patient'))], depends=['patient'],
        states={'readonly': Equal(Eval('state'), 'done')},
        help="Service document associated to this Imaging Request")


class RequestPatientImagingTest(Wizard):
    'Request Patient Imaging Test'
    __name__ = 'gnuhealth.patient.imaging.test.request'

    open_ = StateAction('sale_pos.act_sale_form')

    def generate_code(self, **pattern):
        Config = Pool().get('gnuhealth.sequences')
        config = Config(1)
        sequence = config.get_multivalue(
            'imaging_req_seq', **pattern)
        if sequence:
            return sequence.get()

    def append_services(self, imgtest, service):
        """ If the ungroup flag is not set, append the img test
            to the associated health service
        """
        HealthService = Pool().get('gnuhealth.health_service')

        hservice = []

        service_data = {}
        service_lines = []

        # Add the imgtest to the service document

        service_lines.append(('create', [{
            'product': imgtest.product.id,
            'desc': imgtest.product.rec_name,
            'qty': 1
            }]))

        hservice.append(service)
        service_data['service_line'] = service_lines

        HealthService.write(hservice, service_data)

    def transition_request(self):
        ImagingTestRequest = Pool().get('gnuhealth.imaging.test.request')
        request_number = self.generate_code()
        imaging_tests = []
        for test in self.start.tests:
            imaging_test = {}
            imaging_test['request'] = request_number
            imaging_test['requested_test'] = test.id
            imaging_test['patient'] = self.start.patient.id
            if self.start.doctor:
                imaging_test['doctor'] = self.start.doctor.id
            if self.start.context:
                imaging_test['context'] = self.start.context.id
            imaging_test['date'] = self.start.date
            imaging_test['urgent'] = self.start.urgent
            imaging_test['inpatient_registration_code'] = self.start.inpatient_registration_code.id if self.start.inpatient_registration_code else None
            imaging_test['payment_mode'] = self.start.payment_mode if self.start.payment_mode else None
            imaging_test['insurance_company'] = self.start.insurance_company.id if self.start.insurance_company else None
            imaging_test['insurance_plan'] = self.start.insurance_plan.id if self.start.insurance_plan else None


            if self.start.service:
                imaging_test['service'] = self.start.service.id
                # Append the test directly to the health service document
                # if the Ungroup flag is not set (default).
                if not self.start.ungroup_tests:
                    self.append_services(test, self.start.service)

            imaging_tests.append(imaging_test)
        created_requests = ImagingTestRequest.create(imaging_tests)

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
                return 'open_'
        except:
            logging.info("there is some error while finishing imaging test request")
            
        return 'end'        

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([('id', '=', self.start.sale_id)])

        return action, {}
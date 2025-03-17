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

__all__ = ['TakeNewSampleStart', 'TakeNewSampleWizard','PhelbotomySample','PrintNewSampleStart']

class PhelbotomySample(ModelView):
    'Phelbotomy Sample'
    __name__ = 'health.proc.phelbotomy.sample'

    name = fields.Char('Tests')
    lab_requests = fields.One2Many('gnuhealth.patient.lab.test',None,'Lab Requests')    
    test_category = fields.Many2One('gnuhealth.lab.test.categories', 'Category') # it will determine the tube (yellow-top, etc)
    sample_type = fields.Many2One('anth.proc.sample.type', 'Sample-Type') # chemistory, special-chemistry, hematology, histopathology
    container_color = fields.Char('Tube Color')
    sample_point = fields.Selection((
        ('in', 'IN'),
        ('out', 'Sample Brought to Lab'),
        ('ipd', 'IPD'), 
        ('outsource', 'Out Source'),
        ), 'Sample Point', select=True)
    external_reference_no = fields.Char('Reference No.', help='Sample Additional information / reference no.') 
    copies = fields.Integer("Copies") # no. of copies required for each bar-code
    color_img = fields.Binary('Color', states ={'readonly':True})


    def get_requests_codes(self, name):
        codes = []
        for req in self.lab_requests:
             codes.append(req.name.name)
        
        return ",".join(codes)

    def get_container_img(self, name):
        if True:
            return self.sample_type.sample_container.container_color_img
    
class TakeNewSampleStart(ModelView):
    'Take New Sample'
    __name__ = 'health.proc.lab.sample.start'
    patient = fields.Many2One('gnuhealth.patient', 'Patient')
    all_patients = fields.Function(fields.One2Many('gnuhealth.patient',None,'All Patients'),'get_active_patients')   


    samples = fields.One2Many('health.proc.phelbotomy.sample', None, 'Samples', readonly=True)
    lab_requests = fields.Function(fields.One2Many('gnuhealth.patient.lab.test',None,
            'Lab Requests',
            add_remove=[],
            domain=[
                  ('patient_id', '=', Eval('patient')),
                  ('state', '=', 'draft'),
                  #(Eval('sample',-1), '=', -1)  # sample is null - no sample is attached to this lab-request
                  ('sample', '=', None)
            ],
            depends=['patient'],
            help="The Lab Requests created for this patient"),
        'get_new_requests', setter='set_new_requests')    
    
    @staticmethod
    def default_patient():
        if Transaction().context.get('active_model') == 'gnuhealth.patient':
            return Transaction().context.get('active_id')
        if Transaction().context.get('active_model') == 'gnuhealth.patient.lab.test':
            LabReq = Pool().get("gnuhealth.patient.lab.test") 
            return LabReq(Transaction().context.get('active_id')).patient_id.id   
    
    def get_active_patients(self,name):
         logging.info("===== getactive paetinet is called")
         return [1,2]
    
    created_samples = fields.One2Many('health.proc.phelbotomy.sample', None, 'Created-Samples')

    def get_new_requests(self, name):
        reqs = []
        return reqs
    
    @classmethod
    def set_new_requests(cls, requests, name, value):
        if not value:
            return

    @fields.depends('lab_requests','patient',methods=['on_change_lab_requests'])
    def on_change_patient(self):
        if self.patient:
            available_reqs = []
            LabReq = Pool().get("gnuhealth.patient.lab.test") 

            reqs = LabReq.search([('patient_id', '=', self.patient.id),('state', '=', 'draft'),('sample', '=', None)])
            for r in reqs:
                available_reqs.append(r.id)       

            self.lab_requests = available_reqs 
            self.on_change_lab_requests()

    @fields.depends('lab_requests','samples')
    def on_change_lab_requests(self):
        samples = []
        for request in self.lab_requests:
            # check if a sample already exists for the same category and sample-type, if so add the lab-request to it
            found_sample = None
            for s in samples:
                  if(s['sample_type'] == request.name.sample_type.id and s['test_category'] == request.name.category.id ):
                        found_sample = s
                  
            # create list of lab-requests for this sample
            if found_sample:
                    # sample exists for this sample-type and test-cateogry, so just add the lab-request to its array of tests
                    lab_reqs = []
                    lab_reqs.append({'id': request.id})
                    updated_lab_reqs = found_sample['lab_requests'] + tuple(lab_reqs)
                    found_sample['lab_requests'] = updated_lab_reqs
                    found_sample['name'] = found_sample['name'] + ", " + request.name.name
            else:
                lab_reqs = []
                lab_reqs.append({'id': request.id})

                sample = {
                    'name': request.name.name, 
                    'sample_type': request.name.sample_type.id,
                    'test_category': request.name.category.id,
                    'lab_requests': tuple(lab_reqs),
                    'container_color': request.name.sample_type.sample_container.name,
                    'sample_point': 'in',
                    'color_img': request.name.sample_type.sample_container.container_color_img,

                }

                samples.append(sample)                

        self.samples = tuple(samples)

class PrintNewSampleStart(ModelView):
    'List New Samples'
    __name__ = 'health.proc.lab.sample.print.start'
    patient = fields.Many2One('gnuhealth.patient', 'Patient')
    created_samples = fields.One2Many('health.proc.lab.sample', None, 'Created Samples', add_remove=[])

class TakeNewSampleWizard(Wizard):
    'Take New Sample Wizard'
    __name__ = 'health.proc.lab.sample.wizard'

    start = StateView('health.proc.lab.sample.start',
        'health_proc.health_proc_lab_sample_start_form_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create New Samples', 'request', 'tryton-ok', default=True),
            ])
    
    open_samples_direct_ = StateAction('health_proc.act_health_proc_lab_samples_view')    
 
    request = StateTransition()

    def transition_request(self):
        # create the lab test first 
        pool = Pool()
        LabTestCreateWizard = pool.get('gnuhealth.lab.test.create', type='wizard')
        session_id, _, _ = LabTestCreateWizard.create()

        context = {
                'active_ids': [l.id for l in self.start.lab_requests],
                'active_id': None,
                'active_model': 'gnuhealth.patient.lab.test',
                }
        with Transaction().set_context(**context):
                LabTestCreateWizard.execute(session_id, {}, 'create_lab_test')
        LabTestCreateWizard.delete(session_id)
    
        all_sample_ids = set()

        self.start.created_samples = list(all_sample_ids)
        #return 'print'
        return 'open_samples_direct_'

    def do_open_samples_direct_(self, action):
        Sample = Pool().get("health.proc.lab.sample")
        LabRequest = Pool().get("gnuhealth.patient.lab.test")

        all_sample_ids = []
        today = datetime.today().date()

        User = Pool().get('res.user')
        user = User(Transaction().user)	        
        if not user.health_center:
            raise ValidationError("No Health Center is attached with your User; please contact I.T department.")
        for sample in self.start.samples:
                # create sample
                samples = Sample.create([{
                    #'payment_term':5, 
                    'patient':self.start.patient.id,
                    'sample_type':sample.sample_type.id,
                    'test_category':sample.test_category.id,
                    'sample_point': sample.sample_point,
                    'sample_condition': 'acceptable',
                    'state': 'sample_due',
                    'sampled_on': datetime.now(),
                    'external_reference_no': sample.external_reference_no,
                    'health_center': user.health_center.id,
                }])

                # attach it to its lab-requests
                if(len(samples) == 1):
                      created_sample = samples[0]
                      all_sample_ids.append(created_sample.id)

                      for req in sample.lab_requests:
                            LabRequest.write([req], {'sample': created_sample.id})

        action['pyson_domain'] = PYSONEncoder().encode([('id', 'in', all_sample_ids)])

        return action, {}
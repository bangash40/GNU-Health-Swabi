# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <falcon@gnu.org>
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
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Bool, And, Equal, Or, In
from sql import Null
import logging
import pytz
from trytond.report import Report
import logging
import urllib, json
import relatorio.reporting

from urllib.request import urlopen, build_opener
import urllib.request
from urllib.request import Request
from urllib.parse import urlencode
import http.cookiejar

from relatorio.templates.pdf import PDFSerializer
from relatorio.templates.base import RelatorioStream
import qrcode
from io import StringIO
from trytond.model import ModelView, ModelSQL, fields
import barcode
from barcode.writer import ImageWriter

from trytond.modules.health.core import get_health_professional
from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserError
from trytond.exceptions import UserWarning
import traceback
import logging
import time
import string
import random
import qrcode
import barcode
import io


__all__ = ['GnuHealthPatientLabTest','Reagent', 'TestType', 'Lab',
    'SampleType','AnalysisSpec', 'GnuHealthLabTestCategories', 'LimsAnalyteResults','TestPdfReport',
 'AnalysisCategory', 'ResultOption', 'AnalysisService','TestTypeAnalysisService', 'AnalysisServiceResult', 'AnalysisServiceResultRange',
'WizardCreateLabTestOrder', 'RequestPatientLabTestStart','SampleBatch', 'Sample', 'SampleContainer','SampleBatchSample','TestTypeTestComponent']

##########################

class GnuHealthPatientLabTest(metaclass=PoolMeta):
    'Patient Lab Test'
    __name__ = 'gnuhealth.patient.lab.test'

    sale_line = fields.Many2One('sale.line', 'SaleLine')
    inpatient_registration_code =  fields.Many2One('gnuhealth.inpatient.registration', 'IPD Reg Code', readonly=True)
    referred_by = fields.Char('Walk In Ref. By')
    comments = fields.Char('Instructions for Pathologist', readonly=True)
    sample_details = fields.Char('Sample Details', help='Details of sample; specially required for Histopathology/Cytology Lab Tests', readonly=True)
    ar_id = fields.Function(fields.Char('LIMS ID'), 'get_ar_id')
    cancelled_by = fields.Many2One('gnuhealth.healthprofessional', 'Cancelled By',
        help="Doctor who cancelled the lab test.", select=True, readonly=True)
    cancelled_on = fields.DateTime('Cancelled On', select=True)
    admission_request_flag = fields.Boolean('Admission Request Flag')
    is_in_icu = fields.Function(fields.Boolean('Is In ICU'),'get_is_in_icu')
    is_hazardous = fields.Boolean('Hazadous Sample?')

    health_center = fields.Many2One('gnuhealth.institution', 'Health Facility', readonly=True)
    # the physical sample craeted against this request - may be same for multiple lab reuqests 
    sample = fields.Many2One('health.proc.lab.sample', 'Sample', readonly=True)

    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Patient Type', select=True
    )

    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Insurance Company',
        select=True
    )

    insurance_plan= fields.Many2One(
        'health.proc.insurance.panel.product.group', 'Insurance Plan',
        help='Insurance company plan',
        domain=[('panel', '=', Eval('insurance_company')),('product_group.group_type', '=', 'plan')],
    )   

        
    def get_specialty(self, name):
        if (self.doctor_id and self.doctor_id.main_specialty):
            specialty = self.doctor_id.main_specialty.specialty
            return specialty.rec_name

    def get_category(self, name):
        if (self.name):
                if self.name.category:
                        return self.name.category.name

    def get_ar_id(self, name):
        if self.state == 'ordered':
                Lab = Pool().get('gnuhealth.lab')
                lab = Lab.search([
		                ('request', '=', self.id),				
		                ])
                if len(lab) == 1:
                        return lab[0].ar_id

    def get_lab_tat(cls):
        tat_info = ''
        #LabRequest = Pool().get("gnuhealth.patient.lab.test")
        #found_lab_request = LabRequest.search([('sale_line','=', cls.id)])
        
        if True:
            lab = cls
            tat_info = lab.name.turnaround_time_normal

            order_date = lab.create_date

            if lab.urgent:
                if lab.name.turnaround_time_emergency:        
                    order_date = (order_date + timedelta(minutes=lab.name.turnaround_time_emergency)  )       
                else:
                    order_date = (order_date + timedelta(minutes=120)  ) 
            else:
                if lab.name.turnaround_time_normal:
                    order_date = (order_date + timedelta(minutes=lab.name.turnaround_time_normal)  )
                else:
                    order_date = (order_date + timedelta(minutes=300)  ) 


            if(lab.health_center):
                if lab.urgent:
                    if lab.health_center.turnaround_time_emergency:        
                        order_date = (order_date + timedelta(minutes=lab.health_center.turnaround_time_emergency)  )       
                else:
                    if lab.health_center.turnaround_time_normal:
                        order_date = (order_date + timedelta(minutes=lab.health_center.turnaround_time_normal)  )


        HMISUtility = Pool().get("anth.proc.hmis.utility")
        order_date = HMISUtility.format_date_time(order_date)
        tat_info = order_date.strftime('%d-%m-%y %I:%M %p')
        return tat_info
    def get_create_order_date(self):
        order_date = None
        Lab = Pool().get('gnuhealth.lab')

        result = Lab.search([
			        ('request', '=', self.id),
			        ])

        # get the create_date of the lab results record
        if len(result) > 0:
                order_date = result[0].create_date

                Company = Pool().get('company.company')

                timezone = None
                company_id = Transaction().context.get('company')
                if company_id:
                    company = Company(company_id)
                    if company.timezone:
                        timezone = pytz.timezone(company.timezone)

                order_date = datetime.astimezone(order_date.replace(tzinfo=pytz.utc), timezone)

        return order_date

    @classmethod
    @ModelView.button
    def canceltest(cls, tests):
        for test in tests:
                if test.state != 'draft':
                    raise ValidationError('The test has already been requested so it can not be cancelled')
                if test.sale_line and test.sale_line.sale.state != 'draft':
                    raise ValidationError('Payment has already been made for this test. Please contact IT/Finance Department to cancel it.')
        SaleLine = Pool().get('sale.line')
        HealthProfessional = Pool().get('gnuhealth.healthprofessional')
        cancelled_by = get_health_professional()
        for test in tests:
                line = SaleLine(test.sale_line)
                SaleLine.delete([test.sale_line])
        cls.write(tests, {
            #'state': 'cancelled', 'inpatient_registration_code': Null})

            'state': 'cancelled', 'sale_line': Null, 'cancelled_by':cancelled_by, 'cancelled_on': datetime.now()})


    @classmethod
    def __setup__(cls):
        super(GnuHealthPatientLabTest, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._order.insert(1, ('request', 'DESC'))
        cls._order.insert(2, ('name', 'ASC'))
        cls._buttons.update({
                'canceltest': {
                    'invisible': Or(Equal(Eval('state'), 'ordered'),
                    Equal(Eval('state'), 'cancelled')),
                    },
		}
	)

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('gnuhealth.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('request'):
                config = Config(1)
                values['request'] = Sequence.get_id(
                    config.lab_request_sequence.id)

        return super(GnuHealthPatientLabTest, cls).create(vlist)

    @classmethod
    def copy(cls, tests, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['request'] = None
        default['date'] = cls.default_date()
        return super(GnuHealthPatientLabTest, cls).copy(tests,
            default=default)

    @classmethod
    def search_rec_name(cls, name, clause):
        """ Search for the name, lastname, PUID, any alternative IDs,
            and any family and / or given name from the person_names
        """
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            #('request',) + tuple(clause[1:]),
            #('ar_id',) + tuple(clause[1:]),
            ('name.name',) + tuple(clause[1:]),
            ('name.code',) + tuple(clause[1:]),
            ('doctor_id.name.name',) + tuple(clause[1:]),
            ('patient_id.name.ref',) + tuple(clause[1:]),
            ('patient_id.name.alternative_ids.code',) + tuple(clause[1:]),
            ('patient_id.name.person_names.family',) + tuple(clause[1:]),            
            ('patient_id.name.person_names.given',) + tuple(clause[1:]),            
            ('patient_id.name.name',) + tuple(clause[1:]),
            ('patient_id.name.lastname',) + tuple(clause[1:]),
	    ('patient_id.name.contact_mechanisms.value',) + tuple(clause[1:]),
            ]


    @classmethod
    def create(cls, vlist):
        #creating sale and sale lines for the lab tests in this request
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        TestType = Pool().get('gnuhealth.lab.test_type')

        first = True
        cnt = 1000
        sale_id = -1
        vlist = [x.copy() for x in vlist]
        panel_patient = False
        panel_global_discount = None
        charge_labs = True
        final_vlist = []
        for values in vlist:
                logging.warning(values)
                if first:
                        pp = Patient(values.get('patient_id'))
                        if values.get('inpatient_registration_code'):
                                logging.warning("\ninpatient registration code is therere: ")
                                logging.warning(values.get('inpatient_registration_code'))
                                InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
                                inpatient = InpatientRegistration(values.get('inpatient_registration_code'))
                                if inpatient.state != 'hospitalized' and inpatient.state != 'done'  and not values.get('admission_request_flag'):
                                        raise ValidationError('The patient has not hospitalized yet or he has been discharged. Order this test as OPD Test')
			
                                if inpatient.sale_id.state == 'draft':
                                        sale_id = inpatient.sale_id
                                else:
                                        raise ValidationError('The Sale for this inpatient record is closed now. Either create new inpatient record or charge in OPD!')
                                pp = inpatient.patient
                                #sales = Sale.create([{
                                #    'currency':1,
                                #    'party':pp.name.id,
                                #    'self_pick_up':'true',
                                #    'invoice_address':pp.name.addresses[0],
                                #    'shipment_address':pp.name.addresses[0],
                                #    'description':'Sale against Lab Test by Patient MRNO: ' + str(pp.name.ref),
                                #    'sale_type': 'ipd',
                                #                    'ipd':inpatient.id,
                                #    }])
                                #sale_id = sales[0].id				
                        else:
                                Date = Pool().get('ir.date')
                                Agent = Pool().get("commission.agent")
                                HealthProf = Pool().get('gnuhealth.healthprofessional')
                                InsuranceCompany = Pool().get("health.proc.insurance.panel")
                                InsurancePlan = Pool().get("health.proc.insurance.panel.product.group")                                

                                doctor_agents = []
                                doctor_party_id = None

                                payment_mode = None
                                insurance_company = None
                                insurance_plan = None
                                panel_credit_sale = False


                                try:
                                    if values.get('doctor_id'):
                                        doctor = HealthProf(values.get("doctor_id"))
                                        doctor_agents = Agent.search([('party', '=',   doctor.name),])	
                                        doctor_party_id = doctor.name.id 	
                                    if(values.get('payment_mode')):
                                        payment_mode = values.get('payment_mode')
                                        if payment_mode == 'panel_credit':
                                            panel_credit_sale = True

                                    if(values.get('insurance_company')):
                                        insurance_company = InsuranceCompany(values.get('insurance_company'))

                                    if(values.get('insurance_plan')):
                                        insurance_plan = InsurancePlan(values.get('insurance_plan'))
                                except:
                                    logging.info(">>>>>> some error")
                                    traceback.print_exc()
                                    traceback.print_stack()

                                sales = Sale.create([{
                                    'currency':1,
                                    'party':pp.name.id,
                                    'self_pick_up':'true',
                                    #'invoice_address':pp.name.addresses[0],
                                    'invoice_address':insurance_company.name.addresses[0] if panel_credit_sale else pp.name.addresses[0],

                                    'shipment_address':pp.name.addresses[0],
                                    'description':'Sale against Lab Test by Patient MRNO: ' + str(pp.name.ref),
                                    'sale_type': 'opd',
                                    'sale_nature': 'lab',
                                    'agent': doctor_agents[0].id if len(doctor_agents) > 0 else None,
                                    'doctor': doctor_party_id,
                                    'sale_report': 'lab_sales',

                                    'payment_mode': payment_mode,
                                    'insurance_company': insurance_company.id if insurance_company else None,
                                    'invoice_party': insurance_company.name.id if panel_credit_sale else None,
                                    'insurance_plan': insurance_plan.id if insurance_plan else None,                                    

                                }])
                                sale_id = sales[0].id
                        first = False

                reqTest = TestType(values.get('name'))	
                reqProduct = Product(reqTest.product_id)

                theSale = Sale(sale_id)
               
                unit_price = reqProduct.list_price		
                gross_unit_price = reqProduct.list_price
                discount = 0

                if insurance_plan: # it is a panel sale
                    if Sale.product_price_exists_in_panel_for_plan(None,  reqProduct.id, insurance_plan):
                        sale_price = Sale.get_product_price_from_panel_for_plan(None, reqProduct.id, insurance_plan)

                        gross_unit_price = sale_price
                        unit_price = sale_price
                        discount = 0

                    else: # product is not found in Panel Price list; return Main List Price
                        gross_unit_price = reqProduct.list_price
                        unit_price = reqProduct.list_price
                        raise ValidationError("The price for this product is not set in the Insurance Plan. Contact IT Department");
               
                saleLines = SaleLine.create([{
	                'product':reqProduct.id, 
	                'sale':sale_id,
	                'unit':1,
	                'discount': discount,
	                'unit_price':unit_price,
	                'gross_unit_price': gross_unit_price,
	                'quantity':1,
	                'sequence':cnt,
	                'description':reqTest.name + " (" + values.get('request') + ")",
	                }])
                cnt = cnt + 1
                values['sale_line'] = saleLines[0].id

                # check the reqTest and update the final_vlist accordingly
                if reqTest.is_profile:
                        # get the components and add them to finla_vlist
                        # must keep the value['sale_line'] as it is
                        for component in reqTest.test_components:
                                values_copy = values.copy()
                                values_copy['name'] = component.id
                                final_vlist.append(values_copy)
                else:
                        final_vlist.append(values)				

        return super(GnuHealthPatientLabTest, cls).create(final_vlist)

class Reagent(ModelSQL, ModelView):
    'Reagent Required for the Test'
    __name__ = 'anth.reagent'

    test = fields.Many2One('gnuhealth.lab.test_type', 'Test type',
        help="Lab test type")

    product = fields.Many2One('product.product', 'Reagent/Item',
        help="Reagent / Item required used in this test")

    min_tests_possible = fields.Integer("Minimum Tests")
    max_tests_possible = fields.Integer("Maximum Tests")


class TestType(metaclass=PoolMeta):
    __name__ = 'gnuhealth.lab.test_type'

    product_id = fields.Many2One('product.product', 'Service', required=True)
    category = fields.Many2One('gnuhealth.lab.test.categories', 'Category')
    
    lims_analysis_profile_id = fields.Char('Profile Id')
    lims_sample_type_id = fields.Char('Sample Type')
    lims_spec_id = fields.Char('Spec Id')
    outsourced = fields.Boolean('Outsourced', help='Select this option when'
        ' this test is outsourced')

    outsourced_to_party = fields.Many2One('party.party', 'Outsourced To')
    turnaround_time_normal = fields.Integer("Turnaround Time (ToT Minutes)")
    turnaround_time_emergency = fields.Integer("Turnaround Time ER (ToT ER Minutes)")
    reagents = fields.One2Many('anth.reagent', 'test',
        'Reagents/Items used')

    qr_code_display = fields.Boolean('Show QR Code?', help='Select this option when'
        ' QR Code is to be displayed')
    patient_photo_display = fields.Boolean('Display Photo?', help='Select this option when'
        ' Patient Photo is to be displayed')

    paragraphic_view = fields.Boolean('Display Result in Paragraph?', help='Select this option when'
        ' the result is displayed in Paragraph instead of table.')

    show_test_type_category = fields.Boolean('Display Test Type Category as Profile Name?', help='Select this option when'
        ' the Category is displayed instead of Test Type Name')

    report_view = fields.Selection([
        (None, ''),
        ('table_view_four_columns', 'Table View 04-columns'),
        ('paragraphic_view', 'Paragraph View'),
        ('table_view_two_columns', 'Table View 02-columns'),
        ], 'Report View', select=True, sort=False)    

    services = fields.Many2Many('anth.proc.test.to.service',
        'test_type_id', 'analysis_service_id', 'Services')
    sample_type = fields.Many2One('anth.proc.sample.type', 'Sample-Type', required=True)
    price = fields.Function(fields.Numeric('Price'), 'get_test_price')
    is_profile = fields.Boolean('Profile/Package?', help="Is this test represents a Profile/Package?")
    test_components = fields.Many2Many('anth.proc.test.to.test_component',
        'test_type_id', 'component_test_type_id', 'Test Components')
    
    def get_test_price(self, name):
        dt_string = self.product_id.list_price
        return dt_string   
    
    def get_rec_name(self, name):
        return self.name
    
class Lab(metaclass=PoolMeta):
    'Lab Test'
    __name__ = 'gnuhealth.lab'

    lims_analytes = fields.Function(fields.One2Many('gnuhealth.lab.lims.analyte.result', None,
            'Analytes'), 'get_lims_analytes')
    referred_by = fields.Char('Walk In Ref. By', readonly=True)
    comments = fields.Text('Comments for Pathologist', readonly=True)
    ar_id = fields.Char('Lims Request Id', readonly=True, select=True)
    date_published = fields.DateTime('Date Published', readonly=True)
    report_path = fields.Char('Report Path', readonly=True)
    is_ready_for_upload = fields.Boolean('Ready for Upload?')
    is_report_uploaded = fields.Boolean('Report Uploaded?', readonly=True)
    request = fields.Many2One(
        'gnuhealth.patient.lab.test', 'Request',
        readonly=True)

    action_required = fields.Char('Action Required?', help='Some action/details required from patient.')
    sample_details = fields.Function(fields.Char('Sample Details'), 'get_sample_details', searcher='search_test_sample_details')
    create_query = fields.Text('Create Query', readonly=True)
    department = fields.Function(fields.Char('Department'), 'get_department', searcher='search_department')
    created_on = fields.Function(fields.Char('Order Date'), 'get_created_on')

    # Add the QR Code to the Patient
    qr = fields.Function(fields.Binary('QR Code'), 'make_qrcode')
    services_results = fields.Function(fields.One2Many('anth.proc.analysis.service.result', None,'LIMS Results'), 'get_lims_analysis_results')
    historical_results = fields.Function(fields.One2Many('gnuhealth.lab.lims.analyte.result', None,
            'Analytes'), 'get_historical_analytes')
    report_without_logo_path = fields.Char('Report Without Logo Path', readonly=True)
    old_results = []
    old_dates_display = fields.Function(fields.Char("Old Date"),'get_old_dates_display')
    hist_one_date = fields.DateTime('Hist-1-date', readonly=True)
    hist_two_date = fields.DateTime('Hist-2-date', readonly=True)
    sample_type = fields.Function(fields.Char('Sample Type'),'get_sample_type_name')
    peripheral_smear = fields.Text('Peripheral Smear')
    specimen_details = fields.Text("Specimen Details")
    clinical_details = fields.Text("Clinical Details")
    gross_examination = fields.Text("Gross Examination")
    microscopic_description = fields.Text("Microscopic Description")
    pathologis_diagnosis = fields.Text("Pathologis Diagnosis")
    qr_optional = fields.Function(fields.Binary('QR Code'), 'make_qrcode_optional')
    photo_optional = fields.Function(fields.Binary('QR Code'), 'make_photo_optional')   
    sample = fields.Function(fields.Many2One('health.proc.lab.sample','Sample'), 'get_sample_from_request')
    department = fields.Function(fields.Char('Department'), 'get_department', searcher='search_department')

    @classmethod
    def write(cls, labs, values):
       
        for lab in labs:
            if lab.state == 'validated':
                raise ValidationError("This lab result can not be updated now!")
                    
        return super(Lab, cls).write(labs, values)

    def get_department(self, name):
        if self.test:
            if self.test.category:
                return self.test.category.name

    @classmethod
    def search_department(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('test.category.name', clause[1], value))
        return res
        
    def get_sample_from_request(self, name):
        if self.request_order:
            LabRequest = Pool().get("gnuhealth.patient.lab.test")
            found_lab_request = LabRequest.search([('request','=', self.request_order)])
            if len(found_lab_request) > 0:
                if found_lab_request[0].sample:
                    return found_lab_request[0].sample.id

    def get_sample_type_name(self, name):
        dt_string = ''
        if self.test.lims_sample_type_id == 'sampletype-1':
                dt_string = 'Blood'

        if self.test.lims_sample_type_id == 'sampletype-2':
                dt_string = 'Serum'

        return dt_string
   
    def get_created_on(self, name):
        dt_string = self.create_date.strftime('%d-%b-%y %H:%M')
        return dt_string   

    def get_old_dates_display(self, name):
        dt_string = ''
        if self.hist_one_date:
                dt_string = '                       ' + self.hist_one_date.strftime('%d-%b-%y')

        if self.hist_two_date:
                dt_string += '                            ' + self.hist_two_date.strftime('%d-%b-%y')


        return dt_string

    def get_cat_ids(cls):
        cat_ids = []
        for anal in cls.lims_analytes:
                if anal.category not in cat_ids:
                        cat_ids.append(anal.category)
        return cat_ids

    def get_cat_ids_culture(cls):
        cat_ids = []
        AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")
        anal_results = AnalysisServiceResult.search([('gnuhealth_lab_id','=', cls.id)])
        for anal in anal_results:
                if anal.parent_anal_service_result:
                        final_result = ''
                        final_result = anal.parent_anal_service_result.get_final_result()
                        if final_result not in cat_ids:                                
                                cat_ids.append(final_result)
        logging.info('Returning list of bacteria found : '  + str(cat_ids))
        
        return cat_ids


    def get_historic_result_count(cls):
        dates = cls.get_historic_result_dates()
        logging.info("================= dates foud are ==========")
        logging.info(dates)
        if cls.test.paragraphic_view:
                return -1
        else:
                if cls.test.report_view:
                        if cls.test.report_view == 'paragraphic_view':
                                return -1
                        if cls.test.report_view == 'table_view_two_columns':
                                return -2
                        if cls.test.report_view == 'table_view_four_columns':
                                return len(dates)
                        if cls.test.report_view == 'table_view_culture_report':
                                return cls.find_count_flag_for_culture_report()
                else:
                        return len(dates)
        return len(dates)

    def find_count_flag_for_culture_report(cls):
        bacteria_list = cls.get_cat_ids_culture()
        logging.info("======= The bacteria list: " + str(bacteria_list))
        # for no bacteria culture report, display paragraphic report view
        if(len(bacteria_list) == 0):
                return -1
        # for single bacteria culture report
        if(len(bacteria_list) >= 1):
                return -3
        # for multiple bacteria culture report
        if(len(bacteria_list) > 5):
                return -4

    def get_historic_result_dates(cls):
        dates = []
        #analytes = cls.get_old_results()
        analytes = cls.old_results
        for an in analytes:
                if an.create_date not in dates:
                        dates.append(an.create_date)

        logging.info("================= dates foud are hist dates ==========")
        logging.info(dates)

        return dates

    def get_old_anal_result_on_date(cls, dt, service_id):
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
        logging.info("===================== dt ==== " + str(dt)  + " service id: " + str(service_id))
        for res in cls.old_results:
                logging.info("Matching ==  dt: " + str(res.create_date) + ", service: " + str(res.service.id)) 
                if res.create_date == dt and res.service.id == service_id:
                        return res.result

    def get_anal_all_old_results(cls, service_id):
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
        logging.info(" service id: " + str(service_id))
        all_results = []
        for res in cls.old_results:
                logging.info(", service: " + str(res.service.id)) 
                if res.service.id == service_id:
                        try:
                                all_results.append(res.create_date.strftime('%d-%b-%y') + ":" + str(res.result))
                        except:
                                all_results.append(res.create_date.strftime('%d-%b-%y') + ":<Un-known>")
                                logging.info("======== error appending to result")

        return ", ".join(all_results)

    def get_old_results(cls):
        lines = set()
        ids = []
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        # get all IDs of the Analysis Services in this Test
        service_ids = []
        for test_service in cls.test.services:
                service_ids.append(test_service.id)

        #logging.info("======== service ids " + str(service_ids))
        logging.info("=============== lab id " + str(cls.id))
        #logging.info("============ services in test " + str(cls.test.services))

        # get all Lab IDs of this patient for this test
        patient_lab_ids = []
        Lab = Pool().get("gnuhealth.lab")
        labs = Lab.search([('patient', '=', cls.patient.id),('test', '=', cls.test.id)])
        logging.info(labs)

        #for lab in labs:
        #        patient_lab_ids.append(lab.id)

        orders = LimsAnalyte.search([
                ('gnuhealth_lab_id', '<', cls.id),
                ('service', 'in', [s.id for s in cls.test.services]),
                ('gnuhealth_lab_id', 'in', [lab.id for lab in labs]),

                #('gnuhealth_lab_id', 'IN', patient_lab_ids),
                ], order=[('create_date', 'DESC')])


        logging.info("================ displayign the orders =================")
        for result in orders:
                result.create_date = result.create_date.replace(minute=0, second=0, microsecond=0)

        logging.info(orders)

        #orders = sorted(orders, key=lambda order: order.category, reverse=True)
        #cls.old_results = orders
        return orders

    def show_category_line(cls, service_id):
        x =22

    def get_category_title(cls):
        y = 333

    def make_qrcode(self, name):
    # Create the QR code
        try:
                patient_puid = self.patient.name.ref
                reg_date = (timedelta(hours=5) + self.date_analysis).strftime('%d/%m/%Y')
                last_name = self.patient.name.full_name
                passport = ''
                
                results = 'NOT DETECTED'

                LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

                final_result = ''
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', self.id)])
                if len(found) >= 1:
                        final_result = found[0].result

                results = self.request.name.rec_name + " - " + final_result


                qr_string = 'ACC. No=' + patient_puid \
                    + '\nREG. DATE=' + reg_date \
                    + '\nNAME=' + last_name \
                
                
                qr_image = qrcode.make(qr_string)
                 
                # Make a PNG image from PIL without the need to create a temp file

                holder = StringIO.StringIO()
                qr_image.save(holder)
                qr_png = holder.getvalue()
                holder.close()

                return bytearray(qr_png)
        except:
                logging.info("Error while calling make_qrcode method")

    def make_qrcode_optional(self, name):
    # Create the QR code
        try:
                if not self.test.qr_code_display:
                        logging.info("====== going to read white image")
                        img = Image.open('/home/gnuhealth/gnuhealth/tryton/server/modules/local/health_proc/report/white_image.png', mode='r')
                        #roi_img = img.crop(box)
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        img_byte_arr = img_byte_arr.getvalue()
                        logging.info("======== rturing byte tarray of the QR Code")
                        return img_byte_arr
                patient_puid = self.patient.name.ref
                reg_date = (timedelta(hours=5) + self.date_analysis).strftime('%d/%m/%Y')
                last_name = self.patient.name.full_name
                results = 'NOT DETECTED'

                LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

                final_result = ''
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', self.id)])
                if len(found) >= 1:
                        final_result = found[0].result

                results = self.request.name.rec_name + " - " + final_result


                qr_string = 'ACC. No=' + patient_puid \
                    + '\nREG. DATE=' + reg_date \
                    + '\nNAME=' + last_name 
                
                qr_image = qrcode.make(qr_string)
                 
                # Make a PNG image from PIL without the need to create a temp file

                holder = StringIO.StringIO()
                qr_image.save(holder)
                qr_png = holder.getvalue()
                holder.close()

                return bytearray(qr_png)
        except:
                logging.info("Error while calling method make_qrcode_optional")
    def make_photo_optional(self, name):
    # get patient photo
        try:
                if not self.test.patient_photo_display:
                        logging.info("====== going to read white image")
                        img = Image.open('/home/gnuhealth/gnuhealth/tryton/server/modules/local/health_proc/report/white_image.png', mode='r')
                        #roi_img = img.crop(box)
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        img_byte_arr = img_byte_arr.getvalue()
                        logging.info("======== rturing byte tarray of the patient photo")
                        return img_byte_arr
                return self.patient.photo
        except:
                logging.info("Error wile caling method make_photo_Optional")


    def get_sample_details(self, name):
        if self.request:
                LabTest = Pool().get('gnuhealth.patient.lab.test')
                lab = LabTest.search([
	                        ('id', '=', self.request.id),				
	                        ])
                if len(lab) == 1:
                        return lab[0].sample_details

    @classmethod
    def search_test_sample_details(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('request.sample_details', clause[1], value))
        return res

    def get_department(self, name):
        if self.test:
                if self.test.category:
                        return self.test.category.name

    @classmethod
    def search_department(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('test.category.name', clause[1], value))
        return res

    def get_sampled_date(self):
        order_date = self.create_date
	
        if True:
            Company = Pool().get('company.company')
            timezone = None
            company_id = Transaction().context.get('company')
            if company_id:
                company = Company(company_id)
                if company.timezone:
                    timezone = pytz.timezone(company.timezone)
            order_date = datetime.astimezone(order_date.replace(tzinfo=pytz.utc), timezone)

        return order_date


    def get_analysis_date(self):
        order_date = self.date_analysis

        if order_date:
		

                Company = Pool().get('company.company')

                timezone = None
                company_id = Transaction().context.get('company')
                if company_id:
                    company = Company(company_id)
                    if company.timezone:
                        timezone = pytz.timezone(company.timezone)

                order_date = datetime.astimezone(order_date.replace(tzinfo=pytz.utc), timezone)

        return order_date



    def get_lims_analytes(self, name):
        lines = set()
        ids = []
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
        orders = LimsAnalyte.search([
		        ('gnuhealth_lab_id', '=', self.id),	
		        ])

        #logging.info(orders)

        #orders = sorted(orders, key=lambda order: order.category, reverse=True)

        for line in orders:
	        #lines.add(line.id)
                ids.append(line.id)

        #logging.info("================ final_ids ===============")
        #logging.info(ids)



        return ids



    def get_historical_analytes(self, name):
        lines = set()
        ids = []
	#LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
	#orders = LimsAnalyte.search([
	#		('gnuhealth_lab_id.patient', '=', self.patient.id),	
	#		('gnuhealth_lab_id.test', '=', self.test.id),	
	#		('gnuhealth_lab_id.state', '=', 'done'),	
	#		])

	#logging.info(orders)

	#orders = sorted(orders, key=lambda order: order.category, reverse=True)

	#for line in orders:
		#lines.add(line.id)
	#	ids.append(line.id)

	#logging.info("================ final_ids ===============")
	#logging.info(ids)



        return ids

    def get_lims_analysis_results(self, name):
        AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")
        lines = set()
        ids = []
        orders = AnalysisServiceResult.search([
                ('gnuhealth_lab_id', '=', self.id),	
	        ])

        for line in orders:
                #lines.add(line.id)
                ids.append(line.id)

        #logging.info("================ final_ids ===============")
        #logging.info(ids)



        return ids


    
    @classmethod
    def view_attributes(cls):
        # Hide the group holding all the demographics when the party is not
        # a person
        return [('//page[@id="page_lims_results_2"]', 'states', {
                #'invisible': Equal(Eval('state'), 'hospitalized'),
		'invisible': ~In(51,Eval('groups',[])),
                })]


    @classmethod
    def __setup__(cls):
        super(Lab, cls).__setup__()
        cls._order.insert(0, ('date_analysis', 'DESC'))
        t = cls.__table__()
        cls._sql_constraints = [
            ('id_uniq', Unique(t, t.name),
             'The test ID code must be unique')
        ]

        #x = []
        cls.state.selection.append({'in_queue', 'In Queue'})
        #cls.state.selection.append({'in_progress', 'In Progress'})
        #cls.field_name.state.append('partial_ready', 'Partial Ready')
        #cls.field_name.state.append('partial', 'Partial')
        #cls.field_name.state.append('prelim_ready', 'Prelim Ready')
        #cls.field_name.state.append('prelim', 'Preliminary')
        #cls.field_name.state.append('cancelled', 'Cancelled')
        #cls.field_name.state.append('verified', 'Verified')
        #cls.field_name.state.append('done', 'Done')
        #cls.field_name.state.append(x)

        cls._buttons.update({
              'receive_sample': {
                    'invisible': Not(Equal(Eval('state'), 'draft')),
                    },
                'save_results': {
                    'invisible': Not(Or(Equal(Eval('state'), 'in_progress'),
                    Equal(Eval('state'), 'prelim'))),
                    },
	
                'submit_results': {
                    'invisible': Not(Or(Equal(Eval('state'), 'in_progress'),
                    Equal(Eval('state'), 'prelim'))),
                    },
	
                'verify_results': {
                    'invisible': Not(Or(Equal(Eval('state'), 'prelim'),
                    Equal(Eval('state'), 'prelim'))),
                    },
                'preview_report': {
                    'invisible': Or(Equal(Eval('state'), 'in_progress'),
                    Equal(Eval('state'), 'in_progress')),
                    },
		
                'publish_results': {
                    'invisible': Not(Or(Equal(Eval('state'), 'verified'),
                    Equal(Eval('state'), 'verified'))),
                    },
	
                'edit_results': {
                    'invisible': Or(Equal(Eval('state'), 'done'),
                    Equal(Eval('state'), 'done')),
		            },
                'reopen_results': {
                    'invisible': Not(Or(Equal(Eval('state'), 'done'),Equal(Eval('state'), 'done'))),
                    },

	})
	
    @classmethod
    @ModelView.button
    def receive_sample(cls, tests):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        for lab_test_result in tests:
                if lab_test_result.state != 'draft':
                        cls.raise_user_error("This action is not applicable now.")

                HealthProfessional = Pool().get('gnuhealth.healthprofessional')
                received_by = get_health_professional()
                Lab.write([lab_test_result],{'state':'draft', 'received_on': datetime.now(), 'received_by':received_by})

    @classmethod
    @ModelView.button
    @ModelView.button_action('health_proc.act_lims_test_results_entry')
    def save_results(cls, tests):
        pass

    @classmethod
    @ModelView.button
    def submit_results(cls, tests):

        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")

        for lab_test_result in tests:
                if False:
                        self.raise_user_error("This feature is for Rapid test only")
                if False:
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
		        #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
		        #continue
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
                if len(found) >= 1:
                        LimsAnalyte.delete(found)

                # also save the result in AnalysisServiceResult table ----------------------
                anal_results = AnalysisServiceResult.search([('gnuhealth_lab_id','=', lab_test_result.id)])


                for result in anal_results:                                           
                        final_result = '<NO RESULT>'
                        if result.service.result_type == 'numeric':
                                #if we str() to convert a decimal number to string, it removes all ending zeros after point
                                try:
                                        if result.service.precision:
                                                precision = "%." + str(result.service.precision) + "f"
                                                final_result =  precision % result.numeric_result
                                        else:
                                                final_result = str(result.numeric_result)
                                except:
                                                final_result = str(result.numeric_result)

                        if result.service.result_type == 'selection':
                                if result.selected_result_option:
                                        final_result = str(result.selected_result_option.label)

                        if result.service.result_type == 'text':
                                if result.text_result:
                                        final_result = result.text_result

                        #at times, the type is NUMERIC but the user enters result in Text, so give Text result precedence
                        if result.text_result:
                                final_result = result.text_result

                        limsAnalyte = LimsAnalyte.create([{
                                'name':result.service.name,
                                'category':result.service.analysis_category.rec_name,
                                'analyte_id':str(lab_test_result.id), 
                                'gnuhealth_lab_id':lab_test_result.id,
                                'value_range':'',
                                'result': final_result,
                                'numeric_result': result.numeric_result,
                                'unit': result.service.unit,
                                'sortable_title': str(result.id),	
                                'lower_limit': result.min_value,
                                'upper_limit': result.max_value,	
                                'value_range': result.result_range,
                                'range_comments': result.range_comment,
                                'service': result.service.id,
                                'hist_one': (result.hist_one + "") if result.hist_one else None,
                                'hist_two': (result.hist_two + "") if result.hist_two else None,
                                'historic_results': result.historic_results,
                                'sortable_title': result.parent_anal_service_result.get_final_result() if result.parent_anal_service_result else None,
                                }])
                        AnalysisServiceResult.write([result],{'state':'prelim'})


                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'results':'test performed', 'state':'prelim', 'date_analysis': datetime.now()})

	
    @classmethod
    @ModelView.button
    def verify_results(cls, tests):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        for lab_test_result in tests:
                if lab_test_result.state != 'prelim':
                        cls.raise_user_error("Please first submit the result to bring to Preliminary State")
                if False:
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
		        #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
		        #continue
                

                anal_results = LimsAnalyte.search([('gnuhealth_lab_id','=', lab_test_result.id)])

                #for result in anal_results:		        
                #        LimsAnalyte.write([result],{'state':'verified'})
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                HealthProfessional = Pool().get('gnuhealth.healthprofessional')
                verified_by = get_health_professional()
                Lab.write([lab_test_result],{'results':'test performed', 'state':'verified', 'date_analysis': datetime.now(), 'pathologist':verified_by})

    @classmethod
    @ModelView.button
    def publish_results(cls, tests):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
        
        report_path = '/home/gnuhealth/'
        shared_report_path = '/portal/lab_reports/'
        for lab_test_result in tests:
                if False:
                        self.raise_user_error("This feature is for Rapid test only")
                if False:
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
			#logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
			#continue
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
               
                anal_results = LimsAnalyte.search([('gnuhealth_lab_id','=', lab_test_result.id)])

                #for result in anal_results:		        
                #        LimsAnalyte.write([result],{'state':'done'})
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")



                #also save the report
                InvoiceReport = Pool().get('anth.proc.lims.lab.report', type='report')
                result = InvoiceReport.execute([lab_test_result.id], {'include_header':'yes'})
                report_format,report_bytes = result[:2]

                report_file_name_raw = lab_test_result.patient.name.ref + "_" + str(lab_test_result.id) + "_" + datetime.now().strftime('%d%m%Y');
                report_file_name = report_file_name_raw + '.pdf'

                #khurram commented this code on 20-oct-21 to improve performance; so stopped wrting file on local file system
                #f = open(report_path+report_file_name,"wb")
                #f.write(report_bytes)
                #f.close()

                f = open(shared_report_path+report_file_name,"wb")
                f.write(report_bytes)
                f.close()


                #also save the report without logo
                InvoiceReport = Pool().get('anth.proc.lims.lab.report', type='report')
                result = InvoiceReport.execute([lab_test_result.id], {'include_header':'no'})
                report_format,report_bytes = result[:2]
                logging.info("============== report format is " + report_format)
                report_file_name_without_logo = report_file_name_raw + '_without_logo' + '.pdf'

                #khurram commented this code on 20-oct-21 to improve performance; so stopped wrting file on local file system
                #f = open(report_path+report_file_name_without_logo,"wb")
                #f.write(report_bytes)
                #f.close()

                f = open(shared_report_path+report_file_name_without_logo,"wb")
                f.write(report_bytes)
                f.close()

                Lab.write([lab_test_result],{'results':'test performed', 'state':'done', 'date_published': datetime.now(), 
                'report_path': report_file_name, 'report_without_logo_path': report_file_name_without_logo, 'is_ready_for_upload': True, 'is_report_uploaded': False })

    
    @classmethod
    @ModelView.button
    @ModelView.button_action('health_proc.act_lims_test_results_entry')
    def edit_results(cls, tests):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')
        
        report_path = '/home/gnuhealth/'
        shared_report_path = '/portal/shared/lab_reports/'
        for lab_test_result in tests:
                Lab.write([lab_test_result],{'state':'prelim', 'date_analysis': datetime.now()})	

    @classmethod
    @ModelView.button
    def reopen_results(cls, tests):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        for lab_test_result in tests:
                if lab_test_result.create_date + timedelta(days=7) < datetime.now():
                        cls.raise_user_error("The test older than seven days can not be opened")
                if lab_test_result.state != 'done':
                        cls.raise_user_error("The Report has NOT been Published.")
			#logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
			#continue
                

                #anal_results = LimsAnalyte.search([('gnuhealth_lab_id','=', lab_test_result.id)])

                #for result in anal_results:		        
                #        LimsAnalyte.write([result],{'state':'verified'})
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'state':'prelim', 'date_analysis': datetime.now()})

    @classmethod
    @ModelView.button
    @ModelView.button_action('health_proc.lims_lab_report_print')
    def preview_report(cls, tests):
        pass

    @staticmethod
    def default_date_requested():
        return datetime.now()

    @staticmethod
    def default_date_analysis():
        return datetime.now()

    @staticmethod
    def default_state():
        return 'draft'


    #this method is ineffective; add new status values to health_crypto_lab package
    @classmethod
    def get_state(cls, method):
        'Return list of Model names for origin Reference'
	#logging.warning("++++++++++++++++++++++++++++++ get origin is called from overridden method; displaying current list")
        x = []
        x = super(Lab,cls)._get_state()
        return x

    @classmethod
    def search_rec_name(cls, name, clause):
        """ Search for the name, lastname, PUID, any alternative IDs,
            and any family and / or given name from the person_names
        """
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            #('request',) + tuple(clause[1:]),
            #('ar_id',) + tuple(clause[1:]),
            ('test.name',) + tuple(clause[1:]),
            ('test.code',) + tuple(clause[1:]),
            ('requestor.name.name',) + tuple(clause[1:]),
            ('pathologist.name.name',) + tuple(clause[1:]),
            ('patient.name.ref',) + tuple(clause[1:]),
            ('patient.name.alternative_ids.code',) + tuple(clause[1:]),
            ('patient.name.person_names.family',) + tuple(clause[1:]),            
            ('patient.name.person_names.given',) + tuple(clause[1:]),            
            ('patient.name.name',) + tuple(clause[1:]),
            ('patient.name.lastname',) + tuple(clause[1:]),
	    ('patient.name.contact_mechanisms.value',) + tuple(clause[1:]),
	    ]


class GnuHealthLabTestCategories(ModelSQL, ModelView):
    'Lab Test Categories'
    __name__ = 'gnuhealth.lab.test.categories'

    name = fields.Char('Category Name', select=True)
    code = fields.Char('Description', select=True)

    @classmethod
    def __setup__(cls):
        super(GnuHealthLabTestCategories, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_uniq', Unique(t, t.name),
             'The Category name must be unique')
        ]


    @classmethod
    def check_xml_record(cls, records, values):
        return True

class LimsAnalyteResults(ModelSQL, ModelView):
    'Lab Test Critearea'
    __name__ = 'gnuhealth.lab.lims.analyte.result'

    name = fields.Char('Analyte', required=True, select=True,
        translate=True)
    
    result = fields.Text('Value')
    numeric_result = fields.Float('Value Numeric')
    result_numeric = fields.Float('Value Numeric')
    lower_limit = fields.Float('Lower Limit')
    upper_limit = fields.Float('Upper Limit')
    out_of_range = fields.Boolean('Out of Range')
    analyte_id = fields.Char('Analyte LIMS ID', required=True, select=True,
        translate=True)
    value_range = fields.Text('Range for analyte - Text')
    range_comments = fields.Text('Range Comments')
    remarks = fields.Char('Remarks')
    gnuhealth_lab_id = fields.Many2One('gnuhealth.lab', 'Test Cases',
        select=True)
    unit = fields.Char('Unit')
    sortable_title = fields.Char('Sortable Title')

    category = fields.Char('Category', select=True,
        translate=True)


    service = fields.Many2One('anth.proc.analysis.service','Analysis Service', readonly=True)

    historic_results = fields.Char('Historic Results', readonly=True)   

    hist_one = fields.Char("Historic-Date-1", readonly=True)
    hist_two = fields.Char("Historic-Date-2", readonly=True)

    @classmethod
    def __setup__(cls):
        super(LimsAnalyteResults, cls).__setup__()
        cls._order.insert(0, ('gnuhealth_lab_id', 'ASC'))
        cls._order.insert(1, ('service.analysis_category.sort_order', 'ASC'))
        cls._order.insert(2, ('service.sort_order', 'ASC'))
        cls._order.insert(3, ('sortable_title', 'ASC'))

        cls._order.insert(4, ('name', 'ASC'))


    def get_result_range(cls):
        return str(cls.lower_limit) + " - " + str(cls.upper_limit)

    def is_out_of_range(cls):
        try:
                if(cls.numeric_result >= cls.lower_limit and cls.numeric_result <= cls.upper_limit):
                        return False
                else:
                        return True	
        except:
                return False


#following class could not be moved from health_proc.py - new version is not compling it on changing the location of class code
#class GnuHealthPatientLabTest(metaclass=PoolMeta):
#    __name__ = 'gnuhealth.patient.lab.test'

class SampleContainer(ModelSQL, ModelView):
    'Sample Container'
    __name__ = 'health.proc.sample.container'

    name = fields.Char('Name', required=True)
    label_text = fields.Char('Label Text', required=True)
    container_color_img = fields.Binary('Color Image')


class SampleType(ModelSQL, ModelView):
    'Sample Type'
    __name__ = 'anth.proc.sample.type'

    name = fields.Char('Name', required=True)
    sample_container = fields.Many2One('health.proc.sample.container', 'Sample Container')

    prefix = fields.Char('Prefix', required=True)
    db_sequence = fields.Char('DB Sequences', required=True)
    description = fields.Char('Description', required=True)

class AnalysisSpec(ModelSQL, ModelView):
    'Analysis Spec'
    __name__ = 'anth.proc.analysis.spec'

    uid = fields.Char('UID', required=True)
    name = fields.Char('Name', required=True)
    min_age_days = fields.Numeric('Min Age in Days', required=True)
    max_age_days = fields.Numeric('Max Age in Days', required=True)
    gender = fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Gender', required=True)
    
    sample_type = fields.Many2One('anth.proc.sample.type', 'Sample Type')
    lab_test_type = fields.Many2One('gnuhealth.lab.test_type', 'Lab Test', required=True)


class TestPdfReport(Report):
    __name__ = 'anth.test_pdf_report'

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        Lab = Pool().get("gnuhealth.lab")
	
        logging.info(report_context)
        logging.info("================================== ids =========================")
        ids = report_context.get('data','').get('ids','')
        logging.info(ids)

        if len(ids) == 0 or len(ids) > 1:
                Lab.raise_user_error("Please select one result from the list and then click 'Lab Report PDF' to view report")

        lab = Lab(ids[0])
        if lab.state != 'done':
                Lab.raise_user_error("The test is not in done state")

        cookie_jar = http.cookiejar.CookieJar()

        top_level_url = "http://localhost:88/lims/"
        username = "admin"
        password = "a8At6Gjk9XKg"
        puidInLims = ""
        logging.info("connecting LIMS at: ")
        logging.info(top_level_url)
        #opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())

        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        urllib.request.install_opener(opener)

        if(True):
                params = urlencode({
                "labId": lab.id,
                })

                params = params.encode('utf-8')
                #f = opener.open("http://localhost:9090/crm/admin/get_lab_report_as_pdf.htm", params)
                #req = Request("http://localhost:9090/crm/admin/get_lab_report_as_pdf.htm", params)
                req = Request("http://localhost:9090/crm/admin/get_lab_report_as_pdf.htm", params)
                res = urlopen(req)      

                data = res.read()
                return data


        params = urlencode({
        "form.submitted": 1,
        "pwd_empty": 0,
        "__ac_name": username,
        "__ac_password": password,
        "submit": "Log in"
        })
        logging.warning("sending admin credentials for logging for getting report.....\n")

        params = params.encode('utf-8')

        req = Request(top_level_url + 'login_form', params)
        #f = opener.open(top_level_url + 'login_form', params)
        
        res = urlopen(req)
        data1 = res.read()
        #data1 = f.read()

        #logging.info("response received is: " + data + "\n")
        f.close()

        # get report id ===========================================
        params = urlencode({
	        "portal_type": "ARReport",
	        "path": "/lims/clients/client-1/" + lab.ar_id,
        })
        params = params.encode('utf-8')

        #http://172.29.0.6:88/lims/@@API/read?portal_type=ARReport&path=/lims/clients/client-1/blood-10445-R01
        logging.warning("-------------------------------------------- params to query patient records: " )
        logging.warning(params)

        #f = opener.open(top_level_url + "@@API/read", params)					
        req = Request(top_level_url + "@@API/read", params)	
        res = urlopen(req)	
        
        data = res.read()
        #logging.info("-----------------------------------------------After Running ARReport portal  query; response received is: \n" + data)
        data = json.loads(data)
        #logging.info(data)
        logging.info("============= total objects in getting all reports query: ")
        logging.info(data['total_objects'])
        remarks = ""
        # If there is some error, raise error
        if not data['success']:
	        Lab.raise_user_error("The LIMS software could not be reached, please try again later")

        # If no. of records returned is 1, it means patient exists in LIMS
        if data['total_objects'] >= 1:
                count = data['total_objects'] - 1
                logging.info(data['objects'][count]['id'] )
                ar_report = data['objects'][count]['id'] 

                f = opener.open("http://localhost:88/lims/clients/client-1/" + lab.ar_id + "/" + ar_report + "/at_download/Pdf")					
                data = f.read()
        else:
                #Lab.raise_user_error("The Report is not published yet. Contact Lab Staff please")

                params = urllib.urlencode({
                "labId": lab.id,
                })

                f = opener.open("http://localhost:9090/crm/admin/get_lab_report_as_pdf.htm", params)
                data = f.read()
                return data

        return data

    @classmethod
    def convert(cls, report, data):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        return output_format, data

class AnalysisServiceResult(ModelSQL, ModelView):
    'Analysis Service Result'
    __name__ = 'anth.proc.analysis.service.result'
    gnuhealth_lab_id = fields.Many2One('gnuhealth.lab','Lab Result ID')
    service = fields.Many2One('anth.proc.analysis.service','Analysis Service')
    numeric_result = fields.Numeric('Numeric Result')
    text_result = fields.Text("Text Result")
    selected_result_option = fields.Many2One('anth.proc.result.option','Selected Result',  domain=[('service', '=', Eval('service'))],
        depends=['service'])
    result_range = fields.Text("Result Range", readonly=True)
    range_comment = fields.Text("Descriptive Result Range", readonly=True)
    is_out_of_range = fields.Boolean("Out of Range?", readonly=True)
    remarks = fields.Char("Remarks")
    hidden = fields.Boolean('Hidden?',help='Exclude from the report')
    date_captured = fields.DateTime('Captured on')

    min_value = fields.Numeric('Min Value', readonly=True)
    max_value = fields.Numeric('Max Value', readonly=True)

 
    state = fields.Selection([
        ('in_progress', 'In Progress'),
	('prelim', 'Preliminary'),
	('cancelled', 'Cancelled'),
        ('verified', 'Verified'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    analysis_category_name = fields.Function(fields.Char('Category'), 'get_category')    
    historic_results = fields.Char('Historic Results', readonly=True)
    hist_one = fields.Char("Historic-Date-1", readonly=True)
    hist_two = fields.Char("Historic-Date-2", readonly=True)
    parent_anal_service_result = fields.Many2One('anth.proc.analysis.service.result','Relateds to Result',  domain=[('gnuhealth_lab_id', '=', Eval('gnuhealth_lab_id'))], depends=['gnuhealth_lab_id'])

    @classmethod
    def fields_view_get_min2(cls, view_id=None, view_type='form'):
        result = super(AnalysisServiceResult, cls).fields_view_get(view_id=view_id, view_type=view_type)
        logging.info("====================== result --------- view_get ''''''''")
        logging.info(result)
        historic_results = result['fields']['historic_results']
        logging.info(historic_results)

        historic_results['string']='21-Nov-20'

        logging.info(historic_results)
        result['fields']['historic_results'] = historic_results

        if len(cls.gnuhealth_lab_id.get_historic_result_dates) >=1:
                hist_one = result['fields']['hist_one']
                logging.info(hist_one)

                hist_one['string']=cls.gnuhealth_lab_id.get_historic_result_dates()[0]
                result['fields']['hist_one'] = hist_one

        if len(cls.gnuhealth_lab_id.get_historic_result_dates) >=2:
                hist_two = result['fields']['hist_two']
                logging.info(hist_two)

                hist_two['string']=cls.gnuhealth_lab_id.get_historic_result_dates()[1]
                result['fields']['hist_two'] = hist_two


        return result

    def get_rec_name(self, name):
        selected_opt = ''
        if self.selected_result_option:
                selected_opt = ': ' + self.selected_result_option.label
        return self.service.name + selected_opt

    def get_category(self, name):
        return self.service.analysis_category.name        


    @staticmethod
    def default_state():
        return 'in_progress'

    def get_hist_one(cls, name):
        return "34665"

    def get_hist_two(cls, name):
        return "45.76"

    def get_result_range(cls):
        return str(cls.min_value) + " - " + str(cls.max_value)

    def is_out_of_range(cls):
        if(cls.numeric_result > cls.max_value):
                return True
        else:
                return False

    @classmethod
    def __setup__(cls):
        super(AnalysisServiceResult, cls).__setup__()
        cls._order.insert(0, ('service.analysis_category.sort_order', 'ASC'))
        cls._order.insert(1, ('service.analysis_category.name', 'ASC'))
        cls._order.insert(2, ('service.sort_order', 'ASC'))
        cls._order.insert(3, ('service.name', 'ASC'))
      

class TestPdfReportWithoutLogo(Report):
    __name__ = 'anth.test_pdf_report_without_logo'

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        Lab = Pool().get("gnuhealth.lab")
	
        logging.info(report_context)
        logging.info("================================== ids =========================")
        ids = report_context.get('data','').get('ids','')
        logging.info(ids)

        if len(ids) == 0 or len(ids) > 1:
                Lab.raise_user_error("Please select one result from the list and then click 'Final Report Without Logo' to view report")

        lab = Lab(ids[0])
        if lab.state != 'done':
                Lab.raise_user_error("The test is not in done state")

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())	

        if True:
	        #Lab.raise_user_error("The Report is not published yet. Contact Lab Staff please")

                params = urllib.urlencode({
                "labId": lab.id,
                "without_logo": True,
                })

                f = opener.open("http://localhost:9090/crm/admin/get_lab_report_as_pdf.htm", params)
                data = f.read()
                return data

        return data

    @classmethod
    def convert(cls, report, data):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        return output_format, data


        logging.info(historic_results)
        result['fields']['historic_results'] = historic_results

        if len(cls.gnuhealth_lab_id.get_historic_result_dates) >=1:
                hist_one = result['fields']['hist_one']
                logging.info(hist_one)

                hist_one['string']=cls.gnuhealth_lab_id.get_historic_result_dates()[0]
                result['fields']['hist_one'] = hist_one

        if len(cls.gnuhealth_lab_id.get_historic_result_dates) >=2:
                hist_two = result['fields']['hist_two']
                logging.info(hist_two)

                hist_two['string']=cls.gnuhealth_lab_id.get_historic_result_dates()[1]
                result['fields']['hist_two'] = hist_two


        return result

    def get_rec_name(self, name):
        selected_opt = ''
        if self.selected_result_option:
                selected_opt = ': ' + self.selected_result_option.label
        return self.service.name + selected_opt

    def get_category(self, name):
        return self.service.analysis_category.name        


    @staticmethod
    def default_state():
        return 'in_progress'

    def get_hist_one(cls, name):
        return "34665"

    def get_hist_two(cls, name):
        return "45.76"

    def get_result_range(cls):
        return str(cls.min_value) + " - " + str(cls.max_value)

    def is_out_of_range(cls):
        if(cls.numeric_result > cls.max_value):
                return True
        else:
                return False

    @classmethod
    def __setup__(cls):
        super(AnalysisServiceResult, cls).__setup__()
        cls._order.insert(0, ('service.analysis_category.sort_order', 'ASC'))
        cls._order.insert(1, ('service.analysis_category.name', 'ASC'))
        cls._order.insert(2, ('service.sort_order', 'ASC'))
        cls._order.insert(3, ('service.name', 'ASC'))
          
##### these are the classes defined in lab_updates.py in health_proc module
class AnalysisCategory(ModelSQL, ModelView):
    'Analysis Category'
    __name__ = 'anth.proc.analysis.category'

    name = fields.Char('Name', select=True)
    description = fields.Text('Description')
    sort_order = fields.Integer('Sort Order')

class ResultOption(ModelSQL, ModelView):
    'Lab Result Option'
    __name__ = 'anth.proc.result.option'

    service = fields.Many2One('anth.proc.analysis.service','Analysis Service')
    value = fields.Integer('Value', required=True)
    label = fields.Char('Label', select=True, required=True)
    sort_order = fields.Integer('Sort Order')
    is_default = fields.Boolean('Is Default?')

        
    def get_rec_name(self, name):
        return self.label


  
class AnalysisServiceResultRange(ModelSQL, ModelView):
    'Analysis Service Rane'
    __name__ = 'anth.proc.result.range'
    service = fields.Many2One('anth.proc.analysis.service','Analysis Service', readonly=True)

    name = fields.Char('Name', required=True)
    min_value = fields.Numeric('Min Value')
    max_value = fields.Numeric('Max Value')
 
    min_age_days = fields.Numeric('Min Age in Days', required=True)
    max_age_days = fields.Numeric('Max Age in Days', required=True)
    gender = fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Gender', required=True)
    
    range_comment = fields.Text("Descriptive Result Range")


class AnalysisService(ModelSQL, ModelView):
    'Analysis Service'
    __name__ = 'anth.proc.analysis.service'

    name = fields.Char('Name', select=True)
    description = fields.Text('Description')
    result_type = fields.Selection([
        ('numeric', 'Numeric'),
        ('selection', 'Selection'),
        ('text', 'Text'),
        ], 'Result Type', select=True)
    precision = fields.Integer('Precision')
    sort_order = fields.Integer('Sort Order')
    keyword = fields.Char('Keyword')
   
    unit = fields.Char('Unit', select=True)
    analysis_category = fields.Many2One('anth.proc.analysis.category','Category', required=True)
    result_options = fields.One2Many('anth.proc.result.option', 'service', 'Result Options')
    result_ranges = fields.One2Many('anth.proc.result.range', 'service', 'Result Range')
    service_range_comment = fields.Text("Descriptive Result Range", help="If no range result-specific, then this text will be displayed")
    default_numeric_result = fields.Numeric('Default Numeric Result')
    default_text_result = fields.Char('Default text Result', select=True)
    eligible_for_parent = fields.Boolean('Eligible for parent?', help="Can this service become parent of another service result")

    @classmethod
    def __setup__(cls):
        super(AnalysisService, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('keyword_uniq', Unique(t, t.keyword),
             'The Keyword must be unique')
        ]

class TestTypeAnalysisService(ModelSQL, ModelView):
    'Lab Result Option'
    __name__ = 'anth.proc.test.to.service'
    test_type_id = fields.Many2One('gnuhealth.lab.test_type','Test Type',required=True, select=True)
    analysis_service_id = fields.Many2One('anth.proc.analysis.service','Analysis Service', required=True, select=True)


class WizardCreateLabTestOrder(metaclass=PoolMeta):
    __name__ = 'gnuhealth.lab.test.create'
          
    def transition_create_lab_test(self):
        logging.info("============================================================================================= transition pay is called ");
        TestRequest = Pool().get('gnuhealth.patient.lab.test')

        if True:
            tests = TestRequest.browse(Transaction().context.get('active_ids'))

            for lab_test_order in tests:
                if not lab_test_order.sale_line:
                    self.raise_user_error('========= A test has no sale genereated for it')
                
                Sale = Pool().get('sale.sale')
                SaleLine = Pool().get('sale.line')

                saleLine = SaleLine(lab_test_order.sale_line)		
                sale = Sale(saleLine.sale)
            
                logging.warning("------------------------ sale id is " + str(sale.id))
                logging.warning("------------------------ sale state is " + str(sale.state))
                if not sale.state in ['processing','done']:
                    if not lab_test_order.inpatient_registration_code:
                        raise UserError("Payment not Received!", "The test can't be ordered without making payment. Please make the payment first.")
        

        state =  super(WizardCreateLabTestOrder, self).transition_create_lab_test()
        logging.info("======== sate " + str(state))
        # set the request reference in the result
        return state
    
    def transition_create_lab_test_new(self):
        TestRequest = Pool().get('gnuhealth.patient.lab.test')
        Lab = Pool().get('gnuhealth.lab')
        TestType = Pool().get('gnuhealth.lab.test_type')
        tests_report_data = []
        tests = TestRequest.browse(Transaction().context.get('active_ids'))
        first = True

        for lab_test_order in tests:
            test_cases = []
            test_report_data = {}

            logging.info("====================================" + lab_test_order.patient_id.name.get_mechanism('phone'))
            if lab_test_order.state == 'ordered':
                self.raise_user_error(
                    "The Lab test order is already created")

            if lab_test_order.state == 'cancelled':
                self.raise_user_error(
                    "The Lab test order is cancelled so it can't be created!")


            if not lab_test_order.sale_line:
                if not lab_test_order.inpatient_registration_code:
                        self.raise_user_error("The Lab test is neither OPD nor IPD. It can't be ordered!")

            testType = TestType(lab_test_order.name)
            #if not testType.lims_analysis_profile_id:
            #    raise UserError("Payment not Received!", "This test's profile / analysis service is not yet integrated with LIMS, so can't be ordered!")

            if not testType.lims_sample_type_id:
                raise UserError("Sample Type not configured!", "This test's sample type is not yet integrated with LIMS, so can't be order")

            Patient = Pool().get('gnuhealth.patient')
            pp = Patient(lab_test_order.patient_id)

            gender = "dk"
            if pp.name.gender == 'm':
                gender = "male"
            else:
                if pp.name.gender == 'f':
                    gender = "female"
            dob = ""
            if pp.name.dob:
                dob = str(pp.name.dob.year) + "-" + str(pp.name.dob.month) + "-" + str(pp.name.dob.day)
            else:
                raise UserError("DoB Mising!", "The Patietn and Test details can't be sent to LIMS as Date of Birth of patient not entered")

            if not pp.name.gender:
                raise UserError("Gender Missing!", "The patient and test details can't be sent to LIMS as Gender of the patient is not found")

            contacts = pp.name.contact_mechanisms
            logging.info("-------------------------------------- contacts")
            logging.info(contacts)
            patientPhone = ''
            for cont in contacts:
            	if cont.type == 'phone' or cont.type == 'mobile':
                        patientPhone = cont.value

            logging.info("========================= phone number is: " + patientPhone)

            # sending the test to Tryton also
            if True: # create it here as well
                #try:
                        WizardCreateLabTestOrder.createTestInTryton(pp, lab_test_order, testType, dob, None, None)
                        logging.info("================ Tryton Test is found so not sending it to LIMS")

                        # don't go ahead and break the loop
                        continue;

                #except:
                        logging.info("some error while creating tryton test")
                        #traceback.print_stack()
                        #traceback.print_exc()
                        #self.raise_user_error("Failed to crate Lab Test in tryton; please contact I.T Department")
                        continue;


            #check whether it is OPD test or IPD test
            if lab_test_order.sale_line and not  lab_test_order.inpatient_registration_code and not lab_test_order.emergency_registration_code:
                # Now get Sale against this sale_line id and check the status of Sale which must be processing or done
                logging.warning("\n\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> This is an OPD order,lab_test_order_id: " +	str(lab_test_order.id) + ", sale_line_id: " + str(lab_test_order.sale_line) )
                Sale = Pool().get('sale.sale')
                SaleLine = Pool().get('sale.line')

                saleLine = SaleLine(lab_test_order.sale_line)		
                sale = Sale(saleLine.sale)

                logging.warning("------------------------ sale id is " + str(sale.id))
                logging.warning("------------------------ sale state is " + str(sale.state))
                if not sale.state in ['processing','done']:
                        self.raise_user_error(
                                "The test can't be ordered without making payment. Please make the payment first.")
		# also check that the product in Sale Line is the same product which is ordered in the Test
	    
	   
	   
            testType = TestType(lab_test_order.name)
            logging.warning("------------------ test id is " + str(testType.id))
            logging.warning("-------------------------- analysis profile id: " + testType.lims_analysis_profile_id);
            logging.warning("-------------------------- sample type id: " + testType.lims_sample_type_id);

       
	    # if the details of the Analysis Request is saved into LIMS
	    #if data['success']:
	    #	logging.warning("----------------------- AR saved Successfully")
	    #else:
	    #	logging.error("Sorry! The AR could not be saved successfully to LIMS")
	    #	self.raise_user_error("Sorry! The Analysis Request could not be saved. Try again later.")

            test_report_data['ar_id'] = the_ar_id
            test_report_data['request'] = lab_test_order.id
            test_report_data['test'] = lab_test_order.name.id
            test_report_data['patient'] = lab_test_order.patient_id.id
            test_report_data['create_query'] = create_query
            test_report_data['state'] = 'in_queue'
            if lab_test_order.doctor_id:
                test_report_data['requestor'] = lab_test_order.doctor_id.id
            test_report_data['date_requested'] = lab_test_order.date

            for critearea in lab_test_order.name.critearea:
                test_cases.append(('create', [{
                        'name': critearea.name,
                        'sequence': critearea.sequence,
                        'lower_limit': critearea.lower_limit,
                        'upper_limit': critearea.upper_limit,
                        'normal_range': critearea.normal_range,
                        'units': critearea.units and critearea.units.id,
                    }]))
            test_report_data['critearea'] = test_cases

            tests_report_data.append(test_report_data)

            # creating a row in Gnuhealth_Lab table
            Lab.create([test_report_data])

	    # updating request status to ordered
            TestRequest.write([lab_test_order], {'state': 'ordered'}) 

       
        #Lab.create(tests_report_data)
        #TestRequest.write(tests, {'state': 'ordered'})
        
        return 'end'

    @classmethod 
    def get_next_id(cls, sampleType):
        cursor = Transaction().connection.cursor()
        cursor.execute("SELECT nextval('" + sampleType + "') ")
        res = cursor.fetchone()

        if res[0] > 0:
            return str(res[0])

    @classmethod
    def get_spec_id(cls, test_type_id, dob, gender, spec_id_with_test):
        spec = ''
        if spec_id_with_test:
            spec = spec_id_with_test
            return spec
        else:
            spec = ''
                
        logging.info(">>>>>>>>> Returning spec for test type" + str(test_type_id) + ", gender:" + gender + ", dob:" + dob + ", spec id: " + spec) 
        AnalysisSpec = Pool().get('anth.proc.analysis.spec')
        today = datetime.today().date()

        curr_age_in_days = datetime.strptime(str(today),'%Y-%m-%d') - datetime.strptime(str(dob), '%Y-%m-%d') 
        logging.info("------------------------------- age in days: " + str(curr_age_in_days.days))
        cur_age = 5600
        specs = AnalysisSpec.search([
			        ('lab_test_type', '=', test_type_id),
			        ('gender', '=', gender),
			        ('min_age_days', '<=', curr_age_in_days.days),
			        ('max_age_days', '>=', curr_age_in_days.days),
			        ])
			
        if len(specs) == 0:
            cls.raise_user_error("No analysis specification found for the test")
        spec = specs[0].uid

        return spec

    @classmethod
    def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(6))

    @classmethod
    def get_result_range(cls, test_type_id, service_id, dob, gender):
        logging.info(">>>>>>>>> Returning spec for test type" + str(test_type_id) + ", gender:" + str(gender) + ", dob:" + dob + ", service id: " + str(service_id)) 
        ResultRange = Pool().get('anth.proc.result.range')
        today = datetime.today().date()

        curr_age_in_days = datetime.strptime(str(today),'%Y-%m-%d') - datetime.strptime(str(dob), '%Y-%m-%d') 
        logging.info("------------------------------- age in days: " + str(curr_age_in_days.days))
        cur_age = 5600
        specs = ResultRange.search([
                ('service', '=', service_id),
                ('gender', '=', gender),
                ('min_age_days', '<=', curr_age_in_days.days),
                ('max_age_days', '>=', curr_age_in_days.days),
                ])
			
        if len(specs) == 0:
	        cls.raise_user_error("No analysis Result Range found for the test")
                
        return specs
    
    @classmethod
    def createTestInTryton(cls, pp, lab_test_order, testType, dob, labsAlreadyCreated=None, ar_id=None):
            tests_report_data = []
            test_cases = []
            test_report_data = {}
            Lab = Pool().get('gnuhealth.lab')

            SampleType = Pool().get("anth.proc.sample.type")

            if labsAlreadyCreated:
                labs=labsAlreadyCreated
            else:

                    if ar_id:
                            the_ar_id = ar_id
                    else:
                            # search prefix for this sample-type
                            sample_types = SampleType.search([
			                ('db_sequence', '=', testType.lims_sample_type_id),
						
			                ])

                            # if exactly one sample-type is found, then use its prefix
                            if(len(sample_types) ==1):  
                                seq_next_id = WizardCreateLabTestOrder.get_next_id(testType.lims_sample_type_id) 
                                the_ar_id =  sample_types[0].prefix + "-" + str(seq_next_id) + '-R01'
                            else:
                                #otherwise set blood as its sample type
                                seq_next_id = WizardCreateLabTestOrder.get_next_id('sampletype-1') 
                                the_ar_id = 'blood-' + str(seq_next_id) + '-R01'

                    test_report_data['ar_id'] = the_ar_id
                    test_report_data['request'] = lab_test_order.id
                    test_report_data['test'] = lab_test_order.name.id
                    test_report_data['patient'] = lab_test_order.patient_id.id
                    test_report_data['create_query'] = ''
                    test_report_data['state'] = 'in_progress'
                    if lab_test_order.doctor_id:
                        test_report_data['requestor'] = lab_test_order.doctor_id.id
                    test_report_data['date_requested'] = lab_test_order.date

                    for critearea in lab_test_order.name.critearea:
                        test_cases.append(('create', [{
                                'name': critearea.name,
                                'sequence': critearea.sequence,
                                'lower_limit': critearea.lower_limit,
                                'upper_limit': critearea.upper_limit,
                                'normal_range': critearea.normal_range,
                                'units': critearea.units and critearea.units.id,
                            }]))
                    test_report_data['critearea'] = test_cases

                    tests_report_data.append(test_report_data)

                    # creating a row in Gnuhealth_Lab table
                    labs = Lab.create([test_report_data])

                    TestRequest = Pool().get('gnuhealth.patient.lab.test')
                    TestRequest.write([lab_test_order], {'state': 'ordered'}) 

            # populate history in lab object
            labs[0].get_old_results()
            old_dates = labs[0].get_historic_result_dates()

            if len(old_dates) >=1:
                Lab.write(labs, {'hist_one_date': old_dates[0], 'hist_two_date': old_dates[1] if len(old_dates)>=2 else None}) 

            #create the analysis services results for this test
            if True:
                AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")
                for service in testType.services:
                        # get the min, max, range_comment/service_range_comment from ResultRange and attach to this result
                        resultRange = WizardCreateLabTestOrder.get_result_range(testType.id, service.id, dob, pp.gender)
                        if len(resultRange) == 0:
                                cls.raise_user_error("No Result Range found for the test")

                        if len(resultRange) > 1:
                                cls.raise_user_error("More than one Result Ranges found for the test")
                        
                        historic_results = labs[0].get_anal_all_old_results(service.id)

                        if len(old_dates) >=1:
                                hist_one = labs[0].get_old_anal_result_on_date(old_dates[0], service.id)
                        else:
                                hist_one = None

                        if len(old_dates) >=2:
                                hist_two = labs[0].get_old_anal_result_on_date(old_dates[1], service.id)
                        else:
                                hist_two = None


                        # get default result_options if any
                        default_option_id = None
                        for opt in service.result_options:
                                if opt.is_default:
                                        default_option_id = opt.id

                        #create range result
                        precision = service.precision if service.precision else 0
                        min_value = 0.0
                        max_value = 0.0
                        result_range = ''
                        if resultRange[0].range_comment:
                                result_range = resultRange[0].range_comment
                                range_comment = resultRange[0].range_comment
                        else:
                                #min_value = round(resultRange[0].min_value, precision)
                                #max_value = round(resultRange[0].max_value, precision)
                                min_value = resultRange[0].min_value
                                max_value = resultRange[0].max_value
                                result_range = str(min_value) + "-" + str(max_value)
                        AnalysisServiceResult.create([{'gnuhealth_lab_id':labs[0].id, 'service': service.id, 'min_value': resultRange[0].min_value, 'max_value': resultRange[0].max_value, 'result_range':result_range, 'historic_results':historic_results, 'selected_result_option': default_option_id, 'hist_one': hist_one, 'hist_two': hist_two, 'numeric_result': service.default_numeric_result, 'text_result': service.default_text_result}])

class RequestPatientLabTestStart(metaclass=PoolMeta):
    __name__ = 'gnuhealth.patient.lab.test.request.start'

    inpatient_registration_code =  fields.Many2One('gnuhealth.inpatient.registration', 'IPD Reg Code', readonly=True)
    total_bill = fields.Numeric('Total Bill', states={'readonly':True})
    sale_id = fields.Integer('Sale ID')
    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Patient Type', select=True,
        states ={'invisible': Bool(Eval('inpatient_registration_code'))}
    )

    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Insurance Company',
        select=True,
        depends=['payment_mode'], 
        domain=[('panel_type', '=', Eval('payment_mode'))],
        states ={'invisible': Bool(Eval('inpatient_registration_code')), 'required': Bool(Eval('payment_mode') != 'cash') , 'readonly': Bool(Eval('payment_mode') == 'cash')}
        )

    insurance_plan= fields.Many2One(
        'health.proc.insurance.panel.product.group', 'Insurance Plan',
        help='Insurance company plan',
        domain=[('panel', '=', Eval('insurance_company')),('product_group.group_type', '=', 'plan')],
        states ={'invisible': Bool(Eval('inpatient_registration_code')), 'required': Bool(Eval('payment_mode') != 'cash'), 'readonly': Bool(Eval('payment_mode') == 'cash')},
        depends=['insurance_company'])        

    @staticmethod
    def default_payment_mode():
        return 'cash'    

    @fields.depends('tests', 'total_bill')
    def on_change_tests(self):
        if self.tests:
                self.total_bill = 0
                for test in self.tests:
                    self.total_bill = self.total_bill + test.price

    def get_total_bill(self, name):
        total = 0
        for test in self.tests:
              total = total + test.price

        return total       

    @staticmethod
    def default_patient():
        if Transaction().context.get('active_model') == 'gnuhealth.patient':
            return Transaction().context.get('active_id')
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            IPD = Pool().get("gnuhealth.inpatient.registration") 
            return IPD(Transaction().context.get('active_id')).patient.id      

    @staticmethod
    def default_inpatient_registration_code():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            return Transaction().context.get('active_id')

class SampleBatchSample(ModelSQL, ModelView):
    'Batch - Sample'
    __name__ = 'health.proc.sample.batch.lab.sample'

    batch = fields.Many2One(
        'health.proc.sample.batch',
        'Batch', required=True)
    sample = fields.Many2One('health.proc.lab.sample', 'Sample', required=True)      

class SampleBatch(ModelSQL, ModelView):
    'Batch of Samples'
    __name__ = 'health.proc.sample.batch'
    STATES = {'readonly': Or(
        Eval('state') == 'ordered',
        Eval('state') == 'received',
        Eval('state') == 'cancelled')}
    
    name = fields.Char('Code', select=True, readonly=True)
    state = fields.Selection((
        ('draft', 'Draft'),
        ('ordered', 'In-Transit'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
        ), 'Batch Status', select=True, readonly=True)      
    notes = fields.Text('Description', states=STATES)
    #samples_in_batch = fields.Many2Many(
    #    'health.proc.sample.batch.lab.sample', 'batch', 'sample',
    #    'Samples in the Batch', required=True, states=STATES
    #)   
    samples_in_batch = fields.One2Many(
        'health.proc.lab.sample', 'batch', 
        'Samples in the Batch',         
        add_remove=[
                ('batch', '=', None),
                ('state', '=', 'sample_due'),
        ],
        domain=[
            ('health_center', '=', Eval('health_center')),
            ],
        required=True, states=STATES
    )   

    the_samples = fields.Function(fields.One2Many('health.proc.lab.sample', 'batch',
        'Samples in Batch',
        add_remove=[
                ('batch', '=', None),
                ('state', '=', 'sample_due'),
        ],
        domain=[
            #('state', '=', 'sample_due'),
            ],
        states={
            'readonly': (
                Eval('state').in_(['ordered', 'received', 'cancelled'])
                ),
            },
        help="The samples in this batch."),
    'get_samples_in_batch', setter='set_samples_in_batch')
    def get_samples_in_batch(self, name):
        moves = []
        Sample = Pool().get('health.proc.lab.sample')
        found_samples = Sample.search([
                ('batch', '=', self.id),	
	        ])
        for move in found_samples:
                moves.append(move.id)
        return moves

    @classmethod
    def set_samples_in_batch(cls, shipments, name, value):
        for val in value:
                logging.info(">>>>>>>>>>>>>> from the setter"+ str(val.name))

    shipped_by = fields.Char('Shipped By', select=True, required=True, states=STATES)

    batch_created_by = fields.Many2One('gnuhealth.healthprofessional', 'Created By', readonly=True)
    shipment_sent_on = fields.DateTime('Sent On', readonly=True)

    shipment_recieved_on = fields.DateTime('Received On', readonly=True)
    shipment_received_by = fields.Many2One('gnuhealth.healthprofessional', 'Received By',
        help="Person who received the sample", readonly=True)       
    
    total_samples = fields.Function(fields.Char('Total Samples'), 'get_sample_count')
    health_center_details = fields.Function(fields.Char('Collection Point'), 'get_health_center_details')
    
    cancelled_by = fields.Char('Cancelled By', select=True,  readonly=True)
    cancelled_on = fields.DateTime('Cancelled On', select=True, readonly=True)

    health_center = fields.Many2One('gnuhealth.institution', 'Health Facility', readonly=True)


    @staticmethod
    def default_state():
        return "draft"

    @staticmethod
    def default_health_center():
        User = Pool().get('res.user')
        user = User(Transaction().user)	        
        if user.health_center:
            return user.health_center.id

    def get_sample_count(self, name):
        if self.samples_in_batch:
                return str(len(self.samples_in_batch)) + ""
        
    def get_health_center_details(self, name):
        health_center_name = ''
        if self.samples_in_batch and len(self.samples_in_batch) > 0:
            try:
                health_center_name = self.samples_in_batch[0].lab_requests[0].health_center.name.name
            except:
                logging.error("some error while getting collection center name for accession sheet")

        return health_center_name
    
    def get_sample_health_center(self, name):
        if self.samples_in_batch and len(self.samples_in_batch) > 0:
            try:
                if self.samples_in_batch[0].lab_requests[0].health_center:
                    return self.samples_in_batch[0].lab_requests[0].health_center.id
            except:
                logging.error("some error while getting collection center name for accessioning")

    @classmethod
    def generate_code(cls, **pattern):
        Config = Pool().get('gnuhealth.sequences')
        config = Config(1)
        sequence = config.get_multivalue(
            'lab_batch_sequence', **pattern)
        if sequence:
            return sequence.get()

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('name'):
                values['name'] = cls.generate_code()

        return super(SampleBatch, cls).create(vlist)        

    @classmethod
    def __setup__(cls):
        super(SampleBatch, cls).__setup__()
        cls._buttons.update({
                'cancelbatch': {
                    'invisible': Not(Equal(Eval('state'), 'draft')),
                    },
                'orderbatch': {
                    'invisible': Not(Equal(Eval('state'), 'draft')),
                    },
                'receivebatch': {
                    'invisible': Not(Equal(Eval('state'), 'ordered')),
                    },                    
		}
	)

    @classmethod
    @ModelView.button
    def cancelbatch(cls, tests):
        for test in tests:
                if test.state != 'draft':
                    raise ValidationError('The batch has already been sent or received so it can not be cancelled')
               
        cancelled_by = get_health_professional()
        cls.write(tests, {'state': 'cancelled', 'cancelled_by':cancelled_by, 'cancelled_on': datetime.now()})    
        
    @classmethod
    @ModelView.button
    def orderbatch(cls, tests):
        for test in tests:
                if test.state != 'draft':
                    raise ValidationError('The batch has already been sent or received so it can not be sent')
               
        batch_created_by = get_health_professional()

        Sample = Pool().get('health.proc.lab.sample')
        for batch in tests:
            logging.info("=========== going to process a batch: " + str(batch.id))
            for sample in batch.samples_in_batch:
                    logging.info(">>>>>>>>>>>>>goint to upate a sampelL: " + sample.name)
                    sample_obj = Sample(sample.id)
                    Sample.write([sample_obj],{'state':'in_transit'})
                
        cls.write(tests, {'state': 'ordered', 'batch_created_by':batch_created_by, 'shipment_sent_on': datetime.now()})     

    @classmethod
    @ModelView.button
    def receivebatch(cls, tests):
        for test in tests:
                if test.state != 'ordered':
                    raise ValidationError('The batch has already been cancelled or received so it can not be received')
        
        # update the state of all samples to received
        received_by = get_health_professional()
        Sample = Pool().get('health.proc.lab.sample')
        for batch in tests:
            for sample in batch.samples_in_batch:
                if sample.sample_condition == 'acceptable':
                    Sample.write([sample],{'state':'received', 'received_on': datetime.now(), 'received_by':received_by})
                else:
                    Sample.write([sample],{'state':'not_testable', 'received_on': datetime.now(), 'received_by':received_by})
                        

        cls.write(tests, {'state': 'received', 'shipment_received_by':received_by, 'shipment_recieved_on': datetime.now()})                  


    qr = fields.Function(fields.Binary('QR Code'), 'make_qrcode')
    bar = fields.Function(fields.Binary('Bar Code39'), 'make_barcode')

    def make_qrcode(self, name):
        # Create the QR code

        batch_id = self.name or ''
        total_samples = self.total_samples or ''

        qr_string = f'{batch_id}\n' \
            f'Total Samples: {total_samples}\n' \

        qr_image = qrcode.make(qr_string)

        # Make a PNG image from PIL without the need to create a temp file

        holder = io.BytesIO()
        qr_image.save(holder)
        qr_png = holder.getvalue()
        holder.close()

        return bytearray(qr_png)

    def make_barcode(self, name):
        # Create the Code39 bar code to encode the TEST ID

        batch_id = self.name or ''

        CODE39 = barcode.get_barcode_class('code39')

        code39 = CODE39(batch_id, add_checksum=False)

        # Make a PNG image from PIL without the need to create a temp file

        holder = io.BytesIO()
        code39.write(holder)
        code39_png = holder.getvalue()
        holder.close()

        return bytearray(code39_png)    
class Sample(ModelSQL, ModelView):
    'Lab Sample'
    __name__ = 'health.proc.lab.sample'
    name = fields.Char('Code', select=True, readonly=True)

    patient =  fields.Many2One('gnuhealth.patient', 'Patient', states ={'readonly':True})

    state = fields.Selection([
        ('sample_due', 'Sample Due'),
        ('in_transit', 'Sample In-Transit'),
        ('not_testable', 'Not-Testable'),        
        ('received', 'Received'),
        ], 'State', required=True, readonly=True)

    sample_point = fields.Selection((
        ('in', 'IN'),
        ('out', 'Sample Brought to Lab'),
        ('ipd', 'IPD'), 
        ('outsource', 'Out Source'),
        ), 'Sample Point', select=True)
    external_reference_no = fields.Char('Reference No.', help='Sample Additional information / reference no.')    
    sample_type = fields.Many2One('anth.proc.sample.type', 'Sample Type')
    test_category = fields.Many2One('gnuhealth.lab.test.categories', 'Category') # it will determine the tube (yellow-top, etc)

    sampled_on = fields.DateTime('Sampled On', readonly=True)
    sampled_by = fields.Many2One('gnuhealth.healthprofessional', 'Sampled By',
        help="The person who took the sample if sanpled in lab", select=True, readonly=True)    
    
    received_on = fields.DateTime('Received On', readonly=True)
    received_by = fields.Many2One('gnuhealth.healthprofessional', 'Received By',
        help="The person who received the sample", select=True, readonly=True)    

    # condition should be editable only when sample state is sample_due or in_transit
    sample_condition = fields.Selection((
        ('acceptable', 'Acceptable'),
        ('not_acceptable', 'Not Acceptable'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
        ), 'Sample Condition', select=True)
    sample_condition_remarks = fields.Char('Sample Condition Remarks', help='Any details on the condition of sample')
    lab_requests = fields.Function(fields.One2Many('gnuhealth.patient.lab.test', None,'Lab Requests'), 'get_lab_requests')
    #lab_results = fields.Function(fields.One2Many('gnuhealth.lab', None,'Lab Results'), 'get_lab_results')
    batch = fields.Many2One('health.proc.sample.batch', 'Sample Batch',readonly=True)
    lab_requests = fields.Function(fields.One2Many('gnuhealth.patient.lab.test', None,'Lab Requests'), 'get_lab_requests')
    lab_requests_in_sale = fields.Function(fields.One2Many('gnuhealth.patient.lab.test', None,'Lab Requests'), 'get_lab_requests_in_sale')
    health_center = fields.Many2One('gnuhealth.institution', 'Health Facility', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Sample, cls).__setup__()
        cls._order.insert(0, ('create_date', 'DESC'))

        cls._buttons.update({
            'print_bar_code': {}
            })

        cls._buttons.update({
            'print_lab_copy': {}
            })
    @classmethod
    @ModelView.button_action('health_proc.report_sample_barcode39')
    def print_bar_code(cls, samples):
        for sample in samples:
            #if (not sale.ticket_number and
            #        sale.residual_amount == Decimal('0.0')):
            #    sale.ticket_number = config.pos_sequence.get()
            #    sale.save()
            x = 20

    @classmethod
    @ModelView.button_action('health_proc.report_sample_lab_copy')
    def print_lab_copy(cls, samples):
        for sample in samples:
            #if (not sale.ticket_number and
            #        sale.residual_amount == Decimal('0.0')):
            #    sale.ticket_number = config.pos_sequence.get()
            #    sale.save()
            x = 20

    @classmethod
    def generate_code(cls, **pattern):
        Config = Pool().get('gnuhealth.sequences')
        config = Config(1)
        sequence = config.get_multivalue(
            'lab_sample_sequence', **pattern)
        if sequence:
            return sequence.get()

    def get_sample_health_center(self, name):
        if self.lab_requests and len(self.lab_requests) > 0:
            if self.lab_requests[0].health_center:
                return self.lab_requests[0].health_center.id
    
    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('name'):
                values['name'] = cls.generate_code()

        return super(Sample, cls).create(vlist)       

    @staticmethod
    def default_sample_condition():
        return 'acceptable'        

    @staticmethod
    def default_state():
        return 'sample_due'        

    @staticmethod
    def default_state():
        return 'in'         
    
    def get_lab_requests(self, name):
        AnalysisServiceResult = Pool().get("gnuhealth.patient.lab.test")
        lines = set()
        ids = []
        orders = AnalysisServiceResult.search([
                ('sample', '=', self.id),	
	        ])

        for line in orders:
                ids.append(line.id)

        return ids

    def get_lab_requests_in_sale(self, name):
        AnalysisServiceResult = Pool().get("gnuhealth.patient.lab.test")
        lines = set()
        ids = []
        orders = AnalysisServiceResult.search([
                ('sample', '=', self.id),	
	        ])

        sale_line_id = None
        for line in orders:
            ids.append(line.id)
            sale_line_id = line.sale_line

        if(sale_line_id):
            SaleLine = Pool().get("sale.line")
            found_sale_line = SaleLine(sale_line_id)
            for the_sale_line in found_sale_line.sale.lines:
                found_lab_requests = AnalysisServiceResult.search([('sale_line','=', the_sale_line.id)])
                for lab_req in found_lab_requests:
                    if lab_req.id in ids:
                        continue
                    else:
                        ids.append(lab_req.id)

        # get other lab request having same sale
        return ids
    
    def get_lab_results(self, name):
        AnalysisServiceResult = Pool().get("gnuhealth.lab")
        lines = set()
        ids = []
        orders = AnalysisServiceResult.search([
                ('sample', '=', self.id),	
	        ])

        for line in orders:
                ids.append(line.id)

        return ids    

    qr = fields.Function(fields.Binary('QR Code'), 'make_qrcode')
    bar = fields.Function(fields.Binary('Bar Code39'), 'make_barcode')

    def make_qrcode(self, name):
        # Create the QR code

        labtest_id = self.name or ''
        labtest_type = self.test or ''

        patient_puid = self.patient.puid or ''
        patient_name = self.patient.rec_name or ''

        requestor_name = self.requestor.rec_name or ''

        qr_string = f'{labtest_id}\n' \
            f'Test: {labtest_type.rec_name}\n' \
            f'Patient ID: {patient_puid}\n' \
            f'Patient: {patient_name}\n' \
            f'Requestor: {requestor_name}'

        qr_image = qrcode.make(qr_string)

        # Make a PNG image from PIL without the need to create a temp file

        holder = io.BytesIO()
        qr_image.save(holder)
        qr_png = holder.getvalue()
        holder.close()

        return bytearray(qr_png)

    def make_barcode(self, name):
        # Create the Code39 bar code to encode the TEST ID

        labtest_id = self.name or ''

        CODE39 = barcode.get_barcode_class('code39')

        code39 = CODE39(labtest_id, add_checksum=False)

        # Make a PNG image from PIL without the need to create a temp file

        holder = io.BytesIO()
        code39.write(holder)
        code39_png = holder.getvalue()
        holder.close()

        return bytearray(code39_png)        

class TestTypeTestComponent(ModelSQL, ModelView):
    'Test Type - Test Component'
    __name__ = 'anth.proc.test.to.test_component'
    test_type_id = fields.Many2One('gnuhealth.lab.test_type','Test Type',required=True, select=True)
    component_test_type_id = fields.Many2One('gnuhealth.lab.test_type','Component Test', required=True, select=True)
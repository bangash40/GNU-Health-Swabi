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
from datetime import datetime
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Bool, And, Equal, Or
from sql import Null
import logging
import pytz
from trytond.report import Report
import logging
import urllib, json
import relatorio.reporting
from relatorio.templates.pdf import PDFSerializer
from relatorio.templates.base import RelatorioStream
import qrcode
from io import StringIO
from trytond.model import ModelView, ModelSQL, fields
import barcode
from barcode.writer import ImageWriter
from decimal import Decimal, ROUND_UP

from trytond.modules.health.core import get_health_professional
from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserError

import urllib, json
import relatorio.reporting

from urllib.request import urlopen, build_opener
import urllib.request
from urllib.request import Request
from urllib.parse import urlencode
import http.cookiejar
from trytond.exceptions import UserWarning
import traceback


__all__ = ['ImagingTestRequest','RadiologyTestReportFinal','ImagingTestResult', 'ImagingTest','RequestPatientImagingTestStart']


class ImagingTestRequest(metaclass=PoolMeta):
    __name__ = 'gnuhealth.imaging.test.request'

    sale_line = fields.Many2One('sale.line', 'SaleLine')
    panel = fields.Integer('Panel-id')
    inpatient_registration_code =  fields.Many2One('gnuhealth.inpatient.registration', 'IPD Reg Code', readonly=True)
    cancelled_by = fields.Many2One('gnuhealth.healthprofessional', 'Cancelled By',
        help="Doctor who cancelled the lab test.", select=True, readonly=True)
    cancelled_on = fields.DateTime('Cancelled On', select=True)
    admission_request_flag = fields.Boolean('admission_request_flag')

    sale_counter = fields.Function(fields.Char("Number in Queue"), 'get_sale_counter')
    qty = fields.Integer("Quantity")
    is_rpp = fields.Boolean('RPP Sale?')

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

    def get_sale_counter(self, name):
        if self.sale_line:
            if self.sale_line.sale.sale_counter:
                return self.sale_line.sale.sale_counter


    @classmethod
    @ModelView.button
    def canceltest(cls, tests):
        for test in tests:
            if test.state != 'draft':
                raise ValidationError('The test has already been requested so it can not be cancelled')

            if  test.sale_line and test.sale_line.sale.state != 'draft':
                raise ValidationError('Payment has already been made for this test. Please contact IT/Finance Department to cancel it.')

        SaleLine = Pool().get('sale.line')
        HealthProfessional = Pool().get('gnuhealth.healthprofessional')
        cancelled_by = HealthProfessional.get_health_professional()
        for test in tests:
            line = SaleLine(test.sale_line)
            SaleLine.delete([test.sale_line])
        cls.write(tests, {
            #'state': 'cancelled', 'inpatient_registration_code': Null})

            'state': 'cancelled', 'sale_line': Null, 'cancelled_by':cancelled_by, 'cancelled_on': datetime.now()})



    @staticmethod
    def get_current_user_sale_shift():
        cursor = Transaction().connection.cursor()
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if user.sale_shift:
                return user.sale_shift 

    @classmethod
    def create(cls, vlist):
	#creating sale and sale lines for the imagaing tests in this request
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        ImagingTest = Pool().get('gnuhealth.imaging.test')
        HealthProf = Pool().get("gnuhealth.healthprofessional")

        first = True
        cnt = 1
        sale_id = -1
        vlist = [x.copy() for x in vlist]

        for values in vlist:
                if first:
                        pp = Patient(values.get('patient'))
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
                        else:    
                            Date = Pool().get('ir.date')
                            doctor_party_id = None
                            
                            Agent = Pool().get("commission.agent")
                            InsuranceCompany = Pool().get("health.proc.insurance.panel")
                            InsurancePlan = Pool().get("health.proc.insurance.panel.product.group")

                            doctor_agents = []
                            payment_mode = None
                            insurance_company = None
                            insurance_plan = None
                            panel_credit_sale = False


                            try:
                                if(values.get('doctor')):
                                    the_doctor = HealthProf(values.get('doctor'))
                                    doctor_party_id = the_doctor.name.id 
                                    doctor_agents = Agent.search([('party', '=',   the_doctor.name),])	

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
                                    'description':'Sale against Imaging Test by Patient MRNO: ' + str(pp.name.ref),
                                    'sale_type': 'opd',
                                    'sale_nature': 'imaging',
                                    'agent': doctor_agents[0].id if len(doctor_agents) > 0 else None,
                                    'doctor': doctor_party_id,

                                    'payment_mode': payment_mode,
                                    'insurance_company': insurance_company.id if insurance_company else None,
                                    'invoice_party': insurance_company.name.id if panel_credit_sale else None,
                                    'insurance_plan': insurance_plan.id if insurance_plan else None,
                                    }])
                            sale_id = sales[0].id
                        first = False

                reqTest = ImagingTest(values.get('requested_test'))
                reqProduct = Product(reqTest.product)                

                theSale = Sale(sale_id)
                HealthProf = Pool().get("gnuhealth.healthprofessional")
                doctor_name = ''
                try:
                    if(values.get('doctor')):
                        the_doctor = HealthProf(values.get('doctor'))
                        doctor_name = " [" + the_doctor.name.rec_name + "] "
                except:
                     logging.info(">>>>>> some error")
               
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
	                'description':reqTest.name + doctor_name + " (" + values.get('request') + ") " 
	                }])
                cnt = cnt + 1
                values['sale_line'] = saleLines[0].id

        return super(ImagingTestRequest, cls).create(vlist)
    
    @classmethod
    def requested(cls, requests):
        pool = Pool()
        Request = pool.get('gnuhealth.imaging.test.request')
        Result = pool.get('gnuhealth.imaging.test.result')
        ImagingTest = pool.get('gnuhealth.imaging.test')

	
        for request in requests:
                if request.state == 'done':
                    raise ValidationError("Test already created!", "The Imaging test is already created")

                if request.state == 'cancelled':
                    raise ValidationError("Test is already cancelled!","The Imaging test order is cancelled so it can't be requested!")

                if not request.sale_line:
                        if not request.inpatient_registration_code and not request.emergency_registration_code:
                                raise ValidationError(
					"The Radiology test is neither OPD nor IPD nor ER. It can't be requested!")

                if request.sale_line:
                        # Now get Sale against this sale_line id and check the status of Sale which must be processing or done
                        logging.warning("\n\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> This is an OPD Radiology order; 	`			lab_test_order_id: " +	str(request.id) + ", sale_line_id: " + str(request.sale_line) )
                        Sale = Pool().get('sale.sale')
                        SaleLine = Pool().get('sale.line')

                        saleLine = SaleLine(request.sale_line)		
                        sale = Sale(saleLine.sale)

                        logging.warning("------------------------ sale id is " + str(sale.id))
                        logging.warning("------------------------ sale state is " + str(sale.state))
                        if not sale.state in ['processing','done']:
                            if not request.inpatient_registration_code:
                                raise ValidationError("Payment not Received!", "The test can't be ordered without making payment. Please make the payment first.")
                        # also check that the product in Sale Line is the same product which is ordered in the Test


        return super(ImagingTestRequest, cls).requested(requests)

class RadiologyTestReportFinal(Report):
    __name__ = 'anth.proc.radiology.pdf_report'

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        ImagingTestResult = Pool().get("gnuhealth.imaging.test.result")
	
        logging.info(report_context)
        ids = report_context.get('data','').get('ids','')
        logging.info(ids)

        if len(ids) == 0 or len(ids) > 1:
            raise ValidationError("Selet a Result!","Please select one result from the list and then click 'Radiology PDF Report' to view report")

        testResult = ImagingTestResult(ids[0])
        logging.warn("============ going to get pdf for imagaing test id: " + str(testResult.id) + ", state: " + str(testResult.state)) 
        #if testResult.state != 'done':
        #    raise ValidationError("Report Not Ready!","The Imaing Test is not in done state")
        #ImagingTestResult.write([testResult],{'report':testResult.comment})

        #opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        urllib.request.install_opener(opener)

        params = urlencode({
                "resultId": testResult.id,
                "the_patient_name": testResult.patient.name.get_party_info(),
                "the_patient_age": testResult.patient.age,
                "the_patient_mrno": testResult.patient.puid,
                "the_patient_gender": testResult.patient.gender,
                "the_report_date": testResult.report_date,
                "the_doctor_name": testResult.doctor.name.name if testResult.doctor else '',
                "the_signed_by_name" : testResult.signed_by.name.name if testResult.signed_by else '',
                "the_test": testResult.requested_test.name,
                "the_info": testResult.signed_by.info if testResult.signed_by else '',
                "the_report": testResult.comment,
                "state": "<b>manual report</b>",
        })

        logging.warn(params)

        params = params.encode('utf-8')
        req = Request("http://localhost:9090/CRM/admin/get_radiology_report_as_pdf.htm", params)
	
       	res = urlopen(req)      

       	data = res.read()
       	return data
	
    @classmethod
    def convert(cls, report, data):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        return output_format, data

class ImagingTestResult(metaclass=PoolMeta):
    __name__ = 'gnuhealth.imaging.test.result'
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ], 'State', readonly=True)
    report_date = fields.DateTime('Report Prepared On', readonly=True)
    signed_by = fields.Many2One(
        'gnuhealth.healthprofessional', 'Radiologist', readonly=True,
        states={'invisible': Equal(Eval('state'), 'in_progress')},
        help="Health Professional that finnished the radiology report.")    
    report_path = fields.Char("Report Path")
    report = fields.Text("Report")

    @classmethod
    def __setup__(cls):
        super(ImagingTestResult, cls).__setup__()
      
        cls._buttons.update({
            'end_imaging_test': {'invisible': Or(Equal(Eval('state'), 'cancelled'),
                Equal(Eval('state'), 'done'))}, 
            })

        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    @ModelView.button
    def end_imaging_test(cls, imagingResults):
        signing_hp = get_health_professional()

        for img_test_result in imagingResults:
                # in case some old report is opened, the result would already be in Final Report
                #if img_test_result.report:
                #        raise ValidationError("The Final Report should be empty in order to Publish the report")

                cls.write([img_test_result], {
                    'state': 'done', 
	                'signed_by': signing_hp,           
                    'report_date': datetime.now(),
                    'report': img_test_result.comment,
                })        

    @staticmethod
    def default_state():
        return 'in_progress'
    
class ImagingTest(metaclass=PoolMeta):
    __name__ = 'gnuhealth.imaging.test'

    report_template = fields.Text('Report Template', required=False)


class RequestPatientImagingTestStart(ModelView):
    __name__ = 'gnuhealth.patient.imaging.test.request.start'

    inpatient_registration_code =  fields.Many2One('gnuhealth.inpatient.registration', 'IPD Reg Code', readonly=True)
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



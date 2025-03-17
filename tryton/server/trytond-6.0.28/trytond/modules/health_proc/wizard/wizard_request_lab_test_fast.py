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

__all__ = ['RequestLabTestFastStart', 'RequestLabTestFastWizard','ConfirmPosPaymentStart']


class RequestLabTestFastStart(ModelView):
    'Request Lab Test Form'
    __name__ = 'gnuhealth.request.lab_test.fast'

    EXISTING_STATES = {'readonly': Bool(Eval('new_patient')), 'required':  Not(Bool(Eval('new_patient')))}
    NEW_STATES = {'readonly': Not(Bool(Eval('new_patient'))), 'required':  Bool(Eval('new_patient'))}
    NEW_STATES_OPTIONAL = {'readonly': Not(Bool(Eval('new_patient')))}

    prefix = fields.Selection([
        (None, ''),
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ], 'Prefix', sort=False,  states=NEW_STATES)    
    name = fields.Char('Name', help='First Name', states=NEW_STATES)
    dob = fields.Date('Date of Birth', help='Date of Birth', states=NEW_STATES)
    est_years = fields.Integer('Age Years', help="Referred years", states=NEW_STATES_OPTIONAL)
    #est_dob = fields.Boolean('Est', help="Estimated from referred years")

    age = fields.Function(fields.Char('Age'), 'person_age')
    family_relation = fields.Selection((
        (None, ''),
        ('s/o', 's/o'),
        ('w/o', 'w/o'),        
        ('f/o', 'f/o'),
        ('h/o', 'h/o'),        
        ('d/o', 'd/o'),
        ('m/o', 'm/o'),
        ('b/o', 'b/o'),
        ('other', 'other'),                                
        ), 'Relationship', states=NEW_STATES)      
    family_relation_person = fields.Char('Relationship Name', states=NEW_STATES)   
    gender = fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Gender', states=NEW_STATES)

    mobile_no = fields.Char('Mobile No.', help='Mobile No.', size=11, states=NEW_STATES)
    cnic = fields.Char('CNIC (without dashes)', help='CNIC No. without any dashes, type digits only.', size=13 ,states=NEW_STATES)
    address = fields.Char('Address', help='Patient Address', states=NEW_STATES)
    country  = fields.Many2One('country.country', 'Country', states=NEW_STATES)
    city  = fields.Many2One('country.subdivision', 'City', domain=[('country','=', Eval('country'))], states=NEW_STATES)
    
    date = fields.DateTime('Sample Date')
    patient = fields.Many2One('gnuhealth.patient', 'Existing Patient', states=EXISTING_STATES)
    new_patient = fields.Boolean('New Patient?')
    doctor = fields.Many2One('gnuhealth.healthprofessional', 'Doctor', states={'required':  Bool(Eval('service'))})
    service = fields.Many2One('product.product', 'Service', states={'required':  Bool(Eval('doctor'))}, 
                              domain=[('template.type', '=', 'service'), ('is_medicament', '=', False), ('is_bed', '=', False)])
    sale_id = fields.Integer('Sale ID')    
    patient_id = fields.Integer('Patient ID')    

    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Patient Type', select=True
    )

    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Insurance Company',
        domain=[('panel_type', '=', Eval('payment_mode'))],
        depends=['payment_mode'], 
        states ={'required': Bool(Eval('payment_mode') != 'cash'), 'readonly': Bool(Eval('payment_mode') == 'cash')},
        select=True)

    insurance_plan= fields.Many2One(
        'health.proc.insurance.panel.product.group', 'Insurance Plan',
        help='Insurance company plan',
        domain=[('panel', '=', Eval('insurance_company')),('product_group.group_type', '=', 'plan')],
        states ={'required': Bool(Eval('payment_mode') != 'cash'), 'readonly': Bool(Eval('payment_mode') == 'cash')},
        depends=['insurance_company'])    

    @fields.depends('prefix', 'gender')
    def on_change_prefix(self):
        if (self.prefix):
            if self.prefix == 'Mr':
                self.gender = 'm'
                self.family_relation = 's/o';
            
            if self.prefix == 'Mrs':
                self.gender = 'f'
                self.family_relation = 'w/o';

            if self.prefix == 'Miss':
                self.gender = 'f'
                self.family_relation = 'd/o';
        else:
             self.gender = None
             self.family_relation = None

    @fields.depends('est_years', 'dob')
    def on_change_est_years(self):
        if (self.est_years):
            self.dob = estimated_date_from_years(self.est_years)
            #self.est_dob = True
            #self.age = self.person_age(name='age')
            # Resets the referred age in years to None after it computes
            # the age, so the form won't confuse the reader.
            self.est_years = None

    #@fields.depends('insurance_company', 'insurance_plan')
    #def on_change_payment_mode(self):
    #    self.insurance_company = None
    #    self.insurance_plan = None

    def person_age(self, name):
        return compute_age_from_dates(self.dob, None,
                                None, self.gender, name, None)
    
    @staticmethod
    def default_payment_mode():
        return 'cash'
    
    @staticmethod
    def default_country():
        return 2

    @staticmethod
    def default_city():
        return 70     

class ConfirmPosPaymentStart(ModelView):
    'Confirm Payment'
    __name__ = 'health.proc.confirm.pos.payment.start'
    sale = fields.Many2One('sale.sale', 'Sale', readonly=True)
    total_amount =  fields.Function(fields.Numeric('Amount'),'get_sale_total_amount')
    device = fields.Many2One('sale.device', 'PoS Device', readonly=True)
    user = fields.Many2One('res.user', 'User', readonly=True)
    welfare = fields.Many2One('anth.proc.discount.request', 'Welfare', readonly=True)
    welfare_discount = fields.Function(fields.Numeric('Welfare Discount'),'get_welfare_discount')
    net_amount =  fields.Function(fields.Numeric('Net Payable'),'get_net_amount_payable')
    sale_id = fields.Integer('Sale ID')    

    def get_sale_total_amount(self, name):
        return self.sale.total_amount        

    def get_welfare_discount(self, name):
        return None

    def get_net_amount_payable(self, name):
        return None


class RequestLabTestFastWizard(Wizard):
    'Patient Registration and Charging'
    __name__ = 'gnuhealth.request.lab_test.fast.wizard'

    start = StateView('gnuhealth.request.lab_test.fast',
        'health_proc.request_lab_test_fast_form_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Register Patient & Book Appointment', 'request', 'tryton-ok', default=True),
            ])
    
    confirm_payment = StateView('health.proc.confirm.pos.payment.start',
        'health_proc.health_proc_confirm_pos_payment_start_form_view', [
            Button('Pay Now', 'pay_now', 'tryton-ok', default=True),
            Button('Open Sale', 'open_', 'tryton-ok'),
            Button('Close', 'end', 'tryton-ok'),
            ])

    request = StateTransition()
    pay_now = StateTransition()
    open_payment_workflow = StateAction('sale_payment.wizard_sale_payment')
    open_ = StateAction('sale_pos.act_sale_form')
    open_patients_ = StateAction('health.action_gnuhealth_patient_view')
    show_ticket_ = StateReport('sale_pos.sale_ticket')      

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

    def transition_request(self):
        Patient = Pool().get("gnuhealth.patient")
        Party = Pool().get("party.party")
        patient_obj = None
       
        if(self.start.new_patient):
                # do validations
                if self.start.cnic:
                      cnic_text = str(self.start.cnic)
                      if len(self.start.cnic) != 13:
                            raise ValidationError("CNIC is not valid. The lenght of CNIC must be 13 digits.")
                      if not cnic_text.isnumeric():
                            raise ValidationError("CNIC is not valid. Only digits are allowed in a CNIC.")
                      
                if self.start.mobile_no:
                      mobile_no_text = str(self.start.mobile_no)
                      if len(self.start.mobile_no) != 11:
                            raise ValidationError("MObile No. is not valid. The length of Mobile No. must be 11 digits (starting with 0).")
                      if not mobile_no_text.isnumeric():
                            raise ValidationError("Mobile No. is not valid. Only digits are allowed in Mobile Number. ")
                      if mobile_no_text[:1] != '0':
                            raise ValidationError("Mobile No. should start with 0 ")
                #create party
                party = Party.create([{'is_patient': True, 'is_person':True, 'name': self.start.name, 'gender': self.start.gender, 
                        'family_relation': self.start.family_relation, 'family_relation_person': self.start.family_relation_person,
                        'dob':self.start.dob, 'fed_country':'PAK','alternative_identification':True if self.start.cnic else False}])
                
                #update prefix
                if self.start.prefix:
                    PersonName = Pool().get("gnuhealth.person_name")
                    pName = party[0].person_names[0]
                    PersonName.write([pName],{'prefix':self.start.prefix})


                #create party address
                PartyAddress = Pool().get("party.address")
                address = PartyAddress.create([{'party': party[0].id, 'name':self.start.address, 
                            'country':self.start.city.country.id if self.start.city else None, 
                            'subdivision':self.start.city.id if self.start.city else None}])

                #create party mobile
                PartyContact = Pool().get("party.contact_mechanism")
                contact = PartyContact.create([{'party':party[0].id, 'type':'mobile', 'value': self.start.mobile_no, 'active': True}])
                
                #Create alternative ID
                if self.start.cnic:
                        AlternativePersonId = Pool().get("gnuhealth.person_alternative_identification")
                        cnic = AlternativePersonId.create([{'name':party[0].id, 'code':self.start.cnic, 'alternative_id_type': 'country_id'}])

                #create patient
                patient = Patient.create([{'name':party[0].id, }])
                
                patient_obj = patient[0]


        else:
                patient_obj = self.start.patient
        
        self.start.patient_id = patient_obj.id
        if(self.start.doctor and self.start.service):
                Agent = Pool().get("commission.agent")
                doctor_agents = Agent.search([
	                        ('party', '=', self.start.doctor.name),				
	                        ])
                
                #findng price
                Sale = Pool().get("sale.sale")
                SaleLine = Pool().get("sale.line")                
                unit_price = self.start.service.list_price
                gross_unit_price = self.start.service.list_price
                reqProduct = self.start.service
                insurance_plan = None
                if(self.start.insurance_plan):
                     insurance_plan = self.start.insurance_plan

                panel_credit_sale = False 
                if insurance_plan: # it is a panel sale
                        if Sale.product_price_exists_in_panel_for_plan(None,  reqProduct.id, insurance_plan):
                                logging.info("The product exits in the insurance plan.............................................................................")
                                sale_price = Sale.get_product_price_from_panel_for_plan(None, reqProduct.id, insurance_plan)

                                gross_unit_price = sale_price
                                unit_price = sale_price
                                discount = 0

                                if self.start.insurance_company:
                                    if self.start.payment_mode == 'panel_credit':
                                          panel_credit_sale = True

                        else: # product is not found in Panel Price list; return Main List Price
                                gross_unit_price = reqProduct.list_price
                                unit_price = reqProduct.list_price
                                raise ValidationError("The price for this product is not set in the Insurance Plan. Contact IT Department");

                else: # its an OPD order
                        if self.start.payment_mode != 'cash':
                             raise ValidationError("The Patient Type must be Cash as no Insurance Panel and Plan is selected")
                        gross_unit_price = reqProduct.list_price
                        unit_price = reqProduct.list_price

                
                sales = Sale.create([{
                    #'payment_term':5, 
                    'currency':1,
                    'party':patient_obj.name.id,
                    'self_pick_up':'true',
                    'invoice_address':self.start.insurance_company.name.addresses[0] if panel_credit_sale else patient_obj.name.addresses[0],
                    'shipment_address':patient_obj.name.addresses[0],
                    #'sale_date':Date.today(), 
                    'description':'OPD Sale for Patient MRNO: ' + str(patient_obj.name.ref),
                    'sale_type': 'opd',
                    'payment_mode': self.start.payment_mode if self.start.payment_mode else None,
                    'insurance_company': self.start.insurance_company.id if self.start.insurance_company else None,
                    'invoice_party': self.start.insurance_company.name.id if panel_credit_sale else None,
                    'insurance_plan': self.start.insurance_plan.id if self.start.insurance_plan else None,
                    'agent': doctor_agents[0].id if len(doctor_agents) > 0 else None,
                    'doctor': self.start.doctor.name.id if self.start.doctor else None,
                }])
                sale_id = sales[0].id
                self.start.sale_id = sale_id
                
                doctor_name = ''
                if(self.start.doctor):
                      doctor_name = " [" + self.start.doctor.name.rec_name + "]"

                saleLines = SaleLine.create([{
	                'product':self.start.service.id, 
	                'sale':sale_id,
	                'unit':1,
	                'gross_unit_price': gross_unit_price,
	                'unit_price': unit_price,
	                'quantity':1,
	                'description':self.start.service.name + doctor_name 
	            }])	                

                Appointment = Pool().get("gnuhealth.appointment")
                appointments = Appointment.create([{
	                'patient':patient_obj.id, 
	                'state': 'confirmed',
	                'visit_type': 'new', # change it to refferred
	                'healthprof': self.start.doctor.id if self.start.doctor else None,
                     'sale': sale_id,
	                	                
	                }])


                SysConfig = Pool().get('anth.proc.system.config')
                inst_obj = SysConfig(1)
                try:
                    url = "http://wa.sabtech.org/api/send.php"
                    mobile = '923006655875'
                    mobile_no_text = patient_obj.mobile
                    mobile = "92" +  mobile_no_text[1:]
                    message = 'Test Msg'
                    api_key = '923334795710-9b63a678-9138-4cac-9933-898ae69c6dbb'

                    message = inst_obj.promotion_message
                    if(message):
                        message = message.replace('(000-00-000)', " " + patient_obj.name.ref)
                        url = url + "?api_key=" + api_key + "&mobile=" + mobile + "&message" + message
                        
                        payload={'api_key': api_key, 'mobile':mobile, 'message':message}
                        headers = {}

                        #response = requests.get(url, params=payload, headers=headers,)                    
                        #logging.info(response.text)
                except Exception as err:
                    logging.error("An error occurred: " + str(err))
                    traceback.print_exc()
                    traceback.print_stack()    

                ResUser = Pool().get('res.user')
                user = ResUser(Transaction().user)        

                if inst_obj.lims_server_port == -1:
                    return 'confirm_payment'
                else: 
                    if inst_obj.lims_server_port == user.id:            
                        return 'confirm_payment'
                    else:
                        return 'open_'

        return 'open_patients_'

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([('id', '=', self.start.sale_id)])

        return action, {}
    
    def do_open_payment_workflow(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'active_id': self.start.sale_id,
            })

        action['context'] = PYSONEncoder().encode({
                'active_id': self.start.sale_id,
            })            
        return action, {}

    def do_open_patients_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([('id', '=', self.start.patient_id)])
        return action, {}

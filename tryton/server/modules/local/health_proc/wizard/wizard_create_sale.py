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
from trytond.wizard import Wizard, StateTransition, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pool import Pool
import logging
from trytond.model.exceptions import ValidationError
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal, And, Or, If
from trytond.modules.product import price_digits, round_price

import requests
import traceback
from trytond.wizard.wizard import StateReport
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['CreatePatientSaleStart', 'HealthSaleLine','CreatePatientSale','GeneralSaleLine','DeletePatientSaleLineStart', 'DeletePatientSaleLine','CreateShipmentWizard']

class HealthSaleLine(ModelView):
    'Health Sale Line'
    __name__ = 'gnuhealth.health_lab.sale_line'

    name = fields.Many2One('gnuhealth.patient.sale.create.start', 'Service', readonly=True)
    desc = fields.Char('Description', required=True)
    product = fields.Many2One('product.product', 'Product', required=True, domain=[('active', '=', True)])
    qty = fields.Integer('Qty')
    list_price = fields.Numeric('Unit Price', states ={'readonly':True})
    total_price = fields.Numeric('Total Price', states={'readonly':True})
    
    @staticmethod
    def default_qty():
        return 1

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
                self.desc = self.product.name
                self.list_price = self.product.list_price
                self.qty = 1
                if not self.product.list_price:
                        raise ValidationError("The price for this product is not set yet. Contact IT Department");
                self.total_price = self.qty * self.product.list_price

    @fields.depends('qty','product')
    def on_change_qty(self):
        if self.qty:
                if self.product:
                        if self.qty >=1:
                                self.total_price = self.qty * self.product.list_price
                        else:
                                #self.total_price = 0
                                self.qty = 1
                                self.total_price = self.qty * self.product.list_price
                                #self.raise_user_error('The quantity must be positive')
				
class GeneralSaleLine(ModelView):
    'General Sale Line'
    __name__ = 'anth.proc.general.sale.line'

    desc = fields.Char('Description', required=True)
    product = fields.Many2One('product.product', 'Product', required=True, domain=[('active', '=', True)])
    qty = fields.Integer('Qty')
    list_price = fields.Numeric('Unit Price', states ={'readonly':True})
    total_price = fields.Numeric('Total Price', states={'readonly':True})
    
    @staticmethod
    def default_qty():
        return 1

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
                self.desc = self.product.name
                self.list_price = self.product.list_price
                self.qty = 1
                if not self.product.list_price:
                        raise ValidationError("The price for this product is not set yet. Contact IT Department");
                self.total_price = self.qty * self.product.list_price

    @fields.depends('qty','product')
    def on_change_qty(self):
        if self.qty:
                if self.product:
                        if self.qty >=1:
                                self.total_price = self.qty * self.product.list_price
                        else:
                                #self.total_price = 0
                                self.qty = 1
                                self.total_price = self.qty * self.product.list_price
                                #self.raise_user_error('The quantity must be positive')

class CreatePatientSaleStart(ModelView):
    'Create Patient Sale Start'
    __name__ = 'gnuhealth.patient.sale.create.start'

    date = fields.DateTime('Date')
    patient = fields.Many2One('gnuhealth.patient', 'Patient', required=True, states ={'readonly': Bool(Eval('nature') == 'ipd')})
    nature = fields.Char('OPD/IPD/ER/DayCare?', states={'readonly':True})
    inpatient_registration_code =  fields.Integer('IPD No.', states ={'readonly':True}) 
    emergency_registration_code =  fields.Integer('ER No.', states ={'readonly':True}) 
    ward = fields.Char('Ward', states={'readonly':True})
    bed = fields.Char('Bed', states={'readonly':True})
    department = fields.Char('Department', states={'readonly':True})
    doctor = fields.Many2One('gnuhealth.healthprofessional', 'Doctor')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),
        ], 'State', readonly=True)
    
    general_sale_lines = fields.One2Many('anth.proc.general.sale.line', None, 'List of Other Services', help="List of Services")
    sale_id = fields.Integer('Sale ID')    

    total_bill = fields.Function(fields.Numeric('Total Bill', states ={'readonly':True}, digits=price_digits),'calculate_list_price')

    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Patient Type', select=True,
        states ={'invisible': Bool(Eval('nature') == 'ipd')}
    )

    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Insurance Company',
        select=True,
        depends=['payment_mode'], 
        domain=[('panel_type', '=', Eval('payment_mode'))],
        states ={'invisible': Bool(Eval('nature') == 'ipd'), 'required': Bool(Eval('payment_mode') != 'cash') , 'readonly': Bool(Eval('payment_mode') == 'cash')}
        )

    insurance_plan= fields.Many2One(
        'health.proc.insurance.panel.product.group', 'Insurance Plan',
        help='Insurance company plan',
        domain=[('panel', '=', Eval('insurance_company')),('product_group.group_type', '=', 'plan')],
        states ={'invisible': Bool(Eval('nature') == 'ipd'), 'required': Bool(Eval('payment_mode') != 'cash'), 'readonly': Bool(Eval('payment_mode') == 'cash')},
        depends=['insurance_company'])        

    @staticmethod
    def default_payment_mode():
        return 'cash'
    
    @fields.depends('total_bill','general_sale_lines')
    def on_change_general_sale_lines(self):
        total = 0
        try:
                if(self.general_sale_lines):
                        for line in self.general_sale_lines:
                                if line.total_price:
                                        total = total + line.total_price
                
                        self.total_bill = total
        except:
              total = -1

    def calculate_list_price(self, name):
        total_bill = 0
        if(self.general_sale_lines):
            for line in self.general_sale_lines:
                  total_bill = total_bill + line.total_price
   
        return total_bill
    
    def get_advance_lines(self, name):
        # name is the filed to match the inpatient-registration-id in the gnuhealth_patient_rounding table
        lines = set()
        if self.advance_invoices:
                for line in self.advance_invoices:
                        lines.add(line.invoice.id)

        logging.info(lines)
        return list(lines)
        
    @staticmethod
    def default_date():
        return datetime.now()

    @staticmethod
    def default_patient():
        if Transaction().context.get('active_model') == 'gnuhealth.patient':
            return Transaction().context.get('active_id')

        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                    return inpatient.patient.id

        if Transaction().context.get('active_model') == 'gnuhealth.prescription.order':
                prescription_id = Transaction().context.get('active_id')
                Prescription = Pool().get('gnuhealth.prescription.order')
                pp = Prescription(prescription_id)
                return pp.patient.id

    @staticmethod
    def default_nature():
        nature = 'er'
        if Transaction().context.get('active_model') == 'gnuhealth.patient':
            nature =  "opd"

        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                    nature =  "ipd"

        return nature

    @staticmethod
    def default_bed():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                Bed = Pool().get("gnuhealth.hospital.bed")
                Ward = Pool().get("gnuhealth.hospital.ward")
                Product = Pool().get("product.product")

                if inpatient.bed:
                        bed = Bed(inpatient.bed)
                        product = Product(bed.name)
                        ward = Ward(bed.ward)
                        return str(bed.name) + ":" + str(product.code)

    @staticmethod
    def default_ward():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                Bed = Pool().get("gnuhealth.hospital.bed")
                Ward = Pool().get("gnuhealth.hospital.ward")
                Product = Pool().get("product.product")

                if inpatient.bed:
                        bed = Bed(inpatient.bed)
                        product = Product(bed.name)
                        ward = Ward(bed.ward)
                        return ward.name

    @staticmethod
    def default_inpatient_registration_code():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                return Transaction().context.get('active_id')

    @staticmethod
    def default_sale_line():
        if Transaction().context.get('active_model') == 'gnuhealth.prescription.order':
                prescription_id = Transaction().context.get('active_id')
                Prescription = Pool().get('gnuhealth.prescription.order')
                pp = Prescription(prescription_id)
                sale_lines = []
                for line in pp.prescription_line:
                        logging.info(line)
                        logging.info(line.id)
                        sale_lines.append({'product':line.medicament.name.id, 'description':line.medicament.name.template.name, 'quantity':1})
                return sale_lines
        

class CreatePatientSale(Wizard):
    'Create Patient Sale'
    __name__ = 'gnuhealth.patient.sale.create'

    start = StateView('gnuhealth.patient.sale.create.start',
        'health_proc.patient_sale_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Sale', 'request', 'tryton-ok', default=True),
            ])

    confirm_payment = StateView('health.proc.confirm.pos.payment.start',
        'health_proc.health_proc_confirm_pos_payment_start_form_view', [
            Button('Pay Now', 'pay_now', 'tryton-ok', default=True),
            Button('Open Sale', 'open_', 'tryton-ok'),
            Button('Close', 'end', 'tryton-ok'),
            ])
                
    request = StateTransition()
    pay_now = StateTransition()
    open_ = StateAction('sale_pos.act_sale_form')
    show_ticket_ = StateReport('sale_ticket_other_sale')      

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
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        ProductTemplate = Pool().get('product.template')

        price_list = None
        panel_patient = False
        gross_unit_price = 0
        unit_price = 0

        first = True
        cnt = 1
        sale_id = -1
        insurance_plan_id = None
        sale_type = ''
        panel = None

        insurance_plan = None
        if(self.start.insurance_plan):
                insurance_plan = self.start.insurance_plan

        panel_credit_sale = False 
        if insurance_plan: # it is a panel sale
                if self.start.insurance_company:
                        if self.start.payment_mode == 'panel_credit':
                                panel_credit_sale = True

        # get the agent info as well
        Agent = Pool().get("commission.agent")
        if self.start.doctor:
                doctor_agents = Agent.search([
                        ('party', '=', self.start.doctor.name),				
                ])
        else:
              doctor_agents = []

        for values in self.start.general_sale_lines:	
                if first:
                        pp = Patient(self.start.patient)
                        if self.start.inpatient_registration_code:
                                logging.warning("\ninpatient registration code is therere: ")
                                logging.warning(self.start.inpatient_registration_code)
                                InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
                                inpatient = InpatientRegistration(self.start.inpatient_registration_code)
                                if inpatient.sale_id.state == 'draft':
                                        sale_id = inpatient.sale_id.id
                                else:
                                        raise ValidationError('The Sale for this inpatient record is closed now. Either create new inpatient record or charge in OPD!')

                                if inpatient.payment_mode in ['panel_cash','panel_credit'] and inpatient.panel:
                                        panel_patient = True
                                        panel = inpatient.panel
                                else:
                                        panel_patient = False

                                if inpatient.hospitalization_type == 'ER':
                                        sale_type = 'er'
                                else:
                                        sale_type = 'ipd'
                        else:
                                sale_type = 'opd'
                                if(self.start.nature):
                                      if self.start.nature == 'er':
                                            sale_type = 'er'
                                Date = Pool().get('ir.date')

                                # panel details
                                sales = Sale.create([{
	                                #'payment_term':1, 
	                                'currency':1,
	                                'party':pp.name.id,
	                                'self_pick_up':'true',
                                        'invoice_address':self.start.insurance_company.name.addresses[0] if panel_credit_sale else pp.name.addresses[0],
	                                'shipment_address':pp.name.addresses[0],
	                                'description':'Sale against Misc. Services by Patient MRNO: ' + str(pp.name.ref),
                                        'agent': doctor_agents[0].id if len(doctor_agents) > 0 else None,
	                                'sale_type': sale_type,
                                        'sale_report': 'other_sales',
                                        'doctor': self.start.doctor.name.id if self.start.doctor else None,

                                        'payment_mode': self.start.payment_mode if self.start.payment_mode else None,
                                        'insurance_company': self.start.insurance_company.id if self.start.insurance_company else None,
                                        'invoice_party': self.start.insurance_company.name.id if panel_credit_sale else None,
                                        'insurance_plan': self.start.insurance_plan.id if self.start.insurance_plan else None,
                        
	                                }])
                                sale_id = sales[0].id
                        first = False


                reqProduct = Product(values.product)
                reqProdTemplate = ProductTemplate(reqProduct.template)

                theSale = Sale(sale_id)
                if panel_patient and panel: # it is a panel sale
                        if Sale.product_price_exists_in_panel(panel, reqProduct.id):
                                logging.info("The product exits in the insurance plan.............................................................................")
                                sale_price = Sale.get_product_price_from_panel(panel, reqProduct.id)

                                gross_unit_price = reqProduct.list_price # price in the Main List 
                                unit_price = sale_price #sale_price.get(reqProduct.id, None) # price in the price list
                                discount = 0

                                logging.info("+++++++++++++++++++++++++++++++++++++ final price received from panel price list: " + str(unit_price))
                        else: 
                                gross_unit_price = reqProduct.list_price
                                unit_price = reqProduct.list_price
                                logging.info("+++++++++++++++++< Price not found in Panel> so raising error and not using price from main price list: " + str(unit_price))
                                raise ValidationError("The price for this product is not set in the Insurance Plan. Contact IT Department");

                else: # its an OPD order
                        gross_unit_price = reqProduct.list_price
                        unit_price = reqProduct.list_price

                        if insurance_plan: # it is a panel sale
                                if Sale.product_price_exists_in_panel_for_plan(None,  reqProduct.id, insurance_plan):
                                        logging.info("The product exits in the insurance plan.............................................................................")
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
                        'unit':reqProdTemplate.default_uom,
                        'gross_unit_price': gross_unit_price,
                        'unit_price':unit_price,
                        'quantity':values.qty,
                        'sequence':cnt,
                        'description':values.desc,
                        }])
                cnt = cnt + 1
                self.start.sale_id = sale_id


                #logging.warning("\n----------------- the request id is: " + str())
                logging.warning("\n ,patient id is: " + str(pp.id)) 

                logging.warning("\n , the product is: " + str(reqProduct.id))

        logging.warning('>>>>>>>>>>>>> Sale type is: ' + sale_type)
        
        #if it is an OPD sale then, open the Sale in the End
        if sale_type == 'opd' or sale_type == 'er':
                SysConfig = Pool().get('anth.proc.system.config')
                inst_obj = SysConfig(1)

                if inst_obj.lims_server_ip_address == -1:
                    return 'confirm_payment'
                else:                 
                    return 'open_'
        
        return 'end'        

    def do_open_(self, action):
        pool = Pool()
        Sale = pool.get('sale.sale')
        logging.error('-------------------sale id is: ' + str(self.start.sale_id))
        action['pyson_domain'] = PYSONEncoder().encode([('id', '=', self.start.sale_id)])

        return action, {}

class DeletePatientSaleLineStart(ModelView):
    'Delete Charged Service Start'
    __name__ = 'health.proc.patient.sale.line.delete.start'

    sale_line = fields.Many2One('sale.line', 'Service', required=True, readonly=True)
        
    @staticmethod
    def default_sale_line():
        if Transaction().context.get('active_model') == 'sale.line':
            SaleLine = Pool().get('sale.line')
            saleLine = SaleLine(Transaction().context.get('active_id'))
            if saleLine:
                return Transaction().context.get('active_id')
    
class DeletePatientSaleLine(Wizard):
    'Delete Charged Service'
    __name__ = 'health.proc.patient.sale.line.delete'

    start = StateView('health.proc.patient.sale.line.delete.start',
        'health_proc.patient_sale_line_delete_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Delete Service', 'request', 'tryton-ok', default=True),
            ])
    request = StateTransition()

    def transition_request(self):

        #creating sale and sale lines for the imagaing tests in this request
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        ProductTemplate = Pool().get('product.template')
        if self.start.sale_line:
                if self.start.sale_line.sale.state != 'draft':
                      raise ValidationError("The Sale must be in draft state to delete a service from it.");
                if self.start.sale_line.sale.sale_type != 'ipd':
                      raise ValidationError("This feature is available on for IPD Sales.");
        
                #remove service
                SaleLine.delete([self.start.sale_line])

        else:
                raise ValidationError("No Service is selected for removal.");
              
        return 'end'

class CreateShipmentWizard(Wizard):
    'Create Shipment for Purchase'
    __name__ = 'health.proc.shipment.create.wizard'
  
    start_state = 'create_shipment'
    create_shipment = StateAction('health_proc.act_shipment_form_action')

    def do_create_shipment(self, action):
      
        purchases = Transaction().context.get('active_id')

        try:
            purchase = Pool().get('purchase.purchase').browse([purchases])[0]
        except:
            raise ValidationError("Please select a purchase first ...")
        incoming_moves = []
        StockMove = Pool().get("stock.move")
        for line in purchase.lines:
            moves = StockMove.search([('origin', '=', str(line)),('state', '=', 'draft')])
            logging.info(len(moves))
            if moves and len(moves) == 1:
                  incoming_moves.append(moves[0].id)

        action['pyson_domain'] = PYSONEncoder().encode([
            ('supplier', '=', purchase.party.id),
            ('incoming_moves', '=', incoming_moves),
	
            ])
        action['pyson_context'] = PYSONEncoder().encode({
            'supplier': purchase.party.id,
            'incoming_moves': incoming_moves,
	        #'originating_round': purchase.id,
            })
            
        return action, {}
        
    @classmethod
    def __setup__(cls):
        super(CreateShipmentWizard, cls).__setup__()


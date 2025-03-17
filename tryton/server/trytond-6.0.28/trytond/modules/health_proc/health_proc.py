# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnu.org>
#    Copyright (C) 2013  Sebastián Marro <smarro@thymbra.com>
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
#ty
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from datetime import datetime, date, time, timedelta
from trytond.model import Workflow, ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
import logging
from decimal import Decimal, ROUND_UP
from trytond.config import config
from datetime import datetime
from trytond.pyson import Eval, Not, Bool, And, Equal, Or
import pytz
from sql import Null
from trytond.pyson import PYSONEncoder
from trytond import backend
import traceback
from trytond.exceptions import UserWarning
from trytond.exceptions import UserError

from trytond.modules.health.core import get_health_professional, get_institution
from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserError

from trytond.modules.account_invoice_discount.invoice import discount_digits
from trytond.modules.product import price_digits, round_price
from trytond.wizard.wizard import StateReport
from trytond.wizard import Wizard, StateTransition, StateView, Button, StateAction


__all__ = [
	'SystemConfig', 'SaleLine', 'DiscountRequest', 'DiscountRequestLine','ResUser', 'HMISUtility', 'Sale', 
    'HealthprofType','HealthProfessional','HealthProfessionalServices','DiscountType', 'Lot', 'ReturnSale','PatientData',
    'PartyData','Appointment','AccountStatementLine', 'StockMove','InvoiceLine','WizardSalePayment',
    'ProductGroup','ProductGroupLine','InsurancePanel', 'InsurancePanelProductGroup',
    'PrescriptionLabTest', 'PrescriptionImagingTest','PrescriptionOrder','BirthCertificate','DeathCertificate', 
    'HealthInstitution','Pathology','PrescriptionDisease','InsurancePanelBill', 'Purchase','Shipment','PurchaseRequest',
    'InternalShipment','PurchaseRequisition','ProductProduct','ShipmentIn','ProcedureComplexity','Directions','Surgery','PurchaseLine']

price_digits = (16, config.getint('product', 'price_decimal', default=4))
__metaclass__ = PoolMeta

sequences = ['proc_request_sequence']

class HealthprofType(ModelSQL, ModelView):
    'Health Professional Type'
    __name__ = 'anth.proc.healthprof.type'   

    healthprof_type = fields.Char('Year of Pregnancy')
    description = fields.Char('Description', required=True)   

class HealthProfessionalServices(ModelSQL, ModelView):
    'Health Professional Services'
    __name__ = 'anth.proc.hp_services'

    name = fields.Many2One('gnuhealth.healthprofessional',
                           'Health Professional', required=True)

    product = fields.Many2One(
        'product.product', 'Service', required=True,
        help='Service Code')
    
    product_price = fields.Numeric('Charged to Patient', states ={'readonly':True}, digits=price_digits)

    share_calculation_method = fields.Selection((
        ('amount_based', 'Amount Based'),
        ('percentage_based', 'Percentage Based'),
        ), 'Share Calculation Method', select=True)
    
    share_percentage = fields.Numeric("Share %age")
    share_amount = fields.Numeric("Share Amount")
    calculated_share_amount = fields.Numeric('Paid to Doctor', states ={'readonly':True}, digits=price_digits)
    remarks = fields.Text('Remarks (if any)')

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
               self.product_price = self.product.list_price
    
    def get_rec_name(self, name):
        return self.product.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('product',) + tuple(clause[1:]),
                ]

    @classmethod
    def __setup__(cls):
        super(HealthProfessionalServices, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_uniq', Unique(t, t.name, t.product),
             'This service is already assigned to the Health Professional'),
        ]    

class Surgery(metaclass=PoolMeta):
    __name__ = 'gnuhealth.surgery'
    procedures_requested = fields.Function(fields.One2Many('gnuhealth.directions', None, 'Surgeries Requested from OPD'), 'get_procedures_requested')   
    anesthesia_evaluation_sale = fields.Many2One('sale.sale', 'Anesthesia Evaluation Bill')
    ipd_record = fields.Many2One('gnuhealth.inpatient.registration', 'IPD Admission')
 

    def get_procedures_requested(self, name):
        lines = set()
        #if self.doctor_shares:
        #    for line in self.doctor_shares:
        #        lines.add(line.id)

        return list(lines)    


class HealthProfessional(metaclass=PoolMeta):
    __name__ = 'gnuhealth.healthprofessional'
    healthprof_type = fields.Many2One(
        'anth.proc.healthprof.type', 'Health Professional Type', required=False)
    
    services = fields.One2Many('anth.proc.hp_services', 'name', 'Services')
    eligible_for_doctor_share = fields.Boolean('Eligible for Doctor Share?')


    def get_rec_name(self, name):
        rec_name = super(HealthProfessional, self).get_rec_name(name)
        department_name = ''
        if self.main_specialty:
            rec_name += ', %s %s' % (self.main_specialty.specialty.name, department_name)
        
        return rec_name 

    def get_department(cls):
        department_name = ''
        if cls.main_specialty:
            department_name = cls.main_specialty.specialty.name

        return department_name

class ResUser(metaclass=PoolMeta):
    __name__ = 'res.user'
    statement_journal = fields.Many2One('account.statement.journal', 'Statement Journal')
    specialty = fields.Many2One('gnuhealth.specialty', 'Specialty')
    
    sale_shift = fields.Selection((
        (None, ''),
        ('morning', 'Morning'),
        ('evening', 'Evening'),
        ('night', 'Night'),
        ), 'Sale Shift', select=True, readonly=True)    
    
    health_center = fields.Many2One('gnuhealth.institution', 'Health Facility')

    @classmethod
    def __setup__(cls):
        super(ResUser, cls).__setup__()
        cls._preferences_fields.extend([
                'specialty',
                ])
        cls._context_fields.insert(0, 'specialty')

    def get_status_bar(self, name):
        status = super(ResUser, self).get_status_bar(name)
        if self.specialty:
            status += ' - %s' % (self.specialty.rec_name)
        return status    

class HMISUtility(ModelSQL, ModelView):
        "HMIS Utility Class"
        __name__ = 'anth.proc.hmis.utility'

        @staticmethod
        def format_date_time(date_obj):
                # get the create_date of the lab results record
                if date_obj:

                        Company = Pool().get('company.company')

                        timezone = None
                        company_id = Transaction().context.get('company')
                        if company_id:
                                company = Company(company_id)
                                if company.timezone:
                                        timezone = pytz.timezone(company.timezone)

                        date_obj = datetime.astimezone(date_obj.replace(tzinfo=pytz.utc), timezone)

                return date_obj

class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.line'
    product_group_id = fields.Integer('Product-Group-Id')
    line_created_on = fields.Function(fields.DateTime('Service Ordered On'),'get_created_on_with_timezone')
    amount_without_discount = fields.Function(fields.Numeric('Total Amount',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                'readonly': ~Eval('_parent_sale'),
                },
            depends=['type']), 'get_amount_without_discount')

    line_discount = fields.Function(fields.Numeric('Discount',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                'readonly': ~Eval('_parent_sale'),
                },
            depends=['type']), 'get_line_discount')

    #lot_lines = fields.Function(fields.One2Many('stock.lot', None, 'Batches'),'get_batches',setter='set_batch')
    lot = fields.Selection('get_all_lots', "Batch (s)", select=True)

    @fields.depends('lot', 'product')
    def get_all_lots(cls):
        if not cls.product:
             return []
        pool = Pool()
        options = []
        options.append(('',''))
        Lot = pool.get("stock.lot")
        lots = Lot.search([('product', '=', cls.product.id)] , order=[('expiration_date', 'DESC')])
        test = ''
        Location = pool.get('stock.location')

        locations = Location.search([('type', '=', 'storage')])
        for lot in lots:
            context = {
                'locations': [l.id for l in locations]
                }
            with Transaction().set_context(**context):
                quantity = Lot(lot.id).quantity
                test = test + "[" + str(lot.expiration_date) + ":" + str(quantity) + "], "
                if quantity > 0:
                    lot_details = 'BATCH: ' + str(lot.number) +  ',   QTY: '+ str(quantity) + ',   EXPIRY: ' + str(lot.expiration_date)
                    options.append((str(lot.id), lot_details))


        return options


    def get_move_final(self, shipment_type):
        logging.info("================ get move is called " + str(self.lot))
        move =  super(SaleLine, self).get_move(shipment_type)
        if self.lot:
            if move: 
                move.lot = int(self.lot)
        
        return move


    def get_batches(self, name):
        lines = set()
        Lot = Pool().get("stock.lot")
        lots = Lot.search([('product', '=', self.product.id)] , order=[('expiration_date', 'DESC')])
        

        logging.info(lots)

        for line in lots:
            lines.add(line.id)

        return list(lines)    
    
    @classmethod
    def set_batch(cls, sale_lines, name, value):
        for val in value:
                x = 20

    def get_created_on_with_timezone(self, name):
        Company = Pool().get('company.company')

        timezone = None
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            if company.timezone:
                timezone = pytz.timezone(company.timezone)

        dt = self.create_date
        return datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

    def get_amount_without_discount(self, name):
        if self.type == 'line':
                amount = Decimal('0.0')
                amount += self.sale.currency.round(
                        Decimal(str(self.quantity)) * self.gross_unit_price)
                return amount
        elif self.type == 'subtotal':
            amount = Decimal('0.0')
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += line2.sale.currency.round(
                        Decimal(str(line2.quantity)) * line2.gross_unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal('0.0')
            return amount
        return Decimal('0.0')

    def get_line_discount(self, name):
        if self.type == 'line':	
                amount = Decimal('0.0')
                amount += self.sale.currency.round(
                       Decimal(str(self.quantity)) * Decimal(self.discount) * self.gross_unit_price)
                return amount
        elif self.type == 'subtotal':
            amount = Decimal('0.0')
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += line2.sale.currency.round(
                       Decimal(str(line2.quantity)) * Decimal(line2.discount) * line2.gross_unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal('0.0')
            return amount
        return Decimal('0.0')

    @fields.depends('product', 'discount','description','quantity')
    def on_change_product(self):
        if not self.product:
            return super(SaleLine, self).on_change_product()
         
        if(self.product.template.type != 'goods'):
            return super(SaleLine, self).on_change_product()
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')

        locations = Location.search([('type', '=', 'storage')])

        #Transaction().set_context({'locations': [l.id for l in locations]})
        #context = {'product':self.product.id, location}
        #for l in locations:
        #        logging.info("====== at  " + l.name + " stock is " + str(l.quantity))
        #context['stock_date_end'] = Date.today()
        #Transaction().set_context(context)

        #pbl = Product.products_by_location(
        #        location_ids=Transaction().context['locations'],
        #        product_ids=[self.product.id], with_childs=True)

        
        quantity = -230.7854
        try:
                context = {
                        'locations': [l.id for l in locations]
                        }
                with Transaction().set_context(**context):
                        quantity = Product(self.product.id).quantity
        except:
                logging.info("============= some error in getting quantity")
                traceback.print_exc()
                traceback.print_stack()
        #if pbl.values():
        #    quantity = reduce(lambda x, y: x + y, pbl.values())

        try:

                logging.info("============== quantity found is ==========" + str(quantity))
                if quantity == -23.7854:
                        qtyInfo = "Unable to get current stock"
                else:
                        qtyInfo = "Current Stock: " + str(quantity)
                        if(quantity <= 0):
                                qtyInfo = "The quantity in stock is zero or negative"
                self.description = qtyInfo
                #Lot = Pool().get("stock.lot")
                #lots = Lot.search([('product', '=', self.product.id)])
                #test = ''
                #for lot in lots:
                #        test = test + str(lot.expiration_date) + ", "
                #self.description = qtyInfo + "\n" + test
        except:
                self.description = "some error while getting stock"
                traceback.print_exc()
                traceback.print_stack()

        the_lot_lines = []
        try:
                Lot = Pool().get("stock.lot")
                lots = Lot.search([('product', '=', self.product.id)] , order=[('expiration_date', 'DESC')])
                test = ''

                for lot in lots:
                    context = {
                        'locations': [l.id for l in locations]
                        }
                    with Transaction().set_context(**context):
                        quantity = Lot(lot.id).quantity
                        test = test + "[" + str(lot.expiration_date) + ":" + str(quantity) + "], "
                        if quantity > 0:
                             the_lot_lines.append({'number': lot.number, 'product': self.product.id, 'quantity': quantity, 'expiration_date':lot.expiration_date})
                self.description = self.description + ", " + test
        except:
                self.description = self.description + ", " + "some error while getting lots"
                traceback.print_exc()
                traceback.print_stack()

        #self.lot_lines = tuple(the_lot_lines)	


        return super(SaleLine, self).on_change_product()

    @fields.depends('product','quantity', 'description')
    def on_change_quantity(self):
        logging.info("------------ product quantity cahgned")
        if not self.product:
            return super(SaleLine, self).on_change_product()
                
        if(self.product.template.type != 'goods'):
            return super(SaleLine, self).on_change_quantity()

        # getting the quantity in hand
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')

        locations = Location.search([('type', '=', 'storage')])

        #Transaction().set_context({'locations': [l.id for l in locations]})
        #context = {'product':self.product.id, location}
        #for l in locations:
        #        logging.info("====== at  " + l.name + " stock is " + str(l.quantity))
        #context['stock_date_end'] = Date.today()
        #Transaction().set_context(context)

        #pbl = Product.products_by_location(
        #        location_ids=Transaction().context['locations'],
        #        product_ids=[self.product.id], with_childs=True)
        
        qty = -230.7854
        try:
                context = {
                        'locations': [l.id for l in locations]
                        }
                with Transaction().set_context(**context):
                        qty = Product(self.product.id).quantity
        except:
                logging.info("============= some error in getting quantity for matching with quantity")
        #if pbl.values():
        #    quantity = reduce(lambda x, y: x + y, pbl.values())

        try:

                logging.info("============== quantity found is ==========" + str(qty))
                logging.info("============== quantity sold is ==========" + str(self.quantity))
                if qty == -23.7854:
                        qtyInfo = "Unable to get current stock"
                else:
                        qtyInfo = "Current Stock for sale: " + str(qty) + ", matching with: " + str(self.quantity)
                        if(self.quantity > qty):
                                qtyInfo = qtyInfo + " >>>>> Quantity is lower in stock"
                                #raise UserWarning("The quantity in stock is: " + str(qty) + ", It is less than your enterd quantity " + str(self.quantity))
                                #raise UserError("Some error","Title")
                                qtyInfo = "The quantity in stock is: " + str(qty) + ", It is less than your enterd quantity " + str(self.quantity) + ". Please change quantity"
                                self.quantity = 0
                self.description = qtyInfo
        except:
                self.description = qtyInfo  + " some error while matching stock"
                traceback.print_exc()
                traceback.print_stack()

        return super(SaleLine, self).on_change_quantity()

    def get_lab_tat(cls):
        tat_info = ''
        LabRequest = Pool().get("gnuhealth.patient.lab.test")
        found_lab_request = LabRequest.search([('sale_line','=', cls.id)])
        
        order_date = cls.create_date
        if len(found_lab_request) == 1:
            lab = found_lab_request[0]
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



        order_date = HMISUtility.format_date_time(order_date)
        tat_info = order_date.strftime('%d-%m-%y %I:%M %p')
        return tat_info


            

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()      

        cls._order.insert(0, ('create_date', 'ASC'))


class DiscountRequest(ModelSQL, ModelView):
    "Discount Request"
    __name__ = "anth.proc.discount.request"

    STATES = {'readonly':False}
    sale = fields.Many2One('sale.sale', 'Sale', domain=[('state', '=', 'draft')])
    sale_lines = fields.One2Many('anth.proc.discount.request.line', 'name', 'List of Services', help="List of Services", required=True, states=STATES)
    patient =  fields.Many2One('gnuhealth.patient', 'Patient', states ={'readonly':True})
    total_amount = fields.Numeric('Sale Total Amount', states ={'readonly':True}, digits=price_digits)
    already_offered_discount = fields.Function(fields.Numeric('Already offered discount', states ={'readonly':True}, digits=price_digits),'calculate_already_offered_discount')
    details = fields.Text('Request Details')
    state = fields.Selection((
        (None, ''),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('utilized', 'Utilized'),
        ('returned', 'Returned'),
        ), 'Status', select=True, readonly=True)
    discount_percentage = fields.Numeric("New Discount %age")
    new_discount_amount = fields.Numeric('Total discount', states ={'readonly':True}, digits=price_digits)
    approval_reason = fields.Selection((
        (None, ''),
        ('Needy', 'Needy Patient'),
        ('employee', 'Employee'),
        ('employee_family', 'Employee Family'),
        ('employee_relative', 'Employee Relative'),
        ), 'Approval Reason')

    discount_type = fields.Selection((
        (None, ''),
        ('discount_on_cash', 'Discount on Cash'),
        ('converted_to_panel', 'Converted to Panel'),
        ), 'Discount Type', readonly=True)
    approval_details = fields.Char('Approval Details')
    rejection_reason = fields.Char('Rejection Reason')
    net_amount = fields.Numeric('Net Amount', states ={'readonly':True}, digits=price_digits)
    requested_by = fields.Many2One('gnuhealth.healthprofessional', 'Requested By', readonly=True)
    approved_by = fields.Many2One('gnuhealth.healthprofessional', 'Approved By', readonly=True)
    rejected_by = fields.Many2One('gnuhealth.healthprofessional', 'Rejected By', readonly=True)
    approval_date = fields.DateTime('Approval Date', states = STATES)
    request_date = fields.DateTime('Request Date', states = STATES)
    rejection_date = fields.DateTime('Rejection Date', states = STATES)
    referred_by = fields.Many2One('party.party', 'Reffered By', states = STATES)
    employee =  fields.Many2One('company.employee', 'Employee', states =STATES)
    welfare_fund_account = fields.Many2One('account.account', 'Welfare Fund Account')
    discount_type_selected = fields.Many2One('anth.proc.discount.type', 'Discount Type')
    move = fields.Many2One('account.move', 'Welfare Fund Move')

    # overall discounts entered at top level
    discount_value = fields.Numeric('Overall Discount Amount')
    new_discount = fields.Numeric('Discount percentage', readonly=True)

    @fields.depends('welfare_fund_account','discount_type_selected')
    def on_change_discount_type_selected(self):
        if self.discount_type_selected:
             self.welfare_fund_account = self.discount_type_selected.welfare_fund_account
             

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        requested_by = get_health_professional()
        for values in vlist:
                values['requested_by'] = requested_by
                values['request_date'] = datetime.now()

        return super(DiscountRequest, cls).create(vlist)


    @classmethod
    def write(cls, appointments, values):
        #for appointment in appointments:
        #    if appointment.state != 'requested':
        #        #raise ValidationError("This request can not be updated now!")
        #        x = 20
                    
        return super(DiscountRequest, cls).write(appointments, values)


    @fields.depends('sale_lines', 'total_amount','new_discount_amount','net_amount')
    def on_change_sale_lines_disabled(self):
        total = 0
        discount = 0
        net = 0
        if self.sale_lines:
                for line in self.sale_lines:
                        logging.info('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
                        logging.info(line)
                        if line.total_price:
                                total = total + line.total_price
                        if line.discount_value:
                                discount = discount + line.discount_value
                        if line.final_amount:
                                net = net + line.final_amount
        
                self.total_amount = total
                self.new_discount_amount = discount
                self.net_amount = net
    

    @staticmethod
    def default_state():
        return 'requested'

       
    @fields.depends('sale','sale_lines', 'total_amount','new_discount_amount','net_amount', 'patient')
    def on_change_sale(self):
        total = 0
        discount = 0
        net = 0
        if self.sale:
                Patient = Pool().get('gnuhealth.patient')
                the_patient = Patient.search([
	                        ('name', '=', self.sale.party),				
	                        ])
                logging.info("NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN")
                logging.info(the_patient)
                if len(the_patient) == 1:
                        logging.info(the_patient[0].id)
                        self.patient = the_patient[0].id
	
                the_sale_lines = []
                for line in self.sale.lines:	
                        new_sale_line = {'product':line.product.id, 'qty':line.quantity, 'list_price': line.gross_unit_price, 
                                'total_price':Decimal(str(line.quantity))*Decimal(str(line.gross_unit_price)),
                                'final_amount':Decimal(str(line.quantity))*Decimal(str(line.unit_price)),
                                'new_discount':Decimal(str(line.discount))*Decimal(str(100)),
                                'discount_value':Decimal(str(line.discount)) * Decimal(str(line.gross_unit_price)) * Decimal(str(line.quantity)),
                                'sale_line_id':line.id,
                                }	
                        the_sale_lines.append(new_sale_line)

                        if new_sale_line['total_price']:
                                total = total + new_sale_line['total_price']
                        if new_sale_line['discount_value']:
                                discount = discount + new_sale_line['discount_value']
                        if new_sale_line['final_amount']:
                                net = net + new_sale_line['final_amount']

                self.sale_lines = tuple(the_sale_lines)	

                self.total_amount = total
                self.new_discount_amount = discount
                self.net_amount = net

    @classmethod
    def __setup__(cls):
        super(DiscountRequest, cls).__setup__()      

        cls._order.insert(0, ('request_date', 'DESC'))
        cls._buttons.update({
                'approve_discount': { 
			'invisible': Or(Equal(Eval('state'), 'approved'), Equal(Eval('state'),'rejected')),
		},
                'cancel_discount': { 
			'invisible': Or(Equal(Eval('state'), 'utilized'), Equal(Eval('state'),'rejected')),
		},	
        })

    @classmethod
    @ModelView.button
    def approve_discount(cls, discountRequests):
        discountRequest = discountRequests[0]
        SaleLine = Pool().get('sale.line')

        if not discountRequest.discount_type_selected:
            raise ValidationError("Please specifiy the 'Discount Type' to approve the discount")

        if discountRequest.sale.state != 'draft':
            raise ValidationError("The sale is in paid state; so discount can not be offered")
        
        total_discount = 0.0

        if(discountRequest.sale.sale_type in ['opd','er','ipd']):
             if(not discountRequest.discount_value):
                  raise ValidationError("For all Sales, you must enter 'Overall Discount Amount'. The discount entered on Sale Lines is ignored.")
             if(discountRequest.discount_value > discountRequest.sale.total_amount):
                  raise ValidationError("The discount offered on Sale should not be more than the actual amount of the sale")
             
        if False: #(discountRequest.sale.sale_type not in  ['opd', 'er']):
            for discount_line in discountRequest.sale_lines:
                    sale_line = SaleLine(discount_line.sale_line_id)
                    sale_line.discount = round_price(Decimal(str(discount_line.new_discount)) / 100)
                    
                    logging.info(sale_line.gross_unit_price)	
                    logging.info(discount_line.discount_value)
                    
                    line_discount = round(Decimal(str(sale_line.gross_unit_price)) * Decimal(str(discount_line.new_discount)) / 100, 2)
                    sale_line.unit_price = round(Decimal(str(sale_line.gross_unit_price)) - line_discount, 2)
                    total_discount = round_price(Decimal(str(total_discount)) + (line_discount * Decimal(str(sale_line.quantity))))

                    # the discount gets rounded to 2 digits while paying sales
                    # so the calculated unit-price is more than expected (unit-price set in following write method is ignored)
                    # so its better to update the gross_unit_price as per the discounts being offered.
                    if(sale_line.discount != 1): 
                        sale_line.gross_unit_price = round(Decimal(str(sale_line.unit_price)) / (1 - sale_line.discount), 2)

                    to_update = []
                    to_update.append(sale_line)

                    SaleLine.write(to_update,{'discount':sale_line.discount, 'unit_price': sale_line.unit_price, 'gross_unit_price': sale_line.gross_unit_price})


        Move = Pool().get("account.move")
        

        signing_hp = get_health_professional()
        if not signing_hp:
            raise ValidationError(
                "No health professional associated to this user !")

        cls.write(discountRequests, {'state': 'approved', 'approval_date': datetime.now(),
            'approved_by': signing_hp})
        
    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('patient.name.name',) + tuple(clause[1:]),
                ('patient.name.alternative_ids.code',) + tuple(clause[1:]),
                ('patient.name.contact_mechanisms.value',) + tuple(clause[1:]),
                ]
    def get_rec_name(self, name):
        rec_name = '%s, %s, %s' % (self.patient.name.name, self.patient.name.mobile, self.patient.name.cnic)
        return rec_name

    @classmethod
    @ModelView.button
    def cancel_discount(cls, discountRequests):
        discountRequest = discountRequests[0]

        signing_hp = get_health_professional()
        if not signing_hp:
            raise ValidationError(
                "No health professional associated to this user !")

        cls.write(discountRequests, {'state': 'rejected', 'rejection_date': datetime.now(),
            'rejected_by': signing_hp})

class DiscountRequestLine(ModelSQL, ModelView):
    "Sale Line Discount"
    STATES = {'readonly':False}

    __name__ = "anth.proc.discount.request.line"
    name = fields.Many2One('anth.proc.discount.request', 'Discount Request')
    desc = fields.Char('Description')
    product = fields.Many2One('product.product', 'Product', required=True, states={'readonly':True})

    qty = fields.Float('Qty', required=True, states={'readonly':True})
    list_price = fields.Numeric('Unit Price', states ={'readonly':True})
    total_price = fields.Numeric('Total Price', states={'readonly':True})
    applied_discount = fields.Numeric('Discount Given',   states ={'readonly':True})
    new_discount = fields.Numeric('Discount percentage', states = STATES)
    discount_value = fields.Numeric('Discount Amount')
    net_amount = fields.Numeric('Net Amount', states={'readonly':True})
    final_amount = fields.Numeric('Final Amount', states={'readonly':True})
    sale_line_id = fields.Integer('Sale Line Id of actual sale')

    @fields.depends('product','qty','list_price','new_discount','final_amount')
    def on_change_new_discount(self):
        if self.new_discount < 0 or self.new_discount > 100:
             raise ValidationError("Invalid %age - enter value between 1 and 100")
        self.discount_value = Decimal(str(self.list_price)) * Decimal(str(self.qty)) * Decimal(str(self.new_discount)) / 100
        self.final_amount = (Decimal(str(self.list_price)) * Decimal(str(self.qty)))  - Decimal(str(self.discount_value))

    @fields.depends('product','qty','list_price','new_discount','final_amount','discount_value')
    def on_change_discount_value(self):
        if self.discount_value < 0 or self.discount_value > self.list_price:
             raise ValidationError("Invalid discount value - enter value between 1 and the price of item")
        self.new_discount = Decimal(str(self.discount_value)) / (Decimal(str(self.list_price)) * Decimal(str(self.qty))) * 100
        self.final_amount = (Decimal(str(self.list_price)) * Decimal(str(self.qty)))  - Decimal(str(self.discount_value))


class SystemConfig(ModelSQL, ModelView):
    'System Config'
    __name__ = 'anth.proc.system.config'

    invoice_account_id = fields.Numeric('Invoice Account No', required=True)
    patient_advance_account_id = fields.Numeric('Account No', required=True)
    lims_server_ip_address = fields.Numeric('IP Address', required=True)
    lims_server_port = fields.Numeric('Port', required=True)
    lims_user_id = fields.Char('Lims User Id', required=True)
    lims_user_pwd = fields.Char('Lims User Pwd', required=True)
    advance_payment_term_id = fields.Numeric("Payment Term for Advances from Inpatient", required=True)
    advance_invoice_journal_id = fields.Numeric("Journal for Advance Transactions from Inpatient", required=True)
    advance_account_for_statement = fields.Numeric("Account for Advance for Statement for Inpatient", required=True)
    main_receivable_account_id = fields.Numeric('Main Receivable for getting payment from inpatient', required=True)
    misc_service_id = fields.Numeric('Misc. Inpatient Service Product', required=True)
    ipd_commission_plan =  fields.Many2One("commission.plan",'IPD Commission Plan')
    promotion_message = fields.Text('Promotion Message', required=False)
    
    donation_as_patient_advance_account_id = fields.Integer('Donation as Advance Account ID', required=True)
    donation_expense_account_id = fields.Integer('Donation Expense Account ID', required=True)
    donation_journal_id = fields.Integer("Journal for Donation Expenses", required=True)
    



class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    sale_type = fields.Char('Sale Type', readonly=True)
    sale_counter = fields.Char('Sale Counter')
    sale_shift = fields.Selection((
        (None, ''),
        ('morning', 'Morning'),
        ('evening', 'Evening'),
        ('night', 'Night'),
        ), 'Sale Shift', select=True, readonly=True)    
    sale_total_bill = fields.Function(fields.Numeric('Bill w/o discount', states ={'readonly':True}),'get_bill_without_discount')
    is_return_sale = fields.Boolean('Return Sale?', readonly=True)    
    doctor = fields.Many2One("party.party",'Doctor', domain=[('is_healthprof', '=', True)])
    ipd = fields.Many2One('gnuhealth.inpatient.registration', 'IPD Record', domain=[('patient.name', '=', Eval('party')), ('state', 'in', ['hospitalized'])])
    mrno = fields.Function(fields.Char('MR Number'),'get_patient_mrno')
    patient =  fields.Many2One('gnuhealth.patient', 'Patient', states ={'readonly':True})
    total_sale_discount =fields.Function(fields.Numeric('Total Sale Discount'), 'get_discount_on_sale')
    sale_returns = fields.Function(fields.One2Many('sale.sale', None, 'Sale Returns'), 'get_sale_returns')
    sale_report = fields.Char('Sale Report')
    payment_date = fields.DateTime("Payment Date", readonly=True)
    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Payment Mode', select=True, readonly=True
    )

    # insurance_company = fields.Many2One(
    #    'party.party', 'Insurance Company',
    #    required=False, select=True, readonly=True,
    #    domain=[('is_insurance_company', '=', True)])

    #insurance_plan= fields.Many2One(
    #    'gnuhealth.insurance.plan', 'Insurance Plan',readonly=True,
    #    help='Insurance company plan')   

    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Insurance Company',
        required=False, select=True, readonly=True)

    insurance_plan= fields.Many2One(
        'health.proc.insurance.panel.product.group', 'Insurance Plan',
        help='Insurance company plan', readonly=True)             

    # lab/imaging/procedure/medicine
    sale_nature = fields.Char('Sale Nature')    
    is_welfare_sale = fields.Boolean('Welfare Sale?', readonly=True)        
    welfare_discount_value = fields.Numeric('Welfare Discount')

    norcotic_sale_patient = fields.Char('Norcotic Sale Patient')    
    norcotic_sale_doctor = fields.Char('Norcotic Sale Doctor')    

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._buttons.update({
                'custom_sale_payment_wizard': {
                    'invisible': Eval('state') == 'done',
                    'readonly': Not(Bool(Eval('lines'))),
                    },
                })

    @classmethod
    @ModelView.button_action('health_proc.act_custom_sale_payment_wizard')
    def custom_sale_payment_wizard(cls, sales):
        pass

    @staticmethod
    def default_payment_mode():
        return 'cash'
        
    def get_sale_returns(self, name):
        lines = set()
        ProcRequest = Pool().get('sale.sale')
        orders = ProcRequest.search([('origin', '=', 'sale.sale,'+str(self.id)),	
                    ])
        

        logging.info(orders)

        for line in orders:
            lines.add(line.id)

        return list(lines)

    
    def get_discount_on_sale(self, name):
        logging.info("===================== dtype of the arg passed is " + str(type(self)))
        sale = Pool().get('sale.sale')

        if type(self) == sale:
            return self.get_total_discount()
        else:
                return '' 
        
    @staticmethod
    def get_current_user_sale_shift():
        cursor = Transaction().connection.cursor()
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if user.sale_shift:
                return user.sale_shift 
    
    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            values['reference'] = None
            values['sale_shift'] = Sale.get_current_user_sale_shift()

        sales = super(Sale, cls).create(vlist)

        for sale in sales:
            if sale.ipd:
                InpatientMedicineSale = Pool().get('gnuhealth.inpatient.medicine.sale')
                #ipd_sales = InpatientMedicineSale.create([{'name':sale.ipd.id,'sale':sale.id,}])

        return sales

    def get_bill_without_discount(self, name):
        total_bill = 0
        for line in self.lines:
                total_bill = total_bill + line.amount_without_discount

        return total_bill

    def get_patient_mrno(self, name):
        return self.party.ref
    
    def get_total_bill(cls):
        total_bill = 0
        for line in cls.lines:
                total_bill = total_bill + line.amount_without_discount

        return total_bill

    def get_party_info(cls):
        party_info = ''
        if cls.party.person_names:
            if len(cls.party.person_names) > 0:
                if cls.party.person_names[0].prefix:
                      party_info = cls.party.person_names[0].prefix + ". "
        
        party_info = party_info + cls.party.name 
        
        if(cls.party.family_relation and cls.party.family_relation_person):
            party_info = party_info + " " + cls.party.family_relation + " " + cls.party.family_relation_person

        return party_info
    
    def get_total_discount(cls):
        total_bill = 0
        for line in cls.lines:
                total_bill = total_bill + line.line_discount

        return total_bill

    def get_net_bill(cls):
        total_bill = 0
        if cls.welfare_discount_value:
            if cls.is_return_sale:
                total_bill = cls.total_amount + cls.welfare_discount_value
            else:     
                total_bill = cls.total_amount - cls.welfare_discount_value
        else:
             total_bill = cls.total_amount

        return total_bill

    def is_opd_appointment_sale(cls):
        appointment_sale = False
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        if(len(found) > 0):
            appointment_sale = True
       
        return appointment_sale
    
    def get_opd_appointment(cls):
        appointment = None
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        if(len(found) > 0):
            appointment=found[0]
       
        return appointment

    def get_appointment_fee(cls):
        fee = None
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        for line in cls.lines:
            fee = line.unit_price        

        return fee

    def get_appointment_main_specialty(cls):
        specialty = None
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        if(len(found) > 0):
            if found[0].healthprof.main_specialty:
                  specialty = found[0].healthprof.main_specialty.specialty.name       

        return specialty

    def get_appointment_doctor(cls):
        specialty = None
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        if(len(found) > 0):
            if found[0].healthprof:
                  specialty = found[0].healthprof.name.name 

        if not specialty:
             ImagingRequest = Pool().get("gnuhealth.imaging.test.request")
             if cls.sale_nature  and cls.sale_nature == 'imaging':
                  #sale_line_id = None
                  #for line in cls.lines:
                  #     sale_line_id = line.id
                  #     break
                  if(cls.doctor):
                       specialty = cls.doctor.name
        if not specialty:
            if(cls.doctor):
                specialty = cls.doctor.name
             


        return specialty        

    def get_token_number(cls):
        specialty = None
        Appointment = Pool().get("gnuhealth.appointment")

        found = Appointment.search([
                        ('sale', '=', cls.id),
                        ])
        if(len(found) > 0):
            if True:
                  specialty = found[0].name

        return specialty 
    
    @classmethod
    def get_product_sale_price(cls, price_list, party, product):
        ProductPriceList = Pool().get('product.price_list')
        price_list_obj = ProductPriceList(price_list)
	#calling compute(party, product, default_price, quantity, unit_of_measure)

	#with Transaction().set_context(price_list=price_list):
		
        price = price_list_obj.compute(party, product, -22, 1, product.default_uom)
     
        return price

    @classmethod
    def product_price_exists(cls, price_list, product_id):
        ProductPriceList = Pool().get('product.price_list')
        price_list_obj = ProductPriceList(price_list)

        exists = False
        for line in price_list_obj.lines:	
                if line.product.id == product_id:
                        exists = True
				 
        return exists
    
    @classmethod
    def product_price_exists_in_plan(cls, plan_id, product_id):
        ProductPriceList = Pool().get('gnuhealth.insurance.plan')
        price_list_obj = ProductPriceList(plan_id)

        exists = False
        for line in price_list_obj.product_policy:	
                if line.product.id == product_id:
                        exists = True
				 
        return exists    
    
    @classmethod
    def get_product_price_from_plan(cls, plan_id, product_id):
        ProductPriceList = Pool().get('gnuhealth.insurance.plan')
        price_list_obj = ProductPriceList(plan_id)
        Product = Pool().get("product.product")
        product = Product(product_id)

        price = product.list_price
        for line in price_list_obj.product_policy:	
            if line.product.id == product_id:
                # now either return the price, if it is set or return the actual price of the product
                if line.price:
                    price = Decimal(str(line.price))
                else:
                    price = product.list_price
                        
				 
        return price   
    
    
    @classmethod
    def product_price_exists_in_panel(cls, panel, product_id):
        logging.warn("Searchigh for plans for panel: " + str(panel.id))
        exists = False
        InsurancePanelProductGroup = Pool().get("health.proc.insurance.panel.product.group")
        groups = InsurancePanelProductGroup.search([('panel','=',panel.id), ('product_group.group_type','=', 'plan')])
        ProductGroupLine = Pool().get("health.proc.product.group.line")
        ProductTemplate = Pool().get("product.template")
        Product = Pool().get("product.product")
        final_price = None
        for g in groups:
            lines = ProductGroupLine.search([('group','=', g.product_group.id)])
            logging.warn("Searchigh for lines for group: " + str(g.id))
            for l in lines:
                logging.warn("iterating for products for line id: " + str(l.id))
                if(l.product):
                    # a product is found; apply discout on it
                    if l.product.id == product_id:
                        list_price = l.product.list_price
                        logging.warn("displaying found prouduct in the Plan for product id: " + str(l.product.id) + ", naem: " + l.product.name + ", price: " + str(list_price))
                        exists = True

                        #if(g.discount):
                        #    discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                        #    final_price = list_price - discount_amount
                        #    exists = True
                else:
                    if(l.product_category):
                        # a category is found
                        templates = ProductTemplate.search([('account_category', '=', l.product_category.id)])
                        for t in templates:
                            products = Product.search([('template', '=', t.id)])
                            for p in products:
                                 if p.id == product_id:
                                    list_price = p.list_price
                                    logging.warn("displaying for category the product id: " + str(p.id) + ", naem: " + p.name + ", price: " + str(list_price))
                                    exists = True

                                    #if(g.discount):
                                    #    discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                                    #    final_price = list_price - discount_amount
                                    #   exists = True

        return exists    
    
    @classmethod
    def get_product_price_from_panel(cls, panel, product_id):
        logging.warn("Searchigh for plans for panel: " + str(panel.id))
        exists = False
        InsurancePanelProductGroup = Pool().get("health.proc.insurance.panel.product.group")
        groups = InsurancePanelProductGroup.search([('panel','=',panel.id), ('product_group.group_type','=', 'plan')])
        ProductGroupLine = Pool().get("health.proc.product.group.line")
        ProductTemplate = Pool().get("product.template")
        Product = Pool().get("product.product")        
        final_price = None
        for g in groups:
            lines = ProductGroupLine.search([('group','=', g.product_group.id)])
            logging.warn("Searchigh for lines for group: " + str(g.id))
            for l in lines:
                logging.warn("iterating for products for line id: " + str(l.id))
                if(l.product):
                    # a product is found; apply discout on it
                    if l.product.id == product_id:
                        logging.warn("displaying for product id: " + str(l.product.id) + ", naem: " + l.product.name + ", price: " + str(l.product.list_price))

                        if l.price: #p3
                            final_price = l.price # use fixed-price
                        
                        if(l.discount and l.discount>0): #p2
                            list_price = l.product.list_price
                            discount_amount = Decimal(list_price) * Decimal(l.discount) / 100
                            final_price = list_price - discount_amount
                        
                        if(g.discount and g.discount>0): #p1
                            discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                            list_price = l.product.list_price
                            final_price = list_price - discount_amount
                            
                else:
                    if(l.product_category):
                        # a category is found
                        templates = ProductTemplate.search([('account_category', '=', l.product_category.id)])
                        for t in templates:
                            products = Product.search([('template', '=', t.id)])
                            for p in products:
                                 if p.id == product_id:
                                    list_price = p.list_price
                                    logging.warn("displaying for category the product id: " + str(p.id) + ", naem: " + p.name + ", price: " + str(list_price))
                                    
                                    if(l.discount and l.discount>0): 
                                        list_price = list_price
                                        discount_amount = Decimal(list_price) * Decimal(l.discount) / 100                                      
                                        final_price = list_price - discount_amount

                                    if(g.discount and g.discount>0):
                                        discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                                        final_price = list_price - discount_amount
                                        exists = True
        return final_price       

    @classmethod
    def product_price_exists_in_panel_for_plan(cls, panel, product_id, insurance_plan):
        # panel object is not required
        logging.warn("Searchigh for plans for id: " + str(insurance_plan.id))
        exists = False
        InsurancePanelProductGroup = Pool().get("health.proc.insurance.panel.product.group")
        groups = InsurancePanelProductGroup.search([('id','=',insurance_plan.id)])
        ProductGroupLine = Pool().get("health.proc.product.group.line")
        ProductTemplate = Pool().get("product.template")
        Product = Pool().get("product.product")
        final_price = None
        for g in groups:
            lines = ProductGroupLine.search([('group','=', g.product_group.id)])
            logging.warn("Searchigh for lines for group: " + str(g.id))
            for l in lines:
                logging.warn("iterating for products for line id: " + str(l.id))
                if(l.product):
                    # a product is found; apply discout on it
                    if l.product.id == product_id:
                        list_price = l.product.list_price
                        logging.warn("displaying for product id: " + str(l.product.id) + ", naem: " + l.product.name + ", price: " + str(list_price))

                        exists = True
                else:
                    if(l.product_category):
                        # a category is found
                        templates = ProductTemplate.search([('account_category', '=', l.product_category.id)])
                        for t in templates:
                            products = Product.search([('template', '=', t.id)])
                            for p in products:
                                 if p.id == product_id:
                                    list_price = p.list_price
                                    logging.warn("displaying for category the product id: " + str(p.id) + ", naem: " + p.name + ", price: " + str(list_price))

                                    exists = True

        return exists    
    
    @classmethod
    def get_product_price_from_panel_for_plan(cls, panel, product_id, insurance_plan):
        # panel object might not be required
        logging.warn("Searchigh for plans for id: " + str(insurance_plan.id))
        exists = False
        InsurancePanelProductGroup = Pool().get("health.proc.insurance.panel.product.group")
        groups = InsurancePanelProductGroup.search([('id','=',insurance_plan.id)])
        ProductGroupLine = Pool().get("health.proc.product.group.line")
        ProductTemplate = Pool().get("product.template")
        Product = Pool().get("product.product")        
        final_price = None
        for g in groups:
            lines = ProductGroupLine.search([('group','=', g.product_group.id)])
            logging.warn("Searchigh for lines for group: " + str(g.id))
            for l in lines:
                logging.warn("iterating for products for line id: " + str(l.id))
                if(l.product):
                    # a product is found; apply discout on it
                    if l.product.id == product_id:
                        list_price = l.product.list_price
                        logging.warn("displaying for product id: " + str(l.product.id) + ", naem: " + l.product.name + ", price: " + str(list_price))

                        if l.price: #p3
                            final_price = l.price # use fixed-price
                        
                        if(l.discount and l.discount>0): #p2
                            list_price = l.product.list_price
                            discount_amount = Decimal(list_price) * Decimal(l.discount) / 100
                            final_price = list_price - discount_amount
                        
                        if(g.discount and g.discount>0): #p1
                            discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                            list_price = l.product.list_price
                            final_price = list_price - discount_amount                            
                        
                else:
                    if(l.product_category):
                        # a category is found
                        templates = ProductTemplate.search([('account_category', '=', l.product_category.id)])
                        for t in templates:
                            products = Product.search([('template', '=', t.id)])
                            for p in products:
                                 if p.id == product_id:
                                    list_price = p.list_price
                                    logging.warn("displaying for category the product id: " + str(p.id) + ", naem: " + p.name + ", price: " + str(list_price))

                                    if(l.discount and l.discount>0): 
                                        list_price = list_price
                                        discount_amount = Decimal(list_price) * Decimal(l.discount) / 100                                      
                                        final_price = list_price - discount_amount

                                    if(g.discount and g.discount>0):
                                        discount_amount = Decimal(list_price) * Decimal(g.discount) / 100
                                        final_price = list_price - discount_amount

        return final_price       

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('party.name',) + tuple(clause[1:]),
                ('party.alternative_ids.code',) + tuple(clause[1:]),
                ('party.contact_mechanisms.value',) + tuple(clause[1:]),
                ]
    def get_rec_name(self, name):
        rec_name = super(Sale, self).get_rec_name(name)
        rec_name += ',%s, %s, %s' % (self.party.name, self.party.mobile, self.party.cnic)
        return rec_name
           
    def get_created_by_info(cls):
        ResUser = Pool().get("res.user")
        created_by = ResUser(cls.create_uid)

        return created_by.name
    
class DiscountType(ModelSQL, ModelView):
    "Discount Type"
    __name__ = "anth.proc.discount.type"

    name = fields.Char('Discount Type')
    welfare_fund_account = fields.Many2One('account.account', 'Welfare Fund Account', required=True)

        
class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'
          
    def get_rec_name(self, name):
        rec_name = super(Lot, self).get_rec_name(name)
        if self.expiration_date:
            rec_name += ' - [%s]' % self.expiration_date
        return rec_name

    @classmethod
    def __setup__(cls):
        super(Lot, cls).__setup__()    
        cls._order.insert(0, ('expiration_date', 'ASC'))    

    @classmethod
    def get_quantity(cls, lots, name):
        from_loc = Transaction().context.get('from_loc')

        Location = Pool().get("stock.location")
        locations = Location.search([('type', '=', 'storage')])
        context = {
            'locations': [from_loc if from_loc else -1]
            }
        if from_loc:
            with Transaction().set_context(**context):
                return super(Lot, cls).get_quantity(lots, name)
        else:
             return super(Lot,cls).get_quantity(lots,name)
    
class ReturnSale(metaclass=PoolMeta):
    __name__ = 'sale.return_sale'
          
    def do_return_old(self, action):
        action, data = super(ReturnSale, self).do_return_(action)
        Sale = Pool().get("sale.sale")
        for sid in data['res_id']:
                logging.info(sid)
                sale = Sale(sid)
                Sale.write([sale], {'is_return_sale':True})
        return action, data

    def do_return_(self, action):
        Sale = Pool().get("sale.sale")
        sales = Sale.browse(Transaction().context['active_ids'])
        for s in sales:
            # if it is already a return sale; quit
            if s.is_return_sale:
                    raise ValidationError("You can not create a return sale for a return sale")

            # if it already contains a return sales; quit
            if s.sale_returns and len(s.sale_returns) >= 1:
                    raise ValidationError("A return sale has already been created for this sale")

            # if the total-price is more than the original-sale -- than don't allow payment (paymentWizad change)
            # match all the products, their quantities, unit-prices and discounts (paymentwizard change)

            # if the sale is older than 7 days don't allow

            # if the prescription has already been created for this appointment, only Finance Admin can create this return sale
            appointment = s.get_opd_appointment()
            if appointment:
                PrescriptionOrder = Pool().get("gnuhealth.prescription.order")
                found = PrescriptionOrder.search([
                                ('appointment', '=', appointment.id),
                                ])
                if(len(found) > 0):
                    User = Pool().get("res.user")
                    user = User(Transaction().user)
                    admin_found = False
                    for group in user.groups:
                         if group.id == 39:
                              admin_found = True
                    if not admin_found:
                        raise ValidationError("A Prescription is already created for this OPD Consultation, so it can't be refunded.")

        action, data = super(ReturnSale, self).do_return_(action)

        for sid in data['res_id']:
                logging.info(sid)
                sale = Sale(sid)
                Sale.write([sale], {'is_return_sale':True, 'sale_device':None})
        return action, data
        

class PatientData(metaclass=PoolMeta):
    __name__ = 'gnuhealth.patient'

    mobile = fields.Function(fields.Char('Mobile'),'get_patient_mobile')
    cnic = fields.Function(fields.Char('cnic'),'get_patient_cnic')
    crm_pwd = fields.Char("CRM Pwd")

    def get_rec_name(self, name):
        rec_name = super(PatientData, self).get_rec_name(name)
        rec_name += ', %s, %s' % (self.mobile, self.cnic)

        party_sal = ''
        if self.name.person_names:
            if len(self.name.person_names) > 0:
                if self.name.person_names[0].prefix:
                      party_sal = self.name.person_names[0].prefix + ". "
        
        if party_sal:
             rec_name = party_sal + rec_name 
        return rec_name

    def get_patient_mobile(self, name):
        return self.name.mobile        

    
    def get_party_address(cls):
        address = ''

        if cls.name.addresses:
            address = cls.name.addresses[0].full_address
        
            if cls.name.addresses[0].subdivision:
                address = address + ", " + cls.name.addresses[0].subdivision.rec_name

        return address
            
    def get_patient_cnic(self, name):
        return self.name.cnic        

class PartyData(metaclass=PoolMeta):
    __name__ = 'party.party'

    mobile = fields.Function(fields.Char('Mobile'),'get_party_mobile')
    cnic = fields.Function(fields.Char('cnic'),'get_party_cnic')
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
        ), 'Relationship', select=True)      
    family_relation_person = fields.Char('Relationship Name')    

    def get_party_mobile(self, name):
        for contact in self.contact_mechanisms:
             if contact.type == 'mobile':
                  return contact.value
             
        return ''
        
    def get_party_cnic(self, name):
        for alt_id in self.alternative_ids:
            if alt_id.alternative_id_type == 'country_id':
                 return alt_id.code

        return ''
    
    def get_party_info(cls):
        party_info = ''
        if cls.person_names:
            if len(cls.person_names) > 0:
                if cls.person_names[0].prefix:
                      party_info = cls.person_names[0].prefix + ". "
        
        party_info = party_info + cls.name 
        
        if(cls.family_relation and cls.family_relation_person):
            party_info = party_info + " " + cls.family_relation + " " + cls.family_relation_person

        return party_info
    
    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
                #values['account_receivable']=109
                #values['account_payable']=189
                if not 'ref' in values or values['ref'] == '':
	                if 'is_patient' in values and values['is_patient']:
                                Config = Pool().get('gnuhealth.sequences')

                                config = Config(1)
                                
                                sequence = config.get_multivalue(
                                    'patient_sequence')
                                if sequence:
                                    values['ref'] = str(sequence.get())

                                

        return super(PartyData, cls).create(vlist)    


class Appointment(metaclass=PoolMeta):
    __name__ = 'gnuhealth.appointment'
    sale = fields.Many2One('sale.sale', 'Sale', required=False)
    refunded = fields.Boolean('Refunded?', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Appointment, cls).__setup__()      

        cls._buttons.update({
                           'create_prescription': { 
                            'invisible': Equal(Eval('state'), 'checked_in--'),

		}
        })


    @classmethod
    @ModelView.button
    @ModelView.button_action('health_proc.act_create_evaluation_prescription')
    def create_prescription(cls, tests):
        for t in tests:
            if t.refunded:
                 raise ValidationError("The amount for this consultation has already been refunded.")
            if not t.sale:
                 raise ValidationError("This is an invalid appointment; please create an appointment from Register Patient screen")
            if t.sale.state not in ('processing','done'):
                 raise ValidationError("The payment is not yet received for this appointment; please send patient to cash counter")
        pass

class AccountStatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'
    balance = fields.Numeric("Balance")
    serial_no = fields.Integer("S. No")
    receipt_no = fields.Char("Recipt. No")
    visit_no = fields.Char("Visit No.")
    line_type = fields.Selection((
        ('welfare_discount', 'Welfare Discount'),
        ('cash_sale', 'Cash Sale'),
        ('credit_sale', 'Credit Sale'),
        ('sale_refund', 'Refund'),
        ('ipd_advance', 'IPD Advance'), 
        ('ipd_admission', 'Admission'),
        ('ipd_discharge', 'Discharge'),
       
        ), 'Transaction Type', select=True, readonly=True)  
    sale_type = fields.Char("Sale Type", readonly=True)
    final_sale_type = fields.Function(fields.Char('Sale Type', states ={'readonly':True}),'get_final_sale_type')
    panel_bill = fields.Many2One('health.proc.insurance.panel.bill', 'Panel Bill')

    def get_final_sale_type(self, name):
        if(self.sale_type):
            return  self.sale_type
        if(self.sale):
             return self.sale.sale_type
        
    @staticmethod
    def default_line_type():
        return 'cash_sale'        

class StockMove(metaclass=PoolMeta):
    __name__ = 'stock.move'

    STATES = {
        'readonly': Eval('state').in_(['cancel', 'assigned', 'done']),
        }
    retail_price = fields.Numeric('Retail Price', digits=price_digits, states=STATES)
    discount = fields.Numeric('Discount', digits=price_digits, states=STATES)
    gst = fields.Numeric('GST', digits=price_digits, states=STATES)

    @classmethod
    def assign(cls, moves):
        Lot = Pool().get("stock.lot")
        Product = Pool().get("product.product")
        for m in moves:
            context = {
                'locations': [m.from_location.id]
                }
            if m.lot:
                with Transaction().set_context(**context):
                    lot = Lot(m.lot.id)
                    qty = lot.quantity
                    if(m.internal_quantity > qty):
                        msg = "Not Enough Stock. For product: " + m.product.rec_name + ", required quantity of selected lot is: " + str(m.internal_quantity) + ", but stock available is only " + str(qty) 
                        raise ValidationError(msg)
            else:
                with Transaction().set_context(**context):
                    qty = Product(m.product.id).quantity
                    if(m.internal_quantity > qty):
                        msg = "Not Enough Stock. For product: " + m.product.rec_name + ", required quantity of any lots is: " + str(m.internal_quantity) + ", but stock available is only " + str(qty) 
                        raise ValidationError(msg)

                
        return super(StockMove,cls).assign(moves)
                
    @property
    def from_warehouse(self):
        return self.from_location.warehouse
    @property
    def to_warehouse(self):
        return self.to_location.warehouse
    @property
    def warehouse(self):
        return self.from_warehouse or self.to_warehouse


    @classmethod
    def __setup__(cls):
        super(StockMove, cls).__setup__()
        if not cls.lot.context:
            cls.lot.context = {}
        cls.lot.context['from_loc'] = Eval('from_location')
        cls.lot.depends.append('from_location')        
    
class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    warehouse = fields.Function(fields.Many2One(
            'stock.location', "Warehouse"), 'get_warehouse')
    
    def get_warehouse(self, name):
        if (self.invoice_type == 'out'
                or (self.invoice and self.invoice.type) == 'out'):
            warehouses = set(filter(None, [
                        m.from_location.warehouse for m in self.stock_moves]))
        else:
            warehouses = set(filter(None, [
                        m.to_location.warehouse for m in self.stock_moves]))
        if warehouses:
            return list(warehouses)[0].id    

class WizardSalePayment(metaclass=PoolMeta):
    __name__ = 'sale.payment'
    other_sale_print_ = StateReport('sale_ticket_other_sale')      
    lab_sale_print_ = StateReport('sale_ticket_lab_sale')      

    def default_start(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context['active_id'])
        result = super(WizardSalePayment, self).default_start(fields)
        result['self_pick_up'] = sale.self_pick_up
        return result

    def transition_pay_(self):
        logging.info("============================================================================================= transition pay is called ");
        credit_panel_sale = False
        sale = None

        #try:
        if True:
                if Transaction().context.get('active_model') == 'sale.sale' or True:
                        logging.info( Transaction().context.get('active_id'))

                        Sale = Pool().get("sale.sale")
                        sale = Sale(Transaction().context.get('active_id'))

                        if(sale.sale_type == 'ipd'):
                            raise ValidationError("This is an IPD Sale, it should be managed from Hospitalization Module.")


                        # if user has created a sale with minus quantity and is_return_sale flag is false, then this return sale then don't allow payment of this sale
                        med_cat = False
                        for line in sale.lines:
                                logging.info("=========== line quantity " + str(line.quantity))
                                if line.quantity <= 0:
                                        med_cat = True
                                        logging.info("===== negative quantity found == ")

                        if med_cat and not sale.is_return_sale:
                                error_message = 'This Sale can not be paid. Please contact I.T department for support'

                        # if it is a return sale and the amount is more than the actual sale
                        if sale.is_return_sale:
                                logging.info("Its a return sale ... checking for price in original sale: " + str(sale.origin))
                                parts = str(sale.origin).split(",")
                                #if(parts[0] == 'sale.sale'):
                                if(True):
                                        logging.info("============ its origin shown sale.sale")
                                        #actual_sale_id = int(parts[1])
                                        #actual_sale = Sale(actual_sale_id)
                                        actual_sale = sale.origin
                                        logging.info("================= actual sale id: " + str(actual_sale.id) + ", price: " + str(actual_sale.total_amount_cache))
                                        logging.info("================= return sale id: " + str(sale.id) + ", price: " + str(sale.total_amount_cache))
                                        return_sale_amount = 0
                                        for line in sale.lines:
                                                return_sale_amount += Decimal(line.unit_price) * Decimal(line.quantity)

                                        logging.info("================= return sale id: " + str(sale.id) + ", calculated price: " + str(return_sale_amount))
                                        if actual_sale.total_amount_cache and actual_sale.total_amount_cache < -1*return_sale_amount:
                                                logging.info("=================== the return sale is in more price '''''''''''' ")
                                                error_message = "The return sale being paid is more than the actual sale: " + str(actual_sale.total_amount_cache)

                        med_cat = sale.is_opd_appointment_sale()
                        appointment = sale.get_opd_appointment()
                        datefrom = datetime.now()
                        datefrom = datefrom.replace(hour=0, minute=0, second=0, microsecond=0)

                        dateto = datetime.now()
                        dateto = dateto.replace(hour=23, minute=59, second=59, microsecond=999)
                        if med_cat:
                                cursor = Transaction().connection.cursor()
                                cursor.execute("SELECT max(cast(sale_counter as integer)) sl_counter from sale_sale \
                                               where id in (select sale from gnuhealth_appointment where healthprof = %s \
                                               and appointment_date between %s and %s) \
                                               and state in ('done','processing')",(str(appointment.healthprof.id), datefrom, dateto))
                                
                                res = cursor.fetchone()		
                                logging.error("the counter found is --------------------- " + str(res[0]))
                                if len(res) > 0 and res[0]:
                                    next_val = int(res[0]) + 1
                                else:
                                      next_val = 1
                                logging.error("============== for doctor: " + str(appointment.healthprof.id) + " next value returned by sale sequence is " + str(next_val))
                                Sale.write([sale], {'sale_counter': str(next_val), 'payment_date': datetime.now()})
                        else:
                            is_imaging = False
                            if(sale.sale_nature == 'imaging'):
                                 is_imaging = True
                                 
                            seq_query = "SELECT nextval('sale_counter_seq')"
                            if is_imaging:
                                seq_query = "SELECT nextval('img_test_seq')"
                            
                            cursor = Transaction().connection.cursor()
                            cursor.execute(seq_query)
                            res = cursor.fetchone()		
                            next_val = res[0]
                            Sale.write([sale], {'sale_counter': str(next_val), 'payment_date': datetime.now()})

                        # if it is credit-panel-sale
                        if sale.payment_mode == 'panel_credit':
                             credit_panel_sale = True

                             # create staement line and save it; also set statement-line-type to 'panel_credit' so that it can be counted as credit sales
                             # we may also need to override the Validate and Post methods
                             # post invoice



        #except:
        #        logging.info("============ some error while setting counter for sale ============= ")
        #        traceback.print_exc()
        #        traceback.print_stack()
        

        state =  super(WizardSalePayment, self).transition_pay_()
        logging.info("======== sate " + str(state))

        try:
            if credit_panel_sale and sale:
                # search the statement line and update its line-type
                AccountStatementLine = Pool().get("account.statement.line")
                found_lines = AccountStatementLine.search([
                                ('sale', '=', sale.id),				
                                ])
                if len(found_lines) == 1:
                    logging.info("============== updating the statement line type to credit sale .....")
                    AccountStatementLine.write(found_lines,{'line_type':'credit_sale'})

            if sale and sale.is_return_sale:
                AccountStatementLine = Pool().get("account.statement.line")
                found_lines = AccountStatementLine.search([
                                ('sale', '=', sale.id),				
                                ])
                if len(found_lines) == 1:
                    logging.info("============== updating the statement line type to refund .....")
                    AccountStatementLine.write(found_lines,{'line_type':'sale_refund'})

                # in case of Welfare return sale, make necessary changes
                if(sale.is_welfare_sale):
                    advance_amount = 200
                    logging.info("<RET-SALE-WELFARE> A rerturn sale with welfare discount")

                User = Pool().get("res.user")
                user = User(Transaction().user)
                sale_device = user.sale_device
                if not sale.sale_device:
                    Sale.write([sale], {'sale_device': sale_device.id})

                # set the appointment to refunded
                actual = sale.origin
                appointment = actual.get_opd_appointment()

                Appointment = Pool().get("gnuhealth.appointment")
                if(appointment):
                    logging.info("====== appointment id is: " + str(appointment.id))
                    Appointment.write([appointment], {'refunded': True})
                     

                 
        except:
            logging.info("====================== some error while updating statement line type")
            traceback.print_exc()
            traceback.print_stack()


        if(state == 'end'):
              if sale.sale_report == 'other_sales':
                    state = 'other_sale_print_'
              if sale.sale_report == 'lab_sales':
                    state = 'lab_sale_print_'

        return state

    def do_other_sale_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data            

    def do_lab_sale_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data     

class ProductGroup(ModelSQL, ModelView):
    'Product Group'
    __name__ = 'health.proc.product.group'

    name = fields.Char('Name', required=True)

    #main product representing the price of whole package
    product = fields.Many2One(
        'product.product', 'Plan', required=False,
        domain=[('is_insurance_plan', '=', True)],
        help='Insurance company plan')


    is_default = fields.Boolean(
        'Default plan',
        help='Check if this is the default plan when assigning this insurance'
        ' company to a patient')


    group_type = fields.Selection((
        ('package', 'Package'),
        ('plan', 'Plan'),
        ), 'Package or Plan?', select=True)        

    lines = fields.One2Many('health.proc.product.group.line','group', 'Services')
    list_price = fields.Function(fields.Numeric('List Price', states ={'readonly':True}, digits=price_digits),'calculate_list_price')
    notes = fields.Text('Details about this Package/Plan')

    def get_rec_name(self, name):
        return self.name     

    @staticmethod
    def default_group_type():
        return 'package'    
    
    def get_list_price(cls):
        total_bill = 0
        for line in cls.lines:
                total_bill = total_bill + line.product.list_price

        return total_bill      

    def calculate_list_price(self, name):
        if(self.group_type == 'package'):
            return  self.get_list_price()
  

class ProductGroupLine(ModelSQL, ModelView):
    'Product Group Line'
    __name__ = "health.proc.product.group.line"

    group = fields.Many2One('health.proc.product.group','Group', required=True)
    product = fields.Many2One('product.product', 'Product')
    product_category = fields.Many2One('product.category', 'Category')
    list_price = fields.Function(fields.Numeric('Base Price', states ={'readonly':True}, digits=price_digits),'calculate_list_price')
    discount = fields.Float(
        'Discount', digits=(3, 2),
        help="Discount in Percentage. It has higher precedence than "
             "the fixed price when both values coexist")

    price = fields.Float(
        'Fixed Price', help="Apply a fixed price for this product")    

    def calculate_list_price(self, name):
        if(self.product):
            return  self.product.list_price
    
    @classmethod
    def validate(cls, policies):
        super(ProductGroupLine, cls).validate(policies)
        for policy in policies:
            policy.validate_discount()
            policy.validate_policy_elements()

    def validate_policy_elements(self):
        if (not self.product and not self.product_category):
            raise ValidationError("Enter either a Product or a Category")   

    def validate_discount(self):
        if (self.discount):
            if (self.discount < 0 or self.discount > 100):
                raise "Discount %age must be between 0 and 100%"
        if (self.group.group_type == 'plan' and not self.discount and not self.price):
            raise ValidationError("Either provide Price or Discount for this Product as it belongs to a Plan")            

    @fields.depends('product','list_price')
    def on_change_product(self):
        if self.product:
                self.list_price = self.product.list_price
        else:
             return None
              


class InsurancePanelProductGroup(ModelSQL, ModelView):
    'Packages assoicated with the insurance Panel'
    __name__ = "health.proc.insurance.panel.product.group"

    panel = fields.Many2One('health.proc.insurance.panel','Panel')

    product_group = fields.Many2One('health.proc.product.group', 'Package/Plan')

    discount = fields.Float(
        'Discount', digits=(3, 2),
        help="Discount in Percentage. It has higher precedence than "
             "the fixed price when both values coexist")

    price = fields.Float(
        'Package Price', help="Apply a fixed price for this package or plan")

    list_price = fields.Function(fields.Numeric('List Price', states ={'readonly':True}, digits=price_digits),'calculate_list_price')
    nature = fields.Function(fields.Char('Package or Plan?', states ={'readonly':True}),'is_package_or_plan')

    def is_package_or_plan(cls, name):
        return cls.product_group.group_type

    def get_list_price(cls):
        return cls.product_group.list_price   
    
    def calculate_list_price(self, name):
        if(self.product_group.group_type == 'package'):
            return  self.get_list_price() 


    @fields.depends('product_group','list_price')
    def on_change_product_group(self):
        if self.product_group:
                self.list_price = self.product_group.list_price
        else:
             return None

    @classmethod
    def validate(cls, policies):
        super(InsurancePanelProductGroup, cls).validate(policies)
        for policy in policies:
            policy.validate_discount()
            policy.validate_policy_elements()

    def validate_discount(self):
        if (self.discount):
            if (self.discount < 0 or self.discount > 100):
                raise "Discount %age must be between 0 and 100%"
            
        if (self.product_group.group_type == 'package' and  not self.discount and not self.price):
            raise ValidationError("Either provide Price or Discount for this Package")

    def validate_policy_elements(self):
        if (not self.product_group):
              raise ValidationError("Please select a Plan/Package to set its price/discount")

    def get_rec_name(self, name):
        if self.product_group:
                return self.product_group.rec_name                

        
class InsurancePanel (ModelSQL, ModelView):
    'Panel Details'
    __name__ = 'health.proc.insurance.panel'

    name = fields.Many2One('party.party','Panel Name', required=True)

    panel_type = fields.Selection((
        ('panel_credit', 'Credit'),
        ('panel_cash', 'Cash'),
        ), 'Credit or Cash?', select=True)        

    packages = fields.One2Many('health.proc.insurance.panel.product.group','panel', 'Packages/Plans')

    notes = fields.Text('Details about this Panel')    

    @staticmethod
    def default_panel_type():
        return 'panel_credit'            

    def get_rec_name(self, name):
        if self.name:
                return self.name.rec_name            


class PrescriptionLabTest(ModelSQL, ModelView):
    'Prescription - LabTest'
    __name__ = 'health.proc.prescription.lab.test'

    prescription = fields.Many2One(
        'gnuhealth.prescription.order',
        'Prescription', required=True)
    test = fields.Many2One('gnuhealth.lab.test_type', 'Test', required=True)  

class PrescriptionImagingTest(ModelSQL, ModelView):
    'Prescription - ImagingTest'
    __name__ = 'health.proc.prescription.imaging.test'

    prescription = fields.Many2One(
        'gnuhealth.prescription.order',
        'Prescription', required=True)
    test = fields.Many2One('gnuhealth.imaging.test', 'Test', required=True)              


class PrescriptionDisease(ModelSQL, ModelView):
    'Prescription - Diesease'
    __name__ = 'health.proc.prescription.pathology'

    prescription = fields.Many2One(
        'gnuhealth.prescription.order',
        'Prescription', required=True)
    disease = fields.Many2One('gnuhealth.pathology', 'Disease', required=True)   

class PrescriptionOrder(metaclass=PoolMeta):
    __name__ = 'gnuhealth.prescription.order'
    STATES = {'readonly': Not(Eval('state') == 'draft')}

    appointment = fields.Many2One('gnuhealth.appointment','Appointment', required=False)

    tests = fields.Many2Many(
        'health.proc.prescription.lab.test', 'prescription', 'test',
        'Lab Tests', required=False)        
    imaging_tests = fields.Many2Many(
        'health.proc.prescription.imaging.test', 'prescription', 'test',
        'Radiology Tests', required=False)   

    diseases = fields.Many2Many(
        'health.proc.prescription.pathology', 'prescription', 'disease',
        'Disease', required=False)   

    chief_complaint = fields.Char('Chief Complaint', help='Chief Complaint',
                                  states=STATES)
    notes_complaint = fields.Text('Complaint details', states=STATES)
    present_illness = fields.Text('Present Illness', states=STATES)
    evaluation_summary = fields.Text('Clinical and physical', states=STATES)

    glycemia = fields.Float(
        'Glycemia',
        help='Blood glucose level (mg/dL)', states=STATES)

    hba1c = fields.Float(
        'HbA1c',
        help='Last Glycated Hemoglobin HbA1c level(mmol/mol)',
        states=STATES)

    cholesterol_total = fields.Integer(
        'Last Cholesterol',
        help='Last cholesterol reading (mg/dL)',
        states=STATES)

    hdl = fields.Integer(
        'HDL',
        help='Last HDL Cholesterol reading (mg/dL)',
        states=STATES)

    ldl = fields.Integer(
        'LDL',
        help='Last LDL Cholesterol reading (mg/dL)',
        states=STATES)

    tag = fields.Integer(
        'TAGs',
        help='Last Triglicerides level, (mg/dL)',
        states=STATES)

    systolic = fields.Integer(
        'Systolic Pressure',
        help='Systolic pressure (mmHg)',
        states=STATES)

    diastolic = fields.Integer(
        'Diastolic Pressure',
        help='Diastolic pressure (mmHg)',
        states=STATES)

    bpm = fields.Integer(
        'Heart Rate',
        help='Heart rate (beats per minute)',
        states=STATES)

    respiratory_rate = fields.Integer(
        'Respiratory Rate',
        help='Respiratory rate expressed in breaths per minute',
        states=STATES)

    osat = fields.Integer(
        'Oxygen Saturation',
        help='Arterial oxygen saturation expressed as a percentage',
        states=STATES)

    malnutrition = fields.Boolean(
        'Malnutrition',
        help='Check this box if the patient show signs of malnutrition. If'
        ' associated  to a disease, please encode the correspondent disease'
        ' on the patient disease history. For example, Moderate'
        ' protein-energy malnutrition, E44.0 in ICD-10 encoding',
        states=STATES)

    dehydration = fields.Boolean(
        'Dehydration',
        help='Check this box if the patient show signs of dehydration. If'
        ' associated  to a disease, please encode the  correspondent disease'
        ' on the patient disease history. For example, Volume Depletion, E86'
        ' in ICD-10 encoding',
        states=STATES)

    temperature = fields.Float(
        'Temperature',
        help='Temperature in celcius',
        states=STATES)

    weight = fields.Float('Weight', digits=(3, 2), help='Weight in kilos',
                          states=STATES)

    height = fields.Float('Height', digits=(3, 1),
                          help='Height in centimeters', states=STATES)

    bmi = fields.Float(
        'BMI', digits=(2, 2),
        help='Body mass index',
        states=STATES)

    head_circumference = fields.Float(
        'Head',
        help='Head circumference in centimeters',
        states=STATES)

    abdominal_circ = fields.Float('Waist', digits=(3, 1),
                                  help='Waist circumference in centimeters',
                                  states=STATES)

    hip = fields.Float('Hip', digits=(3, 1),
                       help='Hip circumference in centimeters',
                       states=STATES)

    whr = fields.Float(
        'WHR', digits=(2, 2), help='Waist to hip ratio . Reference values:\n'
        'Men : < 0.9 Normal // 0.9 - 0.99 Overweight // > 1 Obesity \n'
        'Women : < 0.8 Normal // 0.8 - 0.84 Overweight // > 0.85 Obesity',
        states=STATES)

    conditions = fields.Function(fields.One2Many('gnuhealth.patient.disease', 'none', 'Medical Conditions', domain=[('name', '=', Eval('patient'))]), 'get_patient_conditions', 'set_patient_conditions')
    procedures = fields.One2Many('gnuhealth.directions', 'prescription', 'Surgeries',  help='Surgeries Requested', states=STATES)
    surgery = fields.Many2One('gnuhealth.surgery','Surgery', required=False)    
    surgery_date = fields.DateTime('Surgery Date', states = STATES)


    def get_patient_conditions(self, name):
        lines = set()
        PatientCondition = Pool().get('gnuhealth.patient.disease')

        roundings = PatientCondition.search([
                ('name', '=', self.patient.id),	
                ])

        for line in roundings:
            lines.add(line.id)

        return list(lines)
        
    @classmethod
    def set_patient_conditions(cls, recs, name, value):
        if not value:
            return

        Patient = Pool().get("gnuhealth.patient")
        for p in recs:
            Patient.write([p.patient], {'diseases': value})        

    @classmethod
    def __setup__(cls):
        super(PrescriptionOrder, cls).__setup__()      

        cls._buttons.update({
                'confirm_surgery': { 
			'invisible': Eval('surgery'),
		    },
                'cancel_surgery': { 
			'invisible': Not(Eval('surgery')),
		    },	
        })

    @classmethod
    @ModelView.button
    def cancel_surgery(cls, prescriptions):
        raise ValidationError("Surgery is cancelled...")
         
    @classmethod
    @ModelView.button
    def confirm_surgery(cls, records):
        prescription = records[0]

        if not prescription.surgery_date:
             raise ValidationError("Please enter the date when surgery is going to be performed.")
        proc_lines = []
        if not prescription.procedures:
            raise ValidationError("Please enter the procedure/sugery to be performed.")
        
        Surgery = Pool().get('gnuhealth.surgery')
        Procedure = Pool().get("gnuhealth.operation")
        Prescription = Pool().get("gnuhealth.prescription.order")
        surgery = Surgery.create([{
			'patient':prescription.patient.id, 
			'surgery_date':  prescription.surgery_date,
			'surgeon': prescription.healthprof.id,
            'state': 'pre_anesthesia',
			}])        
        cls.write([prescription], {'surgery': surgery[0].id})

        for test in prescription.procedures:
            proc = Procedure.create([{
                    'procedure': test.procedure.id,
                    'name': surgery[0].id,
                    'notes': test.comments
                }])


class BirthCertificate (metaclass=PoolMeta):
    __name__ = 'gnuhealth.birth_certificate'

    born_dead_alive = fields.Selection((
        ('alive', 'Alive'),
        ('dead', 'Dead'),
        ), 'Born dead or alive?', select=True)        

    delivered_by_doctor = fields.Many2One('gnuhealth.healthprofessional', 'Medical Officer - Labour')
    time_of_birth = fields.Time('Time of Birth')

    @staticmethod
    def default_born_dead_alive():
        return 'alive'   

    @staticmethod
    def default_code():
        return (datetime.now()+timedelta(hours=5)).strftime('%d%m%y-%H%M%S')         


class DeathCertificate (metaclass=PoolMeta):
    __name__ = 'gnuhealth.death_certificate'
    brought_in_dead = fields.Boolean('Brought in Dead?')    
    ipd = fields.Many2One('gnuhealth.inpatient.registration','IPD Record')

    @staticmethod
    def default_code():
        return (datetime.now()+timedelta(hours=5)).strftime('%d%m%y-%H%M%S')    

class HealthInstitution (metaclass=PoolMeta):
    __name__ = 'gnuhealth.institution'
    turnaround_time_normal = fields.Integer("Turnaround Time (ToT Minutes)")
    turnaround_time_emergency = fields.Integer("Turnaround Time ER (ToT ER Minutes)")
    main_price_list = fields.Many2One('product.price_list','Main Price List')    


class Pathology (metaclass=PoolMeta):
    __name__ = 'gnuhealth.pathology'    
    disease_local_name = fields.Char("Disease Local Name")

    @classmethod
    def __setup__(cls):
        super(Pathology, cls).__setup__()    
        cls._order.insert(0, ('disease_local_name', 'ASC'))

    # Include code + description in result
    def get_rec_name(self, name):
        if self.disease_local_name:
            return (self.disease_local_name + ' (' + self.code + ' : ' + self.name + ')')
        else:
            return  self.code + ' : ' + self.name 
    # Search by the health condition code or the description
    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('code',) + tuple(clause[1:]),
                ('disease_local_name',) + tuple(clause[1:]),
                ]

class InsurancePanelBill (ModelSQL, ModelView):
    'Panel Bill'
    __name__ = 'health.proc.insurance.panel.bill'

    name = fields.Many2One('health.proc.insurance.panel','Panel', required=True)
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)
    statement_lines = fields.One2Many('account.statement.line','panel_bill', 'Patient Bills')

    state = fields.Selection((
        ('draft', 'Prepared'),
        ('submitted', 'Submitted'),
        ('cleared', 'Cleared'),
        ), 'Bill Status?', select=True)    
    notes = fields.Text('Details about this Panel')    

    def get_rec_name(self, name):
        if self.name:
                return self.name.rec_name            


class Purchase (metaclass=PoolMeta):
    __name__ = 'purchase.purchase'    

    @staticmethod
    def default_party():
        if Transaction().context.get('active_model') == 'purchase.purchase':
            Purchase = Pool().get('purchase.purchase')
            p = Purchase(Transaction().context.get('active_id'))
            if p:
                if p.party:
                     return p.party.id

    @staticmethod
    def default_purchase_date():
        return datetime.now()


    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        party_domain = cls.party.domain[:]
        if party_domain:
            cls.party.domain = [
                'AND',
                party_domain,
                [('is_institution', '=', True)],
                ]
        else:
            cls.party.domain = [
                ('is_institution', '=',True),
                ]
         
class Shipment (metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'    

    @staticmethod
    def default_supplier():
        if Transaction().context.get('active_model') == 'purchase.purchase':
            Purchase = Pool().get('purchase.purchase')
            p = Purchase(Transaction().context.get('active_id'))
            if p:
                if p.supplier:
                     return p.supplier.id

class PurchaseRequest (metaclass=PoolMeta):
    __name__ = 'purchase.request'    

    emp_name = fields.Function(fields.Char('Employee'),'get_emp_name')
    
    def get_emp_name(self, name):
        PurchaseRequisitionLine = Pool().get("purchase.requisition.line")
        origin = self.origin
        if origin and isinstance(self.origin, PurchaseRequisitionLine):
             if self.origin.requisition.employee:
                  return self.origin.requisition.employee.party.name

class InternalShipment (metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'    
    purchase_requisition = fields.Many2One('purchase.requisition','Purchase Requisition', readonly=True)

    @fields.depends('from_location')
    def on_change_from_location(self, name=None):
        if self.from_location:
            with Transaction().set_context(store_location=self.from_location.id):
                 x = 20

class ShipmentIn (metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'    
    store_location = fields.Many2One('stock.location', 'Store Location')

    @fields.depends('store_location')
    def on_change_with_warehouse_storage(self, name=None):
        if self.store_location:
            return self.store_location.id
        else:
            return super(ShipmentIn, self).on_change_with_warehouse_storage(name)
        
class PurchaseRequisition(metaclass=PoolMeta):
    __name__ = 'purchase.requisition'
    internal_shipments = fields.One2Many('stock.shipment.internal', 'purchase_requisition', 'Rounds by various doctors/nurses')
    internal_shipments_list = fields.Function(fields.One2Many('stock.shipment.internal', 'purchase_requisition','Shipments'), 'get_internal_shipments')
    store_location = fields.Function(fields.Many2One('stock.location', "Store Location"), 'get_store_location')
    
    @staticmethod
    def default_employee():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if user.employee:
            return user.employee.id
        
    @staticmethod
    def default_supply_date():
        return datetime.now()
        
    def get_store_location(self, name):
        if self.employee:
            if self.employee.department:
                 if self.employee.department.store_location:
                      return self.employee.department.store_location.id    
                 
    def get_internal_shipments(self, name):
        lines = set()
        if self.internal_shipments:
            for line in self.internal_shipments:
                    lines.add(line.id)

        logging.info(lines)
        return list(lines)

    @classmethod
    def __setup__(cls):
        super(PurchaseRequisition, cls).__setup__()
        cls._buttons.update({
            'createinternalshipment': {
                'invisible': Or(Equal(Eval('state'), 'processing'),
                    Equal(Eval('state'), 'done')),
            },
        })

    @classmethod
    @ModelView.button
    def createinternalshipment(cls, requisitions):
        for req in requisitions:
            if not req.warehouse:
                 raise ValidationError("Warehouse must be seleted")
            
            if not req.store_location:
                 raise ValidationError("Please configure a store for the department of this employee, where stock will be moved.")
            
            InternalShipment = Pool().get("stock.shipment.internal")
            StockMove = Pool().get("stock.move")
            shipments = InternalShipment.create([{
                'purchase_requisition':req.id, 
                'from_location': req.warehouse.storage_location.id, 
                'to_location': req.store_location.id,
                'state': 'request',
                'reference': req.description,
                'planned_date': req.supply_date,
                'planned_start_date': req.supply_date,
            }])

            for req_line in req.lines:
                move = StockMove.create([{
                    'shipment': str(shipments[0]),
                    'from_location': req.warehouse.storage_location.id,
                    'to_location': req.store_location.id,
                    'state': 'draft',
                    'product': req_line.product.id,
                    'quantity': req_line.quantity,
                    'uom': req_line.unit.id,
                    'planned_date': req.supply_date,
                }])

class ProductProduct(metaclass=PoolMeta):
    __name__ = 'product.product'
    is_norcotic = fields.Boolean('Norcotic Product?')
    is_fridge_item = fields.Boolean('Fridge Item?')
    is_discountable = fields.Boolean('Discount Allowed?')

class ProcedureComplexity(ModelSQL, ModelView):
    'Procedure Complexity'
    __name__ = 'health.proc.procedure.complexity'
    name = fields.Char('Procedure Complexity/Class')

class Directions(metaclass=PoolMeta):
    __name__ = 'gnuhealth.directions'
    prescription = fields.Many2One('gnuhealth.prescription.order', 'Prescription', readonly=True)    
    procedure_complexity = fields.Many2One('health.proc.procedure.complexity','Procedure Complexity', required=False)

class PurchaseLine(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    retail_price = fields.Numeric('Retail Price', digits=price_digits, 
                                  states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('purchase_state') != 'draft',
            })


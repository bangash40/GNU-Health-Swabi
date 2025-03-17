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
from datetime import datetime, date
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, reduce_ids
from sql import Literal, Table
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Bool, And, Equal, Or, In
from trytond import backend
import logging
from trytond.config import config
from decimal import Decimal
import pytz

from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserError
from trytond.modules.health.core import get_health_professional


__all__ = ['InpatientRegistration','InpatientAdvanceInvoices', 'IpdPackageChargeLine','IpdDoctorShare']

price_digits = (16, config.getint('product', 'price_decimal', default=4))

class InpatientRegistration(metaclass=PoolMeta):
    __name__ = 'gnuhealth.inpatient.registration'
    STATES = {'readonly': Or(
        Eval('state') == 'confirmed',
        Eval('state') == 'hospitalized',
        Eval('state') == 'done',
        Eval('state') == 'done_finance',        
        Eval('state') == 'finished')}

    STATES_DISCHARGED = {'readonly': Or(
	    Eval('state') == 'done',
        Eval('state') == 'finished',
        Eval('state') == 'done_finance',
	)}
    

    final_diagnosis = fields.Char('Final Diagnosis', states = STATES_DISCHARGED)
    discharge_summary = fields.Text('Brief Hospital Treatment Summary', states = STATES_DISCHARGED)
    discharge_mgmt_plan = fields.Text('Discharge Management Plan', states = STATES_DISCHARGED)

    sale_id = fields.Many2One('sale.sale', 'IPD Sale',  states ={'readonly':True})
    final_invoice_id = fields.Many2One('account.invoice','Final Invoice', states={'readonly':True})

    lines = fields.Function(fields.One2Many('sale.line', None,
            'Services'), 'get_lines')
    
    advance_invoices = fields.One2Many('gnuhealth.inpatient.advance.invoice', 'name',
        'Advance Invoices', states = STATES)
    advance_lines = fields.Function(fields.One2Many('account.invoice', None,
            'Advances'), 'get_advance_lines')

    packages = fields.One2Many('health.proc.ipd.package.charge.line', 'name',
        'Packages Charged', states = STATES)
    package_lines = fields.Function(fields.One2Many('health.proc.ipd.package.charge.line', None,
            'Packages'), 'get_package_lines')
	    

    payment = fields.Function(fields.Numeric('Advance Payment', states ={'readonly':True}, digits=price_digits),'calculate_advance_payment')

    total_bill = fields.Function(fields.Numeric('Total Bill', states ={'readonly':True}, digits=price_digits),'calculate_total_bill')

    change = fields.Function(fields.Numeric('Balance Amount', states ={'readonly':True}, digits=price_digits), 'calculate_balance_amount')
	
    package_discount_surplus = fields.Function(fields.Numeric('Package Discount/Surplus', states ={'readonly':True}, digits=price_digits),'calculate_total_package_discount_surplus')


    doctor_shares = fields.One2Many('health.proc.ipd.doctor.share', 'name',
        'Doctor Shares', states = STATES)
    doctor_share_lines = fields.Function(fields.One2Many('health.proc.ipd.doctor.share', None,
            'Doctor Share'), 'get_doctor_share_lines')
    total_doctor_share = fields.Function(fields.Numeric('Total Doctor Share', states ={'readonly':True}, digits=price_digits),'calculate_total_doctor_share')   


    discharge_plan = fields.Text('Discharge Plan', states = STATES_DISCHARGED)
    financial_discharged_by = fields.Many2One(
        'gnuhealth.healthprofessional', 'Financial Discharge by', readonly=True,
        help="Health Professional that financially discharged the patient")

    nursing_discharged_by = fields.Many2One(
        'gnuhealth.healthprofessional', 'Nursing Discharge by', readonly=True,
        help="Health Professional that nursing discharged the patient")

    financial_notes = fields.Text('Financial Notes')
    history = fields.Text('History',states = STATES_DISCHARGED)
    findings = fields.Text('Examination/Findings',states = STATES_DISCHARGED)
    investigations = fields.Text('Investigations',states = STATES_DISCHARGED)
    follow_up_plan = fields.Text('Follow-up Plan',states = STATES_DISCHARGED)

    actual_discharge_date = fields.DateTime('Discharge Date',
         select=True, states = STATES)
   
    ward = fields.Function(
        fields.Char('Ward', help="Ward where patient is admitted in."),
        'get_ipd_ward', searcher="search_ipd_ward")

    specialty = fields.Function(
        fields.Char('Specialty', help="Specialty where patient is admitted under."),
        'get_ipd_specialty', searcher="search_ipd_specialty")

    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Payment Mode', select=True, states = {
            'readonly': Or(Eval('state') == 'done',
                            Eval('state') == 'finished',
				Eval('state') == 'hospitalized',
			        Eval('state') == 'done_finance',
                        )
            }
        )

    panel = fields.Many2One('health.proc.insurance.panel', 'Insurance Panel', states = {
            'readonly': Or(Eval('state') == 'done',
                            Eval('state') == 'finished',
				Eval('state') == 'hospitalized',
			        Eval('state') == 'done_finance',
                        )
            })


    tentative_package = fields.Many2One('health.proc.insurance.panel.product.group', 'Package', 
                                        domain=[('product_group.group_type', '=', 'package'),('panel','=', Eval('panel'))],
                                        depends=['panel'])


    
    advance_amount = fields.Numeric('Advance Amount', help='Amount taken as advance at the time of admission', states = STATES)

    requested_by = fields.Many2One(
        'gnuhealth.healthprofessional', 'Admitted By',
        help="Doctor who sent the admission for this patient", readonly=True)

    requested_on = fields.Function(
        fields.DateTime(
            'Adm. Request On',
            help="Date/Time when the admission request was sent."),
        'get_requested_on')
    was_in_icu = fields.Boolean('Was in ICU')

    payment_status = fields.Function(
        fields.Char(
            'Payment Status',
            help="The status of the generated invoice,"),
        'get_payment_status')

    attendant = fields.Char('Attendant')

    hospitalization_type = fields.Selection([
        (None, ''),
        ('IPD', 'IPD'),
        ('ER', 'ER'),
        ], 'Hospitalization type', required=False, select=True)

    def get_created_by_info(cls):
        ResUser = Pool().get("res.user")
        created_by = ResUser(cls.create_uid)

        return created_by.name

    def get_service_doctor(cls, sale_line_id):
        doctor_name = ''

        if cls.doctor_shares:
            for line in cls.doctor_shares:
                    if line.sale_line_id == sale_line_id:
                         doctor_name = line.doctor_one.rec_name

        return doctor_name

    def get_net_amount_paid_by_patient(cls):
        net_amount = 0
        if cls.payment_mode in ('cash','panel_cash'):
            if cls.sale_id.welfare_discount_value:
                net_amount = cls.total_bill - cls.sale_id.welfare_discount_value - cls.payment
            else:
                net_amount = cls.total_bill - cls.payment

        if net_amount > 0:
             return net_amount

    def get_net_bill_refund_to_patient(cls):
        net_amount = 0
        if cls.payment_mode in ('cash','panel_cash'):
            if cls.sale_id.welfare_discount_value:
                net_amount = cls.total_bill - cls.sale_id.welfare_discount_value - cls.payment
            else:
                net_amount = cls.total_bill - cls.payment

        if net_amount < 0:
             return net_amount
        
    def get_requested_on(self, name):
        return self.create_date

    def get_payment_status(self, name):
        Invoice = Pool().get('account.invoice')
        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
        registration_id = InpatientRegistration(self.id)

        if not registration_id.final_invoice_id:
            return "Not Invoiced yet"
        
        invoice = Invoice(registration_id.final_invoice_id)

        return invoice.state


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
    
    @fields.depends('packages','package_discount_surplus')
    def on_change_packages(self):
        if self.packages:
                total = 0
                for line in self.packages:
                        total = total + line.discount_surplus_amount if line.discount_surplus_amount else 0

                return {'package_discount_surplus':total}

    def calculate_total_package_discount_surplus(self, name):
        total = 0
        if self.packages:
            for line in self.packages:
                total = total + line.discount_surplus_amount if line.discount_surplus_amount else 0

        return total     

    def calculate_total_doctor_share(self, name):
        total = 0
        if self.packages:
            for line in self.doctor_shares:
                if line.doctor_one and line.doctor_one_share:
                    total = total + line.doctor_one_share

                if line.doctor_two and line.doctor_two_share:
                    total = total + line.doctor_two_share

        return total     
    
    @fields.depends('lines','total_bill')
    def on_change_lines(self):
        if self.lines:
                total = 0
                for line in self.lines:
                        total = total + line.amount

                return {'total_bill':total}

    def calculate_total_bill(self, name):
        total = 0
        if self.sale_id:
                for line in self.sale_id.lines:
                        total = total + line.amount

        return total

    def calculate_advance_payment(self, name):
        total = 0
        Invoice = Pool().get('account.invoice')
        fields = {'total_amount','tax_amount','untaxed_amount'}

        if self.advance_invoices:
            for line in self.advance_invoices:
                try:
                    if line.invoice.state == 'posted' or line.invoice.state == 'paid':
                        invoices = []
                        invoices.append(line.invoice)
                        result = Invoice.get_amount(invoices,fields)
                        #logging.info("========================== invoice get amount results====================")
                        logging.info(result)
                        total = total + result['total_amount'][line.invoice.id]
                except Exception as inst:
                    total = total + 0
                    #logging.info("====================== displaying exception")
                    logging.info(type(inst))
                    logging.info(inst.args)
                    logging.info(inst)
                    
                #logging.info("========================== invoice total====================")
            logging.info(total)

        return total


    def calculate_balance_amount(self, name):
        total = 0
        if not self.total_bill:
                total_bill = 0
        if not self.payment:
                self.payment = 0

        total = self.total_bill - self.payment
        return total

    @fields.depends('payment','total_bill','change')
    def on_change_payment(self):
        if self.payment:
                if self.total_bill:
                        self.change = self.total_bill - self.payment

    def get_lines(self, name):
        lines = set()
        if self.sale_id:
                for line in self.sale_id.lines:
                        lines.add(line.id)
        logging.info(lines)
        return list(lines)

    def get_advance_lines(self, name):
        # name is the filed to match the inpatient-registration-id in the gnuhealth_patient_rounding table
        lines = set()
        if self.advance_invoices:
                for line in self.advance_invoices:
                        lines.add(line.invoice.id)

        logging.info(lines)
        return list(lines)
    
    def get_package_lines(self, name):
        lines = set()
        if self.packages:
                for line in self.packages:
                        lines.add(line.id)

        logging.info(lines)
        return list(lines)

    def get_doctor_share_lines(self, name):
        lines = set()
        if self.doctor_shares:
                for line in self.doctor_shares:
                        lines.add(line.id)

        logging.info(lines)
        return list(lines)

    @staticmethod
    def default_hospitalization_type():
        context = Transaction().context
        is_er = False
        for key in context:
            #logging.info(str(key) + ": " + str(context[key]))
            if(key == 'ER'):
                is_er = True

        if is_er:
             return 'ER'
        else:
             return 'IPD'


    @staticmethod
    def default_payment_mode():
        return 'cash'
        

    @staticmethod
    def default_hospitalization_date():
        return datetime.now()

    @staticmethod
    def default_discharge_date():
        return datetime.now()

    def get_patient_puid(self, name):
        return self.patient.name.ref

    @classmethod
    def search_patient_puid(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('patient.name.ref', clause[1], value))
        return res

    def get_ipd_ward(self, name):
        if self.bed:
                return self.bed.ward.name		

    @classmethod
    def search_ipd_ward(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('bed.ward.name', clause[1], value))
        return res

    def get_ipd_specialty(self, name):
        try:
                if self.attending_physician:
                        if self.attending_physician.main_specialty:
                                if self.attending_physician.main_specialty.specialty:
                                        return self.attending_physician.main_specialty.specialty.name	
        except:
                logging.info("=========== error getting specialty column  value")

    @classmethod
    def search_ipd_specialty(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('attending_physician.main_specialty.specialty.name', clause[1], value))
        return res

    ## Method to check for availability and make the hospital bed reservation
    # Checks that there are not overlapping dates and status of the bed / room
    # is not confirmed, hospitalized or done but requiring cleaning ('done')
    @classmethod
    @ModelView.button
    def confirmed(cls, registrations):
        registration_id = registrations[0]


        if registration_id.hospitalization_type == None:
                raise ValidationError("Please enter Hospitalization type before confirming admission. Is it IPD or ER case?")

        if registration_id.admission_type == None:
                raise ValidationError("Please enter admission type before confirming admission")

        if registration_id.payment_mode == None:
                raise ValidationError("Please enter Patient-Type before confirming admission")
        else:
            if registration_id.payment_mode in ['panel_credit', 'panel_cash'] and not registration_id.panel:
                raise ValidationError("Please select a Panel first")
        
        if registration_id.hospitalization_date == None:
                raise ValidationError("Please enter 'Hospitalization Date & Time' before confirming admission")

        if registration_id.discharge_date == None:
                raise ValidationError("Please enter expected 'Discharge Date & Time' before confirming admission")

        if registration_id.bed == None and registration_id.hospitalization_type != "ER":
                raise ValidationError("Please select the 'Hospital Bed' before confirming admission")

        if registration_id.attending_physician == None:
                raise ValidationError("Please select the 'Attending Physician' before confirming admission")

        if (registration_id.discharge_date.date() <
            registration_id.hospitalization_date.date()):
            raise ValidationError("The Discharge date must later than the \
                Admission")

        if registration_id.hospitalization_type == 'IPD':
            if registration_id.payment_mode != 'panel_credit' and registration_id.advance_amount == None:
                raise ValidationError("Please enter 'Advance Amount' taken from patient before confirming admission")

        Bed = Pool().get('gnuhealth.hospital.bed')

        if registration_id.bed:
            cursor = Transaction().connection.cursor()
            bed_id = registration_id.bed.id
            cursor.execute("SELECT COUNT(*) \
                FROM gnuhealth_inpatient_registration \
                WHERE (hospitalization_date::timestamp,discharge_date::timestamp) \
                    OVERLAPS (timestamp %s, timestamp %s) \
                AND (state = %s or state = %s or state = %s) \
                AND bed = CAST(%s AS INTEGER) ",
                (registration_id.hospitalization_date,
                registration_id.discharge_date,
                'confirmed', 'hospitalized', 'done', str(bed_id)))
            res = cursor.fetchone()

            if res[0] > 0:
                raise ValidationError('bed_is_not_available')

        Sale = Pool().get('sale.sale')
        sale_id = registration_id.sale_id

        Patient = Pool().get('gnuhealth.patient')
        pp = Patient(registration_id.patient)
        Date = Pool().get('ir.date')
        price_list = None
        panel = None

        # getting attribute for sale recrod if the patient is a panel patient
        panel_sale = False
        if registration_id.payment_mode in ['panel_credit']:
            if registration_id.panel:
                    panel_sale = True
            else:
                    raise ValidationError('Please select the panel name')
       
        if sale_id:
            found_sale = Sale(sale_id)
            Sale.write([found_sale],{'party':pp.name.id, 
                                     'invoice_address':registration_id.panel.name.addresses[0] if registration_id.panel else pp.name.addresses[0],
                                     'invoice_party': registration_id.panel.name.id if registration_id.panel else pp.name.id,
                                     'shipment_address': pp.name.addresses[0],})
        else:
                sale_type = 'ipd'
                if registration_id.hospitalization_type == 'ER':
                     sale_type = 'er';
                
                sales = Sale.create([{
                    'currency':1,
                    'party':pp.name.id, # it is insurance company if panel; otherwise patient party
                    'self_pick_up':'true',
                    'invoice_address':registration_id.panel.name.addresses[0] if registration_id.panel else pp.name.addresses[0],
                    'invoice_party': registration_id.panel.name.id if registration_id.panel else pp.name.id,
                    'shipment_address':pp.name.addresses[0],
                    #'sale_date':Date.today(), 
                    'description':'Sale against inpatient registration no. ' + str(registration_id.name),
                    'sale_type': sale_type,
                    'payment_mode': registration_id.payment_mode if registration_id.payment_mode else None,

                }])
                sale_id = sales[0].id
                logging.info("============ IPD Sale is created with id: " + str(sale_id) + ", for IPD-Admission: " + str(registration_id.name))

        # save the advance 
        if(registration_id.payment_mode != 'panel_credit' and registration_id.advance_amount):
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
            if len(stmts) == 1:
                    logging.info(stmts[0].id)
                    statement_id = stmts[0].id
            else:
                    raise ValidationError('The statement for the user is not opened yet')

            sysConfig = SystemConfig(1);
            description = ""
            Date = Pool().get('ir.date')			
            Invoice = Pool().get('account.invoice')
            invoiceLine = [{'type':'line', 
                    'description':description, 
                    'quantity':1, 
                    'unit_price':registration_id.advance_amount,
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
            logging.info("============================== invice id generated")
            logging.info(invoices[0].id)

            stmtLine = {'statement':statement_id,'date':Date.today(),'amount':registration_id.advance_amount,'party':pp.name.id, 'line_type': 'ipd_admission', 'sale_type': 'ipd',
                    'account':sysConfig.advance_account_for_statement, 'invoice':invoices[0].id, 'description': 'advance from patient MRNO:' + pp.name.ref + ", Inpatient Code: " + registration_id.name}
            logging.info(stmtLine)
            StatementLine.create([stmtLine])
    
            InpatientAdvanceInvoice = Pool().get('gnuhealth.inpatient.advance.invoice')
            invoices = InpatientAdvanceInvoice.create([{'name':registration_id.id,'invoice':invoices[0].id, 'advance_type':'admission'}])

        # finally write inpatient and bed record
        if not sale_id:
            logging.error(">>>>>>>>>>>>>>>>>>>> Unable to create Sale for this IPD_Admission: " + str(registration_id.name))
            raise ValidationError("There is some issue in creation of IPD Bill, please try again or contact Administrator")

        cls.write(registrations, {'state': 'confirmed', 'sale_id':sale_id})
        
        if registration_id.bed:
            Bed.write([registration_id.bed], {'state': 'reserved'})

    @classmethod
    @ModelView.button
    def discharge(cls, registrations):
        registration_id = registrations[0]
        Bed = Pool().get('gnuhealth.hospital.bed')

        signing_hp = get_health_professional()

        if not signing_hp:
            raise ValidationError(
                "No health professional associated to this user !")

        cls.write(registrations, {'state': 'done', 
            'discharged_by': signing_hp, 'actual_discharge_date': datetime.now()})

        if registration_id.bed:
            Bed.write([registration_id.bed], {'state': 'free'})

    @classmethod
    @ModelView.button
    def cancel(cls, registrations):
        registration_id = registrations[0]
        Bed = Pool().get('gnuhealth.hospital.bed')

        cls.write(registrations, {'state': 'cancelled'})

        if registration_id.bed:
            Bed.write([registration_id.bed], {'state': 'free'})

    @classmethod
    @ModelView.button
    def admission(cls, registrations):
        registration_id = registrations[0]
        Bed = Pool().get('gnuhealth.hospital.bed')

        old_admission = False
        if (registration_id.hospitalization_date.date() !=
            datetime.today().date()):
            #raise ValidationError("The Admission date must be today")
            old_admission = True
            
        cursor = Transaction().connection.cursor()
        cursor.execute("SELECT COUNT(*) \
            FROM gnuhealth_inpatient_registration \
            WHERE state = %s  \
                AND patient = CAST(%s AS INTEGER)",
            ('hospitalized', str(registration_id.patient.id)))
        res = cursor.fetchone()

        if res[0] > 0:
            raise ValidationError('The patient is already hospitalized in IPD or ER.')

        if registration_id.bed:
            Bed.write([registration_id.bed], {'state': 'occupied'})
            
        cls.write(registrations, {'state': 'hospitalized', 'hospitalization_date':datetime.now()})

    @classmethod
    @ModelView.button
    def getfinalinvoice(cls, registrations):
        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
        Date = Pool().get('ir.date')
        Move = Pool().get('account.move')
        MoveLine = Pool().get('account.move.line')
        Period = Pool().get('account.period')
        SystemConfig = Pool().get('anth.proc.system.config')

        registration_id = registrations[0]
        if registration_id.state != 'done':
            raise ValidationError("The patient is not discharged yet; so Final Bill can not be prepared. Get the patient discharged first, please!")

        if registration_id.final_invoice_id:
            raise ValidationError("The Final Invoice has already been prepared. Please get the payment and click 'Pay Final Invoice' button.")
        Sale = Pool().get('sale.sale')
        sale = Sale(registration_id.sale_id)
        logging.info("================================ going to put in quote the following sale")
        logging.info(sale)

        # update date and set sale_date to today
        Date = Pool().get('ir.date')
        Sale.write([sale], {'sale_date': Date.today()})


        p = Sale.quote([sale])
        logging.info("========================================== after quote")
        logging.info(p)



        sale = Sale(registration_id.sale_id)
        p = Sale.confirm([sale])
        logging.info("========================================== after confirming")
        logging.info(p)

        sale = Sale(registration_id.sale_id)        
        p = Sale.process([sale])
        logging.info("========================================== after processing")
        logging.info(p)

        # adding advance line in the draft invoice created for this sale
        final_invoice_id = -1
        logging.info("======================= getting final invoice")

        SaleLine = Pool().get('sale.line')
        the_sale_lines = SaleLine.search([
				        ('sale', '=', registration_id.sale_id),		
			        ])

        InvoiceLine = Pool().get('account.invoice.line')
        invoice_line = None
        #if len(the_sale_lines) > 0:
        invoice_line = InvoiceLine.search(['origin', '=', "sale.line," + str(the_sale_lines[0].id)])

        logging.info(invoice_line)
        #if invoice_line:
        final_invoice_id = invoice_line[0].invoice.id
        InpatientRegistration.write([registration_id], {'final_invoice_id':final_invoice_id})

        # setting the invoice field patient - its not working
        Invoice = Pool().get("account.invoice")
        final_invoice_obj = Invoice(final_invoice_id)
        #Invoice.write([final_invoice_obj], {'patient': registration_id.patient.id})


        SystemConfig = Pool().get('anth.proc.system.config')
        sysConfig = SystemConfig(1);
        #if final_invoice_id != -1:
        InvoiceLine = Pool().get('account.invoice.line')
        invoiceLine = [{'type':'line', 
		        'description':'Less all advances from patient MRNO:' + registration_id.patient.name.ref + ", Inpatient Code: " + registration_id.name, 
		        'quantity':1, 
		        'unit_price':registration_id.payment * -1,
		        'invoice': final_invoice_id,
		        'account': sysConfig.patient_advance_account_id,
		        'party': registration_id.patient.name.id,}]
        InvoiceLine.create(invoiceLine)

        #check if a discount is approved for this sale
        discount_request = None
        sale = Sale(registration_id.sale_id)        
        DiscountRequest = Pool().get("anth.proc.discount.request")
        discounts = DiscountRequest.search([
            ('sale', '=', sale.id),('state', '=', 'approved')				
        ])

        welfare_discount = 0
        if(len(discounts) == 1):
            discount_request = discounts[0]
            welfare_discount = discount_request.discount_value 
            if welfare_discount > 0:
                #utilizt the discount
                DiscountRequest.write([discount_request],{'state': 'utilized'})
                
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

                second_currency = None
                amount_second_currency = None

                description = ''
                donation_exp_account = 19
                dep_move_line =  MoveLine(
                    debit=welfare_discount,
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
                    credit=welfare_discount,
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
                        'description':'Less welfare discount for patient MRNO:' + sale.party.ref , 
                        'quantity':1, 
                        'unit_price':welfare_discount * -1,
                        'invoice': final_invoice_id,
                        'account': sysConfig.donation_as_patient_advance_account_id,
                        'party': sale.party.id,}]
                InvoiceLine.create(invoiceLine)

                Sale.write([sale], {'is_welfare_sale': True,'welfare_discount_value': welfare_discount})
        else:
            if(len(discounts) > 1):
                raise ValidationError("More than one Welfare Discounts are found for this IPD Sale; please keep only one and reject all others.")



    @classmethod
    @ModelView.button
    def payfinalinvoice(cls, registrations):
        registration_id = registrations[0]

        if not registration_id.final_invoice_id:
                raise ValidationError('Please prepare the invoice first in order to pay final invoice.')


        if registration_id.final_invoice_id.state != 'draft':
                raise ValidationError("The Final Invoice has already been prepared. Please get the payment and click 'Pay Final Invoice' button.")

        Invoice = Pool().get('account.invoice')
        final_invoice = Invoice(registration_id.final_invoice_id)
        logging.info("=================================== final invoice id =======================")
        logging.info(final_invoice)


        logging.info("=================================== final invoice party id =======================")
        logging.info(final_invoice.party.id)

        # update invoice_date and accounting date of the invoice so that when statement is posted, these dates are not set wrongly
        Date = Pool().get('ir.date')			
        Invoice.write([final_invoice],{'invoice_date': Date.today(), 'accounting_date': Date.today(), 'journal':1,})

        # get the statement object
        SystemConfig = Pool().get('anth.proc.system.config')
        StatementLine = Pool().get('account.statement.line')
        ResUser = Pool().get('res.user')
        user = ResUser(Transaction().user)
        AccountStatement = Pool().get('account.statement')
        statement_id = -1
        Date = Pool().get('ir.date')

        # if not user.statement_journal:
        #         raise ValidationError('No statement jounral found for the user. Contact IT department for configuration.')
        # stmts = AccountStatement.search([('journal', '=', user.statement_journal.id) ,( 'state', '=', 'draft'),])
        # if len(stmts) == 1:
        #         logging.info(stmts[0].id)
        #         statement_id = stmts[0].id
        # else:
        #         raise ValidationError('The statement for the user is not opened yet')

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

        if registration_id.payment_mode in ['panel_credit'] and registration_id.panel:
	        # for panel patient earlier the invoice was posted by not saved to statement , but now its being done
                Invoice.post([final_invoice])
                fields = {'total_amount','tax_amount','untaxed_amount'}
                result = Invoice.get_amount([final_invoice],fields)
                invoice_amount = result['total_amount'][final_invoice.id]

                logging.info("=================================== amount of final invoice =======================")
                logging.info(invoice_amount)

                sysConfig = SystemConfig(1);
                stmtLine = {'statement':statement_id,'date':Date.today(),'amount':invoice_amount,'party':registration_id.panel.name.id, 'line_type':'credit_sale', 'sale_type': 'ipd',
                        'account':sysConfig.main_receivable_account_id, 'invoice':final_invoice.id, 'sale': registration_id.sale_id,
                        'description': 'payment against final invoice on discharge from patient MRNO:' + registration_id.patient.name.ref + ", Inpatient Code: " + registration_id.name}
                logging.info(stmtLine)
                if invoice_amount != 0:
                    StatementLine.create([stmtLine])                
        else:
                # allother sales even cash_panel is our cash sale
                Invoice.post([final_invoice])
                fields = {'total_amount','tax_amount','untaxed_amount'}
                result = Invoice.get_amount([final_invoice],fields)
                invoice_amount = result['total_amount'][final_invoice.id]

                logging.info("=================================== amount of final invoice =======================")
                logging.info(invoice_amount)

                sysConfig = SystemConfig(1);
                stmtLine = {'statement':statement_id,'date':Date.today(),'amount':invoice_amount,'party':registration_id.patient.name.id, 'line_type':'ipd_discharge', 'sale_type': 'ipd',
                        'account':sysConfig.main_receivable_account_id, 'invoice':final_invoice.id, 'sale': registration_id.sale_id, 
                        'description': 'payment against final invoice on discharge from patient MRNO:' + registration_id.patient.name.ref + ", Inpatient Code: " + registration_id.name}
                logging.info(stmtLine)
                if invoice_amount != 0:
                    StatementLine.create([stmtLine])

    @classmethod
    def __setup__(cls):
        super(InpatientRegistration, cls).__setup__()
        cls._buttons.update({
            'getadvance': {},
            'getbedcharges': {},
            'getfinalinvoice': {
                'invisible': Not(Equal(Eval('state'), 'done')),
            },
		    'payfinalinvoice': {
                'invisible': Not(Equal(Eval('state'), 'done')),
            },
            'chargepackage': {},
            'calculatedoctorshare': {},
            'dischargefinancial': {},
            

        })

    @classmethod
    @ModelView.button
    def dischargefinancial(cls, registrations):
        registration_id = registrations[0]

        signing_hp = get_health_professional()
        if not signing_hp:
            raise ValidationError("No health professional associated to this user !")

        if registration_id.state != 'done':
            raise ValidationError('Financial clearance process can only be started after Discharge by Attending Physician')

        if not registration_id.final_invoice_id:
            raise ValidationError('Please prepare the invoice first in order to give financial clearance')

        # normally the final invoide should be in posted state. however, if the amount of final invoice is 0, it will be in paid state. change condtition acccordingly
        if registration_id.final_invoice_id.state != 'posted' and registration_id.final_invoice_id.state != 'paid':
            raise ValidationError('Please get the final invoice/bill from the patient in order to give financial clearance')

        
        #create commission invoices
        pool = Pool()
        Commission = pool.get('commission')
        InvoiceLine = Pool().get("account.invoice.line")
        Date = pool.get('ir.date')
        today = Date.today()
        Agent = Pool().get("commission.agent")
        SystemConfig = Pool().get('anth.proc.system.config')
 
        sysConfig = SystemConfig(1);
        if not sysConfig.ipd_commission_plan:
             raise ValidationError("No IPD plan defined in configuration.")
        plan = sysConfig.ipd_commission_plan

        for share in registration_id.doctor_shares:
            invoice_lines = InvoiceLine.search([
                ('origin', '=', 'sale.line,'+str(share.sale_line_id)),		
            ])

            if(len(invoice_lines) > 0):
                if share.doctor_one and share.doctor_one_share:
                    doctor_agents = Agent.search([
                        ('party', '=', share.doctor_one.name),				
                    ])              
                    
                    if len(doctor_agents) == 0:
                         raise ValidationError("No Agent fould for the Doctor One: " + share.doctor_one.name.name)
                    agent = doctor_agents[0]

                    logging.info("============ Going to create commission invoice for doctor one for doctor-share id: " + str(share.id))
                    commission = Commission()
                    commission.origin = invoice_lines[0]
                    commission.date = today
                    commission.agent = agent
                    commission.product = plan.commission_product
                    commission.amount = share.doctor_one_share

                    Commission.save([commission])

            if share.doctor_two and share.doctor_two_share:
                    doctor_agents = Agent.search([
                        ('party', '=', share.doctor_two.name),				
                    ])              
                    
                    if len(doctor_agents) == 0:
                         raise ValidationError("No Agent fould for the Doctor Two: " + share.doctor_two.name.name)
            
                    agent = doctor_agents[0]

                    logging.info("============ Going to create commission invoice for doctor two for doctor-share id: " + str(share.id))
                    commission = Commission()
                    commission.origin = invoice_lines[0]
                    commission.date = today
                    commission.agent = agent
                    commission.product = plan.commission_product
                    commission.amount = share.doctor_two_share

                    Commission.save([commission])


        cls.write(registrations, {'state': 'done_finance','financial_discharged_by': signing_hp})
            
    @classmethod
    @ModelView.button_action('health_proc.patient_advance_get')
    def getadvance(cls, registrations):
        pass

    @staticmethod
    def default_state():
        return 'free'

    @classmethod
    def validate(cls, registrations):
        super(InpatientRegistration, cls).validate(registrations)
        for registration in registrations:
            registration.check_discharge_context()

    def check_discharge_context(self):
        if ((not self.discharge_reason 
            or not self.admission_reason)
            and self.state == 'done'):
                raise ValidationError('admission and discharge reasons are needed!')
        
    @classmethod
    @ModelView.button_action('health_proc.patient_sale_create')
    def getbedcharges(cls, registrations):
        pass

    @classmethod
    @ModelView.button_action('health_proc.wizard_charge_package')
    def chargepackage(cls, registrations):
        pass

    @classmethod
    @ModelView.button_action('health_proc.wizard_calculate_doctor_share')
    def calculatedoctorshare(cls, registrations):
        pass

class InpatientAdvanceInvoices (ModelSQL, ModelView):
    'Inpatient Advance Invoices'
    __name__ = 'gnuhealth.inpatient.advance.invoice'

    name = fields.Many2One('gnuhealth.inpatient.registration','Registration Code')
    invoice = fields.Many2One('account.invoice', 'Invoice Id of the advance invoice')
    advance_type = fields.Char('Advance Type')   

class IpdPackageChargeLine(ModelSQL, ModelView):
    'IPD Package Charge Line'
    __name__ = 'health.proc.ipd.package.charge.line'

    name = fields.Many2One('gnuhealth.inpatient.registration','Registration Code')
    desc = fields.Char('Description', required=False)
    product_group = fields.Many2One('health.proc.product.group', 'Package', required=True, domain=[('group_type', '=', 'package')])
    qty = fields.Integer('Qty')
    list_price = fields.Numeric('Cash Price', states ={'readonly':True})
    discount_percent = fields.Numeric('Discount %age', states ={'readonly':True})
    discount_amount = fields.Numeric('Discount amount', states ={'readonly':True})
    panel_price = fields.Numeric('Panel Price for this package', states ={'readonly':True})
    net_price = fields.Numeric('Net Price Charged', states={'readonly':True})
    discount_surplus_amount = fields.Numeric('Discount/Surplus amount', states ={'readonly':True})    

    def get_rec_name(self, name):
        if self.product_group:
                return self.product_group.rec_name 

class IpdDoctorShare(ModelSQL, ModelView):
    'IPD Doctor Share'
    __name__ = 'health.proc.ipd.doctor.share'

    name = fields.Many2One('gnuhealth.inpatient.registration','IPD Code')
    desc = fields.Char('Description', required=False)
    product_group = fields.Many2One('health.proc.product.group', 'Package', domain=[('group_type', '=', 'package')])
    product = fields.Many2One('product.product', 'Service')
    list_price = fields.Numeric('Service Cash Price', states ={'readonly':True})

    doctor_one = fields.Many2One('gnuhealth.healthprofessional','Doctor-One', required=True)
    doctor_one_share = fields.Numeric('Doctor-One-Share', states ={'readonly':True})

    doctor_two = fields.Many2One('gnuhealth.healthprofessional','Doctor-Two', required=False)
    doctor_two_share = fields.Numeric('Doctor-two-Share', states ={'readonly':True})

    sale_line_id = fields.Integer("Sale Line", readonly=True)

    def get_rec_name(self, name):
        if self.product:
                return self.product.rec_name 

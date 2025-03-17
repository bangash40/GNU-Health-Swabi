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
from decimal import Decimal


__all__ = ['ChargePackageStart','ChargePackageWizard','PackageChargeLine', 'CalculateDoctorShareWizard', 'CalculateDoctorShareStart','DoctorShare']

class PackageChargeLine(ModelView):
    'General Package Charge Line'
    __name__ = 'health.proc.general.package.charge.line'

    product_group = fields.Many2One('health.proc.product.group', 'Package', required=True, domain=[('group_type', '=', 'package')])
    list_price = fields.Numeric('Cash Price', states ={'readonly':True})
    discount_percent = fields.Numeric('Discount %age', states ={'readonly':True})
    discount_amount = fields.Numeric('Discount amount', states ={'readonly':True})
    panel_price = fields.Numeric('Panel Price for this package', states ={'readonly':True})
    net_price = fields.Numeric('Net Price Charged', states={'readonly':True})
    discount_surplus_amount = fields.Numeric('Discount/Surplus amount', states ={'readonly':True})

    def get_rec_name(self, name):
        if self.product_group:
                return self.product_group.rec_name   

    @fields.depends('product_group')
    def on_change_product_group(self):
        if self.product_group:
                list_price = self.product_group.get_list_price()
                self.list_price = list_price
                if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                        PanelPackage = Pool().get("health.proc.insurance.panel.product.group")
                        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
                        inpatient = InpatientRegistration(Transaction().context.get('active_id'))

                        discount_percent = None
                        discount_amount = None
                        panel_price = None
                        net_price = list_price
                        discount_surplus_amount = None
                        if inpatient.panel:
                                panel_package_details = PanelPackage.search([('panel','=',inpatient.panel.id),('product_group','=',self.product_group.id)])
                                if(len(panel_package_details) > 0):
                                        found_panel_package = panel_package_details[0]
                                        discount_percent = found_panel_package.discount
                                        if(discount_percent):
                                                discount_amount = (Decimal(list_price) * Decimal(str(discount_percent))) / 100
                                        if(discount_percent):
                                                net_price = Decimal(list_price) - Decimal(discount_amount)
                                                discount_surplus_amount = discount_amount
                                        else:
                                                panel_price = found_panel_package.price                         
                                                net_price = panel_price
                                                discount_surplus_amount = Decimal(list_price) - Decimal(net_price)

                                self.discount_percent = Decimal(discount_percent) if discount_percent else None
                                self.discount_amount = Decimal(discount_amount) if discount_amount else None
                                self.panel_price = Decimal(panel_price) if panel_price else None
                                self.net_price = Decimal(net_price) if net_price else None
                                self.discount_surplus_amount = Decimal(discount_surplus_amount) if discount_surplus_amount else None

class ChargePackageStart(ModelView):
    'Charge Packages to Patient'
    __name__ = 'health.proc.charge.package.start'

    date = fields.DateTime('Date')
    patient = fields.Many2One('gnuhealth.patient', 'Patient', required=True, states ={'readonly':True})
    nature = fields.Char('OPD/IPD/ER/DayCare?', states={'readonly':True})
    inpatient_registration_code =  fields.Integer('IPD No.', states ={'readonly':True}) 
    department = fields.Char('Department', states={'readonly':True})
    amount = fields.Numeric('Amount', help='Amount charged against packages', required=False)
    description = fields.Char('Description', required=True)
    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Payment Mode', states= {'readonly':True}
        )    
    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Panel',
        required=False, select=True,
        states= {'readonly':True})
    #charged_packages = fields.One2Many('health.proc.ipd.package.charge.line', None, 'List of Packages', help="List of Packages Charged")
    charged_packages = fields.One2Many('health.proc.general.package.charge.line', None, 'Packages', 
                                        domain=[('product_group.group_type', '=', 'package')],
                                        depends=['insurance_company'])
    sale_id = fields.Integer('Sale ID')    

    @staticmethod
    def default_charged_packages():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            PanelPackage = Pool().get("health.proc.insurance.panel.product.group")
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            package_lines = []
            if inpatient and inpatient.packages:
                for line in inpatient.packages:
                        list_price = line.product_group.get_list_price()
                        discount_percent = None
                        discount_amount = None
                        panel_price = None
                        net_price = list_price
                        discount_surplus_amount = None
                        if inpatient.panel:
                                panel_package_details = PanelPackage.search([('panel','=',inpatient.panel.id),('product_group','=',line.product_group.id)])
                                if(len(panel_package_details) > 0):
                                        found_panel_package = panel_package_details[0]
                                        discount_percent = found_panel_package.discount
                                        if(discount_percent):
                                                discount_amount = (Decimal(list_price) * Decimal(str(discount_percent))) / 100
                                        if(discount_percent):
                                                net_price = Decimal(list_price) - Decimal(discount_amount)
                                                discount_surplus_amount = discount_amount
                                        else:
                                                panel_price = found_panel_package.price                         
                                                net_price = panel_price
                                                discount_surplus_amount = Decimal(list_price) - Decimal(net_price)

                        charge_line = {'product_group': line.product_group.id, 'list_price':list_price, 
                                       'discount_percent':Decimal(discount_percent) if discount_percent else None, 
                                       'discount_amount':Decimal(discount_amount) if discount_amount else None,
                                       'panel_price': Decimal(panel_price) if panel_price else None, 
                                       'net_price': Decimal(net_price) if net_price else None, 
                                       'discount_surplus_amount':Decimal(discount_surplus_amount) if discount_surplus_amount else None
                                       }
                        package_lines.append(charge_line)

        return tuple(package_lines)

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

    @staticmethod
    def default_payment_mode():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                    return inpatient.payment_mode


    @staticmethod
    def default_insurance_company():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient and inpatient.panel:
                    return inpatient.panel.id
                    
    @staticmethod
    def default_inpatient_registration_code():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                return Transaction().context.get('active_id')

class ChargePackageWizard(Wizard):
    'Charge a Package'
    __name__ = 'health.proc.charge.package'

    start = StateView('health.proc.charge.package.start',
        'health_proc.health_proc_charge_package_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Charge Package(s)', 'request', 'tryton-ok', default=True),
            ])
    request = StateTransition()

    def transition_request(self):
        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
        IpdPackageChargeLine = Pool().get("health.proc.ipd.package.charge.line")
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        ProductTemplate = Pool().get('product.template')

        panel_patient = False
        gross_unit_price = 0
        unit_price = 0

        first = True
        cnt = 1
        sale_id = -1
        insurance_plan_id = None
        sale_type = ''

        # delete the ones removed now
        to_be_removed = []
        already_saved_lines =  IpdPackageChargeLine.search([('name', '=', self.start.inpatient_registration_code)]) 
        for line in already_saved_lines:
                deleted = True
                for values in self.start.charged_packages:
                        if values.product_group.id == line.product_group.id:
                              deleted = False
                              continue
                if deleted:
                      to_be_removed.append(line)

        # also remove the sale_lines
        inpatient = InpatientRegistration(self.start.inpatient_registration_code)

        for line in to_be_removed:
              sale_line = SaleLine.search([('sale', '=', inpatient.sale_id.id), ('product_group_id','=', line.product_group.id)])
              SaleLine.delete(sale_line)

        # now call delete to remove these lines
        IpdPackageChargeLine.delete(to_be_removed)

        for values in self.start.charged_packages:
                logging.warning(values)		
                found =  IpdPackageChargeLine.search([('name', '=', self.start.inpatient_registration_code),('product_group', '=', values.product_group.id)]) 
                if(len(found) >=1):
                      logging.info("============== Package is already charged   --------")
                      continue;
                
                if first:
                        pp = Patient(self.start.patient)
                        if self.start.inpatient_registration_code:
                                logging.warning("\ninpatient registration code is therere: ")
                                logging.warning(self.start.inpatient_registration_code)
                                inpatient = InpatientRegistration(self.start.inpatient_registration_code)
                                if inpatient.sale_id.state == 'draft':
                                        sale_id = inpatient.sale_id.id
                                else:
                                        raise ValidationError('The Sale for this inpatient record is closed now. Either create new inpatient record or charge in OPD!')

                                if inpatient.payment_mode == 'panel' and inpatient.insurance_plan:
                                        panel_patient = True
                                        insurance_plan_id = inpatient.insurance_plan.id
                                else:
                                        panel_patient = False

                                if inpatient.hospitalization_type == 'ER':
                                        sale_type = 'er'
                                else:
                                        sale_type = 'ipd'
                        
                        first = False


                theSale = Sale(sale_id)
                # find discount or surplus amount
                if False and panel_patient and insurance_plan_id: # it is a panel sale
                        if Sale.product_price_exists_in_plan(insurance_plan_id, reqProduct.id):
                                logging.info("The product exits in the insurance plan.............................................................................")
                                #with Transaction().set_context(price_list=theSale.price_list.id, customer=theSale.party.id):
                                #        sale_price = Product.get_sale_price([reqProduct],1)
                                sale_price = Sale.get_product_price_from_plan(insurance_plan_id, reqProduct.id)

                                gross_unit_price = sale_price #reqProduct.list_price # price in the Main List 
                                unit_price = sale_price #sale_price.get(reqProduct.id, None) # price in the price list
                                discount = 0

                                logging.info("+++++++++++++++++++++++++++++++++++++ final price received from panel price list: " + str(unit_price))
                        else: # product is not found in Panel Price list; return Main List Price
                                gross_unit_price = reqProduct.list_price
                                unit_price = reqProduct.list_price
                                logging.info("+++++++++++++++++< Price not found in Panel> so raising error and not using price from main price list: " + str(unit_price))
                                raise ValidationError("The price for this product is not set in the Insurance Plan. Contact IT Department");

                # save as an ipd package as well
                # logging.info("======== discoutt is : " + str(values.))
                ipdLines = IpdPackageChargeLine.create([{
                                        'name':self.start.inpatient_registration_code, 
                                        'product_group':values.product_group.id,
                                        'list_price':values.product_group.get_list_price(),
                                        'discount_percent':Decimal(values.discount_percent) if values.discount_percent else None, 
                                        'discount_amount':Decimal(values.discount_amount) if values.discount_amount else None,
                                        'panel_price': Decimal(values.panel_price) if values.panel_price else None, 
                                        'net_price': Decimal(values.net_price) if values.net_price else None, 
                                        'discount_surplus_amount':Decimal(values.discount_surplus_amount) if values.discount_surplus_amount else None
                                        }])

                for line in values.product_group.lines:
                        if line.product:
                                logging.info("============ Product is: " + line.product.name)
                                reqProduct = line.product
                                reqProdTemplate = ProductTemplate(reqProduct.template)
                                saleLines = SaleLine.create([{
                                        'product':reqProduct.id, 
                                        'sale':sale_id,
                                        'unit':reqProdTemplate.default_uom,
                                        'unit_price':reqProduct.list_price,
                                        'gross_unit_price': reqProduct.list_price,
                                        'quantity':1,
                                        'sequence':cnt,
                                        'description':reqProduct.name,
                                        'product_group_id': values.product_group.id
                                        }])
                                cnt = cnt + 1
                self.start.sale_id = sale_id


                #logging.warning("\n----------------- the request id is: " + str())
                logging.warning("\n ,patient id is: " + str(pp.id)) 

                logging.warning("\n , the product is: " + str(reqProduct.id))

        logging.warning('>>>>>>>>>>>>> Sale type is: ' + sale_type)

        # finally remove alread calculated shares
        IpdPackageChargeLine = Pool().get("health.proc.ipd.doctor.share")
        to_be_removed = []
        already_saved_lines =  IpdPackageChargeLine.search([('name', '=', self.start.inpatient_registration_code)]) 
        for line in already_saved_lines:
                deleted = True
                #for values in self.start.charged_services:
                #        if values.product_group.id == line.product_group.id:
                #              deleted = False
                #              continue
                if deleted:
                      to_be_removed.append(line)


        # now call delete to remove these lines
        IpdPackageChargeLine.delete(to_be_removed)

        
        return 'end'        

class DoctorShare(ModelView):
    'General IPD Doctor Share'
    __name__ = 'health.proc.general.doctor.share'

    desc = fields.Char('Description', required=False)
    product_group = fields.Many2One('health.proc.product.group', 'Package', domain=[('group_type', '=', 'package')])
    product = fields.Many2One('product.product', 'Service')
    list_price = fields.Numeric('Service Cash Price', states ={'readonly':True})

    doctor_one = fields.Many2One('gnuhealth.healthprofessional','Doctor-One', required=False)
    doctor_one_share = fields.Numeric('Doctor-One-Share', states ={'readonly':False})

    doctor_two = fields.Many2One('gnuhealth.healthprofessional','Doctor-Two', required=False)
    doctor_two_share = fields.Numeric('Doctor-two-Share', states ={'readonly':False})
    sale_line_id = fields.Integer("Sale Line", readonly=True)

    def get_rec_name(self, name):
        if self.product:
                return self.product.rec_name 
        
    @fields.depends('doctor_one','doctor_one_share', 'doctor_two', 'doctor_two_share', 'product', 'sale_line_id','product_group')
    def on_change_doctor_one(self):
        if self.doctor_one:
                if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                        if self.product and not self.doctor_one_share:
                                if self.doctor_one.eligible_for_doctor_share:
                                        self.doctor_one_share = self.product.list_price
                                else:
                                       self.doctor_one_share = 0
                               
    @fields.depends('doctor_one','doctor_one_share', 'doctor_two', 'doctor_two_share', 'product', 'sale_line_id', 'product_group')
    def on_change_doctor_two(self):
        if self.doctor_two:
                if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                        HealthProfessional = Pool().get("gnuhealth.healthprofessional")

                        if self.product and not self.doctor_two_share:
                                if self.doctor_two.eligible_for_doctor_share:
                                      self.doctor_one_share = self.product.list_price / 2
                                      self.doctor_two_share = self.product.list_price / 2
                                else:
                                       self.doctor_one_share = self.product.list_price / 2
                                       self.doctor_two_share = 0
                               
                #discount_amount = (Decimal(list_price) * Decimal(str(discount_percent))) / 100

class CalculateDoctorShareStart(ModelView):
    'Calculate Doctor Share Start'
    __name__ = 'health.proc.calculate.doctor.share.start'

    date = fields.DateTime('Date')
    patient = fields.Many2One('gnuhealth.patient', 'Patient', required=True, states ={'readonly':True})
    nature = fields.Char('OPD/IPD/ER/DayCare?', states={'readonly':True})
    inpatient_registration_code =  fields.Integer('IPD No.', states ={'readonly':True}) 
    department = fields.Char('Department', states={'readonly':True})
    amount = fields.Numeric('Amount', help='Amount charged against packages', required=False)
    description = fields.Char('Description', required=True)
    payment_mode = fields.Selection([
        (None, ''),
        ('cash', 'Cash'),
        ('panel_cash', 'Panel (Cash)'),
        ('panel_credit', 'Panel (Credit)'),
        ], 'Payment Mode', states= {'readonly':True}
        )    
    insurance_company = fields.Many2One(
        'health.proc.insurance.panel', 'Panel',
        required=False, select=True,
        states= {'readonly':True})
    charged_services = fields.One2Many('health.proc.general.doctor.share', None, 'Service-wise Shares')
    sale_id = fields.Integer('Sale ID')    

    @staticmethod
    def default_charged_services():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            PanelPackage = Pool().get("health.proc.insurance.panel.product.group")
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            SaleLine = Pool().get("sale.line")

            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            package_lines = []
            if inpatient and inpatient.doctor_shares:
                for share in inpatient.doctor_shares:
                        service_line = {'product_group':share.product_group.id if share.product_group else None, 
                                        'product': share.product.id, 'list_price': share.product.list_price,
                                        'doctor_one': share.doctor_one.id if share.doctor_one else None, 
                                        'doctor_one_share': share.doctor_one_share if share.doctor_one_share else None,
                                        'doctor_two': share.doctor_two.id if share.doctor_two else None, 
                                        'doctor_two_share': share.doctor_two_share if share.doctor_two_share else None,
                                        'sale_line_id': share.sale_line_id
                                        }
                        package_lines.append(service_line)                

            # following code was written earlier which was adding those services which belonged to packages and whose share was not yet created
            # the logic was to come from selected package and not the current IPD sale; this is now changed using the next paragraph SALE_LINE based logic
            #if inpatient and inpatient.packages:
            #    for package in inpatient.packages:
            #            for line in package.product_group.lines:
            #                    logging.error(line)

                                # first confirm that the share for the current service is not already set
            #                    found = False
            #                    for added_line in package_lines:
            #                            if added_line['product_group'] == package.product_group.id and added_line['product'] == line.product.id:
            #                                  found = True
            #                    if not found:
            #                            service_line = {'product_group':package.product_group.id, 'product': line.product.id, 'list_price': line.product.list_price}
            #                            package_lines.append(service_line)

            #### adding those packaged-services whose share is not yet saved
            sale_lines = SaleLine.search([('sale', '=', inpatient.sale_id.id)])
            for line in sale_lines:
                   if line.product_group_id:
                        # first confirm that the share for the current service is not already set
                                found = False
                                for added_line in package_lines:
                                        if added_line['product_group'] == line.product_group_id and added_line['product'] == line.product.id:
                                              found = True
                                if not found:
                                        service_line = {'product_group':line.product_group_id, 'product': line.product.id, 'list_price': line.product.list_price, 'sale_line_id': line.id}
                                        package_lines.append(service_line)

            # add all non-package sale lines
            sale_lines = SaleLine.search([('sale', '=', inpatient.sale_id.id)])
            for line in sale_lines:
                   if not line.product_group_id:
                        # first confirm that the share for the current service is not already set
                                found = False
                                for added_line in package_lines:
                                        if added_line.get('sale_line_id',None) and added_line['sale_line_id'] == line.id:
                                              found = True
                                if not found:
                                        service_line = {'product_group':None, 'product': line.product.id, 'list_price': line.product.list_price, 'sale_line_id': line.id}
                                        package_lines.append(service_line)
            return tuple(package_lines)

                

        

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

    @staticmethod
    def default_payment_mode():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient:
                    return inpatient.payment_mode


    @staticmethod
    def default_insurance_company():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
            InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
            inpatient = InpatientRegistration(Transaction().context.get('active_id'))
            if inpatient and inpatient.panel:
                    return inpatient.panel.id
                    
    @staticmethod
    def default_inpatient_registration_code():
        if Transaction().context.get('active_model') == 'gnuhealth.inpatient.registration':
                return Transaction().context.get('active_id')


class CalculateDoctorShareWizard(Wizard):
    'Calculate Doctor Package'
    __name__ = 'health.proc.calculate.doctor.share'

    start = StateView('health.proc.calculate.doctor.share.start',
        'health_proc.health_proc_calculate_doctor_share_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Save Doctor Share(s)', 'request', 'tryton-ok', default=True),
            ])
    request = StateTransition()

    def transition_request(self):
        InpatientRegistration = Pool().get('gnuhealth.inpatient.registration')
        Patient = Pool().get('gnuhealth.patient')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')
        Product = Pool().get('product.product')
        ProductTemplate = Pool().get('product.template')

        panel_patient = False
        gross_unit_price = 0
        unit_price = 0

        first = True
        cnt = 1
        sale_id = -1
        insurance_plan_id = None
        sale_type = ''

        # delete the ones removed now
        IpdPackageChargeLine = Pool().get("health.proc.ipd.doctor.share")
        to_be_removed = []
        already_saved_lines =  IpdPackageChargeLine.search([('name', '=', self.start.inpatient_registration_code)]) 
        for line in already_saved_lines:
                deleted = True
                #for values in self.start.charged_services:
                #        if values.product_group.id == line.product_group.id:
                #              deleted = False
                #              continue
                if deleted:
                      to_be_removed.append(line)


        # now call delete to remove these lines
        IpdPackageChargeLine.delete(to_be_removed)

        for values in self.start.charged_services:
                logging.warning(values)		
                #found =  IpdPackageChargeLine.search([('name', '=', self.start.inpatient_registration_code),('product_group', '=', values.product_group.id)]) 
                #if(len(found) >=1):
                #      logging.info("============== Package is already charged   --------")
                #      continue;
                
                if first:
                        pp = Patient(self.start.patient)
                        if self.start.inpatient_registration_code:
                                logging.warning("\ninpatient registration code is therere: ")
                                logging.warning(self.start.inpatient_registration_code)
                                inpatient = InpatientRegistration(self.start.inpatient_registration_code)
                                if inpatient.state == 'done':
                                        sale_id = inpatient.sale_id.id
                                else:
                                        raise ValidationError('The Sale and Doctor Shares for this inpatient record are closed now. Please contact I.T Support.')

                                if inpatient.payment_mode == 'panel' and inpatient.insurance_plan:
                                        panel_patient = True
                                        insurance_plan_id = inpatient.insurance_plan.id
                                else:
                                        panel_patient = False

                                if inpatient.hospitalization_type == 'ER':
                                        sale_type = 'er'
                                else:
                                        sale_type = 'ipd'
                        
                        first = False


                theSale = Sale(sale_id)
                # find discount or surplus amount
                if False and panel_patient and insurance_plan_id: # it is a panel sale
                        if Sale.product_price_exists_in_plan(insurance_plan_id, reqProduct.id):
                                logging.info("The product exits in the insurance plan.............................................................................")
                                #with Transaction().set_context(price_list=theSale.price_list.id, customer=theSale.party.id):
                                #        sale_price = Product.get_sale_price([reqProduct],1)
                                sale_price = Sale.get_product_price_from_plan(insurance_plan_id, reqProduct.id)

                                gross_unit_price = sale_price #reqProduct.list_price # price in the Main List 
                                unit_price = sale_price #sale_price.get(reqProduct.id, None) # price in the price list
                                discount = 0

                                logging.info("+++++++++++++++++++++++++++++++++++++ final price received from panel price list: " + str(unit_price))
                        else: # product is not found in Panel Price list; return Main List Price
                                gross_unit_price = reqProduct.list_price
                                unit_price = reqProduct.list_price
                                logging.info("+++++++++++++++++< Price not found in Panel> so raising error and not using price from main price list: " + str(unit_price))
                                raise ValidationError("The price for this product is not set in the Insurance Plan. Contact IT Department");

                # save as an ipd package as well
                # logging.info("======== discoutt is : " + str(values.))
                if(values.doctor_one or values.doctor_two):
                        ipdLines = IpdPackageChargeLine.create([{
                                                'name':self.start.inpatient_registration_code, 
                                                'product_group':values.product_group.id if values.product_group else None,
                                                'product': values.product.id,
                                                'list_price':values.list_price,
                                                'doctor_one':values.doctor_one.id if values.doctor_one else None, 
                                                'doctor_one_share':Decimal(values.doctor_one_share) if values.doctor_one_share else None,
                                                'doctor_two':values.doctor_two.id if values.doctor_two else None, 
                                                'doctor_two_share':Decimal(values.doctor_two_share) if values.doctor_two_share else None,
                                                'sale_line_id': values.sale_line_id,

                                                }])

                self.start.sale_id = sale_id


                #logging.warning("\n----------------- the request id is: " + str())
                logging.warning("\n ,patient id is: " + str(pp.id)) 
        
        return 'end'   
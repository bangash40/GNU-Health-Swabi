# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from datetime import datetime, time, timedelta, tzinfo
import operator
from itertools import  groupby
from functools import wraps

from sql import Column, Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case

from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    StateReport, Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend
import logging
from sql.aggregate import Max, Count, Sum
from sql import Literal, Join
from trytond.rpc import RPC
import logging
from trytond.modules.company import CompanyReport
import pytz
from trytond.exceptions import UserWarning
import logging

__all__ = ['IDHRegistrationReceiptReport','LimsLabReportReport','LabRequestLabelsCode39','ServicesSummaryReportCategoryWise',
           'ServicesSummaryReportCategoryWiseStart', 'WizardServicesSummaryReportCategoryWise','PatientAdmissionOrderReport',
           'PatientSummaryBillReport','PatientDischargeCertificateReport','PrescriptionSlipReport', 'DoctorShareDetailsReport',
           'DoctorShareDetailsReportStart','WizardDoctorShareDetails', 'DoctorShareSummaryReport',
           'DoctorShareSummaryReportStart','WizardDoctorShareSummary','PanelBillReport','OpdStatsReport', 'OpdStatsReportStart', 
           'WizardOpdStats', 'PhlebotomyAccessionSheetReport','StockInventoryReportStart','WizardStockInventoryReport','StockInventoryDetailsReport',
           'DoctorServicesDetailsReportStart','WizardDoctorServicesDetails','DoctorServicesDetailsReport',
           'StockNearExpiryReportStart','WizardStockNearExpiryReport','StockNearExpiryReport','StockExpiredReportStart','WizardStockExpiredReport','StockExpiredReport',
           'OpdStatsDetailedReport', 'WizardOpdStatsDetailed','VisitOpdPatient','WizardPatientVisitOpdReport','VisitOpdPatientDetailsReport',
           'SurgeryRecommendedOpdPatient','WizardSurgeryRecommendedOpdReport','SurgeryRecommendedOpdDetailsReport',
           'StockInternalShipmentReportStart','WizardStockInternalShipmentReport','StockInternalShipmentReport',
           'CriticalAnalytesReportStart','WizardCriticalAnalytesReport','CriticalAnalytesReport',
           'PurchaseReportStart','WizardPurchaseReport','PurchaseReport', 'OPDTurnoverReportStart','WizardOPDTurnoverReport','OPDTurnoverReport']

class IDHRegistrationReceiptReport(Report):
	__name__ = 'health_proc.idh_registration_receipt_report'
	
class LimsLabReportReport(Report):
    __name__ = 'anth.proc.lims.lab.report'   

    @classmethod
    def get_context(cls, records, header, data):
        report_context = super(LimsLabReportReport, cls).get_context(records, header, data)
        for r in records:
                logging.info(r)
                if(r.state not in ['done', 'verified']):
                        raise UserWarning("Report Not Ready!","The Report is not published yet")

                sale_type = 'OPD'
                report_context['include_header'] = 'yes'
                report_context['objects'] = records

                if data.get('include_header'):
                        report_context['include_header'] = data.get('include_header')

                report_context['sale_type'] = sale_type
                x = r.get_old_results()

        return report_context      

class LabRequestLabelsCode39(Report):
    __name__ = 'labtest.barcode39'   

    @classmethod
    def get_context(cls, records, header, data):
        from_lab_request = False
        if(data['model'] == 'gnuhealth.patient.lab.test'):
              from_lab_request = True
                
        report_context = super(LabRequestLabelsCode39, cls).get_context(records, header, data)
        if Transaction().context.get('active_model') == 'gnuhealth.patient.lab.test':
               logging.error("active model is lab test request")
        new_records = []
        LabResult = Pool().get("gnuhealth.lab")
        for r in records:
                found_lab = LabResult.search([
			        ('request_order', '=', r.request)])
                if(len(found_lab) == 1):
                        new_records.append(found_lab[0])

        if from_lab_request:
                report_context['records'] = new_records

        return report_context
    
class ServicesSummaryReportCategoryWise(Report):
    __name__ = 'akhf.services.summary.report'   

    @classmethod
    def get_context(cls, records, header, data):
        if data['datefrom']:
                datefrom = data['datefrom']
        else:
                datefrom = datetime.now()

        if data['dateto']:
                dateto = data['dateto']
        else:
                dateto = datetime.now()

        logging.info(data)
        query = "select account,(select name from account_account aa2 where aa2.id=account), parent_ac ,(select name from account_account aa2 where aa2.id=parent_ac), is_asset, is_revenue  , sum(db), sum(cr) from( " \
        " select asl.id, aml.account account, aml.debit db , aml.credit cr, aa.parent parent_ac, aat.assets is_asset, aat.revenue is_revenue from account_statement_line asl  " \
        " inner join account_statement as2  on asl.statement = as2.id   " \
        " inner join account_move_line aml on aml.move = asl.move " \
        " inner join account_account aa on aa.id = aml.account " \
        " inner join account_account_type aat on aat.id  = aa.type " \
        " where as2.write_date between %s and %s and as2.state = 'posted'" \
        " union  " \
        " select asl.id, aml.account account, aml.debit db , aml.credit cr, aa.parent parent_ac, aat.assets is_asset, aat.revenue is_revenue from account_statement_line asl " \
        " inner join account_statement as2  on asl.statement = as2.id  " \
        " inner join account_invoice ai on ai.id = asl.invoice " \
        " inner join account_move_line aml on aml.move = ai.move " \
        " inner join account_account aa on aa.id = aml.account " \
        " inner join account_account_type aat on aat.id  = aa.type" \
        " where as2.write_date between %s and %s and as2.state = 'posted' " \
        ") kk group by account , parent_ac , is_asset, is_revenue " \

        data = []
        cursor = Transaction().connection.cursor()
        cursor.execute(query,(datefrom, dateto, datefrom, dateto))
        all_recs = cursor.fetchall()
        parents = {}
        children = {}
        total_debit = 0
        total_credit = 0
        for rec in all_recs:
               #(10, 'opd revenue', 6, 'Main Revenue', False, True, Decimal('0'), Decimal('500.00'))
               logging.error(rec)
               key = str(rec[2]) + rec[3]
               found_parent = parents.get(key, None)
               if(found_parent):
                     db = found_parent[3]+rec[6]
                     cr = found_parent[4]+rec[7]
                     
                     if rec[4]:
                        db_net = db-cr
                     else:
                           db_net = None
                     
                     if(rec[5]):
                        cr_net = cr-db
                     else:
                           cr_net = None
                     parents[key] = (rec[3], rec[4], rec[5], db, cr, db_net, cr_net)
               else:
                     db = rec[6]
                     cr = rec[7]

                     if rec[4]:
                        db_net = db-cr
                     else:
                           db_net = None
                     if(rec[5]):
                        cr_net = cr-db
                     else:
                           cr_net = None
                     parents[key] = (rec[3], rec[4], rec[5], db, cr, db_net, cr_net )

                
               #data.append({'account': rec[0]})
      
        for rec in all_recs:
                logging.error(rec)
                # find a parent record
                key = str(rec[2]) + rec[3]
                found_parent = children.get(key, None)
                #logging.error("=================== found parent is: " + str(found_parent))
                db = rec[6]
                cr = rec[7]

                if rec[4]:
                        db_net = db-cr
                else:
                        db_net = None
                
                if(rec[5]):
                        cr_net = cr-db
                else:
                        cr_net = None

                final_rec = (rec[0], rec[1], rec[2], rec[3], rec[4], rec[5], db, cr, db_net, cr_net)
                # if parent is found, add child to its children, otherwise create an empty array and add it
                if(found_parent):
                        #logging.error("=============== parent is found: " + str(rec[2]))
                        found_parent.append(final_rec)
                else:
                        #logging.error("!!!!!!!!!!!!!!!!!!!!!! parent is not found " + str(rec[2]))
                        children[key] = [final_rec]

                found_parent = None
                logging.error(children)
                #logging.error("\n\n")
        
        #for p in parents:
        logging.error("============ dispayig parent") 
        logging.error(parents)


        logging.error("======================================================================")
        logging.error("============ dispayig children") 
        logging.error(children)

        # finding totals of debit and credit for parents
        for key in parents:
                if parents[key][5]:
                    total_debit += parents[key][5]

                if parents[key][6]:
                    total_credit += parents[key][6]
                
        report_context = super(ServicesSummaryReportCategoryWise, cls).get_context(records, header, data)
        report_context['data'] = data
        report_context['parents'] = parents
        report_context['children'] = children
        report_context['total_debit'] = total_debit
        report_context['total_credit'] = total_credit
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto

        return report_context

class ServicesSummaryReportCategoryWiseStart(ModelView):
    'Services Summary Report'
    __name__ = 'akhf.services.summary.report.start'
    
    datefrom = fields.DateTime('From Date', required=True)
    dateto = fields.DateTime('To Date', required=True)
    
    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        #return datetime.combine(datetime.today(), time(0,0,0))
        return  datetime.now().replace(hour=0, minute=0, second=0)
	
    @staticmethod
    def default_dateto():
        #return datetime.now()
        return datetime.now().replace(hour=18, minute=59, second=59)

class WizardServicesSummaryReportCategoryWise(Wizard):
    'Services Summary Report Wizard'
    __name__ = 'akhf.services.summary.wizard'
    start = StateView('akhf.services.summary.report.start',
        'health_proc.services_summary_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('akhf.services.summary.report')

    def do_print_(self, action):        
        data = {
            'company': self.start.company.id,
            #'datefrom': datetime.combine(self.start.datefrom, time(0,0,0)),
	    #'dateto': datetime.combine(self.start.dateto, time(23,59,59)),
            'datefrom': self.start.datefrom,
	    'dateto': self.start.dateto,
            }

        return action, data

    def transition_print_(self):
        return 'end'

class PatientAdmissionOrderReport(Report):
    __name__ = 'health.proc.patient.admission.order.report'

class PatientSummaryBillReport(Report):
    __name__ = 'health.proc.patient.summary.bill.report'    

class PatientDischargeCertificateReport(Report):
    __name__ = 'health.proc.patient.discharge.certificate.report'       

class PrescriptionSlipReport(Report):
    __name__ = 'health.proc.prescription.slip.report'  

class DoctorShareDetailsReport(Report):
    __name__ = 'health.proc.doctor.share.details.report'   

    @classmethod
    def get_context(cls, records, header, data):
        if data['datefrom']:
                datefrom = data['datefrom']
        else:
                datefrom = datetime.now()

        if data['dateto']:
                dateto = data['dateto']
        else:
                dateto = datetime.now()    
        
        commission_agent = data['commission_agent']
        CommissionAgent = Pool().get("commission.agent")
        doctor = CommissionAgent(commission_agent)

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)
        query = "select party_party.ref, party_party.name, party_party.family_relation, party_party.family_relation_person, product_template.name, inv.create_date, commission.agent, amount, inv.party from commission " \
                "inner join account_invoice_line inv_line on 'account.invoice.line,' || inv_line.id = commission.origin " \
                "inner join product_product on product_product.id =  inv_line.product " \
                "inner join product_template on product_template.id = product_product.template " \
                "inner join account_invoice inv on inv.id = inv_line.invoice "\
                "inner join party_party on party_party.id = inv.party " \
                " where commission.create_date between %s and %s and commission.agent = %s " \
        

        data = []
        cursor = Transaction().connection.cursor()
        cursor.execute(query,(datefrom, dateto, commission_agent))
        all_recs = cursor.fetchall()

        total_earned = 0
        total_returned = 0
        net_share = 0
        commission_lines  = []
        commission_lines_return = []
        for rec in all_recs:
                line = {'mrno':rec[0], 'patient_name': rec[1], 'family_relation': rec[2], 'family_relation_person': rec[3], 'service': rec[4], 'inv_date': rec[5], 'amount': rec[7] }
                if rec[7] >= 0:
                        commission_lines.append(line)
                        total_earned = total_earned + rec[7]
                else:
                        commission_lines_return.append(line)
                        total_returned = total_returned + rec[7]
                net_share = net_share + rec[7]                        

        report_context = super(DoctorShareDetailsReport, cls).get_context(records, header, data)
        report_context['data'] = data
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto
        report_context['commission_lines'] = commission_lines
        report_context['commission_lines_return'] = commission_lines_return        
        report_context['doctor_name'] = doctor.party.rec_name
        report_context['total_earned'] = total_earned
        report_context['total_returned'] = total_returned
        report_context['net_share'] = net_share                

        return report_context                

class DoctorShareDetailsReportStart(ModelView):
    'Doctor Share Details'
    __name__ = 'health.proc.doctor.share.details.start'
    
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)
    commission_agent = fields.Many2One('commission.agent', 'Doctor', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        return datetime.now()
       
    @staticmethod
    def default_dateto():
        return datetime.now()

class WizardDoctorShareDetails(Wizard):
    'Doctor Share Details Report Wizard'
    __name__ = 'health.proc.doctor.share.details.wizard'
    start = StateView('health.proc.doctor.share.details.start',
        'health_proc.doctor_share_details_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('health.proc.doctor.share.details.report')

    def do_print_(self, action):        
        data = {
            'company': self.start.company.id,
            'datefrom': datetime.combine(self.start.datefrom, time(0,0,0)),
	    'dateto': datetime.combine(self.start.dateto, time(23,59,59)),          
            'commission_agent': self.start.commission_agent.id,
            }

        return action, data

    def transition_print_(self):
        return 'end'    


class DoctorShareSummaryReport(Report):
    __name__ = 'health.proc.doctor.share.summary.report'   

    @classmethod
    def get_context(cls, records, header, data):
        if data['datefrom']:
                datefrom = data['datefrom']
        else:
                datefrom = datetime.now()

        if data['dateto']:
                dateto = data['dateto']
        else:
                dateto = datetime.now()    
        
        #commission_agent = data['commission_agent']
        CommissionAgent = Pool().get("commission.agent")
        doctor = None #CommissionAgent(commission_agent)

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)
        all_shares = []
        for doctor_id in data['doctors']:
                query = "select  commission.agent, sale_sale.sale_type, product_template.name, sum(amount/abs(amount)) , sum(amount) from commission " \
                        "inner join account_invoice_line inv_line on 'account.invoice.line,' || inv_line.id = commission.origin " \
                        "inner join product_product on product_product.id =  inv_line.product " \
                        "inner join product_template on product_template.id = product_product.template " \
                        "inner join account_invoice inv on inv.id = inv_line.invoice "\
                        "inner join party_party on party_party.id = inv.party " \
                        "inner join sale_line on 'sale.line,' || sale_line.id = inv_line.origin " \
                        "inner join sale_sale on sale_sale.id = sale_line.sale " \
                        " where commission.create_date between %s and %s and commission.agent = %s " \
                        " group by product_template.name, sale_sale.sale_type, commission.agent "
                

                cursor = Transaction().connection.cursor()
                cursor.execute(query,(datefrom, dateto, doctor_id))
                all_recs = cursor.fetchall()

                total_earned_opd = 0
                total_earned_ipd = 0
                net_share = 0
                commission_lines_opd  = []
                commission_lines_ipd = []
                for rec in all_recs:
                        line = {'doctor':rec[0], 'type': rec[1], 'service': rec[2], 'count': round(rec[3],0), 'amount': round(rec[4],2) }
                        logging.info(line )
                        if rec[1] == 'opd' or rec[1] == 'er':
                                commission_lines_opd.append(line)
                                total_earned_opd = total_earned_opd + rec[4]
                        if rec[1] == 'ipd':
                                commission_lines_ipd.append(line)
                                total_earned_ipd = total_earned_ipd + rec[4]
                        net_share = net_share + rec[4]          


                doctor = CommissionAgent(doctor_id)

                one_doctor_date = {'doctor_name': doctor.party.rec_name, 'commission_lines_opd': commission_lines_opd, 'commission_lines_ipd': 
                                commission_lines_ipd, 'total_earned_opd': total_earned_opd, 'total_earned_ipd': total_earned_ipd, 'net_share': net_share}
                
                all_shares.append(one_doctor_date)

        report_context = super(DoctorShareSummaryReport, cls).get_context(records, header, data)
        report_context['data'] = all_shares
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto
        report_context['commission_lines_opd'] = commission_lines_opd
        report_context['commission_lines_ipd'] = commission_lines_ipd        
        report_context['doctor_name'] = doctor.party.rec_name
        report_context['total_earned_opd'] = round(total_earned_opd,2)
        report_context['total_earned_ipd'] = round(total_earned_ipd,2)
        report_context['net_share'] = round(net_share,2)

        

        report_context['objects'] = records
          

        return report_context                

class DoctorShareSummaryReportStart(ModelView):
    'Doctor Share Summary Reprot'
    __name__ = 'health.proc.doctor.share.summary.start'
    
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)
    #commission_agent = fields.Many2One('commission.agent', 'Doctor', required=True, select=True)
    doctors = fields.MultiSelection('get_all_doctors', "Doctor (s)", sort=True, select=True)

    @classmethod
    def get_all_doctors(cls):
        pool = Pool()
        Agent = pool.get('commission.agent')
        options = []
        #options.append((-1, 'All Doctors'))
        all_agents = Agent.search([])
        for agent in all_agents:
              options.append((agent.id, agent.party.name))
        #options = [('first_option','First Option'),('second_option','Second Option')]

        return options

    
    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        return datetime.now()
       
    @staticmethod
    def default_dateto():
        return datetime.now()

class WizardDoctorShareSummary(Wizard):
    'Doctor Share Summary Report Wizard'
    __name__ = 'health.proc.doctor.share.summary.wizard'
    start = StateView('health.proc.doctor.share.summary.start',
        'health_proc.doctor_share_summary_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('health.proc.doctor.share.summary.report')

    def do_print_(self, action):        
        data = {
            'company': self.start.company.id,
            'datefrom': datetime.combine(self.start.datefrom, time(0,0,0)),
	    'dateto': datetime.combine(self.start.dateto, time(23,59,59)),          
            #'commission_agent': self.start.commission_agent.id,
            'doctors': self.start.doctors,
            }

        return action, data

    def transition_print_(self):
        return 'start'            
    
class PanelBillReport(Report):
    __name__ = 'health.proc.insurance.panel.bill.report'   

    @classmethod
    def get_context(cls, records, header, data):
        logging.info("============ generating panel bill")
        data = []
        total_bill = 0
        for r in records:
              for line in r.statement_lines:
                  total_bill = total_bill + line.sale.total_amount  

        report_context = super(PanelBillReport, cls).get_context(records, header, data)
        report_context['data'] = data

        report_context['records'] = records
        report_context['total_bill'] = total_bill
                   

        return report_context                

class OpdStatsReportStart(ModelView):
    'OPD Stats Report'
    __name__ = 'health.proc.opd.stats.report.start'
    
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)

    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        return datetime.now()
       
    @staticmethod
    def default_dateto():
        return datetime.now()

class WizardOpdStats(Wizard):
    'OPD Stats Wizard'
    __name__ = 'health.proc.opd.stats.report.wizard'
    start = StateView('health.proc.opd.stats.report.start',
        'health_proc.opd_stats_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('health.proc.opd_stats.report')

    def do_print_(self, action):        
        logging.error("============ do printis called for opd stats")
        data = {
            'company': self.start.company.id,
            'datefrom': datetime.combine(self.start.datefrom, time(0,0,0)),
	    'dateto': datetime.combine(self.start.dateto, time(23,59,59)),          
            }

        return action, data
    
class OpdStatsReport(Report):
    'OPD Stats Report'
    __name__ = 'health.proc.opd_stats.report'

    @classmethod
    def get_context(cls, records, header, data):
        if data['datefrom']:
                datefrom = data['datefrom']
        else:
                datefrom = datetime.now()

        if data['dateto']:
                dateto = data['dateto']
        else:
                dateto = datetime.now()    
        

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)
        query = "select  commission.agent, sale_sale.sale_type, product_template.name, sum(amount/abs(amount)) , sum(amount) from commission " \
                "inner join account_invoice_line inv_line on 'account.invoice.line,' || inv_line.id = commission.origin " \
                "inner join product_product on product_product.id =  inv_line.product " \
                "inner join product_template on product_template.id = product_product.template " \
                "inner join account_invoice inv on inv.id = inv_line.invoice "\
                "inner join party_party on party_party.id = inv.party " \
                "inner join sale_line on 'sale.line,' || sale_line.id = inv_line.origin " \
                "inner join sale_sale on sale_sale.id = sale_line.sale " \
                " where commission.create_date between %s and %s " \
                " group by product_template.name, sale_sale.sale_type, commission.agent "
        query = "select account_category, to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale " \
                " inner join sale_line where sale_line.sale = sale.id " \
                " inner join product_product on product_product.id = sale_line.product " \
                " inner join product_template on product_template.id = product_prodcut.template " \
                " where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'opd' and sale_nature='imaging' group by account_category, date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"
        query = "select  to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'opd' and sale_nature='imaging' group by date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"


        data = []
        cursor = Transaction().connection.cursor()
        cursor.execute(query,(datefrom, dateto))
        all_recs = cursor.fetchall()

        stats = {}
        total_earned_opd = 0
        total_earned_ipd = 0
        net_share = 0
        commission_lines_opd  = []
        commission_lines_ipd = []
        for rec in all_recs:
                net_share = net_share + rec[3]
                dimension = rec[0]                        
                data = stats.get(dimension, None)
                if data: 
                      stats[dimension] = {'imaging': rec[3], 'lab':0, 'opd':0, 'er':0, 'total': rec[3]}
                else:
                      stats[dimension] = {'imaging': rec[3], 'lab':0, 'opd':0, 'er':0, 'total':rec[3]}

        # labs
        query = "select  to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'opd' and sale_nature='lab' group by date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"
        

        
        cursor.execute(query,(datefrom, dateto))
        all_recs = cursor.fetchall()  
        for rec in all_recs:
                net_share = net_share + rec[3]
                dimension = rec[0]                        
                data = stats.get(dimension, None)
                if data: 
                      total = data['imaging'] + rec[3]
                      stats[dimension] = {'imaging': data['imaging'], 'lab':rec[3], 'opd':0, 'er':0, 'total':total}
                else:
                      stats[dimension] = {'imaging': 0, 'lab':rec[3], 'opd':0, 'er':0, 'total': rec[3]}

        # opd
        query = "select  to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'opd' and sale_nature is null group by date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"
        
        cursor.execute(query,(datefrom, dateto))
        all_recs = cursor.fetchall()
        for rec in all_recs:
                net_share = net_share + rec[3]
                dimension = rec[0]                        
                data = stats.get(dimension, None)
                if data: 
                      total = data['imaging'] + data['lab'] + rec[3]                      
                      stats[dimension] = {'imaging': data['imaging'], 'lab':data['lab'], 'opd':rec[3], 'er':0, 'total':total}
                else:
                      stats[dimension] = {'imaging': 0, 'lab':0, 'opd':rec[3], 'er':0, 'total': rec[3]}

        # er
        query = "select  to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'er' group by date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"
        
        cursor.execute(query,(datefrom, dateto))
        all_recs = cursor.fetchall()
        for rec in all_recs:
                net_share = net_share + rec[3]
                dimension = rec[0]                        
                data = stats.get(dimension, None)
                if data: 
                      total = data['imaging'] + data['lab'] + data['opd'] + rec[3]                      
                      stats[dimension] = {'imaging': data['imaging'], 'lab':data['lab'], 'opd':data['opd'], 'er':rec[3], 'total':total}
                else:
                      stats[dimension] = {'imaging': 0, 'lab':0, 'opd':0, 'er':rec[3], 'total': rec[3]}

        logging.error(str(stats))                      

        report_context = super(OpdStatsReport, cls).get_context(records, header, data)

        report_context['data'] = data
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto
        report_context['commission_lines_opd'] = commission_lines_opd
        report_context['commission_lines_ipd'] = commission_lines_ipd        
        report_context['total_earned_opd'] = round(total_earned_opd,2)
        report_context['total_earned_ipd'] = round(total_earned_ipd,2)
        report_context['doctor_name'] = 'OPD Stats'
        report_context['net_share'] = round(net_share,2)
        report_context['stats'] = stats
        report_context['objects'] = records
          
        return report_context                    

class OpdStatsDetailedReportStart(ModelView):
    'OPD Stats Detailed Report'
    __name__ = 'health.proc.opd.stats.detailed.report.start'
    
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)

    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        return datetime.now()
       
    @staticmethod
    def default_dateto():
        return datetime.now()

class WizardOpdStatsDetailed(Wizard):
    'OPD Stats Detailed Wizard'
    __name__ = 'health.proc.opd.stats.detailed.report.wizard'
    start = StateView('health.proc.opd.stats.report.start',
        'health_proc.opd_stats_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('health.proc.opd_stats_detailed_final.report')

    def do_print_(self, action):        
        logging.error("============ do printis called for opd stats")
        data = {
            'company': self.start.company.id,
            'datefrom': datetime.combine(self.start.datefrom, time(0,0,0)),
	        'dateto': datetime.combine(self.start.dateto, time(23,59,59)),          
            }

        return action, data
    
class OpdStatsDetailedReport(Report):
    'OPD Stats Detailed Report'
    __name__ = 'health.proc.opd_stats_detailed.report'

    @classmethod
    def get_context(cls, records, header, data):
        if data['datefrom']:
                datefrom = data['datefrom']
        else:
                datefrom = datetime.now()

        if data['dateto']:
                dateto = data['dateto']
        else:
                dateto = datetime.now()    
        

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)
        
        query = "select account_category, to_char(date_TRUNC('month', sale_sale.payment_date + interval '5 hours'),'MON-YY') dimension, " \
                " Count(case when is_return_sale = 'f' then party end) Total_Patients, Count(case when is_return_sale = 't' then party end) Total_Patients_returns, " \
                " Count(case when is_return_sale = 'f' then party end) - Count(case when is_return_sale = 't' then party end) final_count " \
                " from sale_sale " \
                " inner join sale_line where sale_line.sale = sale.id " \
                " inner join product_product on product_product.id = sale_line.product " \
                " inner join product_template on product_template.id = product_prodcut.template " \
                " where sale_sale.payment_date + interval '5 hour' >= timestamp %s " \
                " and sale_sale.payment_date + interval '5 hour' <= timestamp %s and sale_sale.state in ('processing','done') " \
                " and sale_type = 'opd' and sale_nature='imaging' group by account_category, date_TRUNC('month', sale_sale.payment_date + interval '5 hours')  order by 1"
        
        data = []
        cursor = Transaction().connection.cursor()
        cursor.execute(query,(datefrom, dateto))
        all_recs = cursor.fetchall()
      
        for rec in all_recs:
                net_share = net_share + rec[3]
                dimension = rec[0]                        
                data = stats.get(dimension, None)
                if data: 
                      total = data['imaging'] + data['lab'] + data['opd'] + rec[3]                      
                      stats[dimension] = {'imaging': data['imaging'], 'lab':data['lab'], 'opd':data['opd'], 'er':rec[3], 'total':total}
                else:
                      stats[dimension] = {'imaging': 0, 'lab':0, 'opd':0, 'er':rec[3], 'total': rec[3]}

        logging.error(str(stats))                      

        report_context = super(OpdStatsReport, cls).get_context(records, header, data)

        report_context['data'] = data
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto
        report_context['commission_lines_opd'] = commission_lines_opd
        report_context['commission_lines_ipd'] = commission_lines_ipd        
        report_context['total_earned_opd'] = round(total_earned_opd,2)
        report_context['total_earned_ipd'] = round(total_earned_ipd,2)
        report_context['doctor_name'] = 'OPD Stats'
        report_context['net_share'] = round(net_share,2)
        report_context['stats'] = stats
        report_context['objects'] = records
          
        return report_context                    

class PhlebotomyAccessionSheetReport(Report):
    __name__ = 'health.proc.sample.batch.report'   

    @classmethod
    def get_context(cls, records, header, data):
        data = []
            
        report_context = super(PhlebotomyAccessionSheetReport, cls).get_context(records, header, data)
        report_context['data'] = data

        report_context['records'] = records
        return report_context         
    
class StockInventoryReportStart(ModelView):
    'Stock Inventory Report Start'
    __name__ = 'health.proc.stock.inventory.start'

    
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[('type', '=', 'warehouse')],
    )
    sub_store = fields.Many2One('stock.location', "Sub Store", required=True)

    category = fields.Many2One('product.category', 'Category')
    form = fields.Many2One('gnuhealth.drug.form', 'Form')

    datefrom = fields.Date('From Date', required=True)  
    dateto = fields.Date('To Date', required=True)      

    @staticmethod
    def default_datefrom():
        return datetime.now().date()

    @staticmethod
    def default_dateto():
        return datetime.now().date()


class WizardStockInventoryReport(Wizard):
    'Stock Inventory Report Wizard'
    __name__ = 'health.proc.stock.inventory.wizard'

    # Starting state, where the form is shown to the user
    start = StateView('health.proc.stock.inventory.start',
        'health_proc.stock_inventory_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    
    print_ = StateReport('health.proc.stock.inventory.details.report')

    
    def do_print_(self, action):
        data = {
            'warehouse': self.start.warehouse.id,
            'sub_store': self.start.sub_store.id,
            'category': self.start.category.id if self.start.category else None,
            'form': self.start.form.id if self.start.form else None,
            'datefrom': self.start.datefrom,  
            'dateto': self.start.dateto,  
            
    
        }
        return action, data

    
    def transition_print_(self):
        return 'end'


class StockInventoryDetailsReport(Report):
    __name__ = 'health.proc.stock.inventory.details.report'   

    @classmethod
    def get_context(cls, records, header, data):  
        warehouse_id = data['warehouse']  # Used only as a filter, not for display
        sub_store_id = data['sub_store']
        category = data['category']
        form = data['form']
        date_from = data.get('datefrom')
        date_to = data.get('dateto')


        StockLocation = Pool().get('stock.location')
        sub_store = StockLocation(sub_store_id) if sub_store_id else None

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)

        
        query = """
            SELECT lot.number as lot, templates.name, SUM(moves.quantity) as quantity, 
                TO_CHAR(lot.expiration_date, 'MM/DD/YYYY') as expiration_date
            FROM product_template as templates
            JOIN product_product as products ON templates.id = products.template
            JOIN stock_lot as lot ON products.id = lot.product
            JOIN stock_move as moves ON lot.id = moves.lot
            JOIN stock_location as locations ON moves.to_location = locations.id
            JOIN product_category pc on templates.account_category = pc.id 
            JOIN gnuhealth_medicament gm on products.id = gm."name" 
            JOIN gnuhealth_drug_form gdf on gm.form = gdf.id 
            WHERE locations.id = %s AND locations.parent = %s
                AND (%s IS NULL OR pc.id = %s)
                AND (%s IS NULL OR gdf.id = %s)
            GROUP BY lot.number, templates.name, lot.expiration_date
        """
        
        cursor = Transaction().connection.cursor()
        cursor.execute(query, (sub_store_id, warehouse_id, category, category,form, form))
        all_recs = cursor.fetchall()
        
        stock_lines = [{
            'lot': rec[0],
            'product': rec[1],
            'quantity': rec[2],
            'expiration_date': rec[3],
        } for rec in all_recs]

        
        report_context = super(StockInventoryDetailsReport, cls).get_context(records, header, data)
        report_context['stock_lines'] = stock_lines
        report_context['sub_store'] = sub_store.rec_name if sub_store else None
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to

        return report_context    

class DoctorServicesDetailsReport(Report):
    __name__ = 'health.proc.doctor.services.details.report'

    @classmethod
    def get_context(cls, records, header, data):
        datefrom = data['datefrom'] or datetime.now()
        dateto = data['dateto'] or datetime.now()
        doctor_id = data.get('doctor')
        
        # Fetch the doctor's name
        doctor_name = ""
        if doctor_id:
            cursor = Transaction().connection.cursor()
            cursor.execute(
                "SELECT party_party.name FROM gnuhealth_healthprofessional "
                "JOIN party_party ON gnuhealth_healthprofessional.name = party_party.id "
                "WHERE gnuhealth_healthprofessional.id = %s", (doctor_id,)
            )
            result = cursor.fetchone()
            if result:
                doctor_name = result[0]
        
        # SQL Query to fetch the report data filtered by doctor_id
        query = """
            SELECT
                sale_sale.sale_date::date AS sale_date, 
                party_party.ref AS mrno,
                party_party.name AS party_name,
                product_template.name AS service,
                sale_line.quantity,
                sale_line.unit_price AS price,
                sale_sale.id AS sale_id
            FROM sale_line
                JOIN sale_sale ON sale_sale.id = sale_line.sale
                JOIN product_product ON product_product.id = sale_line.product
                JOIN product_template ON product_template.id = product_product.template
                JOIN gnuhealth_healthprofessional gh ON sale_sale.doctor = gh."name" 
                JOIN party_party ON sale_sale.party = party_party.id
            WHERE sale_line.create_date BETWEEN %s AND %s
                AND sale_sale.state IN ('processing', 'done', 'confirmed')
                AND gh.id = %s  -- Filter by the selected doctor's ID
            GROUP BY 
                sale_sale.sale_date, party_party.ref, product_template.name, 
                party_party.name, sale_line.quantity, sale_line.unit_price, 
                sale_sale.id
        """
        
        
        cursor.execute(query, (datefrom, dateto, doctor_id))
        doctor_services = []
        for rec in cursor.fetchall():
            doctor_services.append({
                'sale_date': rec[0],         
                'mrno': rec[1],              
                'party_name': rec[2],        
                'service': rec[3],           
                'quantity': rec[4],          
                'price': rec[5],             
                'sale_id': rec[6],          
            })


        report_context = super().get_context(records, header, data)
        report_context['doctor_services'] = doctor_services
        report_context['doctor_name'] = doctor_name  
        report_context['date_from'] = datefrom
        report_context['date_to'] = dateto

        return report_context

class DoctorServicesDetailsReportStart(ModelView):
    'Doctor Services Details'
    __name__ = 'health.proc.doctor.services.details.start'
    
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)
    doctor = fields.Many2One('gnuhealth.healthprofessional', 'Doctor', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
        
    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_datefrom():
        return datetime.now()

    @staticmethod
    def default_dateto():
        return datetime.now()


class WizardDoctorServicesDetails(Wizard):
    'Doctor Services Details Report Wizard'
    __name__ = 'health.proc.doctor.services.details.wizard'
    
    start = StateView('health.proc.doctor.services.details.start',
                      'health_proc.doctor_services_details_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate Report', 'print_', 'tryton-print', default=True),
                      ])
    print_ = StateReport('health.proc.doctor.services.details.report')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'datefrom': self.start.datefrom,
            'dateto': self.start.dateto,
            'doctor': self.start.doctor.id,
        }
        return action, data

    def transition_print_(self):
        return 'end'

class StockNearExpiryReportStart(ModelView):
    'Stock Near Expiry Report Start'
    __name__ = 'health.proc.stock.near.expiry.start'

    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[('type', '=', 'warehouse')],
    )
    sub_store = fields.Many2One('stock.location', "Sub Store", required=True)
    datefrom = fields.Date('From Date', required=True)  
    dateto = fields.Date('To Date', required=True)

    @staticmethod
    def default_datefrom():
        return datetime.now().date()

    @staticmethod
    def default_dateto():
        return datetime.now().date()

class WizardStockNearExpiryReport(Wizard):
    'Stock Near Expiry Report Wizard'
    __name__ = 'health.proc.stock.near.expiry.wizard'

    start = StateView('health.proc.stock.near.expiry.start',
        'health_proc.stock_near_expiry_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('health.proc.stock.near.expiry.details.report')

    def do_print_(self, action):
        data = {
            'warehouse': self.start.warehouse.id,
            'sub_store': self.start.sub_store.id,
            'datefrom': self.start.datefrom.isoformat(),  
            'dateto': self.start.dateto.isoformat(),  
        }
        return action, data

    def transition_print_(self):
        return 'end'

class StockNearExpiryReport(Report):
    __name__ = 'health.proc.stock.near.expiry.details.report'   

    @classmethod
    def get_context(cls, records, header, data):  
        warehouse_id = data['warehouse']
        sub_store_id = data['sub_store']
        date_from = data.get('datefrom')
        date_to = data.get('dateto')
        near_expiry_date = (datetime.fromisoformat(date_to) + timedelta(days=180)).date()

        StockLocation = Pool().get('stock.location')
        sub_store = StockLocation(sub_store_id) if sub_store_id else None

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)

        query = """
            SELECT lot.id, lot.number as lot, templates.name, pl.unit_price as rate, 
                TO_CHAR(lot.expiration_date, 'MM/DD/YYYY') as expiration_date, gdf.name as form, pc.name as category
            FROM product_template as templates
            JOIN product_product as products ON templates.id = products.template
            JOIN stock_lot as lot ON products.id = lot.product
            JOIN stock_move as moves ON lot.id = moves.lot
            JOIN stock_location as locations ON moves.to_location = locations.id
            JOIN product_category pc on templates.account_category = pc.id 
            JOIN gnuhealth_medicament gm ON products.id = gm.name 
            JOIN gnuhealth_drug_form gdf ON gm.form = gdf.id 
            JOIN purchase_line pl ON products.id = pl.product 
            WHERE locations.id = %s AND locations.parent = %s 
                AND lot.expiration_date BETWEEN %s AND %s
            GROUP BY lot.id, lot.number, templates.name, lot.expiration_date, pl.unit_price, gdf.name, pc.name
        """

        cursor = Transaction().connection.cursor()
        cursor.execute(query, (sub_store_id, warehouse_id, date_from, near_expiry_date))
        all_recs = cursor.fetchall()
        
        stock_lines = []
        for index, rec in enumerate(all_recs, start=1):
            lot_id = rec[0]
            quantity = cls.get_lot_quantity(lot_id)
            amount = Decimal(quantity) * rec[3]  # Convert quantity to Decimal before multiplication
            stock_lines.append({
                's_no': index,
                'lot': rec[1],
                'product': rec[2],
                'quantity': quantity,
                'rate': rec[3],
                'amount': amount,
                'expiration_date': rec[4],
                'form': rec[5],
                'category': rec[6],
                'status_of_days': (datetime.strptime(rec[4], '%m/%d/%Y').date() - datetime.now().date()).days,
            })

        report_context = super(StockNearExpiryReport, cls).get_context(records, header, data)
        report_context['stock_lines'] = stock_lines
        report_context['sub_store'] = sub_store.rec_name if sub_store else None
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to

        return report_context

    @classmethod
    def get_lot_quantity(cls, lot_id):
        pool = Pool()
        Move = pool.get('stock.move')
        quantity = 0.0
        moves = Move.search([('lot', '=', lot_id), ('state', '=', 'done')])
        for move in moves:
            if move.to_location.type == 'storage':
                quantity += move.quantity
            if move.from_location.type == 'storage':
                quantity -= move.quantity
        return quantity

class StockExpiredReportStart(ModelView):
    'Stock Expired Report Start'
    __name__ = 'health.proc.stock.expired.start'

    main_warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[('type', '=', 'warehouse')],
    )
    sub_store = fields.Many2One('stock.location', "Sub Store", required=True)
    dateto = fields.Date('To Date', required=True)

    @staticmethod
    def default_dateto():
        return datetime.now().date()

class WizardStockExpiredReport(Wizard):
    'Stock Expired Report Wizard'
    __name__ = 'health.proc.stock.expired.wizard'

    start = StateView('health.proc.stock.expired.start',
        'health_proc.stock_expired_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('health.proc.stock.expired.details.report')

    def do_print_(self, action):
        data = {
            'main_warehouse': self.start.main_warehouse.id,
            'sub_store': self.start.sub_store.id,
            'dateto': self.start.dateto.isoformat(),  
        }
        return action, data

    def transition_print_(self):
        return 'end'

class StockExpiredReport(Report):
    __name__ = 'health.proc.stock.expired.details.report'   

    @classmethod
    def get_context(cls, records, header, data):  
        warehouse_id = data['main_warehouse']
        sub_store_id = data['sub_store']
        date_to = data.get('dateto')

        StockLocation = Pool().get('stock.location')
        sub_store = StockLocation(sub_store_id) if sub_store_id else None

        logging.error("================== called the get_context for summary report=========================")
        logging.info(data)

        query = """
            SELECT DISTINCT ON (lot.id) lot.id, lot.number as lot, templates.name, pl.unit_price as rate, 
                TO_CHAR(lot.expiration_date, 'MM/DD/YYYY') as expiration_date, gdf.name as form, pc.name as category
            FROM product_template as templates
            JOIN product_product as products ON templates.id = products.template
            JOIN stock_lot as lot ON products.id = lot.product
            JOIN stock_move as moves ON lot.id = moves.lot
            JOIN stock_location as locations ON moves.to_location = locations.id
            JOIN product_category pc on templates.account_category = pc.id 
            JOIN gnuhealth_medicament gm ON products.id = gm.name 
            JOIN gnuhealth_drug_form gdf ON gm.form = gdf.id 
            JOIN purchase_line pl ON products.id = pl.product 
            WHERE locations.id = %s AND locations.parent = %s 
                AND lot.expiration_date <= %s
            ORDER BY lot.id, lot.expiration_date
        """

        cursor = Transaction().connection.cursor()
        cursor.execute(query, (sub_store_id, warehouse_id, date_to))
        all_recs = cursor.fetchall()

        stock_lines = []
        for index, rec in enumerate(all_recs, start=1):
            lot_id = rec[0]
            quantity = cls.get_lot_quantity(lot_id)
            amount = Decimal(quantity) * rec[3]  # Convert quantity to Decimal before multiplication
            status_of_days = (datetime.now().date() - datetime.strptime(rec[4], '%m/%d/%Y').date()).days * -1
            stock_lines.append({
                's_no': index,
                'lot': rec[1],
                'product': rec[2],
                'quantity': quantity,
                'rate': rec[3],
                'amount': amount,
                'expiration_date': rec[4],
                'form': rec[5],
                'category': rec[6],
                'status_of_days': status_of_days,
            })

        report_context = super(StockExpiredReport, cls).get_context(records, header, data)
        report_context['stock_lines'] = sorted(stock_lines, key=lambda x: x['expiration_date'])
        report_context['sub_store'] = sub_store.rec_name if sub_store else None
        report_context['date_to'] = date_to

        return report_context

    @classmethod
    def get_lot_quantity(cls, lot_id):
        pool = Pool()
        Move = pool.get('stock.move')
        quantity = 0.0
        moves = Move.search([('lot', '=', lot_id), ('state', '=', 'done')])
        for move in moves:
            if move.to_location.type == 'storage':
                quantity += move.quantity
            if move.from_location.type == 'storage':
                quantity -= move.quantity
        return quantity
    
class VisitOpdPatient(ModelView):
    'Visit Opd Patient'
    __name__ = 'health.proc.visit.opd.patient.start'

    doctor_name = fields.Many2One('gnuhealth.healthprofessional', 'Doctor', required=False)
    date_from = fields.Date('From Date', required=False)
    date_to = fields.Date('To Date', required=False)

class WizardPatientVisitOpdReport(Wizard):
    'Opd Patient Visit Report Wizard'
    __name__ = 'health.proc.visit.opd.patient.wizard'

    start = StateView('health.proc.visit.opd.patient.start',
                      'health_proc.visit_opd_patient_report_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate Report', 'print_', 'tryton-print', default=True),
                      ]
                      )
    print_ = StateReport('health.proc.visit.opd.patient.details.report')

    def do_print_(self, action):
        data = {
            'doctor_name': self.start.doctor_name.id if self.start.doctor_name else None,
            'date_from': self.start.date_from if self.start.date_from else None,
            'date_to': self.start.date_to if self.start.date_to else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'

class VisitOpdPatientDetailsReport(Report):
    __name__ = 'health.proc.visit.opd.patient.details.report'

    @classmethod
    def get_context(cls, records, header, data):
        cursor = Transaction().connection.cursor()

        doctor_id = data.get('doctor_name')
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        # Fetch the doctor's name
        doctor_name = ""
        if doctor_id:
            cursor.execute(
                "SELECT party_party.name FROM gnuhealth_healthprofessional "
                "JOIN party_party ON gnuhealth_healthprofessional.name = party_party.id "
                "WHERE gnuhealth_healthprofessional.id = %s", (doctor_id,)
            )
            result = cursor.fetchone()
            if result:
                doctor_name = result[0]

        logging.error("================== called the get_context for visit opd patient report=========================")
        logging.info(data)

        query = """
            SELECT pp.name as patient_name, pp."ref" as mrno, pp2."name" as doctor_name, gs.name as specialty,
                   ga.appointment_type as type, ga.appointment_date as date
            FROM gnuhealth_appointment ga
            JOIN gnuhealth_patient gp ON gp.id = ga.patient
            JOIN party_party pp ON gp.name = pp.id
            JOIN gnuhealth_healthprofessional gh ON ga.healthprof = gh.id
            JOIN party_party pp2 ON gh."name" = pp2.id
            JOIN gnuhealth_hp_specialty ghs ON gh.main_specialty = ghs.id
            JOIN gnuhealth_specialty gs ON ghs.specialty = gs.id
            WHERE 1=1
        """
        
        params = []

        if date_from:
            query += " AND ga.appointment_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND ga.appointment_date <= %s"
            params.append(date_to)

        if doctor_id:
            query += " AND gh.id = %s"
            params.append(doctor_id)

        # Update ORDER BY clause to include doctor_name first, then appointment_date
        query += """
            GROUP BY pp.name, pp."ref", pp2."name", gs.name, ga.appointment_type, ga.appointment_date 
            ORDER BY pp2."name" ASC, ga.appointment_date ASC
        """

        cursor.execute(query, params)
        all_recs = cursor.fetchall()

        appointment_lines = []
        for index, rec in enumerate(all_recs, start=1):
            appointment_lines.append({
                's_no': index,
                'mrno': rec[1],
                'patient_name': rec[0],
                'doctor_name': rec[2],
                'specialty': rec[3],
                'type': rec[4],
                'date': rec[5],
            })

        report_context = super(VisitOpdPatientDetailsReport, cls).get_context(records, header, data)
        
        # Add doctor name, date range, and appointment lines to the context
        report_context['doctor_name'] = doctor_name
        report_context['date_from'] = str(date_from) if date_from else ''
        report_context['date_to'] = str(date_to) if date_to else ''
        report_context['appointment_lines'] = appointment_lines

        return report_context
    
class SurgeryRecommendedOpdPatient(ModelView):
    'Surgery Recommended Opd Patient'
    __name__ = 'health.proc.surgery.recommended.opd.patient.start'

    doctor_name = fields.Many2One('gnuhealth.healthprofessional', 'Doctor', required=False)
    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)

class WizardSurgeryRecommendedOpdReport(Wizard):
    'Surgery Recommended Opd Report Wizard'
    __name__ = 'health.proc.surgery.recommended.opd.patient.wizard'

    start = StateView('health.proc.surgery.recommended.opd.patient.start',
                      'health_proc.opd_patient_surgery_recommended_report_start_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Generate Report', 'print_', 'tryton-print', default=True),
                      ]
                      )
    print_ = StateReport('health.proc.surgery.recommended.opd.patient.details.report')

    def do_print_(self, action):
        data = {
            'doctor_name': self.start.doctor_name.id if self.start.doctor_name else None,
            'date_from': self.start.date_from if self.start.date_from else None,
            'date_to': self.start.date_to if self.start.date_to else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'

class SurgeryRecommendedOpdDetailsReport(Report):
    __name__ = 'health.proc.surgery.recommended.opd.patient.details.report'

    @classmethod
    def get_context(cls, records, header, data):
        cursor = Transaction().connection.cursor()  # Initialize cursor at the beginning

        doctor_id = data.get('doctor_name')
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        # Fetch the doctor's name
        doctor_name = ""
        if doctor_id:
            cursor.execute(
                "SELECT party_party.name FROM gnuhealth_healthprofessional "
                "JOIN party_party ON gnuhealth_healthprofessional.name = party_party.id "
                "WHERE gnuhealth_healthprofessional.id = %s", (doctor_id,)
            )
            result = cursor.fetchone()
            if result:
                doctor_name = result[0]

        logging.error("================== called the get_context for surgery recommended opd patient report=========================")
        logging.info(data)

        query = """
            SELECT pp.name as patient_name, pp."ref" as mrno, pp2."name" as doctor_name, ga.appointment_type as type,
                   gpe.present_illness, gp2.description, gd."comments", gpe.evaluation_start as ev_start_time, gpe.evaluation_endtime as ev_end_time
            FROM gnuhealth_appointment ga
            JOIN gnuhealth_patient gp ON gp.id = ga.patient
            JOIN party_party pp ON gp.name = pp.id
            JOIN gnuhealth_healthprofessional gh ON ga.healthprof = gh.id
            JOIN party_party pp2 ON gh."name" = pp2.id
            JOIN gnuhealth_patient_evaluation gpe ON gpe.patient = ga.patient
            JOIN gnuhealth_directions gd ON gd."name" = gpe.id
            JOIN gnuhealth_procedure gp2 ON gd.procedure = gp2.id
            WHERE 1=1 AND gp2.description IS NOT NULL
        """
        
        params = []

        if date_from:
            query += " AND gpe.evaluation_start >= %s"
            params.append(date_from)
        if date_to:
            query += " AND gpe.evaluation_start <= %s"
            params.append(date_to)

        if doctor_id:
            query += " AND gh.id = %s"
            params.append(doctor_id)

        query += """
            GROUP BY pp.name, pp."ref", pp2."name", ga.appointment_type, gpe.present_illness, gp2.description, gd."comments", gpe.evaluation_start, gpe.evaluation_endtime 
            ORDER BY pp2."name" ASC, gpe.evaluation_start ASC
        """

        cursor.execute(query, params)
        all_recs = cursor.fetchall()

        surgery_lines = []
        for index, rec in enumerate(all_recs, start=1):
            surgery_lines.append({
                's_no': index,
                'mrno': rec[1],
                'patient_name': rec[0],
                'type': rec[3],
                'doctor_name': rec[2],
                'present_illness': rec[4],
                'description': rec[5],
                'comments': rec[6],
                'ev_start_time': rec[7],
                'ev_end_time': rec[8],
            })

        report_context = super(SurgeryRecommendedOpdDetailsReport, cls).get_context(records, header, data)
        
        # Add the doctor name, date from, and date to to the context
        report_context['doctor_name'] = doctor_name
        report_context['date_from'] = str(date_from) if date_from else ''
        report_context['date_to'] = str(date_to) if date_to else ''
        report_context['surgery_lines'] = surgery_lines
        
        return report_context     
       

class StockInternalShipmentReportStart(ModelView):
    'Stock Internal Shipment Report Start'
    __name__ = 'stock.internal.shipment.report.start'

    from_location = fields.Many2One(
        'stock.location', "From Location", required=True)
     #   domain=[('type', 'in', ['warehouse', 'view'])],
    #)
    to_location = fields.Many2One('stock.location', "To Location")
    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)

    @staticmethod
    def default_date_from():
        return datetime.now().replace(hour=0, minute=0, second=0)

    @staticmethod
    def default_date_to():
        return datetime.now().replace(hour=18, minute=59, second=59)


class WizardStockInternalShipmentReport(Wizard):
    'Stock Internal Shipment Report Wizard'
    __name__ = 'stock.internal.shipment.report.wizard'

    start = StateView('stock.internal.shipment.report.start',
        'health_proc.stock_internal_shipment_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('stock.internal.shipment.report')

    def do_print_(self, action):
        data = {
            'from_location': self.start.from_location.id,
            'to_location': self.start.to_location.id if self.start.to_location else None,
            'date_from': self.start.date_from.isoformat(),
            'date_to': self.start.date_to.isoformat(),
        }
        return action, data

    def transition_print_(self):
        return 'end'

class StockInternalShipmentReport(Report):
    __name__ = 'stock.internal.shipment.report'

    @classmethod
    def get_context(cls, records, header, data):
        from_location_id = data['from_location']
        to_location_id = data.get('to_location')
        date_from = data['date_from']
        date_to = data['date_to']

        # Fetch from_location name
        cursor = Transaction().connection.cursor()
        cursor.execute("SELECT name FROM stock_location WHERE id = %s", (from_location_id,))
        from_location_name = cursor.fetchone()[0]

        query = """
            SELECT 
                shipment.number AS shipment_number,
                to_location.name AS to_location_name,
                product_template.name AS product_name,
                TO_CHAR(lot.expiration_date, 'MM/DD/YYYY') AS expiration_date,
                moves.quantity AS product_quantity,
                pu.name AS uom,
                lot.number AS lot_name,
                shipment.planned_date,
                shipment.effective_date,
                shipment.state
            FROM 
                stock_shipment_internal AS shipment
                LEFT JOIN stock_location AS from_location ON shipment.from_location = from_location.id
                LEFT JOIN stock_location AS to_location ON shipment.to_location = to_location.id
                LEFT JOIN stock_move AS moves ON moves.shipment = CONCAT('stock.shipment.internal,', shipment.id::text)
                LEFT JOIN product_product AS product ON moves.product = product.id
                LEFT JOIN product_template ON product.template = product_template.id
                LEFT JOIN stock_lot AS lot ON moves.lot = lot.id
                LEFT JOIN product_uom pu ON moves.uom = pu.id 
            WHERE 
                shipment.from_location = %s AND 
                shipment.planned_date BETWEEN %s AND %s
                {to_location_clause}
            ORDER BY 
                shipment.planned_date, from_location.name, to_location.name;
        """

        to_location_clause = ""
        query_params = (from_location_id, date_from, date_to)
        if to_location_id:
            to_location_clause = "AND shipment.to_location = %s"
            query = query.format(to_location_clause=to_location_clause)
            query_params += (to_location_id,)
        else:
            query = query.format(to_location_clause="")

        cursor.execute(query, query_params)
        all_recs = cursor.fetchall()

        stock_lines = []
        for index, rec in enumerate(all_recs, start=1):
            quantity = rec[4]
            if quantity is not None:
                quantity = int(quantity) if quantity.is_integer() else quantity
            stock_lines.append({
                's_no': index,
                'shipment_no': rec[0],
                'to_location': rec[1],
                'product': rec[2],
                'expiration_date': rec[3],
                'quantity': quantity,
                'uom': rec[5],
                'lot': rec[6],
                'planned_date': rec[7],
                'effective_date': rec[8],
                'state': rec[9],
            })

        report_context = super(StockInternalShipmentReport, cls).get_context(records, header, data)
        report_context['stock_lines'] = stock_lines
        report_context['from_location'] = from_location_name
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to

        return report_context
class CriticalAnalytesReportStart(ModelView):
    'Critical Analytes Report Start'
    __name__ = 'critical.analytes.report.start'

    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)
    analyte = fields.Many2One('gnuhealth.lab.test.critearea', 'Analyte', required=False)
    test_type = fields.Many2One('gnuhealth.lab.test_type', 'Test Type', required=False)

    @staticmethod
    def default_date_from():
        return datetime.now().replace(hour=0, minute=0, second=0)

    @staticmethod
    def default_date_to():
        return datetime.now().replace(hour=18, minute=59, second=59)


class WizardCriticalAnalytesReport(Wizard):
    'Critical Analytes Report Wizard'
    __name__ = 'critical.analytes.report.wizard'

    start = StateView('critical.analytes.report.start',
        'health_proc.critical_analytes_report_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('critical.analytes.report')

    def do_print_(self, action):
        data = {
            'date_from': self.start.date_from.isoformat(),
            'date_to': self.start.date_to.isoformat(),
            'analyte': self.start.analyte.id if self.start.analyte else None,
            'test_type': self.start.test_type.id if self.start.test_type else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'


class CriticalAnalytesReport(Report):
    __name__ = 'critical.analytes.report'

    @classmethod
    def get_context(cls, records, header, data):
        date_from = data['date_from']
        date_to = data['date_to']
        analyte_id = data.get('analyte')
        test_type_id = data.get('test_type')

        cursor = Transaction().connection.cursor()

        query = """
            SELECT pp.name as patient, pp.ref as MR, gl.date_analysis, gl.name as test_id, gltt.name as test_type, 
                   gltc2.name as category, gltc.name as analyte, gltc.result as value, 
                   gltc.lower_limit, gltc.upper_limit, gltu.name as unit
            FROM gnuhealth_lab_test_critearea gltc 
            JOIN gnuhealth_lab_test_units gltu on gltc.units = gltu.id
            JOIN gnuhealth_lab gl on gltc.gnuhealth_lab_id = gl.id 
            JOIN gnuhealth_patient gp on gl.patient = gp.id 
            JOIN party_party pp on gp.name = pp.id
            JOIN gnuhealth_lab_test_type gltt on gl.test = gltt.id
            JOIN gnuhealth_lab_test_categories gltc2 on gltt.category = gltc2.id 
            WHERE gltc.warning = 'true' AND gl.state='validated'
              AND gl.date_analysis BETWEEN %s AND %s
              {analyte_clause}
              {test_type_clause}
            ORDER BY gl.date_analysis;
            """

        analyte_clause = ""
        test_type_clause = ""
        query_params = [date_from, date_to]

        if analyte_id:
            analyte_clause = "AND gltc.id = %s"
            query_params.append(analyte_id)

        if test_type_id:
            test_type_clause = "AND gltt.id = %s"
            query_params.append(test_type_id)

        query = query.format(analyte_clause=analyte_clause, test_type_clause=test_type_clause)
        cursor.execute(query, query_params)
        all_recs = cursor.fetchall()

        analytes_lines = []
        for index, rec in enumerate(all_recs, start=1):
            analytes_lines.append({
                's_no': index,
                'patient_name': rec[0],
                'mr_no': rec[1],
                'date': rec[2],
                'test_type': rec[4],
                'category': rec[5],
                'analyte': rec[6],
                'value': rec[7],
                'upper_limit': rec[9],
                'lower_limit': rec[8],
                'unit': rec[10],
            })

        report_context = super(CriticalAnalytesReport, cls).get_context(records, header, data)
        report_context['analytes_lines'] = analytes_lines
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to

        return report_context
       
class PurchaseReportStart(ModelView):
    'Purchase Report Start'
    __name__ = 'purchase.report.start'

    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)
    supplier = fields.Many2One('party.party', 'Supplier', required=False)
    product = fields.Many2One('product.product', 'Item', required=False)

    @staticmethod
    def default_date_from():
        return datetime.now().replace(hour=0, minute=0, second=0)

    @staticmethod
    def default_date_to():
        return datetime.now().replace(hour=18, minute=59, second=59)

class WizardPurchaseReport(Wizard):
    'Purchase Report Wizard'
    __name__ = 'purchase.report.wizard'

    start = StateView('purchase.report.start',
        'health_proc.purchase_report_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('purchase.report')

    def do_print_(self, action):
        data = {
            'date_from': self.start.date_from.isoformat(),
            'date_to': self.start.date_to.isoformat(),
            'supplier': self.start.supplier.id if self.start.supplier else None,
            'product': self.start.product.id if self.start.product else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'

class PurchaseReport(Report):
    __name__ = 'purchase.report'

    @classmethod
    def get_context(cls, records, header, data):
        date_from = data['date_from']
        date_to = data['date_to']
        supplier_id = data.get('supplier')
        product_id = data.get('product')

        cursor = Transaction().connection.cursor()

        query = """
            SELECT DISTINCT 
                pp2.name AS supplier,
                po.purchase_date AS purchase_date,
                po.number AS PO,
                pt.name AS item,
                line.quantity,
                pu.name AS unit,
                line.unit_price AS rate,
                line.discount,
                ai.number AS invoice,
                sl.number AS lot,
                po.invoice_state,
                po.shipment_state,
                po.state AS purchase_state
            FROM 
                purchase_line line
            JOIN 
                purchase_purchase AS po ON line.purchase = po.id
            JOIN 
                product_product pp ON line.product = pp.id 
            JOIN 
                product_template pt ON pp.template = pt.id 
            JOIN 
                product_uom pu ON line.unit = pu.id 
            JOIN 
                party_party pp2 ON po.party = pp2.id
            LEFT JOIN 
                account_invoice_line ail ON ail.origin LIKE CONCAT('purchase.line,', line.id)
            LEFT JOIN 
                account_invoice ai ON ail.invoice = ai.id 
            LEFT JOIN 
                stock_move sm ON sm.origin LIKE CONCAT('purchase.line,', line.id)
            LEFT JOIN 
                stock_lot sl ON sm.lot = sl.id
            WHERE po.state = 'done' AND po.invoice_state = 'paid' 
            AND po.shipment_state = 'received' 
            AND po.purchase_date BETWEEN %s AND %s 
            {supplier_clause} 
            {product_clause} 
            ORDER BY po.purchase_date;
        """

        supplier_clause = ""
        product_clause = ""
        query_params = [date_from, date_to]

        if supplier_id:
            supplier_clause = "AND po.party = %s"
            query_params.append(supplier_id)

        if product_id:
            product_clause = "AND line.product = %s"
            query_params.append(product_id)

        query = query.format(supplier_clause=supplier_clause, product_clause=product_clause)
        cursor.execute(query, query_params)
        all_recs = cursor.fetchall()

        purchase_lines = []
        total_amount = 0
        total_net_amount = 0

        for index, rec in enumerate(all_recs, start=1):
            quantity = float(rec[4])
            rate = float(rec[6])
            amount = quantity * rate
            discount = float(rec[7]) * 100  # Convert to percentage
            net_amount = amount - (amount * discount / 100)  # Adjust net amount calculation

            purchase_lines.append({
                's_no': index,
                'date': rec[1],
                'purchase_order': rec[2],
                'invoice_no': rec[8],
                'supplier': rec[0],
                'product': rec[3],
                'lot_no': rec[9],
                'quantity': quantity,
                'unit': rec[5],
                'unit_price': rate,
                'amount': round(amount, 2),
                'discount': f"{discount:.2f}%",  # Format as percentage
                'net_amount': round(net_amount, 2),
            })

            total_amount += amount
            total_net_amount += net_amount

        report_context = super(PurchaseReport, cls).get_context(records, header, data)
        report_context['purchase_lines'] = purchase_lines
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to
        report_context['total_amount'] = round(total_amount, 2)
        report_context['total_net_amount'] = round(total_net_amount, 2)

        return report_context

class OPDTurnoverReportStart(ModelView):
    'OPD Turnover Report Start'
    __name__ = 'opd.turnover.report.start'

    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)
    doctor = fields.Many2One('gnuhealth.healthprofessional', 'Doctor', required=False)
    service = fields.Many2One('product.product', 'Service', required=False)
    department = fields.Selection([
        ('opd', 'OPD'),
        ('er', 'ER')
    ], 'Department', required=False)

    @staticmethod
    def default_date_from():
        return datetime.now().replace(hour=0, minute=0, second=0)

    @staticmethod
    def default_date_to():
        return datetime.now().replace(hour=23, minute=59, second=59)

class WizardOPDTurnoverReport(Wizard):
    'OPD Turnover Report Wizard'
    __name__ = 'opd.turnover.report.wizard'

    start = StateView('opd.turnover.report.start',
        'health_proc.opd_turnover_report_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate Report', 'print_', 'tryton-print', default=True),
        ]
    )

    print_ = StateReport('opd.turnover.report')

    def do_print_(self, action):
        data = {
            'date_from': self.start.date_from.isoformat(),
            'date_to': self.start.date_to.isoformat(),
            'doctor': self.start.doctor.id if self.start.doctor else None,
            'service': self.start.service.id if self.start.service else None,
            'department': self.start.department if self.start.department else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'


class OPDTurnoverReport(Report):
    __name__ = 'opd.turnover.report'

    @classmethod
    def get_context(cls, records, header, data):
        date_from = data['date_from']
        date_to = data['date_to']
        doctor_id = data.get('doctor')
        service_id = data.get('service')
        department = data.get('department')

        # Fetch the doctor's name
        doctor_name = ""
        if doctor_id:
            cursor = Transaction().connection.cursor()
            cursor.execute(
                "SELECT party_party.name FROM gnuhealth_healthprofessional "
                "JOIN party_party ON gnuhealth_healthprofessional.name = party_party.id "
                "WHERE gnuhealth_healthprofessional.id = %s", (doctor_id,)
            )
            result = cursor.fetchone()
            if result:
                doctor_name = result[0]

        cursor = Transaction().connection.cursor()

        base_query = """
            SELECT 
                sl.create_date AS date,
                pp."ref" AS mr_no,
                pp."name" AS patient_name,
                invoice_party.name AS invoice_party,
                ss.sale_type AS department,
                ss.payment_mode AS patient_type,
                COALESCE(pp2."name", 'N/A') AS doctor,
                product_template."name" AS service,
                sl.quantity,
                (sl.quantity * sl.unit_price) AS amount,
                (SELECT name FROM res_user WHERE id = ss.create_uid) AS user_name
            FROM 
                sale_line sl
            JOIN 
                sale_sale ss ON sl.sale = ss.id
            JOIN 
                party_party pp ON ss.party = pp.id
            LEFT JOIN 
                gnuhealth_healthprofessional hp ON ss.doctor = hp.id
            LEFT JOIN 
                party_party pp2 ON hp.name = pp2.id
            JOIN 
                product_product ON product_product.id = sl.product
            JOIN 
                product_template ON product_template.id = product_product.template
            LEFT JOIN
                party_party invoice_party ON ss.invoice_party = invoice_party.id
            WHERE 
                ss.state IN ('processing', 'confirmed', 'done')
                AND ss.sale_type IN ('opd', 'er')
                AND sl.create_date BETWEEN %s AND %s
        """

        params = [date_from, date_to]

        if doctor_id:
            base_query += " AND ss.doctor = %s"
            params.append(doctor_id)

        if service_id:
            base_query += " AND sl.product = %s"
            params.append(service_id)

        if department:
            base_query += " AND ss.sale_type = %s"
            params.append(department)

        base_query += " ORDER BY sl.create_date, pp.name"

        cursor.execute(base_query, params)
        all_recs = cursor.fetchall()

        turnover_lines = []
        for index, rec in enumerate(all_recs, start=1):
            turnover_lines.append({
                's_no': index,
                'date': rec[0],
                'mr_no': rec[1],
                'patient_name': rec[2],
                'invoice_party': rec[3],
                'department': rec[4],
                'payment_mode': rec[5],
                'doctor_name': rec[6],
                'service': rec[7],
                'quantity': rec[8],
                'amount': rec[9],
                'user_name': rec[10],
            })

        report_context = super(OPDTurnoverReport, cls).get_context(records, header, data)
        report_context['turnover_lines'] = turnover_lines
        report_context['date_from'] = date_from
        report_context['date_to'] = date_to

        return report_context

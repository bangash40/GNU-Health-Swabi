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
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.pool import Pool
import logging
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from trytond.pyson import Eval, Not, Bool

__all__ = ['TestResultsEntryStart', 'TestResultsEntryWizard', 'LimsTestResultsEntryStart', 'LimsTestResultsEntryWizard']


class TestResultsEntryStart(ModelView):
    'Test Results Entry'
    __name__ = 'anth.proc.test.results.entry.start'
    result = fields.Selection([
        ('0', 'Not Detected'),
        ('1', 'Detected'),
        ], 'Result', select=True, required=True)

    @staticmethod
    def default_result():
        return '0'


class TestResultsEntryWizard(Wizard):
    'Results Entry Wizard'
    __name__ = 'anth.proc.test.results.entry.wizard'

    start = StateView('anth.proc.test.results.entry.start',
        'health_proc.anth_proc_results_entry_form_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Save Results', 'request', 'tryton-ok', default=True),
            Button('Save & Publish', 'publish', 'tryton-ok'),

            ])

    

    request = StateTransition()
    publish = StateTransition()
    publish_tryton = StateTransition()

    def transition_request(self):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        tests_report_data = []
        tests = Lab.browse(Transaction().context.get('active_ids'))

        for lab_test_result in tests:
                rapid_test_id = [880] # it is 832 test, 880 for production
                if lab_test_result.request.name.id not in rapid_test_id:
                        self.raise_user_error("This feature is for Rapid test only")
                if lab_test_result.state == 'done':
                        self.raise_user_error("The Result has already been entered")
		        #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
		        #continue

                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
                if len(found) >= 1:
                        LimsAnalyte.delete(found)

                final_result = ''
                if self.start.result == '0':
                        final_result = 'NOT DETECTED'
                
                if self.start.result == '1':
                        final_result = 'DETECTED'
                
                limsAnalyte = LimsAnalyte.create([{
                        'name':'SARS Cov2 Rapid',
                        'category':'Microbiology',
                        'analyte_id':str(lab_test_result.id), 
                        'gnuhealth_lab_id':lab_test_result.id,
                        'value_range': '',
                        'result':final_result,
                        'unit': 'None',
                        'sortable_title': '',						
                        }])
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'results':'test performed', 'state':'prelim'})

        return 'end'

    def transition_publish(self):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        tests_report_data = []
        tests = Lab.browse(Transaction().context.get('active_ids'))

        for lab_test_result in tests:
                if lab_test_result.request.name.id != 880:
                        self.raise_user_error("This feature is for Rapid test only")
                if lab_test_result.state == 'done':
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
                        #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
                        #continue
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
                if len(found) >= 1:
                        LimsAnalyte.delete(found)

                final_result = ''
                if self.start.result == '0':
                        final_result = 'NOT DETECTED'

                if self.start.result == '1':
                        final_result = 'DETECTED'



                limsAnalyte = LimsAnalyte.create([{
                        'name':'SARS Cov2 Rapid',
                        'category':'Microbiology',
                        'analyte_id':str(lab_test_result.id), 
                        'gnuhealth_lab_id':lab_test_result.id,
                        'value_range':'',
                        'result': final_result,
                        'unit': 'None',
                        'sortable_title': '',						
                        }])
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'results':'test performed', 'state':'done', 'date_analysis': datetime.now()})

        return 'end'


class LimsTestResultsEntryStart(ModelView):
    'Test Results Entry'
    __name__ = 'anth.proc.lims.results.entry.start'

    services_results = fields.One2Many('anth.proc.analysis.service.result', None,'Lab Results')
    comments = fields.Text("Pathologis Comments")
    old_dates_display = fields.Char("Old Date", readonly=True)
    peripheral_smear = fields.Text("Peripheral Smear")
    specimen_details = fields.Text("Specimen Details")
    clinical_details = fields.Text("Clinical Details")
    gross_examination = fields.Text("Gross Examination")
    microscopic_description = fields.Text("Microscopic Description")
    pathologis_diagnosis = fields.Text("Pathologis Diagnosis")
    
    
    @staticmethod
    def default_old_dates_display():
        #Code added by Khurram to get the patient id, if the request is from Hospitalization
        if Transaction().context.get('active_model') == 'gnuhealth.lab':
                Lab = Pool().get("gnuhealth.lab")
                lab = Lab(Transaction().context.get('active_id'))
                               
                dt_string = ''
                if lab.hist_one_date:
                        dt_string = '                       ' + lab.hist_one_date.strftime('%d-%b-%y')

                if lab.hist_two_date:
                        dt_string += '                            ' + lab.hist_two_date.strftime('%d-%b-%y')


                return dt_string

    
    @staticmethod
    def default_services_results():
	#Code added by Khurram to get the patient id, if the request is from Hospitalization
        if Transaction().context.get('active_model') == 'gnuhealth.lab':
                AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")
                lines = set()
                ids = []
                orders = AnalysisServiceResult.search([
	                        ('gnuhealth_lab_id', '=', Transaction().context.get('active_id')),	
	                        ])

                #logging.info(orders)

                #orders = sorted(orders, key=lambda order: order.category, reverse=True)

                for line in orders:
                        #lines.add(line.id)
                        ids.append(line.id)

                logging.info("================ final_ids ===============")
                #logging.info(ids)



                return ids

    @staticmethod
    def default_comments():
        #Code added by Khurram to get the patient id, if the request is from Hospitalization
        if Transaction().context.get('active_model') == 'gnuhealth.lab':
                Lab = Pool().get("gnuhealth.lab")
                lab = Lab(Transaction().context.get('active_id'))
	                       
                dt_string = ''
                if lab.diagnosis:
                        dt_string = lab.diagnosis

                return dt_string
class LimsTestResultsEntryWizard(Wizard):
    'Results Entry Wizard'
    __name__ = 'anth.proc.lims.results.entry.wizard'

    start = StateView('anth.proc.lims.results.entry.start',
        'health_proc.anth_proc_lims_results_entry_form_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Save Results', 'save_results', 'tryton-ok', default=True),
            
            ])

    

    save_results = StateTransition()
    publish = StateTransition()
    publish_tryton = StateTransition()

    def transition_save_results(self):
        Lab = Pool().get('gnuhealth.lab')
        AnalysisServiceResult = Pool().get("anth.proc.analysis.service.result")

        tests_report_data = []
        tests = Lab.browse(Transaction().context.get('active_ids'))

        for lab_test_result in tests:
                if False:
                        self.raise_user_error("This feature is for Rapid test only")
                if False:
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
	                #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
	                #continue
                found = AnalysisServiceResult.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
                #if len(found) >= 1:
                #        AnalysisServiceResult.delete(found)

                # also save the result in AnalysisServiceResult table ----------------------


                for result in self.start.services_results:
                        found = AnalysisServiceResult.search([('id','=', result.id)])
                        if len(found) == 0:
                                limsAnalysisResult = AnalysisServiceResult.create([{
                                        'gnuhealth_lab_id':lab_test_result.id,
                                        'service': result.service.id,
                                        'numeric_result': result.numeric_result,
                                        'text_result': result.text_result,
                                        'selected_result_option': result.selected_result_option.id if result.selected_result_option else None,
                                        'result_range':result.result_range,
                                        'state': 'in_progress',
                                }])
                        else:
                                AnalysisServiceResult.write([result], {'numeric_result':result.numeric_result, 'text_result': result.text_result,
                                        'selected_result_option': result.selected_result_option.id if result.selected_result_option else None,
                                        'result_range':result.result_range,}) 	
                if self.start.comments:
                        Lab.write([lab_test_result],{'diagnosis':self.start.comments, 'clinical_details': self.start.peripheral_smear})	
		
        return 'end'
    def transition_publish(self):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        tests_report_data = []
        tests = Lab.browse(Transaction().context.get('active_ids'))

        for lab_test_result in tests:
                if lab_test_result.request.name.id != 880:
                        self.raise_user_error("This feature is for Rapid test only")
                if lab_test_result.state == 'done':
                        self.raise_user_error("The Report has already been Published. Open report from Report menu.")
	                #logging.info("The values have already been migrated from LIMS for " + lab_test_result.ar_id)
	                #continue
                found = LimsAnalyte.search([('gnuhealth_lab_id', '=', lab_test_result.id)])
                if len(found) >= 1:
                        LimsAnalyte.delete(found)

                final_result = ''
                if self.start.result == '0':
                        final_result = 'NOT DETECTED'

                if self.start.result == '1':
                        final_result = 'DETECTED'



                limsAnalyte = LimsAnalyte.create([{
	                'name':'SARS Cov2 Rapid',
	                'category':'Microbiology',
	                'analyte_id':str(lab_test_result.id), 
	                'gnuhealth_lab_id':lab_test_result.id,
	                'value_range':'',
	                'result': final_result,
	                'unit': 'None',
	                'sortable_title': '',						
	                }])
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'results':'test performed', 'state':'done', 'date_analysis': datetime.now()})

        return 'end'

    def transition_publish_tryton(self):
        Lab = Pool().get('gnuhealth.lab')
        LimsAnalyte = Pool().get('gnuhealth.lab.lims.analyte.result')

        tests_report_data = []
        tests = Lab.browse(Transaction().context.get('active_ids'))

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

                for result in self.start.services_results:
                        limsAnalyte = LimsAnalyte.create([{
	                        'name':result.service.name,
	                        'category':'Microbiology',
	                        'analyte_id':str(lab_test_result.id), 
	                        'gnuhealth_lab_id':lab_test_result.id,
	                        'value_range':'',
	                        'result': str(result.numeric_result),
	                        'unit': 'None',
	                        'sortable_title': 'aaa_iuiu',						
	                        }])
                logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                logging.info("\n\n\n")

                Lab.write([lab_test_result],{'results':'test performed', 'state':'done', 'date_analysis': datetime.now(), 'comments': lab_test_result.diagnosis, 'peripheral_smear': lab_test_result.clinical_details })

        InvoiceReport = Pool().get('anth.proc.test.report.print', type='report')
        result = InvoiceReport.execute([lab_test_result.id], {'include_header':True})
        report_format,report_bytes = result[:2]
        f = open("/home/gnuhealth/abc.odt","wb")
        f.write(report_bytes)
        f.close()

        #SalePrint = Pool().get("sale.payment", type='wizard')
        #sid = Wizard.create()
        #logging.info(sid)
        #xxx = SalePrint.execute(sid[0],{},'start')
        #logging.info(xxx)


        return 'end'

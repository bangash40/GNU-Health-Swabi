from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.tools import grouped_slice, reduce_ids
from sql import Literal, Table
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Bool, And, Equal, Or, In
from trytond import backend
from trytond.config import config

from trytond.model.exceptions import ValidationError
from trytond.exceptions import UserError
from trytond.modules.health.core import get_health_professional

from decimal import Decimal
from datetime import datetime, time, timedelta, tzinfo
import operator
from itertools import  groupby
from functools import wraps

from sql import Column, Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case

from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    StateReport, Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
import logging
from sql.aggregate import Max, Count, Sum
from sql import Literal, Join
from trytond.rpc import RPC
from trytond.modules.company import CompanyReport
import pytz
from trytond.exceptions import UserWarning
import logging
import urllib, json
import relatorio.reporting

from urllib.request import urlopen, build_opener
import urllib.request
from urllib.request import Request
from urllib.parse import urlencode
import http.cookiejar
from trytond.exceptions import UserWarning
import traceback


__all__ = ['AccountRuleInsuranceCompany','OpdStatsDetailedFinalReport']


class AccountRuleInsuranceCompany(metaclass=PoolMeta):
    __name__ = 'account.account.rule'

    insurance_company = fields.Many2One(
        'party.party', 'Insurance Company',
        required=False, select=True,
        domain=[('is_insurance_company', '=', True)],
        depends=['type'])
    
class OpdStatsDetailedFinalReport(Report):
    __name__ = 'health.proc.opd_stats_detailed_final.report'

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        ImagingTestResult = Pool().get("gnuhealth.imaging.test.result")
	
        logging.info(report_context)
        datefrom = report_context.get('data','').get('datefrom','')
        logging.info(str(datefrom))
        dateto = report_context.get('data','').get('dateto','')
        logging.info(str(dateto))
        #if len(ids) == 0 or len(ids) > 1:
        #    raise ValidationError("Selet a Result!","Please select one result from the list and then click 'Radiology PDF Report' to view report")

        testResult = ImagingTestResult(100)
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
                "the_info": "", #lab.signed_by.info,
                "the_report": testResult.comment,
                "date_from": str(datefrom),
                "date_to": str(dateto),
                "state": "<b>manual report</b>",
        })

        logging.warn(params)

        params = params.encode('utf-8')
        req = Request("http://localhost:9090/CRM/admin/get_opd_stats_detailed_as_pdf.htm", params)
        res = urlopen(req)      

        data = res.read()
        return data

    @classmethod
    def convert(cls, report, data):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        return output_format, data

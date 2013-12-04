# -*- coding: utf-8 -*-
##############################################################################
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
from openerp.osv import osv
from openerp.osv import fields
from openerp import SUPERUSER_ID
from openerp import pooler, tools
from openerp.tools.translate import _
import time
import datetime
import functools

_logger = logging.getLogger(__name__)
_transaction_types = {'app_new': 'NEW',
                      'app_pend': 'PEND',
                      'app_withdraw': 'WITHDRAW',
                      'app_approve': 'CERTIFIED',
                      'app_denied': 'DENIED',
                      'pend-approve': 'APPROVE',
                      'write': 'WRITE',
                      'create': 'CREATE',
                      'decertify': 'DECERTIFY',
                      'certify': 'CERTIFY',
                      'copy': 'COPY'}

_ethnicities = (('A', 'ASIAN PACIFIC ISLANDER'),
                ('AA', 'BLACK'),
                ('AI', 'ASIAN INDIAN'),
                ('C', 'CAUCASIAN'),
                ('H', 'HISPANIC'),
                ('NA', 'NATIVE AMERICAN'),
                ('O', 'OTHER'))

_business_types = (('SP', 'SOLE PROPRIETOR'),
                   ('P', 'PARTNERSHIP'),
                   ('C', 'CORPORATION'),
                   ('NP', 'NON-PROFIT'),
                   ('G', 'GOVERNMENT'),
                   ('LL', 'LIMITED LIABILITY COMPANY'),
                   ('JV', 'JOINT VENTURE'),
                   ('T', 'TRUST'))


class dbe_messages(osv.osv):
    """ DBE Message """
    _name = 'dbe.messages'
    _description = 'DBE Message'
    _inherit = 'mail.message'

    _columns = {
        'vendor_id': fields.integer('Vendor Id'),
        'application_related': fields.boolean('Application'),
        'certification_related': fields.boolean('Certification'),
    }


class dbe_vendor(osv.osv):
    """ DBE Vendor """
    _name = "dbe.vendor"
    _description = "DBE Vendor Entity"
    #_rec_name = 'vendor'
    _order = 'company'
    _log_access = True

    def _eth_codes(self, cr, uid, context=None):
        return _ethnicities

    def _bus_types(self, cr, uid, context=None):
        return _business_types

    def _company_classes(self, cr, uid, context=None):
        classes = (('01', 'RETAIL'),
                   ('02', 'SERVICE'),
                   ('03', 'CONSTRUCTION'),
                   ('04', 'PROFESSIONAL (A/E)'),
                   ('05', 'PROFESSIONAL (OTHER)'),
                   ('06', 'MANUFACTURING'),
                   ('07', 'DISTRIBUTOR'),
                   ('08', 'WHOLESALER'),
                   ('09', 'MATERIAL SUPPLIER'),
                   ('10', 'OTHER'))
        return classes

    def _gross_average(self, cr, uid, ids, field, arg, context):
        """Compute the 3 year gross average income"""
        if not ids: return {}
        res = {}
        for i in ids:
            res[i] = [0.00]
            sql_req = """
      SELECT 
        round((v.gross1 + v.gross2 + v.gross3)/3, 2) AS gaverage
      FROM 
        dbe_vendor v
      WHERE
        (v.id = %d)
      """ % (i,)

            cr.execute(sql_req)
            sql_res = cr.dictfetchone()
            res[i] = sql_res['gaverage'] or 0.00

        return res

    _columns = {
        'vendor_id': fields.integer('Vendor Id'),
        'dbe_qualifications': fields.boolean('Meets DBE Qualifications', help="Vendor meets federal DBE requirements"),
        'company': fields.char('Company', size=255, translate=False, required=True, readonly=False),
        'taxnum': fields.char('Tax Number', size=10, translate=False, required=True, readonly=False),
        'septa_vendor_id': fields.char('SEPTA Vendor Id', size=20, translate=False, required=True, readonly=False),
        'req_date': fields.date('Request Date', required=False, readonly=False),
        'duns_num': fields.char('D-U-N-S Number', size=9, translate=False, required=False, readonly=False),
        'pa_ucp': fields.boolean('In PA UCP'),
        'arra_approved': fields.boolean('ARRA Approval'),
        'ccr_registered': fields.boolean('CCR Registered'),
        'w9_classification': fields.selection(_bus_types, 'W9 Classification', help="IRS tax classification."),
        'note': fields.text('Notes'),
        'description': fields.text('Description'),
        'vuid': fields.many2one('res.users', 'Vendor User Id', help="System user account for client-side access."),
        'contacts': fields.one2many('dbe.vendor.contact', 'vendor_id', 'Contact'),
        'commodities': fields.many2many('commodity.commodity', 'vendor_to_commodity', 'vendor_id', 'commodity_id',
                                        'Commodity'),
        'naics': fields.many2many('naics.code', 'vendor_to_naics', 'rel_vendor_id', 'rel_naics_id', 'NAICS'),
        'application': fields.one2many('dbe.application', 'vendor_id', 'Application'),
        'certification': fields.one2many('dbe.certification', 'vendor_id', 'Certification'),
        'ethnicity': fields.selection(_eth_codes, 'Ethnicity',
                                      help="Select ethnic group membership of majority owner."),
        'gender': fields.selection([('F', 'Female'), ('M', 'Male')], 'Gender', help="Select gender of majority owner."),
        'active': fields.boolean('Active'),
        'established': fields.char('Year Established', size=4, translate=False, required=False, readonly=False,
                                   help="Year company initially went into business."),
        'owned_since': fields.date('Ownership Acquired', required=False, readonly=False,
                                   help="Date current vendor assumed ownership of company."),
        'comp_class': fields.selection(_company_classes, 'Company Class', help="Select vendor company class."),
        'year1': fields.char('1st Year', size=4, translate=False, required=False, readonly=False,
                             help="1st year receipt."),
        'gross1': fields.float('Gross Receipt 1', digits=(8, 2), required=False, readonly=False,
                               help="1st year gross receipt amount"),
        'year2': fields.char('2nd Year', size=4, translate=False, required=False, readonly=False,
                             help="2nd year receipt."),
        'gross2': fields.float('Gross Receipt 2', digits=(8, 2), required=False, readonly=False,
                               help="2nd year gross receipt amount"),
        'year3': fields.char('3rd Year', size=4, translate=False, required=False, readonly=False,
                             help="3rd year receipt."),
        'gross3': fields.float('Gross Receipt 3', digits=(8, 2), required=False, readonly=False,
                               help="3rd year gross receipt amount"),
        'gross_average': fields.function(_gross_average, string='3 Year Average', type='float', readonly=True),
        'write_date': fields.date('Last Update', required=False, readonly=True),
        'write_uid': fields.many2one('res.users', 'Updated', readonly=True),
    }

    _defaults = {
        'active': lambda *a: True,
        'gross1': lambda *a: 0.00,
        'gross2': lambda *a: 0.00,
        'gross3': lambda *a: 0.00,
        'req_date': fields.date.context_today,
    }

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = []
        for record in self.browse(cr, uid, ids, context=context):
            name = record.company
            res.append((record.id, name))

        return res

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name: # There is no field for Name so instead we search for company or SEPTA vendor id.
            ids = self.search(cr, user, [('company', '=', name)] + args, limit=limit, context=context)
            if not ids: # If no equals match then use like.
                ids = self.search(cr, user, [('company', operator, name)] + args, limit=limit, context=context)
            if not ids: # Maybe the SEPTA vendor id is what they wanted.
                ids = self.search(cr, user, [('septa_vendor_id', '=', name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
            # Return the proper value for Name in the search results.
        result = self.name_get(cr, user, ids, context=context)
        return result


dbe_vendor()


class dbe_contact_category(osv.osv):
    """ DBE Document Category """
    _name = 'dbe.contact.category'
    _description = 'DBE Contact Category'
    _auto = True
    _order = 'name'
    #_rec_name = 'contact_category'
    _log_access = False
    _columns = {
        'name': fields.char('Document Type', size=50, translate=False, required=True, readonly=False),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: True,
    }


dbe_contact_category()


class dbe_job_position(osv.osv):
    """ DBE Document Category """
    _name = 'dbe.job.position'
    _description = 'DBE Job Position'
    _auto = True
    _order = 'name'
    #_rec_name = 'job_position'
    _log_access = False
    _columns = {
        'name': fields.char('Position', size=50, translate=False, required=True, readonly=False),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: True,
    }


dbe_job_position()


class vendor_contact(osv.osv):
    """ DBE Vendor Contact """
    _name = 'dbe.vendor.contact'
    _description = 'DBE Vendor Contact'
    _auto = True
    #_rec_name = 'vendor_contact'
    _order = 'name'
    _log_access = True

    #def _eth_codes(self, cr, uid, context=None):
    #eth_dict = dict((x, y) for x, y in _ethnicities)
    #contacts = self.browse(cr, uid, ids)
    #for contact in contacts:
    #if contact.ethnicity == 'O':
    #other = contact.other_ethnicity
    #eth_dict['O'] = other

    #return eth_dict.items()

    def _getTypes(self, cr, uid, context=None):
        return (
            ('company', 'Company'),
            ('organization', 'Organization'),
            ('personal', 'Personal'),
            ('shipping', 'Shipping'),
            ('owner', 'Owner'),
            ('partner', 'Partner'),
            ('mailing', 'Mailing'),
            ('department', 'Department'),
            ('other', 'Other'))

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        return super(vendor_contact, self).create(cr, uid, vals, context=context)

    _columns = {
        'vendor_id': fields.many2one('dbe.vendor', 'Vendor', ondelete='cascade', required=False, readonly=False),
        'contact_type': fields.selection(_getTypes, 'Contact Type', help="Type of contact."),
        'name': fields.char('Name', size=128, translate=False, required=True, readonly=False),
        'title': fields.many2one('res.partner.title', 'Title'),
        'position': fields.many2one('dbe.job.position', 'Job Position', required=True,
                                    help="Position within vendor company."),
        'address1': fields.char('Address', size=128, translate=False, required=False, readonly=False),
        'address2': fields.char('', size=128, translate=False, required=False, readonly=False),
        'city': fields.char('City', size=128, translate=False, required=True, readonly=False),
        'state_id': fields.many2one('res.country.state', 'State'),
        'zip': fields.char('Zip', change_default=True, size=24),
        'country_id': fields.many2one('res.country', 'Country'),
        'email': fields.char('Email', size=220),
        'phone1': fields.char('Office', size=64),
        'ext': fields.char('Extension', size=10),
        'phone2': fields.char('Cell', size=64),
        'fax': fields.char('Fax', size=64),
        'website': fields.char('Web Address', size=256, help="Internet address of company website."),
        'attention': fields.char('Attention', size=50),
        'note': fields.text('Notes:'),
        'ethnicity': fields.selection(_ethnicities, 'Ethnicity', help="Select ethnic group membership of contact."),
        'gender': fields.selection([('F', 'Female'), ('M', 'Male')], 'Gender', help="Select gender of contact."),
        'own_percent': fields.char('Owning Percentage', size=4,
                                   help="Percentage of company controlled if contact is an owner."),
        'active': fields.boolean('Active'),
        #'other_ethnicity':fields.char('Other Ethnicity', size=64),
    }
    _defaults = {
        'active': lambda *a: True,
        'own_percent': lambda *a: "N/A",
        'country_id': 235,
    }

    def _email_send(self, cr, uid, ids, email_from, subject, body, on_error=None):
        contacts = self.browse(cr, uid, ids)
        for contact in contacts:
            if contact.email:
                tools.email_send(email_from, [contact.email], subject, body, on_error)
        return True

    def email_send(self, cr, uid, ids, email_from, subject, body, on_error=''):
        while len(ids):
            self.pool.get('ir.cron').create(cr, uid, {
                'name': 'Send Vendor Emails',
                'user_id': uid,
                'model': 'dbe.vendor.contact',
                'function': '_email_send',
                'args': repr([ids[:16], email_from, subject, body, on_error])
            })
            ids = ids[16:]
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        name = self.read(cr, uid, [id], ['name'], context)[0]['name']
        default.update({'name': _('%s (copy)') % name})
        return super(vendor_contact, self).copy(cr, uid, id, default, context)

    def onchange_state(self, cr, uid, ids, state_id, context=None):
        if state_id:
            country_id = self.pool.get('res.country.state').browse(cr, uid, state_id, context).country_id.id
            return {'value': {'country_id': country_id}}
        return {}


vendor_contact()


class dbe_certification_history(osv.osv):
    """ DBE Certification History """
    _name = 'dbe.certification.history'
    _description = 'DBE Certification History'
    _auto = True
    #_rec_name = 'cert_history'
    _order = 'write_date desc'
    _log_access = True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        return super(dbe_certification_history, self).create(cr, uid, vals, context=context)


    _columns = {
        'certification_id': fields.many2one('dbe.certification', 'Certification Id', ondelete='cascade', required=False,
                                            readonly=False),
        'current_status': fields.char('Current Status', size=25, translate=False, required=True, readonly=True),
        'certification_date': fields.date('Certification Date', required=False, readonly=True),
        'anniversary_date': fields.date('Anniversary Date', required=False, readonly=True),
        'dbe_specialist': fields.many2one('res.users', 'DBE Specialist', readonly=True),
        'dbe_manager': fields.many2one('res.users', 'DBE Manager', readonly=True),
        'transaction_type': fields.char('Action', size=25, translate=False, required=True, readonly=True),
        'write_date': fields.date('Last Updated', required=False, readonly=True),
        'write_uid': fields.many2one('res.users', 'Updated', readonly=True),
    }


dbe_certification_history()


class dbe_certification(osv.osv):
    """ DBE Certification """
    _inherit = ['mail.thread', 'dbe.certification.rules', 'dbe.certification.workflow']
    _name = 'dbe.certification'
    _description = 'DBE Certification'
    _auto = True
    _order = 'certification_date'
    _log_access = True

    def _nextyear(self, dt):
        """ Add one year to a datetime allowing for leap years """
        try:
            nextyear = dt.replace(year=dt.year + 1)
        # leap year correction
        except ValueError:
            # Add 365 days to adjust for Feb. 29th
            nextyear = dt + timedelta(days=365)

        return nextyear

    def create(self, cr, uid, vals, context=None):
        """ create Certification records """
        if context is None:
            context = {}
            # compute anniversary date from certification_date
        if 'certification_date' in vals:
            cd = self._nextyear(datetime.datetime.strptime(vals.get('certification_date'), "%Y-%m-%d %H:%M:%S"))
            vals['anniversary_date'] = cd

        return super(dbe_certification, self).create(cr, uid, vals, context=context)

    def _create_certification_history(self, cr, uid, ids, vals, context):
        """ Creates new certification history objects """
        current_certification = self.browse(cr, uid, ids, context=context)[0]
        # we are only working with a single record here
        vals['certification_id'] = current_certification.id
        vals['current_status'] = current_certification.status
        vals['certification_date'] = current_certification.certification_date
        vals['anniversary_date'] = current_certification.anniversary_date
        vals['dbe_specialist'] = current_certification.dbe_specialist.id
        vals['dbe_manager'] = current_certification.dbe_manager.id
        # get certification history object and call its create
        _logger.debug("Certification history create called with ids %s and vals %s", str(ids), str(vals))
        history_id = self.pool.get('dbe.certification.history').create(cr, uid, vals, context=context)
        return history_id

    def _transaction_history(func):
        """ Decorator function for historical logging of transactions """

        @functools.wraps(func) # ensuring we still have a name after wrapping
        def wrapped(self, cr, uid, ids, vals, context={}):
            history_id = None
            func_name = func.__name__
            # if the wrapped function name matches a transaction type create a corresponding history record
            if func_name in _transaction_types.keys():
                vals_copy = vals.copy()
                vals_copy['transaction_type'] = _transaction_types[func_name]
                history_id = self._create_certification_history(cr, uid, ids, vals_copy, context)

            if history_id:
                _logger.debug("Certification history created for transaction type %s with record #%d",
                              _transaction_types[func_name], history_id)
                # call wrapped function without explicit self
            return func(self, cr, uid, ids, vals, context)

        return wrapped

    _columns = {
        'vendor_id': fields.many2one('dbe.vendor', 'Vendor Id', ondelete='cascade', required=False, readonly=True),
        'company': fields.related('vendor_id', 'company', string="Company", type='char', relation='dbe.vendor',
                                  readonly=True),
        'status': fields.selection([('decertified', 'Decertified'),
                                    ('certified', 'Certified')],
                                   'Certification Status',
                                   help="Status of DBE Certification",
                                   track_visibility='onchange'),
        'certification_number': fields.char('SEPTA Cert. Number', size=25, translate=False, required=False,
                                            readonly=False),
        'paucp_cert_number': fields.char('PAUCP Cert. Number', size=25, translate=False, required=False,
                                         readonly=False),
        'certification_type': fields.selection([('sbe', 'SBE'), ('dbe', 'DBE')], 'Certification Type',
                                               help="Select DBE or SBE certification type (Select DBE if both certifications)."),
        'certifier': fields.selection([('s', 'SEPTA'), ('o', 'Other')], 'Certifier',
                                      help="Source of DBE Certification"),
        'certification_date': fields.date('Certification Date', required=False, readonly=True),
        'anniversary_date': fields.date('Anniversary Date', required=False, readonly=True),
        'dbe_specialist': fields.many2one('res.users', 'DBE Specialist', readonly=True),
        'dbe_manager': fields.many2one('res.users', 'Verifying Manager', readonly=True),
        'history': fields.one2many('dbe.certification.history', 'certification_id', 'Certification History'),
        'documents': fields.one2many('dbe.document', 'certification_id', 'DBE Documentation'),
        'onsite_report': fields.one2many('dbe.onsite.visit', 'certification_id', 'Onsite Visit Report'),
        'active': fields.boolean('Active'),
        'write_date': fields.date('Last Updated', required=False, readonly=True),
        'write_uid': fields.many2one('res.users', 'Updated', readonly=True),
    }
    _defaults = {
        'active': lambda *a: True,
        'certification_type': lambda *a: "dbe",
        'status': lambda *a: "certified",
        'certifier': lambda *a: "s",
    }

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = []
        for record in self.browse(cr, uid, ids, context=context):
            name = record.company
            res.append((record.id, name))

        return res

    @_transaction_history
    def write(self, cr, uid, ids, vals, context=None):
        """ update data for Certification record """
        _logger.debug("Certification WRITE() called with ids %s and vals %s", str(ids), str(vals))

        return super(dbe_certification, self).write(cr, uid, ids, vals, context=context)

    @_transaction_history
    def certify(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'status': 'certified'}, context=context)

    @_transaction_history
    def decertify(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'status': 'decertified'}, context=context)


dbe_certification()


class dbe_application_history(osv.osv):
    """ DBE Application History """
    _name = 'dbe.application.history'
    _description = 'DBE Application History'
    _auto = True
    #_rec_name = 'app_history'
    _order = 'write_date desc'
    _log_access = True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        return super(dbe_application_history, self).create(cr, uid, vals, context=context)

    _columns = {
        'application_id': fields.many2one('dbe.application', 'Application Id', ondelete='cascade', required=True,
                                          readonly=True),
        'current_status': fields.char('Status', size=25, translate=False, required=False, readonly=True),
        'completion': fields.integer('Completed', required=False, readonly=True),
        'dbe_specialist': fields.many2one('res.users', 'DBE Specialist', readonly=True),
        'note': fields.text('Notes', required=False, readonly=True),
        'onsite_visit_date': fields.date('Onsite Visit Date', required=False, readonly=False),
        'onsite_visit_notes': fields.text('Visit Notes', readonly=True),
        'visit_approved': fields.boolean('Onsite Visit Approved', required=False, readonly=True),
        'docs_completed': fields.boolean('All Documents Approved', required=False, readonly=True),
        '90_days_flag': fields.boolean('90 Day Warning', readonly=True),
        'write_uid': fields.many2one('res.users', 'Last Change User', readonly=True),
        'write_date': fields.date('Last Update', required=True, readonly=True),
        'transaction_type': fields.char('Action', size=25, translate=False, required=True, readonly=True),
    }


dbe_application_history()


class dbe_application(osv.osv):
    """ DBE Application """
    _inherit = ['mail.thread', 'dbe.application.rules', 'dbe.application.workflow']
    _name = 'dbe.application'
    _description = 'DBE Application'
    _auto = True
    #_rec_name = 'application'
    _order = 'id asc'
    _log_access = True
    vals = {}

    def _getStates(self, cr, uid, context=None):
        return (
            ('new', 'New'),
            ('pend', 'Pending: Review'),
            ('pend-approve', 'Pending: Approval'),
            ('withdraw', 'Withdraw'),
            ('approve', 'Certified'),
            ('denied', 'Denied'))

    def _create_application_history(self, cr, uid, ids, vals, context=None):
        """ Creates new application history objects """
        current_application = self.browse(cr, uid, ids, context=context)[0]
        # we are only working with a single record here
        vals['application_id'] = current_application.id
        vals['current_status'] = current_application.state
        vals['completion'] = current_application.completion
        vals['note'] = current_application.note
        # get id from the ORM browse record since ORM can't recognize its own objects
        vals['dbe_specialist'] = current_application.dbe_specialist.id
        vals['onsite_visit_date'] = current_application.onsite_visit_date
        vals['onsite_visit_notes'] = current_application.onsite_visit_notes
        vals['visit_approved'] = current_application.visit_approved
        vals['docs_completed'] = current_application.docs_completed
        # get application history object and call its create
        _logger.debug("Application history create called with ids %s and vals %s", str(ids), str(vals))
        history_id = self.pool.get('dbe.application.history').create(cr, uid, vals, context=context)
        return history_id

    def _transaction_history(func):
        """ Decorator function for historical logging of transactions
        if the passed function name matches a transaction type a history record is created
        @param accepts a regular function object
        @return function
        """

        @functools.wraps(func) # ensuring we still have a name after wrapping
        def wrapped(self, cr, uid, ids, vals, context={}):
            history_id = None
            func_name = func.__name__
            # if the wrapped function name matches a transaction type create a corresponding history record
            if func_name in _transaction_types.keys():
                vals_copy = vals.copy()
                vals_copy['transaction_type'] = _transaction_types[func_name]
                history_id = self._create_application_history(cr, uid, ids, vals_copy, context)

            if history_id:
                _logger.debug("Application history created for transaction type %s with record #%d",
                              _transaction_types[func_name], history_id)
                # call wrapped function without explicit self
            return func(self, cr, uid, ids, vals, context)

        return wrapped


    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        new_vendor_id = vals.get('vendor_id', False)
        if new_vendor_id:
            _logger.debug("Application created for vendor #%d by user %d", new_vendor_id, uid)
            return super(dbe_application, self).create(cr, uid, vals, context=context)
        else:
            raise osv.except_osv(_('ValidateError'),
                                 _('An Application cannot be created without selecting a Vendor - Vendor Id missing!'))

        return True

    _columns = {
        'vendor_id': fields.many2one('dbe.vendor', 'Vendor', ondelete='cascade', required=False, readonly=False),
        'vendor_name': fields.related('vendor_id', 'company', type="char", relation='dbe.vendor', string="Vendor",
                                      store=False),
        'intake_date': fields.date('Review Begin', required=True, states={'new': [('readonly', True)],
                                                                          'withdraw': [('readonly', True)],
                                                                          'pend-approve': [('readonly', True)],
                                                                          'approve': [('readonly', True)],
                                                                          'pend': [('readonly', True)]},
                                   help="This is the date that application review begins. All future deadlines are computed from this date."),
        'state': fields.selection(_getStates, 'Curent Status', readonly=True, select=True, track_visibility='onchange'),
        'completion': fields.integer('Completed', required=False, readonly=False,
                                     help="Completion must be 100% before the application can be approved."),
        'dbe_specialist': fields.many2one('res.users', 'DBE Specialist', track_visibility='onchange',
                                          help="The Specialist assigned to review the application."),
        'note': fields.text('Notes', readonly=False),
        'onsite_visit_date': fields.date('Onsite Visit Date', required=False, readonly=False,
                                         help="Date of onsite review and interview."),
        'onsite_visit_notes': fields.text('Visit Notes', readonly=False,
                                          help="Enter the outcome of the interview and info regarding the notification letter. Also include info regarding any related appeals and corresponding dates."),
        'visit_approved': fields.boolean('Onsite Visit Approved', readonly=False,
                                         help="The Onsite Visit must be approved before the application can be approved."),
        'documents': fields.one2many('dbe.document', 'application_id', 'DBE Documentation'),
        'onsite_report': fields.one2many('dbe.onsite.visit', 'application_id', 'Onsite Visit Report'),
        'docs_completed': fields.boolean('Documents Approved', readonly=False,
                                         help="All vendor submitted documentation has been reviewed and approved."),
        '90_days_flag': fields.boolean('90 Day Warning', readonly=False),
        'messages': fields.many2one('dbe.messages', 'DBE Message History'),
        'history': fields.one2many('dbe.application.history', 'application_id', 'Application History'),
        'verifier': fields.many2one('res.users', 'Verified', states={'new': [('readonly', True)],
                                                                     'withdraw': [('readonly', True)],
                                                                     'approve': [('readonly', False)],
                                                                     'pend': [('readonly', True)]},
                                    required=False,
                                    track_visibility='onchange',
                                    help="The application approval must be verified by a DBE Manager before the Certification is created."),
        'verified_date': fields.datetime('Date Verified', required=False, states={'new': [('readonly', True)],
                                                                                  'withdraw': [('readonly', True)],
                                                                                  'approve': [('readonly', False)],
                                                                                  'pend': [('readonly', True)]},
                                         help="The application approval must be verified by a DBE Manager before the Certification is created."),
        'write_date': fields.date('Last Update', required=False, readonly=True),
        'write_uid': fields.many2one('res.users', 'Updated', readonly=True),
        'active': fields.boolean('Active'),
        'certification_type': fields.selection([('sbe', 'SBE'), ('dbe', 'DBE')], 'Certification Type',
                                               help="Select DBE or SBE certification type (Select DBE if both certifications)."),
    }

    _defaults = {
        'active': lambda *a: True,
        'state': lambda *a: 'new',
        'intake_date': lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = []
        for record in self.browse(cr, uid, ids, context=context):
            name = record.vendor_name
            res.append((record.id, name))

        return res

    @_transaction_history
    def app_new(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'state': 'new'}, context=context)

    @_transaction_history
    def app_pend(self, cr, uid, ids, vals, context):
        date_format = "%Y-%m-%d %H:%M:%S"
        now = datetime.datetime.now()
        return self.write(cr, uid, ids,
                          {'state': 'pend', 'intake_date': now.strftime(date_format), '90_days_flag': True},
                          context=context)

    @_transaction_history
    def app_withdraw(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'state': 'withdraw'}, context=context)

    @_transaction_history
    def app_pend_approve(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'state': 'pend-approve'}, context=context)

    @_transaction_history
    def app_approve(self, cr, uid, ids, vals, context):
        """ Setting the application record state to 'approve' from form action """
        app_record = self.browse(cr, uid, ids, context=context)[0]
        onsite_approved = app_record.visit_approved
        completed = app_record.completion
        if completed and onsite_approved:
            return self.write(cr, uid, ids, {'state': 'approve'}, context)
        else:
            raise osv.except_osv(_('ValidateError'), _('Completion must 100% and Onsite Visit must be approved!'))
            return False

        return True


    @_transaction_history
    def app_deny(self, cr, uid, ids, vals, context):
        return self.write(cr, uid, ids, {'state': 'denied'}, context=context)

    def _create_certification(self, cr, uid, ids, vals, context=None):
        """ Creates Certification when Application approved and verified """
        existing_certification = None
        current_application = self.browse(cr, uid, ids, context=context)[0]
        vendor_id = current_application.vendor_id.id
        #existing_certification = self.pool.get('dbe.certification').search(cr, uid, [('vendor_id', '=', vendor_id)], order=None, limit=1, context=context)
        if not existing_certification:
            if not vals.get('verifier'):
                verifier = current_application.verifier.id
            else:
                verifier = vals.get('verifier')

            cert_vals = {'vendor_id': vendor_id,
                         'certifier': 's',
                         'status': 'certified',
                         'dbe_manager': verifier,
                         'dbe_specialist': current_application.dbe_specialist.id,
                         'certification_date': vals.get('verified_date'),
                         'certification_type': current_application.certification_type,
                         'anniversary_date': False,
                         'active': True,
            }
            existing_certification = self.pool.get('dbe.certification').create(cr, uid, cert_vals, context=context)
        else:
            existing_certification = None

        if existing_certification is not None:
            _logger.debug("Application WRITE() created new certification for vendor id %s", str(vendor_id))
            return True

        return False

    @_transaction_history
    def write(self, cr, uid, ids, vals, context=None):
        """ update data for Application record """
        #_logger.debug("Application WRITE() called with ids %s and vals %s", str(ids), str(vals))
        #lets see if it is time to generate a new certification
        if 'current_status' in vals:
            current_status = vals.get('current_status')
        else:
            current_status = self.browse(cr, uid, ids, context=context)[0].state

        _logger.debug("Application WRITE() current_status = %s", str(current_status))
        if current_status == 'approve' and vals.get('verified_date') and vals.get('verifier'):
            cert = self._create_certification(cr, uid, ids, vals, context)
            if not cert:
                raise osv.except_osv(_('ValidateError'), _('New Certification not created!'))

        return super(dbe_application, self).write(cr, uid, ids, vals, context=context)


    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}

        default.update({
            'state': 'new',
            'completion': 0,
            'history': [],
            'verifier': [],
            'active': True,
            'docs_completed': False,
            'visit_approved': False,
            '90_days_flag': False,
            'verified_date': False,
            'onsite_visit_date': False,
        })
        return super(dbe_application, self).copy(cr, uid, id, default, context)

    def onchange_verifier(self, cr, uid, ids, verifier, context=None):
        date_format = "%Y-%m-%d %H:%M:%S"
        now = datetime.datetime.now()
        return {'value': {'verified_date': now.strftime(date_format)}}


dbe_application()


class dbe_document_category(osv.osv):
    """ DBE Document Category """
    _inherit = 'mail.thread'
    _name = 'dbe.document.category'
    _description = 'DBE Document Category'
    _order = 'name'
    #_rec_name = 'document_category'
    _log_access = False
    _columns = {
        'name': fields.char('Document Type', size=128, translate=False, required=True, readonly=False),
        'description': fields.char('Description', size=256, translate=False, required=False, readonly=False),
        'active': fields.boolean('Active'),
        'association': fields.selection([('application', 'Application'),
                                         ('certification', 'Certification'),
                                         ('other', 'Other')],
                                        'Category Relationship',
                                        help="Select whether the document category pertains to Certifications or Applications. Choose Other if neither applies.",
        ),
        'required': fields.boolean('Mandatory'),
    }
    _defaults = {
        'active': lambda *a: True,
    }


dbe_document_category()


class dbe_document_index(osv.osv):
    """ DBE Document Index """
    _name = 'dbe.document.index'
    _description = 'DBE Document Index'
    _order = 'name'
    _log_access = True
    
    def create(self, cr, uid, vals, context=None):
      if context is None:
          context = {}
          
      _logger.debug("<CREATE INDEX> DBE Document Index create called for category %d", vals['type_of'])
      return super(dbe_document_index, self).create(cr, uid, vals, context=context)
    
    _columns = {
        'name': fields.char('Document Type', size=128, translate=False, required=True, readonly=False),
        'category': fields.many2one('dbe.document.category', 'Document Category', required=True),
        'complete': fields.boolean('complete'),
        'required': fields.boolean('Mandatory'),
        'application_id': fields.many2one('dbe.application', 'Application Id', ondelete='cascade', required=False,
                                          readonly=False),

    }
    _defaults = {
        'complete': lambda *a: False,
    }


dbe_document_index()


class dbe_document(osv.osv):
    """ DBE Document """
    _inherit = ['ir.attachment', 'mail.thread']
    _name = 'dbe.document'
    _description = 'DBE Document'
    _auto = True
    #_rec_name = 'dbe_document'
    _order = 'vendor_id'
    _log_access = True

    def _getStates(self, cr, uid, context=None):
        return (
            ('new', 'New'),
            ('pend', 'Review'),
            ('reject', 'Rejected'),
            ('approve', 'Approved'))

    def create_index(self, cr, uid, vals, doc_id, context=None):
        res = None
        association_id = self.read(cr, uid, doc_id, ['application_id'], context=context) 
        if association_id['application_id']:
            app_id = association_id['application_id']
            category_id = vals['type_of']
            category_object = self.pool.get('dbe.document.category')
            category = category_object.browse(cr, uid, category_id)
            if category.active and category.association == 'application':
                index_object = self.pool.get('dbe.document.index')
                index_ids = index_object.search(cr, uid, [('application_id', '=', app_id),
                                                          ('category', '=', category.id)])
                if not index_ids:
                    res = index_object.create(cr, uid, {
                        'name': 'V-' + str(vals['vendor_id']) + '-A-' + str(app_id) + '-C-' + category.name,
                        'application_id': app_id,
                        'required': category.required,
                        'category': category.id,
                    }, context=context)

        _logger.debug("<CREATE> DBE Document Index called for document #%d for category %d", doc_id, vals['type_of'])
        return res


    _columns = {
        'application_id': fields.many2one('dbe.application', 'Application Id', ondelete='cascade', required=False,
                                          readonly=False),
        'certification_id': fields.many2one('dbe.certification', 'Certification Id', ondelete='cascade', required=False,
                                            readonly=False),
        'state': fields.selection(_getStates, 'Status', track_visibility='onchange'),
        'type_of': fields.many2one('dbe.document.category', 'Document Category', required=True),
        'category_description': fields.related('type_of',
                                               'description',
                                               type="char",
                                               relation='dbe.document.category',
                                               string="Category Description",
                                               store=False,
                                               readonly=True),
        'note': fields.text('Notes'),
        'vendor_id': fields.many2one('dbe.vendor', 'Vendor', ondelete='cascade', required=False, readonly=False),
        'locked': fields.boolean('Lock'),
    }

    _defaults = {
        'state': lambda *a: 'new',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        docs = self.browse(cr, uid, ids, context=context)
        for doc in docs:
            if doc.locked:
                if doc.id in ids:
                    ids.remove(doc.id)

        return super(dbe_document, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        """Creates a new dbe.document instance. Called by both internal app and client.
           documents are associated to dbe.vendor, dbe.application and dbe.certification.
        @param vals: All dbe.document field values as a dictionary.
        @return ID of new dbe.document instance.
        """
        if context is None:
            context = {}
        _logger.debug("<CREATE> DBE Document context: %s", str(context))
        doc_id = None
        association_id = None
        # vendor_id is passed with vals when documents are created from the client side.
        new_vendor_id = vals.get('vendor_id', False)
        if new_vendor_id:
            doc_id = super(dbe_document, self).create(cr, uid, vals, context=context)
            _logger.debug("<CREATE> DBE Document (%d) created for vendor #%d by user %d", doc_id, new_vendor_id, uid)
        else: # within OpenERP we cannot get vendor_id from context so we do it caveman style.
            doc_id = super(dbe_document, self).create(cr, uid, vals, context=context)
            association_id = self.read(cr, uid, doc_id, ['application_id', 'certification_id'], context=context)
            if association_id['application_id']:
                application_id = association_id['application_id'][0]
                application_obj = self.pool.get('dbe.application')
                application = application_obj.browse(cr, uid, application_id)
                new_vendor_id = application.vendor_id.id
            elif association_id[
                'certification_id']: # since there is no application maybe its a certification related doc....
                certification_id = association_id['certification_id'][0]
                certification_obj = self.pool.get('dbe.certification')
                certification = certification_obj.browse(cr, uid, certification_id)
                new_vendor_id = certification.vendor_id.id
            else: # Documents not associated with either an Application or Certification are unacceptable.
                raise osv.except_osv(_('ValidateError'), _(
                    '<CREATE> A DBE Document cannot be created without an application or certification - Association Missing!'))

            if new_vendor_id: # brute-force association to dbe.vendor.
                vals.update({'vendor_id': new_vendor_id})
                self.write(cr, uid, doc_id, vals, context)

                _logger.debug("<CREATE> DBE Document (%d) created for vendor #%d by user %d", doc_id, new_vendor_id,
                              uid)

            else: # too bad - no vendor, no doc.
                _logger.debug("<CREATE> DBE Document (%d) removed because vendor_id missing for user %d", doc_id, uid)
                raise osv.except_osv(_('ValidateError'), _(
                    '<CREATE> A DBE Document cannot be created without selecting a Vendor - Vendor Id Missing!'))

        doc_index = self.create_index(cr, uid, vals, doc_id, context)
        if doc_index:
            _logger.debug("<CREATE> DBE Document Index (%d) created for vendor #%d by user %d", doc_index,
                          new_vendor_id,
                          uid)
        else:
            _logger.debug("<CREATE> DBE Document Index not created for vendor #%d by user %d", 
                          new_vendor_id,
                          uid)
        return doc_id

    def doc_new(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {'state': 'new'}, context=context)

    def doc_pend(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {'state': 'pend'}, context=context)

    def doc_reject(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {'state': 'reject'}, context=context)

    def doc_approve(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {'state': 'approve', 'locked': True}, context=context)


dbe_document()


class dbe_onsite_visit(osv.osv):
    """ DBE Site Visit Report """
    version = '02/2011'
    _inherit = ['mail.thread']
    _name = 'dbe.onsite.visit'
    _description = 'DBE Site Visit Report'
    _auto = True
    _order = 'visit_date'
    _log_access = True

    def _next_visit(self, dt):
        nextvisit = dt.replace(year=dt.year + 6)

        return nextvisit

    _columns = {
        'vendor_id': fields.many2one('dbe.vendor', 'Vendor', ondelete='cascade', required=False, readonly=False),
        'vendor_name': fields.related('vendor_id', 'company', type="char", relation='dbe.vendor', string="Vendor",
                                      store=False),
        'visit_date': fields.date('Visit Date', required=True, readonly=False,
                                  help="This is the date that the on-site visit was conducted."),
        'followup_date': fields.date('Next Visit Date', required=False, readonly=False,
                                     help="This is the date of the next follow-up on-site visit."),
        'recommended': fields.selection([('certify', 'Certify'), ('deny', 'Deny'), ('other', 'Other')],
                                        'Recommendation',
                                        help="Result of on-site visit."),
        'note': fields.text('Justification of Recommendation'),
        'location': fields.char('Place of On-site Visit', size=256, translate=False, required=False, readonly=False,
                                help="Location of On-site Visit."),
        'revision': fields.char('Report Version', size=20),
        'applicants': fields.many2many('dbe.vendor.contact', 'onsite_to_contact', 'rel_onsite_id', 'rel_contact_id',
                                       'Applicant(s)'),
        'dbe_specialist': fields.many2one('res.users', 'Reviewer', required=True,
                                          help="The Specialist assigned to conduct the On-site visit."),
        'reason': fields.selection(
            [('application', 'Initial Application'), ('followup', 'Follow-Up'), ('status', 'Status Change'),
             ('other', 'Other')], 'Reason', help="Reason for on-site visit."),
        'origin': fields.char('Source of Report', size=256, translate=False, required=False, readonly=False,
                              help="Agency that originated this on-site visit report."),
        'questions': fields.text('Questions'),
        'active': fields.boolean('Active'),
        'write_date': fields.date('Last Update', required=False, readonly=True),
        'write_uid': fields.many2one('res.users', 'Updated', readonly=True),
        'application_id': fields.many2one('dbe.application', 'Application Id', ondelete='cascade', required=False,
                                          readonly=False),
        'certification_id': fields.many2one('dbe.certification', 'Certification Id', ondelete='cascade', required=False,
                                            readonly=False),

    }
    _defaults = {
        'active': lambda *a: True,
        'origin': lambda *a: 'SEPTA',
        'revision': version,
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        # compute followup visit date from visit_date.
        if not vals['followup_date']:
            cd = self._next_visit(datetime.datetime.strptime(vals.get('visit_date'), "%Y-%m-%d")) # %H:%M:%S
            vals['followup_date'] = cd

        report_id = None
        association_id = None
        new_vendor_id = vals.get('vendor_id', False)
        if new_vendor_id:
            report_id = super(dbe_onsite_visit, self).create(cr, uid, vals, context=context)
            _logger.debug("<CREATE> Site Visit Report (%d) created for vendor #%d by user %d", report_id, new_vendor_id,
                          uid)
            association_id = self.read(cr, uid, report_id, ['application_id', 'certification_id', 'reason'],
                                       context=context)
            if not association_id['application_id'] and not association_id['certification_id']:
                reason = association_id['reason']
                if reason == 'application':
                    application_obj = self.pool.get('dbe.application')
                    application = application_obj.search(cr, uid, [('vendor_id', '=', new_vendor_id),
                                                                   ('state', 'in', ['new', 'pend']),
                                                                   ('active', '=', 'True')], limit=1,
                                                         order='create_date DESC', context=context)
                    if application:
                        self.write(cr, uid, report_id, {'application_id': application[0]})
                    else:
                        raise osv.except_osv(_('ValidateError'), _(
                            '<CREATE> A Site Visit Report cannot be created without an active Application that is not yet approved (Check that you have set the REASON field to the correct value)!'))
                else:
                    certification_obj = self.pool.get('dbe.certification')
                    certification = certification_obj.search(cr, uid, [('vendor_id', '=', new_vendor_id),
                                                                       ('status', '=', 'certified'),
                                                                       ('active', '=', True)], 0, 1,
                                                             'certification_date DESC', context=context)
                    if certification:
                        self.write(cr, uid, report_id, {'certification_id': certification[0]})
                    else:
                        raise osv.except_osv(_('ValidateError'), _(
                            '<CREATE> A Site Visit Report cannot be created without an active Certification that is certified (Check that you have set the REASON field to the correct value)!'))

        else:
            report_id = super(dbe_onsite_visit, self).create(cr, uid, vals, context=context)
            association_id = self.read(cr, uid, report_id, ['application_id', 'certification_id'], context=context)
            if association_id['application_id']:
                application_id = association_id['application_id'][0]
                application_obj = self.pool.get('dbe.application')
                application = application_obj.browse(cr, uid, application_id)
                new_vendor_id = application.vendor_id.id
            elif association_id[
                'certification_id']: # since there is no application maybe its a certification related report....
                certification_id = association_id['certification_id'][0]
                certification_obj = self.pool.get('dbe.certification')
                certification = certification_obj.browse(cr, uid, certification_id)
                new_vendor_id = certification.vendor_id.id
            else: # Reports not associated with either an Application or Certification are unacceptable.
                raise osv.except_osv(_('ValidateError'), _(
                    '<CREATE> A Site Visit Report cannot be created without an application or certification - Association Missing!'))

            if new_vendor_id: # brute-force association to dbe.vendor.
                vals.update({'vendor_id': new_vendor_id})
                self.write(cr, uid, report_id, vals, context)
                _logger.debug("<CREATE> dbe_onsite_visit (%d) created for vendor #%d by user %d", report_id,
                              new_vendor_id, uid)
            else: # too bad - no vendor, no report.
                _logger.debug("<CREATE> dbe_onsite_visit (%d) removed because vendor_id missing for user %d", report_id,
                              uid)
                raise osv.except_osv(_('ValidateError'), _(
                    '<CREATE> A DBE Site Visit Report cannot be created without selecting a Vendor - Vendor Id Missing!'))

        return report_id


dbe_onsite_visit()

# coding=utf-8
# -*- encoding: utf-8 -*-

import glob
import itertools
import json
import operator
import os
import cStringIO
import urllib
import urllib2
import xmlrpclib
import zlib
import simplejson
import base64
import logging
from xml.etree import ElementTree
from simpletal import simpleTAL, simpleTALES
import werkzeug.utils
import werkzeug.wrappers
import openerp
from openerp.tools.translate import _

#from .. import http
import openerp.addons.web.http as septaweb

#septaweb = http
_logger = logging.getLogger(__name__)
# utility functions

_DB_NAME = 'dev_main'

def api_create(req, vid, model):
    Model = req.session.model(model)
    pass


def api_update(req, vid, model):
    Model = req.session.model(model)
    pass


def api_delete(req, vid, model):
    Model = req.session.model(model)
    pass


def fields_get(req, model):
    Model = req.session.model(model)
    fields = Model.fields_get(False, req.context)
    #_logger.debug('fields: %s', fields)
    return fields

#				 (req, 'dbe.vendor', ['id', 'company'], 0, False, [('vuid', '=', uid)], None)
def do_search_read(req, model, fields=False, offset=0, limit=False, domain=None, sort=None):
    """ Performs a search() followed by a read() (if needed) using the
	provided search criteria

	:param req: a JSON-RPC request object
	:type req: septaweb.JsonRequest
	:param str model: the name of the model to search on
	:param fields: a list of the fields to return in the result records
	:type fields: [str]
	:param int offset: from which index should the results start being returned
	:param int limit: the maximum number of records to return
	:param list domain: the search domain for the query
	:param list sort: sorting directives
	:returns: A structure (dict) with two keys: ids (all the ids matching
				the (domain, context) pair) and records (paginated records
				matching fields selection set)
	:rtype: list
	"""
    Model = req.session.model(model)

    ids = Model.search(domain, offset or 0, limit or False, sort or False,
                       req.context)
    if limit and len(ids) == limit:
        length = Model.search_count(domain, req.context)
    else:
        length = len(ids) + (offset or 0)
    if fields and fields == ['id']:
        # shortcut read if we only want the ids
        return {
            'length': length,
            'records': [{'id': id} for id in ids]
        }

    records = Model.read(ids, fields or False, req.context)
    records.sort(key=lambda obj: ids.index(obj['id']))
    return {
        'length': length,
        'records': records
    }


def newSession(req):
    """ create admin session for testing purposes only """
    db = 'dev_main'
    login = 'admin'
    password = 'openerp'
    uid = req.session.authenticate(db, login, password)
    return uid


def check_partner_parent(pid):
    res = None
    parent_id = None
    try:
        res = do_search_read(req, 'res.partner', ['active', 'parent_id'], 0, False, [('id', '=', pid)], None)
    except Exception:
        _logger.debug('Session expired or Partner not found for partner ID: %s', pid)

    if res:
        record = res['records'][0]
        if record['parent_id'] and record['active']:
            parent_id = record['parent_id']
        else:
            raise Exception("AccessDenied")
    else:
        return False

    return parent_id


def get_partner(req, pid):
    partner = None
    fields = fields_get(req, 'res.partner')
    try:
        partner = do_search_read(req, 'res.partner', fields, 0, False, [('id', '=', pid)], None)
    except Exception:
        _logger.debug('Partner not found for ID: %s', pid)

    if not partner:
        raise Exception("AccessDenied")

    return partner


def get_vendor_id(req, uid=None, **kwargs):
    """ Find the vendor associated to the current logged-in user """
    vendor_ids = None
    try:
        vendor_ids = do_search_read(req, 'dbe.vendor', ['id', 'company'], 0, False, [('vuid.id', '=', uid)], None)
    except Exception:
        _logger.debug('Session expired or Vendor not found for user ID: %s', uid)

    if not vendor_ids:
        raise Exception("AccessDenied")

    _logger.debug('Vendor ID: %s',
                  vendor_ids) #{'records': [{'company': u'Gomez Electrical Supply', 'id': 3}], 'length': 1}
    return vendor_ids


def get_partner_id(req, uid=None, **kwargs):
    """ Find the partner associated to the current logged-in user """
    partner_ids = None
    try:
        partner_ids = do_search_read(req, 'res.users', ['partner_id'], 0, False, [('id', '=', uid)], None)
    except Exception:
        _logger.debug('Session expired or Partner not found for user ID: %s', uid)

    if not partner_ids:
        raise Exception("AccessDenied")

    record = partner_ids['records'][0]
    pid = record['partner_id'][0]
    parent_id = check_partner_parent(pid)
    if parent_id:
        p = get_partner(parent_id)
        parent = p['records'][0]
        record['company'] = parent['name']
        record['company_id'] = parent['id']
        partner_ids['records'].append(record)
        partner_ids.pop(0)

    _logger.debug('Partner ID: %s',
                  partner_ids) #{'records': [{'groups_id': [3, 9, 19, 20, 24, 27], 'partner_id': (20, u'Partner'), 'id': 13, 'name': u'Partner'}], 'length': 1}
    return partner_ids


def get_contacts(req, vid, **kwargs):
    vendor_contacts = None
    fields = fields_get(req, 'dbe.vendor.contact')
    try:
        vendor_contacts = do_search_read(req, 'dbe.vendor.contact', fields, 0, False, [('vendor_id.id', '=', vid)],
                                         None)
    except Exception:
        _logger.debug('Vendor not found for vendor ID: %s', vid)

    if not vendor_contacts:
        raise Exception("AccessDenied")

    return vendor_contacts


def get_application(req, vid, **kwargs):
    vendor_application = None
    fields = fields_get(req, 'dbe.application')
    try:
        vendor_application = do_search_read(req, 'dbe.application', fields, 0, False, [('vendor_id.id', '=', vid)],
                                            None)
    except Exception:
        _logger.debug('application not found for vendor ID: %s', vid)

    if not vendor_application:
        raise Exception("AccessDenied")

    return vendor_application


def get_certification(req, vid, **kwargs):
    vendor_certification = None
    fields = fields_get(req, 'dbe.certification')
    try:
        vendor_certification = do_search_read(req, 'dbe.certification', fields, 0, False, [('vendor_id.id', '=', vid)],
                                              None)
    except Exception:
        _logger.debug('certification not found for vendor ID: %s', vid)

    if not vendor_certification:
        raise Exception("AccessDenied")

    return vendor_certification


def get_documents(req, vid, **kwargs):
    vendor_documents = None
    fields = fields_get(req, 'dbe.document')
    try:
        vendor_documents = do_search_read(req, 'dbe.document', fields, 0, False, [('vendor_id.id', '=', vid)], None)
    except Exception:
        _logger.debug('documents not found for vendor ID: %s', vid)

    if not vendor_documents:
        raise Exception("AccessDenied")

    return vendor_documents


def get_documents_by_id(req, vid, ids, all=False):
    vendor_documents = None
    if all:
        fields = fields_get(req, 'dbe.document')
    else:
        fields = ["create_date",
                  "state",
                  "type_of",
                  "name",
                  "description",
                  "id",
                  "vendor_id",
                  "application_id",
                  "certification_id",
                  "active",
                  "type_of",
                  "locked"]

    try:
        vendor_documents = do_search_read(req, 'dbe.document', fields, 0, False, [('id', 'in', ids)], None)
    except Exception:
        _logger.debug('documents not found for vendor ID: %s', vid)

    if not vendor_documents:
        raise Exception("AccessDenied")

    return vendor_documents

def get_document_indexes(req, vid, **kwargs):
    document_indexes = None
    fields = fields_get(req, 'dbe.document.index')
    applications = get_application(req, vid)['records']
    valid_apps = []
    if applications is not None:
        for application in applications:
            if application['docs_completed']:
                continue
            if application['active'] == False and application['state'] == 'new':
                valid_apps.append(application)

    if valid_apps and len(valid_apps) > 1:
        valid_apps.sort(cmp=lambda y, x: cmp(x['intake_date'], y['intake_date']))
        try:
            document_indexes = do_search_read(req, 'dbe.document.index', fields, 0, False, ['application_id',
                                                                                            '=',
                                                                                            valid_apps[0]['id']],
                                              None)
        except Exception:
            _logger.debug('document indexes not found for vendor ID: %s | application_id %s', vid, valid_apps[0]['id'])

    return document_indexes


def get_document_categories(req, vid, **kwargs):
    document_categories = None
    fields = fields_get(req, 'dbe.document.category')
    try:
        document_categories = do_search_read(req, 'dbe.document.category', fields, 0, False, [], None)
    except Exception:
        _logger.debug('documents not found for vendor ID: %s', vid)

    if not document_categories:
        raise Exception("AccessDenied")

    return document_categories


def get_messages(req, uid, **kwargs):
    vendor_messages = None
    pid = None
    fields = fields_get(req, 'mail.message')
    partner_ids = get_partner_id(req, uid)['records'][0]
    if partner_ids is not None:
        pid = partner_ids['partner_id'][0]
        try:
            vendor_messages = do_search_read(req, 'mail.message', fields, 0, False, [('partner_ids', 'in', pid)], None)
        except Exception:
            _logger.debug('messages not found for user ID: %d', uid)

    if not vendor_messages:
        raise Exception("AccessDenied")

    return vendor_messages


def get_stock_locations(req, pid, **kwargs):
    stock_locations = None
    fields = ['name', 'id', 'location_id', 'partner_id']
    try:
        stock_locations = do_search_read(req, 'stock.location', fields, 0, False, [], None)
    except Exception:
        _logger.debug('stock locations not found for partner ID: %d', pid)

    if not stock_locations:
        raise Exception("AccessDenied")
    _logger.debug('stock locations: %s', str(stock_locations['records']))
    return stock_locations


def get_onsite_reports(req, vid):
    onsite_reports = None
    fields = fields_get(req, 'dbe.onsite.visit')
    try:
        onsite_reports = do_search_read(req, 'dbe.onsite.visit', fields, 0, False, [('vendor_id.id', '=', vid)], None)
    except Exception:
        _logger.debug('onsite_reports not found for vendor ID: %d', vid)

    if not onsite_reports:
        raise Exception("AccessDenied")

    return onsite_reports


def get_vendor_data(req, vid):
    #import pdb; pdb.set_trace()
    vendor = None
    fields = fields_get(req, 'dbe.vendor')
    try:
        vendor = do_search_read(req, 'dbe.vendor', fields, 0, False, [('id', '=', vid)], None)
    except Exception:
        _logger.debug('vendor not found for vendor ID: %d', vid)

    if not vendor:
        raise Exception("AccessDenied")
    return vendor

def get_naics_codes(req, vid, ids=None):
    naics_codes = None
    fields = fields_get(req, 'naics.code')
    if ids is not None:
        try:
            naics_codes = do_search_read(req, 'naics.code', fields, 0, False, [('id', 'in', ids)], None)
        except Exception:
            _logger.debug('naics codes not found for ID: %s', str(ids))

    else:
        v = get_vendor_data(req, vid)['records']
        naics_ids = v[0]['naics']
        try:
            naics_codes = do_search_read(req, 'naics.code', fields, 0, False, [('id', 'in', naics_ids)], None)
        except Exception:
            _logger.debug('naics codes not found for vendor ID: %s', str(vid))

    if not naics_codes:
        raise Exception("AccessDenied")
    return naics_codes


class Utilities(septaweb.Controller):
    _cp_path = "/dbe/utils"

    @septaweb.jsonrequest
    def search(self, req, model, fields=False, offset=0, limit=False, domain=None, sort=None):
        return self.do_search_read(req, model, fields, offset, limit, domain, sort)

    def context_loader(self, req, vid, uid):
        """
        This populates the context object by calling the static methods for each model type
        with the current vendor id.
        @rtype : object
        @param req: OpenERP request object.
        @param vid: Vendor ID
        @param uid: OpenERP User ID
        @return: Context Object.
        """
        vendor_data = get_vendor_data(req, vid)['records']
        application_data = get_application(req, vid)['records']
        for application in application_data:
            if len(application['documents']) > 0:
                d = get_documents_by_id(req, vid, application['documents'])
                if d is not None:
                    application['documents'] = d['records']
                else:
                    application['documents'] = []
                    _logger.debug('<context_loader> no documents found for application id: %s', str(application['id']))

        certification_data = get_certification(req, vid)['records']
        for certification in certification_data:
            if len(certification['documents']) > 0:
                c = get_documents_by_id(req, vid, certification['documents'])
                if c is not None:
                    certification['documents'] = c['records']
                else:
                    certification['documents'] = []
                    _logger.debug('<context_loader> no documents found for application id: %s', str(certification['id']))

        contact_data = get_contacts(req, vid)['records']
        #document_data = get_documents(req, vid)['records']
        message_data = get_messages(req, uid)['records']
        index_data = get_document_indexes(req, vid)
        category_data = get_document_categories(req, vid)['records']
        onsite_report_data = get_onsite_reports(req, vid)['records']
        context_data = vendor_data[0]
        naics_data = get_naics_codes(req, vid, context_data['naics'])['records']
        context_data['naics'] = naics_data
        if index_data is not None:
            context_data['indexes'] = index_data['records']

        context_data['categories'] = category_data
        context_data['messages'] = message_data
        context_data['contacts'] = contact_data
#        import pdb; pdb.set_trace()


#        application_data['documents'] = app_docs
#        certification_data['documents'] = cert_docs
#        app_docs = []
#        cert_docs = []
#        for report in onsite_report_data:
#           if report['id'] in application_data['onsite_report']:
#                app_docs.append(report)
#            if report['id'] in certification_data['onsite_report']:
#                cert_docs.append(report)

#        application_data['onsite_report'] = app_docs
#        certification_data['onsite_report'] = cert_docs

        context_data['application'] = application_data
        context_data['certification'] = certification_data

        return context_data

    @septaweb.jsonrequest
    def dbe_context_json(self, req, login, password):
        """

        @param req:
        @param login:
        @param password:
        @return:
        """
        uid = req.session.authenticate(_DB_NAME, login, password)
        vid = get_vendor_id(req, uid)['records'][0]
        _logger.debug('dbe_context_json called by vendor ID: %s', str(vid))
        return simplejson.dumps(self.context_loader(req, vid.get('id'), uid))

    @septaweb.httprequest
    def dbe_context_http(self, req, login, password):
        """

        @param req:
        @param login:
        @param password:
        @return:
        """
        uid = req.session.authenticate(_DB_NAME, login, password)
        vid = get_vendor_id(req, uid)['records'][0]
        return self.context_loader(req, vid, uid)



class Session(septaweb.Controller):
    _cp_path = "/dbe/client/session"

    def session_info(self, req):
        req.session.ensure_valid()
        uid = req.session._uid
        args = req.httprequest.args
        request_id = str(req.jsonrequest['id'])
        _logger.debug('JSON Request ID: %s', request_id)
        res = {}
        if request_id == 'DBE': # Check to see if user is a DBE vendor
            try:                # Get vendor ID for session
                vendor = get_vendor_id(req, uid)['records'][0]
            except IndexError:
                _logger.debug('Vendor not found for user ID: %s', uid)
                return {'error': _('No Vendor found for this User ID!'), 'title': _('Vendor Not Found')}
            res = {
                "session_id": req.session_id,
                "uid": req.session._uid,
                "user_context": req.session.get_context() if req.session._uid else {},
                "db": req.session._db,
                "username": req.session._login,
                "vendor_id": vendor['id'],
                "company": vendor['company'],
            }
        elif request_id == 'VMI': # Check to see if user is a VMI vendor
            try:                    # Get Partner ID for session
                vendor = get_partner_id(req, uid)['records'][0]
            except IndexError:
                _logger.debug('Partner not found for user ID: %s', uid)
                return {'error': _('No Partner found for this User ID!'), 'title': _('Partner Not Found')}
            company = ""
            if vendor.has_key('company'):
                company = vendor['company']
            res = {
                "session_id": req.session_id,
                "uid": req.session._uid,
                "user_context": req.session.get_context() if req.session._uid else {},
                "db": req.session._db,
                "username": req.session._login,
                "partner_id": vendor['partner_id'][0],
                "company": vendor['partner_id'][1],
            }
        else: # Allow login for valid user without Vendor or Partner such as Admin or Manager
            res = {
                "session_id": req.session_id,
                "uid": req.session._uid,
                "user_context": req.session.get_context() if req.session._uid else {},
                "db": req.session._db,
                "username": req.session._login,
            }
        return res

    @septaweb.jsonrequest
    def get_session_info(self, req):
        return self.session_info(req)

    @septaweb.jsonrequest
    def authenticate(self, req, db, login, password, base_location=None):
        wsgienv = req.httprequest.environ
        env = dict(
            base_location=base_location,
            HTTP_HOST=wsgienv['HTTP_HOST'],
            REMOTE_ADDR=wsgienv['REMOTE_ADDR'],
        )
        req.session.authenticate(db, login, password, env)

        return self.session_info(req)

    @septaweb.jsonrequest
    def change_password(self, req, fields):
        old_password, new_password, confirm_password = operator.itemgetter('old_pwd', 'new_password', 'confirm_pwd')(
            dict(map(operator.itemgetter('name', 'value'), fields)))
        if not (old_password.strip() and new_password.strip() and confirm_password.strip()):
            return {'error': _('You cannot leave any password empty.'), 'title': _('Change Password')}
        if new_password != confirm_password:
            return {'error': _('The new password and its confirmation must be identical.'),
                    'title': _('Change Password')}
        try:
            if req.session.model('res.users').change_password(
                    old_password, new_password):
                return {'new_password': new_password}
        except Exception:
            return {'error': _('The old password you provided is incorrect, your password was not changed.'),
                    'title': _('Change Password')}
        return {'error': _('Error, password not changed !'), 'title': _('Change Password')}


    @septaweb.jsonrequest
    def check(self, req):
        req.session.assert_valid()
        return None

    @septaweb.jsonrequest
    def destroy(self, req):
        req.session._suicide = True


class ClientController(septaweb.Controller):
    _cp_path = '/dbe/client'

    # -----------------------------------------------| DBE API Endpoints.
    @septaweb.jsonrequest
    def get_vendor(self, req, uid):
        m = 'dbe.vendor'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_vendor_id(req, uid)

    @septaweb.jsonrequest
    def contacts(self, req, vid):
        m = 'dbe.vendor.contact'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_contacts(req, vid)

    @septaweb.jsonrequest
    def messages(self, req, uid):
        m = 'dbe.vendor.message'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_messages(req, uid)

    @septaweb.jsonrequest
    def documents(self, req, vid):
        m = 'dbe.document'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_documents(req, vid)

    @septaweb.jsonrequest
    def applications(self, req, vid):
        m = 'dbe.application'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_application(req, vid)

    @septaweb.jsonrequest
    def certifications(self, req, vid):
        m = 'dbe.certification'
        if req.params['command']:
            command = req.params['command']
            if command == 'CREATE':
                return api_create(req, vid, m)
            elif command == 'UPDATE':
                return api_update(req, vid, m)
            elif command == 'DELETE':
                pass #return api_delete(req, vid, m)

        return get_certification(req, vid)

    # -----------------------------------------------| DBE Client UI Controllers.
    @septaweb.httprequest
    def index(self, req, mod=None, **kwargs):
        tabs = ''
        js = """
$(document).ready(function(){
	$("form#loginForm").submit(function() { // loginForm is submitted
	var username = $('#username').attr('value'); // get username
	var password = $('#password').attr('value'); // get password


	if (username && password) { // values are not empty
		$.ajax({
		type: "POST",
		url: "/dbe/client/session/authenticate", // URL of OpenERP Authentication Handler
		contentType: "application/json; charset=utf-8",
		dataType: "json",
		// send username and password as parameters to OpenERP
		data: '{"jsonrpc": "2.0", "method": "call", "params": {"session_id": null, "context": {}, "login": "' + username + '", "password": "' + password + '", "db": "dev_main"}, "id": "DBE"}',
		// script call was *not* successful
		error: function(XMLHttpRequest, textStatus, errorThrown) { 
			$('div#loginResult').text("responseText: " + XMLHttpRequest.responseText 
			+ ", textStatus: " + textStatus 
			+ ", errorThrown: " + errorThrown);
			$('div#loginResult').addClass("error");
		}, // error 
		// script call was successful 
		// data contains the JSON values returned by OpenERP 
		success: function(data){
			if (data.result && data.result.error) { // script returned error
				$('div#loginResult').text("Warning: " + data.result.error);
				$('div#loginResult').addClass("notice");
			}
			else if (data.error) { // OpenERP error
				$('div#loginResult').text("Error-Message: " + data.error.message + " | Error-Code: " + data.error.code + " | Error-Type: " + data.error.data.type);
				$('div#loginResult').addClass("error");
			} // if
			else { // login was successful
				responseData = data.result;
				$('form#loginForm').hide();
				$( "#tabs" ).tabs();
				$('div#loginResult').html("<h2>Success!</h2> " 
					+ " Welcome <b>" + data.result.username + "</b>, from "
					+ data.result.company);
				$('div#loginResult').addClass("success");
				$('div#tabs').addClass("info");
			$(function() {
			$( "#tabs" ).tabs({
				beforeLoad: function( event, ui ) {
				ui.ajaxSettings.url += ( /\?/.test( ui.ajaxSettings.url ) ? "&" : "?" ) + 'vid=' + data.result.vendor_id;
				$('div#loginResult').hide();
				ui.jqXHR.error(function() {
					ui.panel.html(
					"Couldn't load this tab. We'll try to fix this as soon as possible. ");
				});
				}
			});
			});
				$('div#tabs').fadeIn();
				sessionid = data.result.session_id;
			//postData = '{"jsonrpc": "2.0", "method": "call", "params": {"session_id": "' + sessionid + '", "context": "{}", "username": "' + responseData.username + '", "uid": ' + responseData.uid + ', "db": "' + responseData.db + '", "vid": ' + responseData.vendor_id + '}, "id": 5}';
			} //else
		} // success
		}); // ajax
	} // if
	else {
		$('div#loginResult').text("enter username and password");
		$('div#loginResult').addClass("error");
	} // else
	$('div#loginResult').fadeIn();
	return false;
	});
});

		"""
#/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/login.html
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/login.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()

        context = simpleTALES.Context()
        # Add a string to the context under the variable title
        context.addGlobal("title", "SEPTA Vendor Portal Login")
        context.addGlobal("script", js)
        context.addGlobal("tabs", tabs)

        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()


    @septaweb.httprequest
    def vendor_details(self, req, vid=None, **kwargs):
        req.session.ensure_valid() # Check for valid session
        uid = newSession(req) # Give AJAX request an Admin session
        details = []
        res = None
        naics = {}
        applications = {}
        certifications = {}
        vendor_fields = ['company', 'description', 'septa_vendor_id', 'comp_class', 'naics', 'ethnicity', 'gender',
                         'application', 'certification', 'w9_classification']
        naics_fields = ['code', 'title']
        application_fields = ['intake_date', 'state', 'visit_approved', 'verified_date', '90_days_flag', 'completion']
        certification_fields = ["paucp_cert_number", "certification_number", "certification_type", "certification_date",
                                "anniversary_date", "status"]
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/vendor_details.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()
        if vid is not None:
            try: # Get the current vendor
                res = do_search_read(req, 'dbe.vendor', vendor_fields, 0, False, [('id', '=', vid)], None)
            except Exception:
                _logger.debug('<vendor_details> Session expired or Vendor not found for vendor ID: %s', vid)

            if res is not None and res['length'] > 0:
                for record in res['records']:
                    naics_ids = record['naics']
                    app_ids = record['application']
                    cert_ids = record['certification']
                    try: # Get the NAICS codes for the current vendor
                        naics = do_search_read(req, 'naics.code', naics_fields, 0, False, [('id', 'in', naics_ids)],
                                               None)
                    except Exception:
                        naics['length'] = 0

                    if naics['length'] > 0:
                        record['naics'] = naics['records']
                    else:
                        del record['naics']
                    try: # Get the Applications for the current vendor
                        applications = do_search_read(req, 'dbe.application', application_fields, 0, False,
                                                      [('id', 'in', app_ids)], None)
                    except Exception:
                        applications['length'] = 0

                    if applications['length'] > 0:
                        record['application'] = applications['records']
                    else:
                        del record['application']
                    try: # Get the Certifications for the current vendor
                        certifications = do_search_read(req, 'dbe.certification', certification_fields, 0, False,
                                                        [('id', 'in', cert_ids)], None)
                    except Exception:
                        certifications['length'] = 0

                    if certifications['length'] > 0:
                        record['certification'] = certifications['records']
                    else:
                        del record['certification']

                    details.append(record.copy())

            else: # Vendor ID not passed
                details.append({'message': 'No details could be found for this vendor!'})
                _logger.debug('vendor ID not passed or Vendor record not found')

        req.session._suicide = True # Destroy session
        context = simpleTALES.Context()
        # Populate context with dynamic values
        context.addGlobal("title", "SEPTA Vendor Details")
        context.addGlobal("script", simplejson.dumps(details[0]))
        context.addGlobal("header", "Vendor Details")
        context.addGlobal("details", details)
        # Expand compiled template and return value to request
        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()

    @septaweb.httprequest
    def vendor_contacts(self, req, vid=None, editflag=False, **kwargs):
        res = None
        vendor_contacts = []
        vendor_fields = ['company', 'contacts']
        contact_fields = ['id', 'name', 'title', 'position', 'address1', 'address2', 'city', 'state_id', 'zip',
                          'country_id', 'website', 'email', 'phone1', 'phone2', 'ext', 'fax', 'attention']
        contacts = {}
        req.session.ensure_valid() # Check for valid session
        uid = newSession(req) # Give AJAX request an Admin session
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/vendor_contacts.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()
        if vid is not None:
            try: # Get the current vendor
                res = do_search_read(req, 'dbe.vendor', vendor_fields, 0, False, [('id', '=', vid)], None)
            except Exception:
                _logger.debug('<vendor_contacts> Session expired or Vendor not found for vendor ID: %s', vid)

            if res is not None and res['length'] > 0:
                for record in res['records']:
                    contact_ids = record['contacts']
                    try: # Get the Contacts for the current vendor
                        contacts = do_search_read(req, 'dbe.vendor.contact', contact_fields, 0, False,
                                                  [('id', 'in', contact_ids)], None)
                    except Exception:
                        contacts['length'] = 0

                    if contacts['length'] > 0:
                        record['contacts'] = contacts['records']
                    else:
                        del record['contacts']

                    vendor_contacts.append(record['contacts'])
                # Obtain display values from associative lists
                for c in vendor_contacts[0]:
                    c['title'] = c['title'][1]
                    c['country_id'] = c['country_id'][1]
                    c['state_id'] = c['state_id'][1]
                    c['position'] = c['position'][1]

            else: # Vendor ID not passed
                vendor_contacts.append({'message': 'No contacts could be found for this vendor!'})
                _logger.debug('vendor ID not passed or Vendor record not found')

        req.session._suicide = True
        context = simpleTALES.Context()
        # Populate context with dynamic values
        context.addGlobal("title", "SEPTA Vendor Contacts")
        context.addGlobal("script", simplejson.dumps(vendor_contacts[0]))
        context.addGlobal("header", "Vendor Contacts")
        context.addGlobal("contacts", vendor_contacts[0])
        if editflag:
            context.addGlobal("edit", True)
        # Expand compiled template and return value to request
        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()


    @septaweb.httprequest
    def upload_dbe_document(self, req, sid, vid, tab, callback, category, model, id, ufile=None):
        req.session.ensure_valid()
        uid = newSession(req)
        Model = req.session.model('dbe.document')
        categories = get_document_categories(req, 1)['records']
        association = None
        out = """<script language="javascript" type="text/javascript">
					var win = window.top.window;
					win.jQuery(win).trigger(%s, %s);
				</script>"""

        for c in categories:
            if c['id'] == int(category):
                association = c['association']
                break
            #else:
            #_logger.debug('<upload_dbe_document> Category ID: %s does not equal %s', category, c['id'])
            #raise ValueError("(%r) is not a proper value for document category!" % category)

        if model == 'dbe.application' and association == 'application':
            try: # Create a DBE doc associated to an Application.
                attachment_id = Model.create({
                                                 'name': ufile.filename,
                                                 'datas': base64.encodestring(ufile.read()),
                                                 'datas_fname': ufile.filename,
                                                 'res_model': model,
                                                 'res_id': int(id),
                                                 'type_of': category,
                                                 'vendor_id': vid,
                                                 'application_id': int(id)
                                             }, req.context)
                args = {
                    'filename': ufile.filename,
                    'id': attachment_id,
                    'tab': tab
                }
            except xmlrpclib.Fault, e:
                args = {'error': e.faultCode}
            _logger.debug('<upload_dbe_document/application> dbe.document uploaded - callback: %s args: %s',
                          simplejson.dumps(callback), simplejson.dumps(args))
            return out % (simplejson.dumps(callback), simplejson.dumps(args))
        elif model == 'dbe.certification' and association == 'certification':
            try: # Create a DBE doc associated to a Certification.
                attachment_id = Model.create({
                                                 'name': ufile.filename,
                                                 'datas': base64.encodestring(ufile.read()),
                                                 'datas_fname': ufile.filename,
                                                 'res_model': model,
                                                 'res_id': int(id),
                                                 'type_of': category,
                                                 'vendor_id': vid,
                                                 'certification_id': int(id)
                                             }, req.context)
                args = {
                    'filename': ufile.filename,
                    'id': attachment_id,
                    'tab': tab
                }
            except xmlrpclib.Fault, e:
                args = {'error': e.faultCode}
            _logger.debug('<upload_dbe_document/certification> dbe.document uploaded - callback: %s args: %s',
                          simplejson.dumps(callback), simplejson.dumps(args))
            return out % (simplejson.dumps(callback), simplejson.dumps(args))
        else:     # Catch documents categorized as Other.
            try: # Create a DBE doc associated to the Vendor.
                attachment_id = Model.create({
                                                 'name': ufile.filename,
                                                 'datas': base64.encodestring(ufile.read()),
                                                 'datas_fname': ufile.filename,
                                                 'res_model': model,
                                                 'res_id': int(id),
                                                 'type_of': category,
                                                 'vendor_id': vid
                                             }, req.context)
                args = {
                    'filename': ufile.filename,
                    'id': attachment_id,
                    'tab': tab
                }
            except xmlrpclib.Fault, e:
                args = {'error': e.faultCode}
            _logger.debug('<upload_dbe_document/other> dbe.document uploaded - callback: %s args: %s',
                          simplejson.dumps(callback), simplejson.dumps(args))
            return out % (simplejson.dumps(callback), simplejson.dumps(args))

    @septaweb.httprequest
    def vendor_documents(self, req, vid=None, **kwargs):
        res = None
        documents = []
        applications = None
        doc_fields = ["create_date", "state", "type_of", "name", "description"]
        sid = req.session_id
        req.session.ensure_valid()
        uid = newSession(req)
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/vendor_documents.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()
        context = simpleTALES.Context()
        form_flag = False # This will determine whether or not the uploading form is rendered.

        def _valid_cert():
            valid_certs = []
            certs = get_certification(req, vid)
            res = {}

            if certs['length'] > 0:
                for cert in certs['records']: # Get certified certs only.
                    if cert['status'] != 'certified':
                        continue
                    else:
                        valid_certs.append(cert)

                if valid_certs:
                # Of remaining Certifications find the most recently created.
                    if len(valid_certs) > 1:
                        valid_certs.sort(cmp=lambda y, x: cmp(x['certification_date'], y['certification_date']))
                    #
                    _logger.debug('<vendor_documents> Valid Certification found - ID: %s', valid_certs[0]['id'])
                    res = valid_certs[0]
                else:
                    _logger.debug('<vendor_documents/cert> None found!')

            return res

        def _valid_app():
            res = {}
            try: # Find all Applications for current vendor.
                applications = get_application(req, vid)
                _logger.debug('<vendor_documents> Valid Application found %s', applications)
            except Exception:
                _logger.debug('<vendor_documents> Session expired or Applications not found for vendor ID: %s', vid)

            valid_apps = []    # From the available Applications get only pending and new.
            if applications is not None and applications['length'] > 0:
                for application in applications['records']:
                    if application['state'] not in ['pend', 'new']:
                        continue
                    else:
                        valid_apps.append(application)

                if valid_apps:
                    _logger.debug('<vendor_documents> Valid Application found - ID: %s', valid_apps[0]['id'])
                    # Of remaining Applications find the most recently created.
                    if len(valid_apps) > 1:
                        valid_apps.sort(cmp=lambda y, x: cmp(x['intake_date'], y['intake_date']))
                    #
                    res = valid_apps[0]
                else:
                    _logger.debug('<vendor_documents/app> None found!')

            return res


        if vid is not None:
            context.addGlobal("vid", vid)
            try: # Obtain documents for the current Vendor
                res = do_search_read(req, 'dbe.document', doc_fields, 0, False, [('vendor_id.id', '=', vid)], None)
            except Exception:
                _logger.debug('<vendor_documents> Session expired or Documents not found for vendor ID: %s', vid)

            if res is not None and res['length'] > 0:
                for record in res['records']:
                    type_of = record['type_of']
                    if type_of.__class__ == type(
                            ()): # Yes shameful, but I didn't program the ORM to switch between returned types.
                    # Obtain display values from tuple
                        record['type_of'] = type_of[1]
                        documents.append(record.copy())
                    else:
                        documents.append(record.copy())

        valid_app = _valid_app()
        valid_cert = _valid_cert()
        if valid_cert.has_key('id'):
            context.addGlobal("certification", valid_cert['id']) # Add hidden Certification field to form.
            form_flag = True
        elif valid_app.has_key('id'):
            context.addGlobal("application", valid_app['id']) # Add hidden application field to form.
            form_flag = True
        else:
            form_flag = False

        script = """\n var document_data = {"documents": %s };\n""" % simplejson.dumps(documents)
        categories = get_document_categories(req, 1)['records']
        # Append context with display data for TAL template.
        context.addGlobal("categories", categories)
        context.addGlobal("title", "DBE/SBE Vendor Documents")
        context.addGlobal("script", script)
        context.addGlobal("header", "Documents are attached to the most recent application and/or certification.")
        context.addGlobal("documents", documents)
        context.addGlobal("sid", sid)
        context.addGlobal("form_flag", form_flag)
        req.session._suicide = True
        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()


    @septaweb.httprequest
    def application_docs(self, req, vid=None, **kwargs):
        """

        @param req:
        @param vid:
        @param kwargs:
        @return: TAL Template - new_vendor_documents.html
        """
        res = None
        documents = []

        doc_fields = ["create_date", "state", "type_of", "name", "description"]
        sid = req.session_id
        req.session.ensure_valid()
        uid = newSession(req)
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/new_vendor_documents.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()
        context = simpleTALES.Context()
        form_flag = False # This will determine whether or not the uploading form is rendered.

        def _valid_cert():
            valid_certs = []
            certs = get_certification(req, vid)
            res = {}

            if certs['length'] > 0:
                for cert in certs['records']: # Get certified certs only.
                    if cert['status'] != 'certified':
                        continue
                    else:
                        valid_certs.append(cert)

                if valid_certs:
                # Of remaining Certifications find the most recently created.
                    if len(valid_certs) > 1:
                        valid_certs.sort(cmp=lambda y, x: cmp(x['certification_date'], y['certification_date']))
                    #
                    _logger.debug('<vendor_documents> Valid Certification found - ID: %s', valid_certs[0]['id'])
                    res = valid_certs[0]
                else:
                    _logger.debug('<vendor_documents/cert> None found!')

            return res

        def _valid_app():
            res = {}
            applications = None
            try: # Find all Applications for current vendor.
                applications = get_application(req, vid)
                _logger.debug('<vendor_documents> Valid Application found %s', applications)
            except Exception:
                _logger.debug('<vendor_documents> Session expired or Applications not found for vendor ID: %s', vid)

            valid_apps = []    # From the available Applications get only pending and new.
            if applications is not None:
                for application in applications['records']:
                    if application['state'] not in ['pend', 'new']:
                        continue
                    else:
                        valid_apps.append(application)

                if valid_apps:
                    _logger.debug('<vendor_documents> Valid Application found - ID: %s', valid_apps[0]['id'])
                    # Of remaining Applications find the most recently created.
                    if len(valid_apps) > 1:
                        valid_apps.sort(cmp=lambda y, x: cmp(x['intake_date'], y['intake_date']))
                    #
                    res = valid_apps[0]
                else:
                    _logger.debug('<vendor_documents/app> None found!')

            return res


        categories = get_document_categories(req, 1)['records']
        tal_categories = []
        if vid is not None:
            context.addGlobal("vid", vid)
            try: # Obtain documents for the current Vendor
                res = do_search_read(req, 'dbe.document', doc_fields, 0, False, [('vendor_id.id', '=', vid)], None)
            except Exception:
                _logger.debug('<vendor_documents> Session expired or Documents not found for vendor ID: %s', vid)

            if res is not None and res['length'] > 0:
                for category in categories:
                    category.update({'documents': []})
                    for record in res['records']:
                        type_of = record['type_of']
                        if type_of.__class__ == type(
                                ()): # Yes shameful, but I didn't program the ORM to switch between returned types.
                        # Obtain display values from tuple
                            record['type_of'] = type_of[1]
                            record.update({'type_id': type_of[0]})
                            documents.append(record.copy())
                        else:
                            documents.append(record.copy())

                        if category['id'] == record['type_id']:
                            category['documents'].append(record.copy())

                    tal_categories.append(category.copy())

        valid_app = _valid_app()
        valid_cert = _valid_cert()
        if valid_cert.has_key('id'):
            context.addGlobal("certification", valid_cert['id']) # Add hidden Certification field to form.
            form_flag = True
        elif valid_app.has_key('id'):
            context.addGlobal("application", valid_app['id']) # Add hidden application field to form.
            form_flag = True
        else:
            form_flag = False

        script = """\n var document_data = {"documents": %s };\n""" % simplejson.dumps(documents)

        # Append context with display data for TAL template.
        context.addGlobal("categories", tal_categories)
        context.addGlobal("title", "DBE/SBE Vendor Documents")
        context.addGlobal("script", script)
        context.addGlobal("header", "Documents are attached to the most recent application and/or certification.")
        context.addGlobal("documents", documents)
        context.addGlobal("sid", sid)
        context.addGlobal("form_flag", form_flag)
        req.session._suicide = True
        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()


    @septaweb.httprequest
    def vendor_messages(self, req, vid=None, **kwargs):
        script = """
		var tbl;

function trim(str){
	return str.replace(/^\s*|\s*$/g,"");
}
function setMessageRead(messageId){
	$.ajax({
	type: "POST",
	url: "/web/dataset/call_kw", // URL of OpenERP Handler
	contentType: "application/json; charset=utf-8",
	dataType: "json",
	data: '{"jsonrpc":"2.0","method":"call","params":{"model":"mail.message","method":"set_message_read","args":[[' + messageId + '],true,true,{"default_model":false,"default_res_id":0,"default_parent_id":' + messageId + '}],"kwargs":{},"session_id":"' + sessionid + '","context":{"lang":"en_US","tz":"EST","uid":' + responseData['uid'] + '}},"id":"DBE"}',
	// script call was *not* successful
	error: function(XMLHttpRequest, textStatus, errorThrown) { 

	}, // error 
	// script call was successful 
	// data contains the JSON values returned by OpenERP 
	success: function(data){
		if (data.result && data.result.error) { // script returned error
			$('div#loginResult').text("Warning: " + data.result.error);
			$('div#loginResult').addClass("notice");
		}
		else if (data.error) { // OpenERP error
			$('div#loginResult').text("Error-Message: " + data.error.message + " | Error-Code: " + data.error.code + " | Error-Type: " + data.error.data.type);
			$('div#loginResult').addClass("error");
		} // if
		else { // successful transaction
			//sessionid = data.result.session_id;
		} //else
	} // success
	}); // ajax
};

function getParent(el, pTagName) {
 if (el == null) return null;
 else if (el.nodeType == 1 && el.tagName.toLowerCase() == pTagName.toLowerCase()) // Gecko bug, supposed to be uppercase
	return el;
 else
	return getParent(el.parentNode, pTagName);
}

function replaceString(oldStr, newStr, original){
	return original.split(oldStr).join(newStr)
}

function toggleSection(lnk){

 var td = lnk.parentNode;
 var table = getParent(td,'TABLE');
 var len = table.rows.length;
 var tr = getParent(td, 'tr');
 var rowIndex = tr.rowIndex;
 var rowHead=table.rows[rowIndex].cells[1].innerHTML;
 var oldReplyLink=table.rows[rowIndex+2].cells[3].innerHTML;
 var message_id=table.rows[rowIndex+2].cells[2].innerHTML;
 var uParam="?message_id=" + message_id;
 var newReplyLink = replaceString("#", uParam, oldReplyLink);
 table.rows[rowIndex+2].cells[3].innerHTML = newReplyLink;
// AJAX call to set message as read.
 setMessageRead(message_id) 
 lnk.innerHTML =(lnk.innerHTML == "+")?"-":"+";

 vStyle =(tbl.rows[rowIndex+1].style.display=='none')?'':'none';

 for(var i = rowIndex+1; i < len;i++){
	if (table.rows[i].cells[1].innerHTML==rowHead){
	table.rows[i].style.display= vStyle;
	table.rows[i].cells[1].style.visibility="hidden";
	}
 }
}

function toggleRows(){
	tables =document.getElementsByTagName("table");
	for(i =0; i<tables.length;i++){
		if(tables[i].className.indexOf("expandable") != -1)
		tbl =tables[i];
	}
	if(typeof tbl=='undefined'){
	 alert("You do not have any messages!");
	 return;
	}

//assume the first row is headings and the first column is empty
 var len = tbl.rows.length;
 var link ='<a href="" onclick="toggleSection(this);return false;">+</a>';

 var rowHead = tbl.rows[1].cells[1].innerHTML;

 for (j=1; j<len;j++){
	//check the value in each row of column 2
	var m = tbl.rows[j].cells[1].innerHTML;

if(m!=rowHead || j==1){
	 rowHead=m;
	 tbl.rows[j].cells[0].innerHTML = link;
	 tbl.rows[j].cells[0].style.textAlign="center";
	 tbl.rows[j].style.background = "#CCFF99";
	}
else
	 tbl.rows[j].style.display = "none";
}

}
toggleRows();
\n
		"""
        header = "Click on the plus sign in the table below to read message."
        mail_flag = True
        messages = []
        message = None
        partner_ids = None
        vendor_fields = ['company', 'vuid', 'active']
        email_fields = ['type', 'email_from', 'author_id', 'partner_ids', 'subject', 'date', 'body', 'message_id',
                        'to_read']
        #uid = req.session._uid
        req.session.ensure_valid()
        uid = newSession(req)
        input = open('/home/amir/dev/parts/openerp-7.0-20131118-002448/openerp/addons/dbe/client/template/vendor_messages.html', 'r')
        template = simpleTAL.compileHTMLTemplate(input)
        input.close()
        context = simpleTALES.Context()

        if vid is not None:
            try: # Find the OpenERP user for the current Vendor.
                res = do_search_read(req, 'dbe.vendor', vendor_fields, 0, False, [('id', '=', vid)], None)
            except Exception:
                _logger.debug('<vendor_messages> Session expired or Vendor not found for vendor ID: %s', vid)
            # Obtain partner_id with user_id to use with finding OpenERP messages for the Vendor.
            if res is not None and res['length'] > 0:
                for record in res['records']:
                    vuid = record['vuid'][0]
                    active = record['active']
                    partner_ids = get_partner_id(req, vuid)['records'][0]
                    if partner_ids is not None:
                        pid = partner_ids['partner_id'][0]
                        try: # Check the mail.
                            message = do_search_read(req, 'mail.message', email_fields, 0, False,
                                                     [('partner_ids', 'in', pid)], None)
                        except Exception:
                            _logger.debug('<vendor_messages>Messages not found for vendor ID: %s', vuid)
                        if message['length'] > 0:
                            messages.append(message['records'])
                            for m in messages[0]: # This is ugly find a better way to handle this.
                                m['active'] = active
                                if m['email_from'] is False:
                                    m['author_id'] = m['author_id'][1]
                                    del m['email_from']
                                else:
                                    m['author_id'] = m['email_from']
                                    del m['email_from']

                            script += """\n var message_data = {"messages":""" + simplejson.dumps(
                                messages[0]) + """};\n"""
                            messages = messages[0]
                        else:
                            header = "There are no messages in your inbox."
                            mail_flag = False

        # Create hidden fields with required values for jQuery reply form.
        formhtml = []
        formhtml.append("""<input id="uid" type="hidden" name="uid" value="%s" />""" % vuid)
        formhtml.append("""<input id="vid" type="hidden" name="vid" value="%s" />""" % vid)
        formhtml.append("""<input id="pid" type="hidden" name="pid" value="%s" />""" % pid)
        req.session._suicide = True
        # Append context with display data for TAL template.
        context.addGlobal("title", "SEPTA Vendor Messages")
        context.addGlobal("script", script)
        context.addGlobal("header", header)
        context.addGlobal("messages", messages)
        context.addGlobal("formhtml", formhtml)
        context.addGlobal("mail_flag", mail_flag)
        # Spit out expanded TAL template to the request.
        output = cStringIO.StringIO()
        template.expand(context, output)
        return output.getvalue()

    @septaweb.httprequest
    def upload_attachment(self, req, callback, model, id, vid, category, sid, ufile):
        uid = newSession(req)
        Model = req.session.model('ir.attachment')
        out = """<script language="javascript" type="text/javascript">
					var win = window.top.window;
					win.jQuery(win).trigger(%s, %s);
				</script>"""
        try:
            attachment_id = Model.create({
                                             'name': ufile.filename,
                                             'datas': base64.encodestring(ufile.read()),
                                             'datas_fname': ufile.filename,
                                             'res_model': model,
                                             'res_id': int(id)
                                         }, req.context)
            args = {
                'filename': ufile.filename,
                'id': attachment_id
            }
        except xmlrpclib.Fault, e:
            args = {'error': e.faultCode}
        return out % (simplejson.dumps(callback), simplejson.dumps(args))

    # -----------------------------------------------| DBE Utility Methods.
    @septaweb.jsonrequest
    def read_contacts(self, req, username, uid, db, vid):
        vendor_contacts = None
        fields = fields_get(req, 'dbe.vendor.contact')
        #['id', 'name', 'title', 'position', 'address1', 'address2', 'city', 'state_id', 'zip', 'country_id', 'website', 'email', 'phone1', 'phone2', 'ext', 'fax', 'attention']
        #vendor_id = req.session._vid
        #uid = req.session._uid
        try:
            vendor_contacts = do_search_read(req, 'dbe.vendor.contact', fields, 0, False, [('vendor_id.id', '=', vid)],
                                             None)
        except Exception:
            _logger.debug('Vendor not found for user ID: %s', uid)

        if not vendor_contacts:
            raise Exception("AccessDenied")

        return vendor_contacts




# -*- coding: utf-8 -*-
##############################################################################
#
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU Affero General Public License as
#	published by the Free Software Foundation, either version 3 of the
#	License, or (at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU Affero General Public License for more details.
#
#	You should have received a copy of the GNU Affero General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv
from openerp.osv import fields
import time


class dbe_certification_rules(osv.osv):
	""" Business Rules and Methods for DBE Certifications """
	_name = "dbe.certification.rules"
	_description = "Business Rules for DBE Certifications"
	
	def time_till_anniversary(self, cr, uid, ids, context=None):
		pass
		
	def time_since_anniversary(self, cr, uid, ids, context=None):
		pass
		
	#def approve(self, cr, uid, ids, context=None):
		#pass 
		
	def decertify(self, cr, uid, ids, context=None):
		pass 
		
	def request_affidavit(self, cr, uid, ids, context=None):
		pass 
		
	def time_since_affidavit_request(self, cr, uid, ids, context=None):
		pass 
		
	def receive_affidavit(self, cr, uid, ids, context=None):
		pass 
		
	def check_affidavit_deadline(self, cr, uid, ids, context=None):
		pass 
		
	def check_second_request(self, cr, uid, ids, context=None):
		pass 
		
	def process_anniversary(self, cr, uid, ids, context=None):
		pass 

	def extend_anniversary_date(self, cr, uid, ids, context=None):
		pass 
		
	def process_affidavit(self, cr, uid, ids, context=None):
		pass 
		
	def get_certification_history(self, cr, uid, ids, context=None):
		pass 
		
	def update_certification_history(self, cr, uid, ids, context=None):
		pass 
		
		
	

	
class dbe_application_rules(osv.osv):
	""" Business Rules and Methods for DBE Applications """
	_name = "dbe.application.rules"
	_description = "Business Rules for DBE Applications"

	def select_dbe_specialist(self, cr, uid, ids, context=None):
		pass 
		
	def change_dbe_specialist(self, cr, uid, ids, context=None):
		pass 

	def process_new_application(self, cr, uid, ids, context=None):
		pass 
		
	def check_application_completed(self, cr, uid, ids, context=None):
		pass 
		
	def check_documentation_complete(self, cr, uid, ids, context=None):
		pass 

	def get_documentation_history(self, cr, uid, ids, context=None):
		pass 
		
	def get_message_history(self, cr, uid, ids, context=None):
		pass 
		
	def get_application_history(self, cr, uid, ids, context=None):
		pass 
		
	def create_application_history(self, cr, uid, transaction, context=None):
		vals = {'application_id': self.id, 
		        'current_status': self.state, 
		        'completion': self.completion,
		        'note': self.note,
		        'dbe_specialist': self.dbe_specialist,
		        'onsite_visit_date': self.onsite_visit_date,
		        'onsite_visit_notes': self.onsite_visit_notes,
		        'visit_approved': self.visit_approved,
		        'docs_completed': self.docs_completed,
		        #'90_days_flag': self.90_days_flag,
		        'transaction_type': transaction
		        }
		        
		history_id = self.pool.get('dbe_application_history').create(cr, uid, vals, context=context)
		return history_id
		 
		
	def set_approved(self, cr, uid, ids, context=None):
		pass 

	def verify_approval(self, cr, uid, ids, context=None):
		pass 
		
	def withdraw(self, cr, uid, ids, context=None):
		pass 
		
	def pending(self, cr, uid, ids, context=None):
		pass 
		
	def send_approval_letter(self, cr, uid, ids, context=None):
		pass 
		
	def send_denial_letter(self, cr, uid, ids, context=None):
		pass 
		
	def reject_application(self, cr, uid, ids, context=None):
		pass 

	def check_90_days(self, cr, uid, ids, context=None):
		pass 
				

	def denied(self, cr, uid, ids, context=None):
		pass  	
		
	def request_further_documents(self, cr, uid, ids, context=None):
		pass 
		
	def set_new_deadline(self, cr, uid, ids, context=None):
		pass 
		
	def check_deadlines(self, cr, uid, ids, context=None):
		pass 
		
	def check_status(self, cr, uid, ids, context=None):
		pass 
		
	def process_onsite_visit(self, cr, uid, ids, context=None):
		pass 
		
		

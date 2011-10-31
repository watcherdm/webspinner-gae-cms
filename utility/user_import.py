import csv
import StringIO
from models.auth import User
from models.site import Site

class UserCsv():
	def read(self, file):
		result = {
			"errors" : [],
			"data" : [],
			"dialect" : None
		}
		csvio = StringIO.StringIO(file)
		dialect = csv.Sniffer().sniff(file)
		csvreader = csv.DictReader(csvio, dialect = dialect)
		for row in csvreader:
			result["data"].append(row)
			"""
			Here we need to render each user account
			store it and get ready to start sending emails etc.
			"""
			if not row.get('             E-MAIL  ADDRESS', None):
				result['errors'].append({
					"message" : "Could not retrieve field             E-MAIL  ADDRESS",
					"row" : row
				})
				continue
			new_user = User.get_by_email(row.get('             E-MAIL  ADDRESS', 'CANCEL'))
			if not new_user:
				site = Site.all().get()
				new_user = User.create_user(row.get('             E-MAIL  ADDRESS', 'NONE'), 'NONE', site.secret)
			new_user.firstname = row.get('FIRST NAME', None)
			new_user.lastname = row.get('LAST NAME', None)
			new_user.spouse = row.get('SPOUSE', None)
			new_user.address = row.get('ADDRESS LINE 1', None) + '\n' + row.get('ADDRESS LINE 2', None) + '\n' + row.get('CITY', None) + '\n' + row.get('STATE', None) + ',' + row.get('ZIP', None) + '\n' + row.get('COUNTRY', None)
			if row.get('PHONE NUMBER', None):
				new_user.phone = row.get('PHONE NUMBER', None)
			if row.get('FAX NUMBER', None):
				new_user.fax = row.get('FAX NUMBER', None)
			
			new_user.put()
		
		#clear the user cache
		return result

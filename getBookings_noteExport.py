import requests
from requests_ntlm import HttpNtlmAuth
import json
import csv
import netrc

# get user / password
host = 'torvmpiis8'
parking_url = 'http://torvmpiis8.na.sas.com/ParkingApp/BookingCalendar/GetBooking'
# Read from the .netrc file in your home directory
secrets = netrc.netrc()
dusername, account, password = secrets.authenticators(host)
#print ("\"" + dusername + "\" \"" + password + "\"")

try:
        bookings = requests.get(parking_url,auth=HttpNtlmAuth(dusername,password))
        bookings.raise_for_status()
except requests.exceptions.HTTPError as err:
        print ("failed to make server connection[parking URL]: " + str(err))
        sys.exit(1)

# parse to json and write to csv
data = json.loads(bookings.text)
spots = data["BList"]

with open('spots.csv', 'w') as csvfile:
        fieldnames = ['pspot','name','date','bookOrPost','period','spot']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        for spot in spots:
                spot['pspot'] = spot['spot'].split(' ')[0]
                spot['name'] = spot['spot'].split(' ')[1]
                spot['period'] = (spot['spot'].split('(')[1]).split(' ')[0]
                writer.writerow(spot)


from __future__ import print_function
#from bs4 import BeautifulSoup
import requests
from requests_ntlm import HttpNtlmAuth
#import uuid
import time
from datetime import datetime
import csv
import random
import json
import netrc
import pandas as pd
# import hashlib

#bookSpotURL = 'http://torvmpiis8/ParkingApp/Spot/BookSpot'
#getMyBookingURL = 'http://torvmpiis8.na.sas.com/ParkingApp/Spot/GetMyBookedSpot'
#parking_url = 'http://torvmpiis8.na.sas.com/ParkingApp/Spot/Index'
getTodayBookingURL = 'http://torvmpiis8.na.sas.com/ParkingApp/Spot/GetTodayBooking'
getBookingURL = 'http://torvmpiis8.na.sas.com/ParkingApp/BookingCalendar/GetBooking'
getAvailSpotURL = 'http://torvmpiis8.na.sas.com/ParkingApp/Spot/GetAvailableSpot?timeselect=UP+To+60+Days'

logfilename = 'logs/log_' + datetime.now().strftime('%Y-%m-%d_%H.%M.%S.%f')+'.csv'
#psafilenamejson = 'logs/psa_' + datetime.now().strftime('%Y-%m-%d_%H.%M.%S.%f')+'.json'
#gtbfilenamejson = 'logs/gtb_' + datetime.now().strftime('%Y-%m-%d_%H.%M.%S.%f')+'.json'
psafilenamehtml = 'logs/psa_' + datetime.now().strftime('%Y-%m-%d_%H.%M.%S.%f')+'.html'
hashprev = ""

##
## write to csv file for now; eventually write to ESP stream
##
def sendEvents(_data):
	#print (_data)
	try:
		with open(logfilename, 'a') as csvfile:
			fieldnames = ['guid','id','opcode','status','spotnum','spotdate','time','availspot']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			writer.writerow(_data)
		##
		## write out to ESP
		##
		return (0)
	except (csv.Error, TypeError) as e:
		print('file {0}, data {1}: {2}'.format(filename, _data, e))
		return (-1)

def parkingLoop(dusername, password, JSONpayloadprev):
	data = o = ravailspot = rtodaybooking = rbooking = {}
	list_of_entries = []
	status = spot_status = booking_str = ""

	try:
		# ravailspot = ""
		ravailspot = requests.get(getAvailSpotURL,auth=HttpNtlmAuth(dusername,password))
		ravailspot.raise_for_status()
		otime =  datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')  # get current time

		##
		## check payload length *num_entries. extract individual entries from JSON payload.
		## compare against previous. If there is a difference (one remove, or added) then
		## write out the difference to sendEvents(CSV/ESP)
		## 

		data = json.loads(ravailspot.text)
		# print("{%}, {%},", type(data), len(data))
		# print(type(JSONpayloadprev))
		if len(data) > len(JSONpayloadprev):
			print("{0}: new item! data:{1}, JSONpayloadprev:{2}".format(datetime.now(),len(data), len(JSONpayloadprev)))
			spot_status = "GASrest"
		elif len(data) < len(JSONpayloadprev):
			print("{0}: item removed! which one? data:{1}, JSONpayloadprev:{2}".format(datetime.now(), len(data), len(JSONpayloadprev)))
			spot_status = "GASrestunset"
			try:
				rbooking = requests.get(getBookingURL,auth=HttpNtlmAuth(dusername,password))
				# rbooking = requests.get(getTodayBookingURL,auth=HttpNtlmAuth(dusername,password))
				rbooking.raise_for_status()
				bookingdata = json.loads(rbooking.text)
				# get bookings from today forward only
				df = pd.read_json(json.dumps(bookingdata["BList"]))
				df = df[df['date'] >= pd.to_datetime('today')]
				df.drop(['bookOrPost','period'],axis=1,inplace=True)
				booking_str = df.transpose().to_json()
                
				o = {"guid": 0, "opcode": "i", "status": spot_status, "time": otime, "availspot": booking_str}
				o["id"] = -1  # this isn't precise
				o["spotnum"] = -1 # this isn't precise
				sendEvents(o)
			except requests.exceptions.HTTPError as err:
				print ("failed to make server connection[getTodayBookingURL]: " + str(err))
				sys.exit(1)
		# else:  ## catch the default case -> no change, so don't do anything
		# 	print("{0} d:{1}, J:{2}".format(otime, len(data), len(JSONpayloadprev)))

		# print("input: " + str(JSONpayloadprev))
		# print("current: " + str(data))

		##
		## parse here for multiple entries; though, that is a rare occurence
		##
		for entry in data:
			# print("Entry: " + str(entry))
			o = {"guid": 0, "opcode": "i", "status": spot_status, "time": otime, "availspot": entry}
			try: 
				print(entry)
				# o["spotdate"] = datetime.fromtimestamp(map(int, re.findall('\d+', str(entry[0])))[0]/1000)
			except TypeError as e:
				print("{0}".format(str(e)))

			o["spotnum"] = entry["parking_spot"]
			o["id"] = entry["id"]
			sendEvents(o)
			# print("o: " + str(o))
			list_of_entries.append(o)

		# print(list_of_entries)
		## sort the list of entries by id
		list_of_entries = sorted(list_of_entries, key=lambda k: k['id'])

		##
		## determine how long to wait before returning
		##
		# if ravailspot.text[1] is not "]":  ### there is a spot!
		if (len(data) > 0):
			# print("Spot Available via REST: " + ravailspot.text + " | " + otime)
			wait = random.uniform(0.25,0.5)  # quick wait so that we catch the booking quickly!
		else:
			if (0 <= datetime.now().weekday() <= 4):
				wait = random.uniform(0.5,2)  # wait a bit longer
			else: 
				wait = random.uniform(1,5)  # wait a bit longer on weekends

		ravailspot = rtodaybooking = message = "" # reset some values
		time.sleep(wait)
		return data
	except requests.exceptions.HTTPError as err:
		print ("failed to make server connection[getAvailSpotURL]: " + str(err))
		return (-1);	

#print (__name__)
if __name__ == '__main__':
	# print ("### main program logic ###")
	# get user / password from .netrc
	secrets = netrc.netrc() # Read from the .netrc file in your home directory
	dusername, account, password = secrets.authenticators('torvmpiis8')
	#print ("\"" + dusername + "\" \"" + password + "\"")

	JSONpayload = ""
	JSONpayloadlist = []

	JSONpayload = {"id": 49, "spotnum": 61, "guid": 0, "opcode": "i", "status": "GASrest", "time": datetime.now()}
	JSONpayloadlist.append(JSONpayload)
	# JSONpayload = {"id": 888, "spotnum": 62456, "guid": 0, "opcode": "i", "status": "GASrest", "time": datetime.now()}
	# JSONpayloadlist.append(JSONpayload)

	while True:
		JSONpayloadlist = parkingLoop(dusername, password, JSONpayloadlist)


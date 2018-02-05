import requests
import json
import sys
import time

NODE = "https://wallet.rise.vision"
NODEPAY = "http://localhost:5555"
PUBKEY = "8786543de4cf3aa09d1f17e046cd43bfb143ff7a7a8bd1d0a091fe0279d722c5"
LOGFILE = 'poollogs.json'
PERCENTAGE = 80
TRANSACTIONFEE = 0.1
WITHDRAW =  {}
RISEPERDAY = 427.72
MINPAYOUT = 1
SECRET = ""
SECONDSECRET = ""

def loadLog ():
	try:
		data = json.load (open (LOGFILE, 'r'))
	except:
		data = {
			"lastpayout": 0, 
			"accounts": {},
			"voters": []
		}
	return data
	
	
def saveLog (log):
	json.dump (log, open (LOGFILE, 'w'), indent=4, separators=(',', ': '))
	


def estimatePayouts (log):
	weight = 0.0
	payouts = []
	accounts=0

	uri = NODE + '/api/delegates/forging/getForgedByAccount?generatorPublicKey=' + PUBKEY + '&start=' + str (log['lastpayout']) + '&end=' + str (int (time.time ()))
	d = requests.get (uri)
	rew = d.json ()['rewards']
	forged = (int (rew) / 100000000)
	forgedwithdraw = forged
	print ('To distribute: %f RISE' % (forged))

	d = requests.get (NODE + '/api/delegates/voters?publicKey=' + PUBKEY).json ()

	WITHDRAWSHARE=0	
	for x in d['accounts']:
		if x['balance'] == '0' or x['address'] not in log['voters']:
			continue

		if not (x['address'] in log['accounts']) and x['balance'] != 0.0:
                	log['accounts'][x['address']] = { 'pending': 0.0, 'received': 0.0 }

		weight += float (x['balance']) / 100000000 
		accounts=accounts+1

		for y in log['voters'][x['address']]['sponsor']:
			if  y in WITHDRAW:
				WITHDRAW[y]+=(float (x['balance']) / 100000000)*(log['voters'][x['address']]['sponsor'][y]/100)
			else:
				WITHDRAW[y]=(float (x['balance']) / 100000000)*(log['voters'][x['address']]['sponsor'][y]/100)
			WITHDRAWSHARE+=(float (x['balance']) / 100000000)*(log['voters'][x['address']]['sponsor'][y]/100)
		
	for x in WITHDRAW:
		WITHDRAW[x]/=WITHDRAWSHARE

	print ('Total weight is: %f' % weight)
	
	log['weight']=weight
	log['riseperday']=RISEPERDAY*PERCENTAGE/100

	#Check for enough forged Rise to cover transaction fees
	if (forged*PERCENTAGE/100-accounts*TRANSACTIONFEE) < 0:
		return payouts
	
	for x in d['accounts']:
		if int (x['balance']) == 0 or x['address'] not in log['voters']:
			continue

		log['accounts'][x['address']]['balance']=float (x['balance']) / (100000000)
		log['accounts'][x['address']]['share']=float (x['balance']) / (weight*1000000)
		log['accounts'][x['address']]['riseperday']=float (x['balance']) / (weight*10000000000)*RISEPERDAY*PERCENTAGE
		
		# check if already exists in payouts
		foundpayout=False
		for y in payouts:
			if log['voters'][x['address']]["payoutaddress"]==y['address']:
				print ('Withdraw additional %f RISE to investor with wallet %s' % ((float (x['balance']) / 100000000 * (forged * log['voters'][x['address']]["share"]/100)) / weight,log['voters'][x['address']]["payoutaddress"]))
				y['balance']=y['balance']+(float (x['balance']) / 100000000 * (forged * log['voters'][x['address']]["share"]/100)) / weight
				foundpayout=True
				break
		if not foundpayout:
			print ('Withdraw %f RISE to investor with wallet %s' % ((float (x['balance']) / 100000000 * (forged * log['voters'][x['address']]["share"]/100)) / weight - TRANSACTIONFEE,log['voters'][x['address']]["payoutaddress"]))
			payouts.append ({ "address": log['voters'][x['address']]["payoutaddress"], "balance": ((float (x['balance']) / 100000000 * (forged * log['voters'][x['address']]["share"]/100)) / weight - TRANSACTIONFEE)})

		forgedwithdraw=forgedwithdraw-(float (x['balance']) / 100000000 * (forged * log['voters'][x['address']]["share"]/100)) / weight

	#Withdraw to defined wallets
	for k, v  in WITHDRAW.items():
		if forged*v>MINPAYOUT:
			print ('Withdraw %f RISE to wallet %s' % (forgedwithdraw*v-TRANSACTIONFEE,k))
			payouts.append ({ "address": k, "balance": (forgedwithdraw*v)-TRANSACTIONFEE})

	return payouts
	
	

if __name__ == "__main__":
	log = loadLog ()
	
	topay = estimatePayouts(log)
	
	f = open ('payments.sh', 'w')
	for x in topay:
		if x['address'] in log['voters']:
			if not (x['address'] in log['accounts']) and x['balance'] != 0.0:
				log['accounts'][x['address']] = { 'pending': 0.0, 'received': 0.0 }
			
			if x['balance'] < MINPAYOUT:
				log['accounts'][x['address']]['pending'] += x['balance']
				continue
			
			log['accounts'][x['address']]['received'] += x['balance']	
		
		f.write ('echo Sending ' + str (x['balance']) + ' to ' + x['address'] + '\n')
		
		data = { "secret": SECRET, "amount": int (x['balance'] * 100000000), "recipientId": x['address'] }
		if SECONDSECRET != None:
			data['secondSecret'] = SECONDSECRET
		
		f.write ('curl -k -H  "Content-Type: application/json" -X PUT -d \'' + json.dumps (data) + '\' ' + NODEPAY + "/api/transactions\n\n")
		f.write ('sleep 10\n')
			
	for y in log['accounts']:
		if  y  in log['voters'] and log['accounts'][y]['pending'] > MINPAYOUT:
			f.write ('echo Sending pending ' + str (log['accounts'][y]['pending']) + ' to ' + y + '\n')
			
			
			data = { "secret": SECRET, "amount": int (log['accounts'][y]['pending'] * 100000000), "recipientId": y }
			if SECONDSECRET != None:
				data['secondSecret'] = SECONDSECRET
			
			f.write ('curl -k -H  "Content-Type: application/json" -X PUT -d \'' + json.dumps (data) + '\' ' + NODEPAY + "/api/transactions\n\n")
			log['accounts'][y]['received'] += log['accounts'][y]['pending']
			log['accounts'][y]['pending'] = 0.0
			f.write ('sleep 10\n')
			
	# Donations
	if 'donations' in log:
		for y in log['donations']:
			f.write ('echo Sending donation ' + str (log['donations'][y]) + ' to ' + y + '\n')
				
			data = { "secret": SECRET, "amount": int (log['donations'][y] * 100000000), "recipientId": y }
			if SECONDSECRET != None:
				data['secondSecret'] = SECONDSECRET
			
		f.write ('curl -k -H  "Content-Type: application/json" -X PUT -d \'' + json.dumps (data) + '\' ' + NODEPAY + "/api/transactions\n\n")
		f.write ('sleep 10\n')


	f.close ()
	
	log['lastpayout'] = int (time.time ())
	
	print (json.dumps (log, indent=4, separators=(',', ': ')))
	
	if len (sys.argv) > 1 and sys.argv[1] == '-y':
		print ('Saving...')
		saveLog (log)
	else:
		yes = input ('save? y/n: ')
		if yes == 'y':
			saveLog (log)

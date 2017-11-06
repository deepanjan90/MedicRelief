from flask import Flask,request,current_app
from flask_restful import Resource, Api
from flask_cors import CORS
import json
import boto3
import uuid
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
#from crypto.Cipher import AES
#import os.sys

app = Flask(__name__, static_url_path='/static/')
api = Api(app)
cors = CORS(app, resources={r"*": {"origins": "*"}})
session = boto3.Session(
    aws_access_key_id='AKIAJ3MLTGN22ULGF3KQ',
    aws_secret_access_key='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'
)
dynamodb = session.resource('dynamodb', region_name='us-east-2')
sqs = session.resource('sqs', region_name='us-east-2')
queuedonor = sqs.get_queue_by_name(QueueName='medicrelief_donor_queue')
queuerequest = sqs.get_queue_by_name(QueueName='medicrelief_request_queue')


class HelloWorld(Resource):
	def get(self):
		#obj = AES.new('This is a key123', AES.MODE_CFB, 'This is an IV456')
		#pwd = obj.encrypt('abc')
		#userid = obj.encrypt('deep8@umbc.edu')
		#table = dynamodb.Table('users')
		#print(userid.strip())
		#try:
		'''table.put_item(
			Item={
			'userid': 'deep8@umbc.edu',
			'name': 'deep',
			'email': 'deep8@umbc.edu',
			'phone': '206-953-5102',
			'address': 'something',
			'usertype': 'General',
			'pass': 'abc'
			}
		)'''
		#except:
			#print("Unexpected error:", sys.exc_info()[0])
		#obj2 = AES.new('This is a key123', AES.MODE_CFB, 'This is an IV456')
		#lsd = obj2.decrypt(pwd).decode()
		#for message in queuedonor.receive_messages():
			#print(message.body)





		return {'hello': 'world'}

class Login(Resource):
	def post(self):
		requestData = request.get_json(force=True)
		user = requestData['user']
		pwd = requestData['pass']
		table = dynamodb.Table('users')
		print('userid - ',user)
		response = table.get_item(
			Key={
			'userid': user
			}
		)
		if 'Item' in response:
			item = response['Item']
			userid = item['userid']
			password = item['pass']
			if password == pwd:
				return {'login':'success', 'userid':userid}
			else:
				return {'login':'failed'}
		else:
			return {'login':'failed'}

class Register(Resource):
	def post(self):
		requestData = request.get_json(force=True)
		name = requestData['name']
		email = requestData['email']
		phone = requestData['phone']
		address = requestData['address']
		deliverytype = requestData['deliverytype']
		pwd = requestData['pass']
		usertype = requestData['usertype']
		medications = requestData['medications']

		if userExists(email):
			return {'registration':'failed', 'message': 'user alread exists'}

		table = dynamodb.Table('users')
		table.put_item(
			Item={
			'userid': email,
			'name': name,
			'email': email,
			'phone': phone,
			'address': address,
			'usertype': usertype,
			'pass': pwd
			}
		)

		if usertype=='General' and len(medications) > 0:
			table = dynamodb.Table('medicine')
			for medicine in medications:
				table.put_item(
					Item={
					'id': email+'_'+medicine['name'].strip().lower()+'_'+medicine['strength'],
					'name': medicine['name'].strip().lower(),
					'strength': medicine['strength']
					}
				)
		#Todo handle mediator with no medication

		return {'registration':'success'}

class ConsumerRequestCreate(Resource):
	def post(self):
		requestData = request.get_json(force=True)
		userid = requestData['userid']
		medicine = requestData['medication']
		quantity = int(requestData['quantity'])
		urgency = requestData['urgency']
		deliverytype = requestData['deliverytype']

		if not userExists(userid):
			return {'consumer_request':'failed', 'message': 'user does not exist'}

		table = dynamodb.Table('consumer_request')
		requestid = str(uuid.uuid4())
		table.put_item(
			Item={
			'id': requestid,
			'name': medicine['name'].strip().lower(),
			'strength': medicine['strength'],
			'quantity': quantity,
			'urgency': urgency,
			'userid': userid,
			'deliverytype': deliverytype,
			'datetime': str(datetime.utcnow()),
			'status': 'Requested'
			}
		)

		queuerequest.send_message(MessageBody=requestid)

		return {'consumer_request':'success'}

class ConsumerRequestView(Resource):
	def get(self,userid):
		table = dynamodb.Table('consumer_request')

		filtering_exp = Key('userid').eq(userid)
		response = table.scan(FilterExpression=filtering_exp)
		newitems = []
		if 'Items' in response:
			items = response['Items']
			for item in items:
				newitem = {}
				newitem['reqid']=item['id']
				newitem['name']=item['name']
				newitem['strength']=item['strength']
				newitem['quantity']=str(item['quantity'])
				newitem['deliverytype']=item['deliverytype']
				newitems.append(newitem)
		return json.dumps(newitems)

class ConsumerRequestDelete(Resource):
	def delete(self,reqid):
		table = dynamodb.Table('consumer_request')
		response = table.delete_item(Key={'id': reqid})

		return {'consumer_request':'success'}

class ProducerRequestCreate(Resource):
	def post(self):
		requestData = request.get_json(force=True)
		userid = requestData['userid']
		medicine = requestData['medication']
		quantity = int(requestData['quantity'])
		expiry = requestData['expiry']
		deliverytype = requestData['deliverytype']

		if not userExists(userid):
			return {'producer_request':'failed', 'message': 'user does not exist'}

		table = dynamodb.Table('producer_request')
		requestid = str(uuid.uuid4())
		table.put_item(
			Item={
			'id': requestid,
			'name': medicine['name'].strip().lower(),
			'strength': medicine['strength'],
			'quantity': quantity,
			'quantityavailable': quantity,
			'userid': userid,
			'expiry': expiry,
			'deliverytype': deliverytype,
			'status': 'AwaitingRequest'
			}
		)
		#Todo handle mediator with no medication
		queuerequest.send_message(MessageBody=requestid)
		return {'producer_request':'success'}

class ProducerRequestView(Resource):
	def get(self,userid):
		table = dynamodb.Table('producer_request')

		filtering_exp = Key('userid').eq(userid)
		response = table.scan(FilterExpression=filtering_exp)

		newitems = []
		if 'Items' in response:
			items = response['Items']
			for item in items:
				newitem = {}
				newitem['reqid']=item['id']
				newitem['name']=item['name']
				newitem['strength']=item['strength']
				newitem['quantity']=str(item['quantity'])
				newitem['quantityavailable']=str(item['quantityavailable'])
				newitem['deliverytype']=item['deliverytype']
				newitems.append(newitem)
		return json.dumps(newitems)

class ProducerRequestDelete(Resource):
	def delete(self,reqid):
		table = dynamodb.Table('producer_request')
		response = table.delete_item(Key={'id': reqid})

		return {'producer_request':'success'}

class ConsumerOptionView(Resource):
	def get(self,reqid):
		table = dynamodb.Table('consumer_request')
		response = table.get_item(
			Key={
			'id': reqid
			}
		)
		if 'Item' in response:
			item = response['Item']
			name = item['name']
			strength = item['strength']
			quantity = item['quantity']
		else:
			return {'ConsumerOption':'invalid reqid'}

		table = dynamodb.Table('producer_request')
		response = table.scan(FilterExpression=Attr('name').eq(name) & Attr('strength').eq(strength) & Attr('quantityavailable').gte(quantity))
		newitems = []
		if 'Items' in response:
			items = response['Items']
			for item in items:
				#newitem['address'] = item['address']
				newitem = {}
				newitem['quantity'] = str(item['quantityavailable'])
				newitem['reqid'] = item['id']
				newitems.append(newitem)
		return json.dumps(newitems)

class ConsumerOptionUpdate(Resource):
	def put(self,conreqid,prodreqid):
		reqid = str(uuid.uuid4())
		table = dynamodb.Table('consumer_request')

		response = table.get_item(
			Key={
			'id': conreqid
			}
		)
		if 'Item' in response:
			item = response['Item']
			name = item['name']
			strength = item['strength']
			quantity = item['quantity']
		else:
			return {'ConsumerOption':'invalid reqid'}

		table = dynamodb.Table('meta_request')
		table.put_item(
			Item={
			'id': reqid,
			'consumer_request_id': conreqid,
			'producer_request_id': prodreqid,
			'name': name,
			'quantity': quantity,
			'strength': strength,
			'status': 'ConsumerAcceptancePending'
			}
		)

		updateStatusConsReq(conreqid,'ConsumerAcceptancePending')

		return {'ConsumerSelectProducer':'Producer Requested', 'reqid':reqid}

def getMediators():
	table = dynamodb.Table('users')

	filtering_exp = Key('usertype').eq('Mediator')
	response = table.scan(FilterExpression=filtering_exp)
	mediators = []
	if 'Items' in response:
		items = response['Items']
		for item in items:
			mediator = {}
			mediator['address'] = item['address']
			mediator['id'] = item['userid']
			mediators.append(mediator)
	return mediators

class ProducerOptionView(Resource):
	def get(self,reqid):
		table = dynamodb.Table('meta_request')

		filtering_exp = Key('producer_request_id').eq(reqid)
		response = table.scan(FilterExpression=filtering_exp)

		newitems = []
		if 'Items' in response:
			items = response['Items']
			for item in items:
				newitem = {}
				newitem['id']=item['id']
				newitem['consumer_request_id']=item['consumer_request_id']
				newitem['name']=item['name']
				newitem['strength']=item['strength']
				newitem['quantity']=str(item['quantity'])
				newitem['status']=item['status']
				newitems.append(newitem)
		return json.dumps(newitems)

class ProducerOptionUpdate(Resource):
	def put(self,metareqid,mediatorid,state):
		table = dynamodb.Table('meta_request')
		response = table.get_item(
			Key={
			'id': metareqid
			}
		)

		medreqid = str(uuid.uuid4())

		if 'Item' in response:
			item = response['Item']
			item['mediator_request_id'] = medreqid
			item['status'] = 'MediatorAcceptancePending'

			if state == 'Accept':

				table = dynamodb.Table('mediator_request')
				table.put_item(
					Item={
					'id': medreqid,
					'mediatorid': mediatorid,
					'meta_request_id': metareqid,
					'consumer_request_id': item['consumer_request_id'],
					'producer_request_id': item['producer_request_id'],
					'name': item['name'],
					'quantity': item['quantity'],
					'strength': item['strength'],
					'status': 'PendingMediator'
					}
				)

				prodreqid = item['producer_request_id']

				table = dynamodb.Table('meta_request')
				table.put_item(Item=item)

				updateStatusConsReq(item['consumer_request_id'],'PendingMediator')

				updateStatusProdReq(item['producer_request_id'],'PendingMediator')

			else:

				updateStatusConsReq(item['consumer_request_id'],'ProducerCancelled')

				updateStatusProdReq(item['producer_request_id'],'ProducerCancelled')

			return {'ProducerOption':'status updated'}
		else:
			return {'ProducerOption':'invalid meta req id'}

class ProducerModerator(Resource):
	def get(self,userid):
		table = dynamodb.Table('users')
		response = table.get_item(
			Key={
			'userid': userid
			}
		)
		if 'Item' in response:
			item = response['Item']
			#based on location
			return json.dumps(getMediators())
		else:
			return json.dumps([])

class MediatorOptionView(Resource):
	def get(self,mediatorid):
		table = dynamodb.Table('mediator_request')
		response = table.scan(FilterExpression=Attr('mediatorid').eq(mediatorid))

		newitems = []
		if 'Items' in response:
			items = response['Items']
			for item in items:
				newitem = {}
				newitem['id']=item['id']
				newitem['consumer_request_id']=item['consumer_request_id']
				newitem['producer_request_id']=item['producer_request_id']
				newitem['name']=item['name']
				newitem['strength']=item['strength']
				newitem['quantity']=str(item['quantity'])
				newitem['status']=item['status']
				newitems.append(newitem)
		return json.dumps(newitems)

class MediatorOptionUpdate(Resource):
	def put(self,medreqid,state):
		if state == 'Accept':
			updateStatus(medreqid,'PendingProducerDelivery')
		elif state == 'ProducerDeliver':
			updateStatus(medreqid,'PendingConsumerDelivery')
		elif state == 'ConsumerDeliver':
			updateStatus(medreqid,'Delivered')
		else:
			updateStatus('MediatorCancelled')
		return {'MediatorOptionUpdate' : 'Status Updated'}

def updateStatus(medreqid,status):
	table = dynamodb.Table('mediator_request')
	response = table.get_item(
		Key={
		'id': medreqid
		}
	)
	if 'Item' in response:
		item = response['Item']
		item['status'] = status
		table.put_item(Item=item)

		table = dynamodb.Table('meta_request')
		response = table.get_item(
			Key={
			'id': item['meta_request_id']
			}
		)
		if 'Item' in response:
			item = response['Item']
			item['status'] = status
			table.put_item(Item=item)

			updateStatusConsReq(item['consumer_request_id'],status)

			updateStatusProdReq(item['producer_request_id'],status)

def updateStatusConsReq(conreqid,status):
	table = dynamodb.Table('consumer_request')
	response = table.get_item(
		Key={
		'id': conreqid
		}
	)
	if 'Item' in response:
		item = response['Item']
		item['status'] = status
		table.put_item(Item=item)

def updateStatusProdReq(prodreqid,status):
	table = dynamodb.Table('producer_request')
	response = table.get_item(
		Key={
		'id': prodreqid
		}
	)
	if 'Item' in response:
		item = response['Item']
		item['status'] = status
		table.put_item(Item=item)

def userExists(userid):
	table = dynamodb.Table('users')
	response = table.get_item(
		Key={
		'userid': userid
		}
	)
	if 'Item' in response:
		return True
	else:
		return False


@app.route('/views/<path:path>')
def send_html(path):
	return current_app.send_static_file('views/' + path)

@app.route('/lib/<path:path>')
def send_lib(path):
	return current_app.send_static_file('node_modules/' + path)

@app.route('/scripts/<path:path>')
def send_scripts(path):
	return current_app.send_static_file('scripts/' + path)

@app.route('/styles/<path:path>')
def send_styles(path):
	return current_app.send_static_file('styles/' + path)

api.add_resource(HelloWorld, '/hello')

api.add_resource(Login, '/login')
api.add_resource(Register, '/register')
api.add_resource(ConsumerRequestCreate, '/request/consumer/create')
api.add_resource(ConsumerRequestView, '/request/consumer/view/<string:userid>')
api.add_resource(ConsumerRequestDelete, '/request/consumer/delete/<string:reqid>')
api.add_resource(ProducerRequestCreate, '/request/producer/create')
api.add_resource(ProducerRequestView, '/request/producer/view/<string:userid>')
api.add_resource(ProducerRequestDelete, '/request/producer/delete/<string:reqid>')

api.add_resource(ConsumerOptionView, '/option/consumer/view/<string:reqid>')
api.add_resource(ConsumerOptionUpdate, '/option/consumer/update/<string:conreqid>/<string:prodreqid>')

api.add_resource(ProducerOptionView, '/option/producer/view/<string:reqid>')
api.add_resource(ProducerOptionUpdate, '/option/producer/update/<string:metareqid>/<string:mediatorid>/<string:state>')

api.add_resource(ProducerModerator, '/option/producer/location/<string:userid>')

api.add_resource(MediatorOptionView, '/option/mediator/view/<string:mediatorid>')
api.add_resource(MediatorOptionUpdate, '/option/mediator/update/<string:medreqid>/<string:state>')

if __name__ == '__main__':
    app.run(debug=False)
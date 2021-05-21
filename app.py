import streamlit as st
import pandas as pd
import io, base64
import requests, json

import SessionState

session_state = SessionState.get(token=None, url=None, objects=None)

## sidebar

if session_state.token is None:
	object_selection = st.sidebar.empty()
else:
	object_selection = st.sidebar.selectbox('Select object', ('') if session_state.objects is None else list(session_state.objects.values()))

## get info about object
if st.sidebar.button('Show object') and session_state.token is not None:

	# get metadata info about desired object
	object_name = 'Account'
	request_url = session_state.url + 'services/data/v51.0/sobjects/'+object_selection.strip()+'/describe'
	header = {
		'Authorization': 'Bearer '+session_state.token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)

	params = ['name', 'label', 'type', 'length', 'referenceTo' ] # ,'picklistValues']

	d = {}
	for r in response['fields']:
		for p in params:
			d[p] = d.get(p,list())
			if p != 'picklistValues':				
				d[p].append(r[p])
			else:
				d[p].append( ';'.join([ ('"%s"' % e['value']) for e in r[p] ]) )
		

	df = pd.DataFrame(d, columns=d.keys())
	st.table(df)

	for field in response['fields']:
		line = \
		field['name'] + '\t' + \
		field['label'] + '\t' + \
		field['type'] + '\t' + \
		str(field['length']) + '\t' + \
		str(field['nillable']) + '\t' + \
		str(field['permissionable']) + '\t' + \
		str(field['updateable']) + '\t' + \
		str(field['autoNumber']) + '\t' + \
		str(field['cascadeDelete']) + '\t' + \
		str(field['custom']) + '\t' + \
		' '.join(field['referenceTo']) + '\t' + \
		';'.join([ '"'+elem['value']+'"' for elem in field['picklistValues']]) +'\n'

# login form
form = st.form(key='conn_form')
url = form.text_input('url')
username = form.text_input('username')
password = form.text_input('password', type="password")
consumer_key = form.text_input('consumer key', type="password")
consumer_secret = form.text_input('consumer secret', type="password")
submit_connect = form.form_submit_button(label='Login')



if submit_connect:
	
	# prepare login statement
	request_url = url+'services/oauth2/token'
	body = {
		'grant_type': 'password'
	  , 'client_id': consumer_key
	  , 'client_secret': consumer_secret
	  , 'username': username
	  , 'password': password
	}

	login_response = requests.post(request_url, data=body)
	if login_response.status_code != 200:
		st.write("Error "+str(login_response.status_code))
		st.write(json.loads(login_response.text))
	else:
		st.write("Login successful")
		response = json.loads(login_response.text)
		session_state.token = response['access_token']
		session_state.url = url


if st.button('Load objects',key='load_obj'):
	if session_state.token is not None:
		#get list of all objects
		request_url = url + 'services/data/v51.0/sobjects'
		header = {
			'Authorization': 'Bearer '+session_state.token
		}
		obj_metadata_response = requests.get(request_url, headers=header)
		response = json.loads(obj_metadata_response.text)
		
		dct = {}
		for obj in response['sobjects']:
			dct[obj['name']] = obj['label']
		session_state.objects = dct
		#st.write(dct)
		#st.write(type(object_selection))
		#object_selection.selectbox('Select object', list(dct.values())) 
	else:
		st.write('Not connected') 



if st.sidebar.button('Logout', key='logout'):
	if session_state.token is not None:
					
		# prepare logout statement
		request_url = session_state.url+'services/oauth2/revoke'
		body = {
    		'token': session_state.token
		}
		session_state.token = None

		# make logout request
		logout_response = requests.post(request_url, data=body)
		if logout_response.status_code != 200:
			st.sidebar.write("Error "+str(logout_response.status_code))
			st.sidebar.write(json.loads(logout_response.text))
		else:
			st.sidebar.write("Logout successful")
			session_state.token = None

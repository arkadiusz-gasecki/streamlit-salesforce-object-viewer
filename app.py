import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import io, base64
import requests, json

import SessionState

# define session variables
session_state = SessionState.get(src_token=None, src_url=None, src_objects=None, tgt_token=None, tgt_url=None, tgt_objects=None)

# define default style
st.markdown(
        f"""
<style>
    .reportview-container .main .block-container{{
		width: 90%;        
		max-width: 2000px;
        padding-top: 1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 1rem;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


######################### functions ###################################

########### logout ##############
def logout(org='src'):

	token = session_state.src_token if org == 'src' else session_state.tgt_token

	if token is not None:
					
		# prepare logout statement
		request_url = session_state.url+'services/oauth2/revoke'
		body = {
    		'token': token
		}
		if org == 'src':
			session_state.src_token = None
		else:
			session_state.tgt_token = None 

		# make logout request
		logout_response = requests.post(request_url, data=body)
		if logout_response.status_code != 200:
			st.sidebar.write("Error "+str(logout_response.status_code))
			st.sidebar.write(json.loads(logout_response.text))
		else:
			st.sidebar.write("Logout successful")


########### login ##############
def login(url, consumer_key, consumer_secret, username, password, org='src'):
	# prepare login statement
	request_url = url+'services/oauth2/token'
	body = {
		'grant_type': 'password'
	  , 'client_id': consumer_key
	  , 'client_secret': consumer_secret
	  , 'username': username
	  , 'password': password
	}

	login_response = requests.request("POST", request_url, data=body)
	if login_response.status_code != 200:
		st.write("Error "+str(login_response.status_code))
		st.write(json.loads(login_response.text))
	else:
		st.write("Login successful")
		response = json.loads(login_response.text)
		if org == 'src':
			session_state.src_token = response['access_token']
			session_state.src_url = url
		elif org == 'tgt':
			session_state.tgt_token = response['access_token']
			session_state.tgt_url = url
		


########### load objects ##############
def load_objects():
	if session_state.token is not None:
		#get list of all objects
		request_url = session_state.url + 'services/data/v51.0/sobjects'
		header = {
			'Authorization': 'Bearer '+session_state.token
		}
		obj_metadata_response = requests.get(request_url, headers=header)
		response = json.loads(obj_metadata_response.text)
		
		dct = {}
		for obj in response['sobjects']:
			dct[obj['name']] = obj['label']
		session_state.objects = dct
	else:
		st.write('Not connected') 


########### describe object ##############

def parse_response(response, params,key='fields'):
	d = {}

	for r in response[key]:
		for p in params:
			d[p] = d.get(p,list())
			if p != 'picklistValues':				
				d[p].append(r[p])
			else:
				d[p].append( ';'.join([ '"{}"'.format(e['value']) for e in r[p] ]) )
	return d

def prepare_html_table(d, length, params):
	html = '<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">'
	html += '<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js"></script>'
	html += '<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.16.0/umd/popper.min.js"></script>'
	html += '<script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>'
	html += '<div class="container" style="max-width: 100%"><div class="table-responsive" style="max-height: 500px"><table class="table table-bordered">'
	for k in d:
		html += ("<th>"+str(k)+"</th>")
	
	for i in range(0,length):
		html += '<tr>'
		for p in params:
			if p == 'picklistValues':
				if len(d[p][i]) > 0:
					elem = '<select style="width: 200px">'+"".join(['<option>'+e.replace('"','')+'</option>' for e in d[p][i].split(';')])+'</select>'
				else:
					elem = ''
				html += ('<td>'+elem+'</td>')
			elif p == 'referenceTo':
				if len(d[p][i]) > 0:
					html += ('<td>'+str(d[p][i][0])+'</td>')
				else:
					html += ('<td></td>')
			else:
				html += ('<td>'+str(d[p][i])+'</td>')
		html += '</tr>'
	
	html+= '</table></div></div>'

	return html

def show_object(object_name):
	# get metadata info about desired object
	request_url = session_state.url + 'services/data/v51.0/sobjects/'+object_name+'/describe'
	header = {
		'Authorization': 'Bearer '+session_state.token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)
	
	#parse response about object
	params = ['name', 'label', 'type', 'length', 'nillable', 'referenceTo' ,'picklistValues']

	d = parse_response(response, params)
	object_structure = prepare_html_table(d, len(d['name']), params)

	#get metadata info about validation rules
	request_url = session_state.url + "services/data/v51.0/tooling/query?q=Select Id,Active,Description,ErrorDisplayField,ErrorMessage From ValidationRule Where EntityDefinition.DeveloperName = '"+object_name+"'"
	header = {
		'Authorization': 'Bearer '+session_state.token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)

	params = ['Id', 'Active', 'Description', 'ErrorDisplayField', 'ErrorMessage' ]
	
	d = parse_response(response, params,key='records')
	validation_rules = prepare_html_table(d, len(d['Id']), params)

	return (object_structure, validation_rules)



######################### main site ###################################

# add code that allow to autocomplete values read from config.ini file
cached_src_url = ''
cached_src_user = ''
cached_src_password = ''
cached_src_key = ''
cached_src_secret = ''

cached_tgt_url = ''
cached_tgt_user = ''
cached_tgt_password = ''
cached_tgt_key = ''
cached_tgt_secret = ''

if st.button('Autocomplete',key='autocomplete'):
	user = 'username'

src_col, tgt_col = st.beta_columns(2)

with src_col:
	src_form = st.form(key='conn_form_10')
	src_url = src_form.text_input('url', cached_src_url, key=11)
	src_username = src_form.text_input('username', cached_src_user, key=12)
	src_password = src_form.text_input('password', cached_src_password, type="password", key=13)
	src_consumer_key = src_form.text_input('consumer key', cached_src_key, type="password", key=14)
	src_consumer_secret = src_form.text_input('consumer secret', cached_src_secret, type="password", key=15)
	src_submit_connect = src_form.form_submit_button(label='Login')

	if st.button('Load source objects',key='load_src_obj'):
		load_objects()

with tgt_col:
	tgt_form = st.form(key='conn_form_20')
	tgt_url = tgt_form.text_input('url', cached_tgt_url, key=21)
	tgt_username = tgt_form.text_input('username', cached_tgt_user, key=22)
	tgt_password = tgt_form.text_input('password', cached_tgt_password, type="password", key=23)
	tgt_consumer_key = tgt_form.text_input('consumer key', cached_tgt_key, type="password", key=24)
	tgt_consumer_secret = tgt_form.text_input('consumer secret', cached_tgt_secret, type="password", key=25)
	tgt_submit_connect = tgt_form.form_submit_button(label='Login')
	
	if st.button('Load target objects',key='load_tgt_obj'):
		load_objects()

if src_submit_connect:
	login(src_url, src_consumer_key, src_consumer_secret, src_username, src_password, org='src')




######################### sidebar ###################################

if session_state.src_token is None:
	object_selection = st.sidebar.empty()
else:
	object_selection = st.sidebar.selectbox('Select object', ('') if session_state.objects is None else list(session_state.objects.values()))

## get info about object
if st.sidebar.button('Show object') and session_state.token is not None:
	
	(object_structure, validation_rules) = show_object(session_state.objects[object_selection.strip()])

	st.markdown('## Table structure ##')
	components.html(object_structure,height=500,scrolling=True)
	
	st.markdown('## Validation rules ##')
	components.html(validation_rules,height=500,scrolling=True)


if st.sidebar.button('Logout', key='logout'):
	logout(org='src')	







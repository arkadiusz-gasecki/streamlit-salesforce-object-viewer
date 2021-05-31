import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import io, base64
import requests, json
import configparser


import SessionState

from streamlit import script_runner


# define session variables
session_state = SessionState.get(src_token=None, src_url=None, src_objects=None, tgt_token=None, tgt_url=None, tgt_objects=None, autocomplete=None, added=False, add_cols=list(),all_columns=list())


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
		
def add_new_cols(new_cols):
	session_state.add_cols = new_cols

########### load objects ##############
def load_objects(org='src'):

	token = session_state.src_token if org == 'src' else session_state.tgt_token
	url = session_state.src_url if org == 'src' else session_state.tgt_url
	if token is not None:
		#get list of all objects
		request_url = url + 'services/data/v51.0/sobjects'
		header = {
			'Authorization': 'Bearer '+token
		}
		obj_metadata_response = requests.get(request_url, headers=header)
		response = json.loads(obj_metadata_response.text)
		
		dct = {}
		for obj in response['sobjects']:
			dct[obj['label']] = obj['name']
		return dct
	else:
		st.write('Not connected')


########### describe object ##############

def parse_response(response, params,key='fields'):
	d = {}
	additional_columns = list()
	if key == 'fields':
		additional_columns = list(response[key][0].keys())

	for r in response[key]:
		for p in params:
			d[p] = d.get(p,list())
			if p != 'picklistValues':				
				d[p].append(r[p])
			else:
				d[p].append( ','.join([ '"{}"'.format(e['value']) for e in r[p] ]) )
	return (d, additional_columns)

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
			if p.startswith('picklistValues'):
				if isinstance(d[p][i],str) and len(d[p][i]) > 0:
					elem = '<select style="width: 200px">'+"".join(['<option>'+e.replace('"','')+'</option>' for e in d[p][i].split(',')])+'</select>'
				else:
					elem = ''
				html += ('<td>'+elem+'</td>')
			elif p.startswith('referenceTo'):
				if isinstance(d[p][i],list) and len(d[p][i]) > 0:
					html += ('<td>'+str(d[p][i][0])+'</td>')
				else:
					html += ('<td></td>')
			else:
				html += ('<td>'+str(d[p][i])+'</td>')
		html += '</tr>'
	
	html+= '</table></div></div>'

	return html

def show_object(object_name,org='src',add=list()):
	# get metadata info about desired object
	token = session_state.src_token if org == 'src' else session_state.tgt_token
	url = session_state.src_url if org == 'src' else session_state.tgt_url

	request_url = url + 'services/data/v51.0/sobjects/'+object_name+'/describe'
	header = {
		'Authorization': 'Bearer '+token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)
	
	#parse response about object
	params = ['name', 'label', 'type', 'length', 'nillable', 'referenceTo' ,'picklistValues'] + add
	
	d, additional_columns = parse_response(response, params)
	df = pd.DataFrame(d)
	
	object_structure = prepare_html_table(d, len(d['name']), params)

	#get metadata info about validation rules
	request_url = url + "services/data/v51.0/tooling/query?q=Select Id,Active,Description,ErrorDisplayField,ErrorMessage From ValidationRule Where EntityDefinition.DeveloperName = '"+object_name+"'"
	header = {
		'Authorization': 'Bearer '+token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)
	
	params = ['Id', 'Active', 'Description', 'ErrorDisplayField', 'ErrorMessage' ]
	
	d, _ = parse_response(response, params,key='records')
	validation_rules = None if len(d) == 0 else prepare_html_table(d, len(d['Id']), params)

	return (object_structure, validation_rules, additional_columns, df)
	
def get_table_download_link_csv(df,filename):
    csv = df.to_csv().encode()
    b64 = base64.b64encode(csv).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="'+filename+'.csv" target="_blank">Download csv file</a>'
    return href

######################### main site ###################################

# add code that allow to autocomplete values read from config.ini file
col1, col2, col3 = st.beta_columns(3)
with col1:
	pwd = st.text_input("Autocmplete password", type="password", key=50)
	auto = st.button('Autocomplete',key='autocomplete')
	

if (auto == True and pwd == st.secrets["auto_complete"]) or session_state.autocomplete:

	cached_src_url      = st.secrets["SOURCE_CONNECTION"]["url"]
	cached_src_key      = st.secrets["SOURCE_CONNECTION"]["client_id"]
	cached_src_secret   = st.secrets["SOURCE_CONNECTION"]["client_secret"]
	cached_src_user     = '' #st.secrets["SOURCE_CONNECTION"]["username"]
	cached_src_password = '' #st.secrets["SOURCE_CONNECTION"]["password"] + st.secrets["SOURCE_CONNECTION"]["token"]

	cached_tgt_url      = st.secrets["TARGET_CONNECTION"]["url"]
	cached_tgt_key      = st.secrets["TARGET_CONNECTION"]["client_id"]
	cached_tgt_secret   = st.secrets["TARGET_CONNECTION"]["client_secret"]
	cached_tgt_user     = '' #st.secrets["TARGET_CONNECTION"]["username"]
	cached_tgt_password = '' #st.secrets["TARGET_CONNECTION"]["password"] + st.secrets["TARGET_CONNECTION"]["token"]

	session_state.autocomplete = True

if session_state.autocomplete is None:
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
		session_state.src_objects = load_objects()

with tgt_col:
	tgt_form = st.form(key='conn_form_20')
	tgt_url = tgt_form.text_input('url', cached_tgt_url, key=21)
	tgt_username = tgt_form.text_input('username', cached_tgt_user, key=22)
	tgt_password = tgt_form.text_input('password', cached_tgt_password, type="password", key=23)
	tgt_consumer_key = tgt_form.text_input('consumer key', cached_tgt_key, type="password", key=24)
	tgt_consumer_secret = tgt_form.text_input('consumer secret', cached_tgt_secret, type="password", key=25)
	tgt_submit_connect = tgt_form.form_submit_button(label='Login')
	
	if st.button('Load target objects',key='load_tgt_obj'):
		session_state.tgt_objects = load_objects('tgt')

if src_submit_connect:
	if pwd == st.secrets["auto_complete"]:
		tmp_src_username = st.secrets["SOURCE_CONNECTION"]["username"] if (src_username is None or src_username == '') else src_username
		tmp_src_password = st.secrets["SOURCE_CONNECTION"]["password"] + st.secrets["SOURCE_CONNECTION"]["token"] if (src_password is None or src_password == '') else src_password
		
		src_password = tmp_src_password
		src_username = tmp_src_username
	login(src_url, src_consumer_key, src_consumer_secret, src_username, src_password, org='src')

if tgt_submit_connect:
	if pwd == st.secrets["auto_complete"]:
		tmp_tgt_username = st.secrets["TARGET_CONNECTION"]["username"] if (tgt_username is None or tgt_username == '') else tgt_username
		tmp_tgt_password = st.secrets["TARGET_CONNECTION"]["password"] + st.secrets["TARGET_CONNECTION"]["token"] if (tgt_password is None or tgt_password == '') else tgt_password
		
		tgt_password = tmp_tgt_password
		tgt_username = tmp_tgt_username
	login(tgt_url, tgt_consumer_key, tgt_consumer_secret, tgt_username, tgt_password, org='tgt')



######################### sidebar ###################################

if session_state.src_token is None:
	src_object_selection = st.sidebar.empty()
else:
	src_object_selection = st.sidebar.selectbox('Select source object', ('') if session_state.src_objects is None else list(session_state.src_objects.keys()))

if session_state.tgt_token is None:
	tgt_object_selection = st.sidebar.empty()
else:
	tgt_object_selection = st.sidebar.selectbox('Select target object', ('') if session_state.tgt_objects is None else list(session_state.tgt_objects.keys()))



## get info about object

object_structure = ''
validation_rules = ''
org_selected = ''
df = pd.DataFrame()
filename = 'capture'
if (st.sidebar.button('Show source object',key='show_src') or session_state.added) and session_state.src_token is not None:
	(object_structure, validation_rules, additional_columns, df) = show_object(session_state.src_objects[src_object_selection.strip()],org='src',add=session_state.add_cols)
	session_state.all_columns = additional_columns
	session_state.added = False
	org_selected = 'Source'
	filename = session_state.src_objects[src_object_selection.strip()]
	
	
if st.sidebar.button('Show target object',key='show_tgt' or session_state.added) and session_state.tgt_token is not None:
	(object_structure, validation_rules, additional_columns, df) = show_object(session_state.tgt_objects[tgt_object_selection.strip()],org='tgt',add=session_state.add_cols)
	session_state.all_columns = additional_columns
	session_state.added = False
	org_selected = 'Target'
	filename = session_state.tgt_objects[tgt_object_selection.strip()]

if st.sidebar.button('Compare objects', key='show_cmp'):
	session_state.added = False
	org_selected = 'Compare'
	(_1,_2,_3, sdf) = show_object(session_state.src_objects[src_object_selection.strip()],org='src',add=session_state.add_cols)
	(_1,_2,_3, tdf) = show_object(session_state.tgt_objects[tgt_object_selection.strip()],org='tgt',add=session_state.add_cols)
	
	sdf = sdf.merge(tdf,how='outer',left_on='name', right_on='name',suffixes=('_src','_tgt'))
	st.markdown(get_table_download_link_csv(sdf,session_state.src_objects[src_object_selection.strip()]), unsafe_allow_html=True)
	
	html = prepare_html_table(sdf.to_dict(), len(sdf), list(sdf.columns)) 
	components.html(html,height=500,scrolling=True)
	

if org_selected != 'Compare':
	st.markdown('## '+org_selected+' Table structure ##')
	st.markdown(get_table_download_link_csv(df,filename), unsafe_allow_html=True)
	components.html(object_structure,height=500,scrolling=True)

## add form for adding columns
col_form = st.form(key='col_form')
new_cols = col_form.multiselect('Select additional columns', session_state.all_columns)
sub = col_form.form_submit_button('Add')
if sub:
	session_state.added = True
	if new_cols != session_state.add_cols:
		add_new_cols(new_cols)
		raise st.script_runner.RerunException(st.script_request_queue.RerunData(None))


## show validation rules
if org_selected != 'compare':
	st.markdown('## Validation rules ##')
	components.html(validation_rules,height=500,scrolling=True)

## add logout

if st.sidebar.button('Logout', key='logout'):
	logout(org='src')
	logout(org='tgt')







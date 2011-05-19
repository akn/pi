from flask import Module, request, session, render_template, redirect, g
from concierge.services_models import Service

from concierge.auth import HistoryEntry
from concierge import db

from flaskext.wtf import Form, Required, Length, BooleanField
from flaskext.wtf.html5 import SearchField

from xml.etree import ElementTree
from common import xml_types, rest_method_parameters
from common.search import match_keywords_to_something


search = Module(__name__, 'search')

class SearchForm(Form):
    search_query = SearchField('query', validators=[Required(), Length(min=1)])
    
def match_search_to_methods_keywords(query, methods):
    '''assumes word separated by single space.
    returns list of pairs of (query, method)'''
    keywords_methods=[([k.keyword for k in method.resource.keywords], method) for method in methods]
    return match_keywords_to_something(query, keywords_methods)

def result_xml_to_text(xml):
    if type(xml)==str or type(xml)==unicode:
        #this is xml in string format
        xml= ElementTree.fromstring(xml.encode('utf-8'))

    if xml.get('type')== xml_types.LIST_TYPE:
        html_children= "".join(map(result_xml_to_text, xml.getchildren()) )
        r, k = xml.get('representative'), xml.get('kind')
        list_str= "%s: %s" % (k,r) if (k and r) else k or "List"
        list_header= '<h3>%s</h3>' % list_str
        data_collapsed= "true" if k else "false"
        return '<div data-role="collapsible" data-collapsed="%s" >%s%s</div>' % (data_collapsed, list_header,html_children)
    else:
        return '<p>%s</p>' % (xml.get('kind') + ": "+ xml.text )


@search.route('/custom_search/', methods=['GET', 'POST'])
def custom_search():
    services = Service.query.all()

    class CustomSearchForm(Form):
        search_query = SearchField('Search', validators=[Required(), Length(min=1)])
        variables = locals()
        for service in services:
            variables[service.name] = BooleanField(service.name)
        
    form = CustomSearchForm(request.form)

    services_names = [ service.name for service in services]
    service_dict = dict(zip(services_names, services))
    
    if form.validate_on_submit():
        query= form.search_query.data
        
        received_names = [ entry.label.text for entry in form \
                            if entry != form.search_query and entry != form.csrf and entry.data]
        received_services = [ service_dict[name] for name in received_names ]    
        
        #creates the entry in the user_history if the user is logged in
        if session.get('auth'):
            hstr_entry = HistoryEntry(user_id=session['id'], query=query)
            db.session.add(hstr_entry)
            db.session.commit()
        
        return search_aux(query, received_services)  
        
    favorite_check = request.args.get('check_favorites', '')   # 
    
        
    if favorite_check:
        user = g.user
        favorites = user.favorite_services
        favorite_services_names = [ service.name for service in favorites ]
        for field in form:
            if field != form.search_query:
                if field.name in favorite_services_names:
                    field.data = True
    
    return render_template('custom_search.html', search_form=form)


@search.route('/search/<search_query>')
def search_history(search_query):
    query = search_query #history search
    return search_aux(query)


@search.route('/search/', methods=['POST'])
def search_view():
    form = SearchForm(request.form)

    if  form.validate_on_submit():
        query= form.search_query.data
            
        #creates the entry in the user_history if the user is logged in
        if session.get('auth'):
            hstr_entry = HistoryEntry(user_id=session['id'], query=query)
            db.session.add(hstr_entry)
            db.session.commit()

        return search_aux(query)
    return redirect('/')   #null string case

def search_aux(query, services=None):
    if services==None:
        services= Service.query.all()
    search_methods= [m.global_search() for m in services]
    matches = match_search_to_methods_keywords(query, search_methods)
    if len(matches)==0:
        #no keywords match
        results_xml=[]
    else:
        results_xml= [method.execute({rest_method_parameters.QUERY: query}) for ignoreme, method in matches]
    search_results= "".join(map(result_xml_to_text, results_xml))
    return render_template('search.html', search_results=search_results)

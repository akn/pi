from sqlalchemy import or_
from sqlalchemy.orm import joinedload
import itertools
import urllib

import xser


def flatten(q):
	r= []
	for x in q:
		if hasattr(x, '__iter__'):
			r.extend(flatten(x))
		else:
			r.append(x)
	return r


def match_keywords_to_something(query, l):
    '''given a query and a list of tuples in the form
    ((K1,K2,...), something)
    where Kn are keywords and something is what you want returned,
    matches the query to the keywords and returns a list of tuples in
    the form
    (processed_query, something)
    where processed_query is the query without the matched keyword'''
    result=[]
    for keywords, v in l:
        splited_query= query.split(' ')
        for keyword in keywords:
            try:
                i= splited_query.index(keyword)
                processed_query_splitted= splited_query[:]
                processed_query_splitted.pop(i)
                processed_query= " ".join(processed_query_splitted)
                result.append( (processed_query, v) )
            except:
                pass    #no match
    return result

def service_search_xmlresponse(model_list, quoted_query):
    query= urllib.unquote_plus(quoted_query)
    results= service_search(model_list, query)
    if len(results) == 0:
        xml_text = ""
    else:
        xml_text = '<entity type="list">'
        for result in results:
            xml_text += result.to_xml_shallow()
        xml_text += '</entity>'
    return xml_text

def service_search(model_list, query):
    '''given a list of model classes and a query, searches the database
    for those models, matching the keywords'''
    keywords_models= [(model.keywords, model) for model in model_list]
    queries_models= match_keywords_to_something(query, keywords_models)
    results_lists= [service_model_search(m, q) for q,m in queries_models]
    results= flatten(results_lists)
    return results

def service_model_search(model_class, query):
    '''given a Model Class and a query string, searches the model class
    table. Assumes the model class has "search_atributes", "search_joins"
    and "search_representative"'''

    atributes= model_class.search_atributes
    join_models= getattr(model_class, "search_joins", [])
    representative= getattr(model_class, "search_representative", None)

    joins= map(joinedload, join_models)
    atributes_likes= [getattr(model_class, atr).match(query) for atr in atributes]

    results= model_class.query.options(*joins).filter(or_(*atributes_likes)).all()
    if representative:
        results= [getattr(r,representative) for r in results]
    return results

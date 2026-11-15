"""Modelo editable de consultas; independiente de los widgets."""

import copy
from uuid import uuid4

from ..config.profiles import COUNTRIES
from ..search.query_builder import prepare


class SearchRows:
    def __init__(self):
        self.rows=[]

    def validate(self,country,criterion,enabled):
        country=country.strip().upper()
        criterion=criterion.strip()
        if country not in COUNTRIES: raise ValueError('Enter a valid two-letter ISO country code')
        if not criterion: raise ValueError('Enter search criteria')
        if type(enabled) is not bool: raise ValueError('Enabled must be a boolean')
        return country,criterion

    def add(self,country,criterion,enabled=True,profile=None):
        country,criterion=self.validate(country,criterion,enabled)
        base=copy.deepcopy(profile) if profile else {
            'schema_version':'1.0','client_id':'manual_'+uuid4().hex,
            'client_name':criterion,'timezone':'America/Bogota',
            'search':{'template_url':'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&is_targeted_country=false&media_type=all&search_type=keyword_unordered&sort_data%5Bdirection%5D=desc&sort_data%5Bmode%5D=total_impressions'},
            'approved_advertiser_ids':[],'approved_domains':[]}
        row={'id':uuid4().hex,'enabled':enabled,'country':country,'criterion':criterion,'profile':base}
        self.rows.append(row)
        return row['id']

    def get(self,row_id):
        return next(row for row in self.rows if row['id']==row_id)

    def update(self,row_id,country,criterion,enabled):
        country,criterion=self.validate(country,criterion,enabled)
        self.get(row_id).update(country=country,criterion=criterion,enabled=enabled)

    def remove(self,row_id):
        self.get(row_id)
        self.rows[:]=[row for row in self.rows if row['id']!=row_id]

    def queries(self,days):
        if type(days) is not int or not 1<=days<=90:
            raise ValueError('Days to review must be between 1 and 90')
        result=[]
        for row in self.rows:
            if not row['enabled']: continue
            profile=copy.deepcopy(row['profile'])
            profile.update(enabled=True,country=row['country'].lower(),days_to_review=days)
            profile['criteria']=[{'query':row['criterion'],'enabled':True}]
            profile['search']['date_range']={'mode':'rolling_days'}
            prepare(profile)
            result.append(profile)
        return result

    def from_profiles(self,profiles):
        self.rows=[]
        for profile in profiles:
            for criterion in profile['criteria']:
                self.add(profile['country'],criterion['query'],
                         profile.get('enabled',True) and criterion.get('enabled',True),profile)

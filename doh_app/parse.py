import pandas as pd
import datetime
from lifelines import CoxPHFitter
import numpy as np
import pickle
from sqlalchemy import create_engine
from sqlalchemy.types import Integer, String, Float

start = datetime.datetime.now()
origin = datetime.datetime.now()

df = pd.read_csv('C:/Users/a/Documents/Projects/doh_app/static/DOHMH_New_York_City_Restaurant_Inspection_Results (3).csv')

df.columns = [x.lower() for x in df.columns]
df.columns = [x.replace(' ','_') for x in df.columns]


df = df[df['inspection_date']!='1900-01-01']
df = df[(df['inspection_type'].str.contains('Cycle')) | 
(df['inspection_type'].str.contains('Pre')) |
        (pd.isna(df['inspection_type']))]
df = df[['camis', 'dba', 'building', 'street', 'boro', 'inspection_date', 'action', 'score','inspection_type','record_date','violation_description',
        'latitude','longitude','cuisine_description','zipcode']]

df['inspection_date'] = df['inspection_date'].astype('datetime64[ns]')
df['record_date'] = df['record_date'].astype('datetime64[ns]')

df['zipcode'] = df['zipcode'].astype(str).replace(r'\.0', '', regex=True)
df['dba'] = df['dba'].astype(str).apply(lambda x: ' '.join(x.split()).title())
df['address'] = df['building'] + ' ' + df['street'] + ', ' + df['boro']
df['address'] = df['address'].astype(str).apply(lambda x: ' '.join(x.split()).title())
df['address'] = df['address'].str.replace('\s{2,}', ' ', regex=True)


df.drop(columns=['building','street','boro'], inplace=True)


small = df['dba'].apply(lambda x: x.lower())
small = small.str.replace('[^a-zA-Z0-9 ]', '', regex=True)
df['small'] = small


df['month'] = df['inspection_date'].dt.month
# df['score'] = df['score'].astype(int)
df.dropna(subset=['latitude','longitude'], inplace=True)


df = df.sort_values(['camis','inspection_date'], ascending=True)
df.reset_index(inplace=True, drop=True)

end = datetime.datetime.now() - start

print('finished preprocessing in {}'.format(end))

# end of Restaurants preprocessing

# sqlite push
start = datetime.datetime.now()


db_uri = 'sqlite:///site.db'
engine = create_engine(db_uri, echo=False)
table_name = 'restaurants'

df.to_sql(
    table_name,
    engine,
    if_exists='replace',
    index=True,
    index_label='index_label',
    chunksize=10000,
    dtype={
    'camis': Integer, 
    'dba': String, 
    'inspection_date': String, 
    'action': String, 
    'score': Integer, 
    'inspection_type': String, 
    'record_date': String, 
    'violation_description': String, 
    'latitude': Float, 
    'longitude': Float, 
    'cuisine_description': String, 
    'address': String, 
    'small': String, 
    'month': Integer
    }
)

end = datetime.datetime.now() - start

print('finished sql push in {}'.format(end))


# preprocess for model fitting

start = datetime.datetime.now()


df['next_grade'] = df['inspection_date'].shift(-1)

df.loc[df.drop_duplicates("camis", keep='last').index,'next_grade'] = pd.NaT

df['time_til'] = df['next_grade'] - df['inspection_date']

df['time_til'] = df['time_til'].where(pd.notnull(df['time_til']), (df['record_date'] - df['inspection_date']))

df['event'] = df['next_grade'].apply(lambda x: 1 if pd.notnull(x) else 0)

df['time_til'] = df['time_til'].dt.days

df = df[df['time_til'] < 1000]
df.reset_index(drop=True, inplace=True)

inspection_bin = []

for i in range(len(df)):
    current_type = df.loc[i,'inspection_type']
    current_score = df.loc[i,'score']
    current_camis = df.loc[i,'camis']
    current_action = df.loc[i,'action']
    current_time = df.loc[i,'time_til']
    current_event = df.loc[i,'event']

    if (df.loc[i,'inspection_date'] < pd.Timestamp('2020-03-17')) & (current_event == 0):
        inspection_bin.append('covid')

    elif (df.loc[i,'inspection_date'] < pd.Timestamp('2020-03-17')) & (df.loc[i,'next_grade'] > pd.Timestamp('2021-07-19')):
        inspection_bin.append('covid')
    
    elif 'losed' in current_action:
        inspection_bin.append('was_closed')
        
    elif 're-open' in current_action:
        inspection_bin.append('re-opened')
        
    elif 'Cycle' in current_type:
        if 'Initial' in current_type:
            if (current_score < 14) & (current_event == 1) & (current_time < 300):
                inspection_bin.append('cyc_init_1')
            elif current_score < 14: # This event shouldn't be able to occur
                inspection_bin.append('cyc_init_0')
            elif current_score > 13:
                inspection_bin.append('cyc_init_1')
                
        elif 'Re-' in current_type:
            previous_score = df.loc[i-1,'score']
            previous_camis = df.loc[i-1,'camis']
            
            if current_camis == previous_camis:
                if previous_score < 14:
                    inspection_bin.append('cyc_re_0')
                elif previous_score > 13 and previous_score < 28:
                    inspection_bin.append('cyc_re_1')
                elif previous_score > 27:
                    inspection_bin.append('cyc_re_2')
            else:
                inspection_bin.append('missing_prior_cycle')
        else:
            inspection_bin.append('other_cycle')
            
            
    elif 'Pre-' in current_type:
        if 'Initial' in current_type:
            if (current_score < 14) & (current_event == 1) & (current_time < 300):
                inspection_bin.append('pre_init_1')
            elif current_score < 14:
                inspection_bin.append('pre_init_0')
            elif current_score > 13:
                inspection_bin.append('pre_init_1')
                
        elif 'Re-' in current_type:
            previous_camis = df.loc[i-1,'camis']
            previous_score = df.loc[i-1,'score']
            
            if current_camis == previous_camis:
                if previous_score < 14:
                    inspection_bin.append('pre_re_0')
                elif previous_score > 13 and previous_score < 28:
                    inspection_bin.append('pre_re_1')
                elif previous_score > 27:
                    inspection_bin.append('pre_re_2')
            else:
                inspection_bin.append('missing_prior_pre')
        else:
            inspection_bin.append('other_pre')
    else:
        inspection_bin.append('other')
        

inspection_bin = pd.Series(inspection_bin)

df['inspection_bin'] = inspection_bin


# fit proportional hazards model


cph = CoxPHFitter()
cph.fit(df[['time_til','event','inspection_bin']], duration_col='time_til', event_col='event', strata=['inspection_bin'])


filename = './static/todays_model.sav'
pickle.dump(cph, open(filename, 'wb'))

end = datetime.datetime.now() - start
print('finished model fit in {}'.format(end))

# build reference table for model args

start = datetime.datetime.now()

model_args = df.drop_duplicates('camis', keep="last")[['time_til','event','inspection_bin','camis']]
model_args.reset_index(drop=True, inplace=True)

table_name = 'arguments'

model_args.to_sql(
    table_name,
    engine,
    if_exists='replace',
    index=True,
    index_label='index_label',
    chunksize=10000,
    dtype={
    'camis': Integer,
    'inspection_bin': String,
    'time_til': Integer,
    'event': Integer 
    }
)


end = datetime.datetime.now() - start
print('model args done in {}'.format(end))

end = datetime.datetime.now() - origin
print('done done in {}'.format(end))

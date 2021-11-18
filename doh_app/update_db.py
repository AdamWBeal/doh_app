import csv
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy import inspect
from app import Restaurants, engine, db
import os

mapper = inspect(Restaurants)
Session = sessionmaker(bind=engine)
session = Session()

# try:
#     db.session.query(Restaurants).delete()
# except:
#     pass

with open('./static/df.csv', 'r') as csv_file:
    read_file = csv.reader(csv_file)

    buffer = []
    for row in read_file:
        buffer.append({
            'camis' : row[1],
            'dba' : row[2],
            'inspection_date' : row[3],
            'action' : row[4],
            'score' : row[5],
            'inspection_type' : row[6],
            'record_date' : row[7],
            'violation_description' : row[8],
            'latitude' : row[9],
            'longitude' : row[10],
            'cuisine_description' : row[11],
            'address' : row[12],
            'small' : row[13],
            'month' : row[14],
        })
        if len(buffer) % 10000 == 0:
            session.bulk_insert_mappings(mapper, buffer)
            buffer = []

session.bulk_insert_mappings(mapper, buffer)

session.commit()
session.close()
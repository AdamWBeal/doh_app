from flask import Flask, redirect, url_for, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import pickle
import datetime
import pandas as pd
import re

app = Flask(__name__)
app.secret_key = 'balls'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Restaurants(db.Model):
    index_label = db.Column("index_label", db.Integer, primary_key=True)
    camis = db.Column(db.Integer, nullable=True)
    dba = db.Column(db.String, nullable=True)
    inspection_date = db.Column(db.String, nullable=True)
    action = db.Column(db.String, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    inspection_type = db.Column(db.String, nullable=True)
    record_date = db.Column(db.String, nullable=True)
    violation_description = db.Column(db.String, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    cuisine_description = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    small = db.Column(db.String, nullable=True)
    month = db.Column(db.Integer, nullable=True)


class Arguments(db.Model):
    index_label = db.Column("index_label", db.Integer, primary_key=True)
    camis = db.Column(db.Integer, nullable=True)
    inspection_bin = db.Column(db.String)
    time_til = db.Column(db.Integer)
    event = db.Column(db.Integer)


@app.route("/", methods=["POST", 'GET'])
def home():
    if request.method == "POST":
        query = request.form['query']
        query = query.lower()
        # query.replace('[^a-zA-Z0-9 ]', '', regex=True)
        query = re.sub('[^a-zA-Z0-9 ]', '', query)
        print(query)
        return redirect(url_for('search', query=query))
    return render_template('index.html', title='Home')


@app.route("/search/<query>")
def search(query):
    result = db.session.query(Restaurants.dba, Restaurants.address, Restaurants.camis).filter(
        Restaurants.small.like('%{}%'.format(query))).distinct().limit(40).all()
    return render_template('search.html', title='Search', rests=result)


@app.route("/details/<int:camis>")
def details(camis):
    prior = Restaurants.query.filter_by(camis=camis)
    prior = prior[::-1]

    priorDict = {}
    for i in prior:
        if i.inspection_date not in priorDict:
            priorDict[i.inspection_date] = []

        priorDict[i.inspection_date].append(i.violation_description)

    lat, lon = prior[0].latitude, prior[0].longitude
    latTolerance = .012837
    lonTolerance = .016154

    highLat = lat + (latTolerance / 2)
    lowLat = lat - ( latTolerance / 2)
    highLon = lon + (lonTolerance / 2)
    lowLon = lon - (lonTolerance / 2)
    currentMonth = datetime.datetime.now().month

    bolo = Restaurants.query.filter(Restaurants.latitude < highLat, Restaurants.latitude > lowLat,
                                    Restaurants.longitude < highLon, Restaurants.longitude > lowLon, Restaurants.month == currentMonth)
    violations = {}
    for i in bolo:
        if i.violation_description not in violations:
            violations[i.violation_description] = 1
        else:
            violations[i.violation_description] += 1

    violations = dict(
        sorted(violations.items(), key=lambda item: item[1], reverse=True))

    asPercent = [round((x / (sum(violations.values()))) * 100, 2)
                 for x in violations.values()]

    bolo = list(zip(violations.keys(), asPercent))

    barValues = asPercent

    barLabs = list(violations.keys())
    barLabels = []
    for i in barLabs:
        if not i:
            barLabels.append(0)
        else:
            barLabels.append(i)

    if len(barValues) > 15:
        barValues = barValues[:15]
        barLabels = barLabels[:15]

    dummyIndex = list(range(1, len(barValues) + 1))



# load the pickled model and run it

    loaded_model = pickle.load(open('./static/todays_model.sav', 'rb'))

    modelArgs = Arguments.query.filter_by(camis=camis)

    arguments = pd.DataFrame({'event': [0], 'time_til': [modelArgs[0].time_til], 
                               'inspection_bin': [modelArgs[0].inspection_bin]})
    model = loaded_model.predict_survival_function(arguments, conditional_after=modelArgs[0].time_til)
    model['days'] = model.index
    model['days'] = model['days'].apply(
        lambda d: pd.to_datetime('today') + pd.DateOffset(d))

    model = model.set_index('days')

    labels = list(model.index.astype(str))
    labels = [x[:10] for x in labels]
    values = list(model.iloc[:, 0])

    return render_template('details.html', title='Details', prior=prior,
                           bolo=bolo, labels=labels, values=values, barValues=barValues,
                           barLabels=barLabels, dummyIndex=dummyIndex, priorDict=priorDict)


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)


# engine = create_engine('sqlite:///restaurants.sqlite3')

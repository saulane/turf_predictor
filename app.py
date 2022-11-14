from flask import Flask, render_template, Response, abort
import pandas as pd
import datetime
from os.path import exists

from predictions import Predictor
app = Flask(__name__)

@app.route("/")
def hello_world(name=None):
    return render_template("home.html", name=name)


@app.route("/preds")
def predictions():
    today = datetime.date.today().strftime("%d-%m-%Y")
    path = f"../predictions/{today}.csv"
    if exists(path):
        preds_df = pd.read_csv(path)
    else:
        try:
            predictor = Predictor(30)
            preds_df = predictor.predict()
        except:
            abort(404, description="Missing Data")

    return Response(preds_df.to_json(orient="records"), mimetype='application/json')
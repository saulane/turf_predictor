from flask import Flask, Response, abort
import pandas as pd
import datetime
from os.path import exists

from predictions import Predictor
app = Flask(__name__)

@app.route("/")
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

if __name__ == "__main__":
    app.run(host='0.0.0.0')
import module
import time
import datetime
import lightgbm as lgb
import pandas as pd
import numpy as np

class Predictor():
    FEATURES = ['num',
            'tpsLastRace',
            'last_race_dist',
            'fer',
            'firstTimeFer',
            'sex',
            'age_x',
            'dist',
            'avisTrainer',
            'lastPerf',
            'meanPerf',
            'medianPerf',
            'modePerf',
            'recordAbs',
            'gain',
            'nombreCourses',
            'nombreVictoires',
            'nombrePlaces',
            'nombrePlacesSecond',
            'nombrePlacesTroisieme',
            'handicapDistance',
            'gainsParticipant_gainsPlace',
            'gainsParticipant_gainsAnneeEnCours',
            'gainsParticipant_gainsAnneePrecedente',
            'nbCourseCouple',
            'nbVictoiresCouple',
            'nb2emeCouple',
            'nb3emeCouple',
            'txReussiteCouple']
    def __init__(self, capital, file=None) -> None:
        self.capital = capital
        self.today_date = datetime.date.today().strftime("%d-%m-%Y")
        self.model = lgb.Booster(model_file="models/modelv3.txt")

    def predict(self):
        return self._get_predictions()

    def save_today_data(self):
        self.board[self.FEATURES].to_csv("today2.csv")

    def load_races_data(self, file):
        races = pd.read_csv(file, index=False)
        self.board = races

    def _get_today_program(self):
        # return module.get_programme("16-11-2022", "16-11-2022")
        return module.get_programme(self.today_date, self.today_date)

    def _get_today_races(self):
        program = self._get_today_program()
        races = module.get_courses(program)
        return races

    def _get_info_horses(self):
        courses = self._get_today_races()
        board = module.get_board(courses)
        board["num"] = board["num"].replace("NP", np.nan)
        board.dropna(subset="num", inplace=True)
        board.to_csv("test.csv")
        return board

    def _get_predictions(self):
        self.board = self._get_info_horses()
        pred_data = self.board.loc[:][self.FEATURES].apply(pd.to_numeric, errors='coerce')
        # pred_data["dernierRapportReference_indicateurTendance"] = pred_data["dernierRapportReference_indicateurTendance"].replace(["+", " ", "-"], [1, 0, -1]).fillna(0)

        predictions = self.model.predict(pred_data)
        self.board["pred"] = predictions
        self.board["pred"] = self.board.groupby("id")["pred"].rank("dense",ascending=True).astype(int)
        self.board["pred"] = self.board.groupby("id")["pred"].rank("first").astype(int)
    
        winners = self.board[["numCoursePMU","num", "nom", "pred"]].loc[self.board["pred"] == 1]
        # print(winners)
        winners.to_csv(f"predictions/{self.today_date}.csv", index=False)
        return winners

    def __repr__(self) -> str:
        return repr(self.preds)

if __name__ == "__main__":
    predictions = Predictor(30)

    print(predictions.predict())
    predictions.save_today_data()
    # print(predictions)
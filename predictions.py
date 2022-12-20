import src.module as module
import time
import datetime
import lightgbm as lgb
import pandas as pd
import numpy as np
import xlogit
import pickle

class Predictor():
    FEATURES_back = ['num',
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
    'nbDiscalifieMusic',
    'nbVictoireMusic',
    'nbPlaceMusic',
    'nbArrivé',
    'nombreCourses',
    'nombreVictoires',
    'nombrePlaces',
    'nombrePlacesSecond',
    'nombrePlacesTroisieme',
    'gainsParticipant_gainsPlace',
    'gainsParticipant_gainsAnneeEnCours',
    'gainsParticipant_gainsAnneePrecedente',
    'nbCourseCouple',
    'nbVictoiresCouple',
    'nb2emeCouple',
    'nb3emeCouple',
    'txReussiteCouple',
    'dernierRapportReference_rapport',
    "dernierRapportReference_indicateurTendance",
            'nbCourseTrainer',
 'nbVictoiresTrainer',
 'nb2emeTrainer',
 'nb3emeTrainer',
 'txReussiteTrainer',
 'nbCourseTandem',
 'nbVictoiresTandem',
 'nb2emeTandem',
 'nb3emeTandem',
 'txReussiteTandem',
 'nbCourseDriver',
 'nbVictoiresDriver',
 'nb2emeDriver',
 'nb3emeDriver',
 'txReussiteDriver']


    FEATURES = ["fer","dernierRapportReference_rapport","maxReduction","num","meanReduction","medianPerf","medianReduction","nbVictoiresTrainer","modePerf","nb2emeTandem_z","nb2emeCouple_z","newDist","timeBehindBestInRace_z","timeBehindBestMeanInRace_z","recordAbs","nbDiscalifieMusic","nbVictoireMusic","nbPlaceMusic","nombrePlacesSecond","nombrePlacesTroisieme_z","gainsParticipant_gainsAnneePrecedente_z","gainsParticipant_gainsVictoires_z","txReussiteTandem_z","lifepercwin","gainsParticipant_gainsAnneeEnCours_z", "txReussiteCouple_z", "nbCourseCouple_z","nbVictoiresCouple_z", "txReussiteTrainer_z", "timeSinceRecord_z", "nombreVictoires_z"]

    def __init__(self, capital, file=None) -> None:
        self.capital = capital
        self.today_date = datetime.date.today().strftime("%d-%m-%Y")
        self.model = lgb.Booster(model_file="models/lightgbm_model_v0.1.txt")

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

    def _normalize(self,df):
        groups = df[['id','nb2emeTandem',
            'nb2emeCouple',
            'timeBehindBestInRace',
            'timeBehindBestMeanInRace',
            'nombrePlacesTroisieme',
            'gainsParticipant_gainsAnneePrecedente',
            'gainsParticipant_gainsVictoires',
            'txReussiteTandem',
            'gainsParticipant_gainsAnneeEnCours',
            'txReussiteCouple',
            'nbCourseCouple',
            'nbVictoiresCouple',
            'txReussiteTrainer',
            'timeSinceRecord',
            'nombreVictoires']].groupby("id")

        mean, std = groups.transform("mean"), groups.transform("std")
        normalized = (df[mean.columns] - mean) / std
        normalized["num"] = df["num"]
        print(normalized)
        return normalized.fillna(0)

    def _get_predictions(self):
        self.board = self._get_info_horses()

        self.board.drop_duplicates(subset=["id","num","nom"],inplace=True)
        self.board["lifepercwin"] = self.board["nombreVictoires"] / self.board["nombreCourses"]
        self.board["winPrace"] = self.board["gainsParticipant_gainsAnneeEnCours"] / self.board["nombreCourses"]
        self.board["newDist"] = abs(self.board["last_race_dist"] - self.board["dist"]) > 150

        self.board["bestTimeInRace"] = self.board.groupby("id")["recordAbs"].transform(min)
        self.board["bestMeanTimeInRace"] = self.board.groupby("id")["meanReduction"].transform(min)
        self.board["timeBehindBestInRace"] = self.board["recordAbs"] - self.board["bestTimeInRace"]
        self.board["timeBehindBestMeanInRace"] = self.board["meanReduction"] - self.board["bestMeanTimeInRace"]

        self.board["trainerIsDriver"] = self.board["entraineur"] == self.board["driver_y"]

        self.board["newDist"] = self.board["newDist"].astype(int)
        self.board["available"] = 1
        self.board.fillna(0,inplace=True)
        self.board = self.board.apply(pd.to_numeric, errors='ignore')

        self.board.fillna(0).to_csv("today.csv")
        # self.board = self._normalize(self.board.apply(pd.to_numeric, errors='ignore'))
        
        self.board = self.board.join(self._normalize(self.board),on="id",lsuffix='', rsuffix='_z')
        
        # pred_data = self.board.loc[:][self.FEATURES].apply(pd.to_numeric, errors='ignore')
        # pred_data["dernierRapportReference_indicateurTendance"] = pred_data["dernierRapportReference_indicateurTendance"].replace(["+", " ", "-"], [1, 0, -1]).fillna(0)


        # self.board = pd.read_csv("test2.csv", index_col=0)

        self.board = self.board.set_index(["id", self.board.groupby("id").cumcount()])
        index = pd.MultiIndex.from_product(self.board.index.levels, names=self.board.index.names)
        self.board = self.board.reindex(index, fill_value=0).reset_index(level=1, drop=True).reset_index()

        nindex = len(self.board.groupby("id")) * list(range(1,self.board.groupby("id").cumcount().max()+2))
        self.board = self.board.assign(num=nindex)



        model = pickle.load(open("models/model_rapport.pickle", "rb"))

        print(self.board.head())

        choice, proba = model.predict(X=self.board[self.FEATURES], varnames=self.FEATURES, ids=self.board["id"], alts=self.board["num"], avail=self.board["available"], return_proba=True)
        print("Predictions ready")
        print(choice, proba)
        # print(self.board.groupby("id")["numCoursePMU"])


        # predictions = self.model.predict(pred_data)
        # self.board["pred"] = predictions
        # self.board["pred"] = self.board.groupby("id")["pred"].rank("dense",ascending=True).astype(int)
        # self.board["pred"] = self.board.groupby("id")["pred"].rank("first").astype(int)
    
        # winners = self.board[["numCoursePMU","num", "nom", "pred"]].loc[self.board["pred"] <= 2]
        # # print(winners)
        # winners.to_csv(f"predictions/{self.today_date}.csv", index=False)
        # return winners

    def __repr__(self) -> str:
        return repr(self.preds)

if __name__ == "__main__":
    predictions = Predictor(30)

    print(predictions.predict())
    predictions.save_today_data()
    # print(predictions)
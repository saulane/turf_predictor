import xlogit
import pandas as pd
import numpy as np
import pickle
import catboost
import lightgbm
from sklearn.preprocessing import binarize

class Predicion():
    def __init__(self, tableau_partant) -> None:
        self.X: pd.DataFrame = tableau_partant

        self.prepare_for_pred()

        self.model1: xlogit.MultinomialLogit = pickle.load(open("models/cl_v1.pickle", "rb"))
        self.model2: xlogit.MultinomialLogit = pickle.load(open("models/second_model2.pickle", "rb"))

        self.model_ranker: lightgbm.LGBMRanker = pickle.load(open("models/rankerv1.pickle", "rb"))
        self.catboost_ranker: lightgbm.LGBMRanker = pickle.load(open("models/catboostranker.pickle", "rb"))

        # self.predict()

    def prepare_for_pred(self):
        self.X.fillna(0, inplace=True)
        self.X.replace([np.inf, -np.inf], 0, inplace=True)
        self.X["lifepercwin"] = self.X["nombreVictoires"] / self.X["nombreCourses"]
        self.X["winPrace"] = self.X["gainsParticipant_gainsCarriere"] / self.X["nombreCourses"]
        self.X["available"] = 1
        self.X.loc[self.X["statut"] == "NON_PARTANT", "available"] = 0

        self.X["gainDifAnnePrec"] = self.X["gainsParticipant_gainsAnneeEnCours"] / self.X["gainsParticipant_gainsAnneePrecedente"]

        self.X["less_dist_than_last_race"] = (self.X["last_race_dist"] > self.X["dist"]).astype(int)
        self.X["place_last_race"] = ((self.X["lastPerf"] <= 3) & (self.X["lastPerf"] >= 1)).astype(int)

        self.X["remontada"] = binarize(self.X["gain_classement_fin"].to_numpy().reshape(-1, 1),threshold=0.25)
        self.X["avisTrainer"] = self.X["avisTrainer"] - 2
        self.X["lessThanPreferedDist"] = binarize(self.X["prefered_dist"].to_numpy().reshape(-1, 1),threshold=0)

        self.X["lastTimeToRecord"] = np.exp(self.X["tpsLastRace"] - self.X["recordAbs"])
        self.X["publicProbaOfWinning"] = 1 / self.X["dernierRapportDirect_rapport"]


        multiindex = [[],[]]

        for i in self.X.id.unique():
            for j in range(0,18):
                multiindex[0].append(i)
                multiindex[1].append(j)

        self.X = self.X.set_index(["id", self.X.groupby("id").cumcount()])
        new_index = pd.MultiIndex.from_arrays(multiindex, names=["id", "num"])
        self.X = self.X.reindex(new_index, fill_value=0).reset_index(level=1, drop=True).reset_index()

        nindex = len(self.X.groupby("id")) * list(range(1,self.X.groupby("id").cumcount().max()+2))
        self.X = self.X.assign(num=nindex)
        self.X.fillna(0, inplace=True)
        self.X.to_csv("test.csv")

    def predict(self):
        # features = ['acceleration_500m','nbVictoiresCouple','nbCourseCouple','rentree','last_race_dist','tpsLastRace','timeSinceRecord',
        #             'minReduction','medianReduction','meanReduction','changementCategorie','distToPreferedDist','prefered_dist','jockeyHabitude',
        #             'nbDiscalifieMusic','nbVictoireMusic','nbPlaceMusic',
        #             'fer','gainsParticipant_gainsCarriere','sex','age','dist', 'firstTimeFer',
        #             'formePlace','formeVictoire','lastPerf','mean_dist_arrivee','nbVictoiresHippo','nombreCourses','nbCourseHippo',
        #             'txVictoireCouple','txVictoireHippo']

        # for f in features:
        #     if f not in list(self.X):
        #         self.X[f] = 0
        self.X["rank_pred"] = self.model_ranker.predict(self.X[self.model_ranker.feature_name_])
        self.X["rank_pred_cat"] = self.catboost_ranker.predict(self.X[self.catboost_ranker.feature_names_], verbose=None)

        self.X["mean_rank"] = np.exp(0.1*self.X["rank_pred"]+0.9*self.X["rank_pred_cat"])

        # choice_estimate, proba_estimate = self.model1.predict(X=self.X[features], varnames=features, ids=self.X["id"], alts=self.X["num"], avail=self.X["available"],return_proba=True)         
        # self.X["proba_1"] = proba_estimate.flatten()
        # self.X["proba_1"].replace(-np.inf,0, inplace=True)
        # self.X["proba_1"].fillna(0, inplace=True)


        self.X["publicProbaOfWinning"].replace(np.inf, 0, inplace=True)
        choice, proba = self.model2.predict(X=self.X[["publicProbaOfWinning","mean_rank"]],varnames=["publicProbaOfWinning","mean_rank"], ids=self.X["id"],alts=self.X["num"],avail=self.X["available"], return_proba=True)

        return choice,proba,self.X["dernierRapportDirect_rapport"].to_numpy().reshape(proba.shape)


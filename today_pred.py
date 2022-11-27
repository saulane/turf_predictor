import module
import datetime
import os
import sys
import pandas as pd
import numpy as np

if __name__ == "__main__":
    args = sys.argv
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    today_str = today.strftime("%d-%m-%Y")

    yesterday_str = yesterday.strftime("%d-%m-%Y")
    if not os.path.exists(f"programmes/{today_str}.csv"):
        programme = module.Programme(yesterday_str, today_str)
        courses = module.Courses(programme).courses
        courses.to_csv(f"programmes/{today_str}.csv")
    else:
        courses = pd.read_csv(f"programmes/{today_str}.csv", index_col=0)

    courses.sort_values(by="heureCourse", inplace=True)

    today = datetime.date.today().strftime("%Y-%m-%d")

    courses["heureCourse"] = pd.to_datetime(today + " " +courses["heureCourse"], format='%Y-%m-%d %H:%M')
    if len(args) > 1 and args[1] == "next":
        tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > datetime.datetime.now() - datetime.timedelta(minutes=5)].iloc[:1])
    else:
        tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > datetime.datetime.now()])
    pred = module.Predicion(tableau_partant)
    choice,proba = pred.predict()

    sorted_proba = np.argsort(proba)

    nom = tableau_partant["nom"].to_numpy()
    num = tableau_partant["num"].to_numpy()

    for i in range(len(choice)):
        numcourses = tableau_partant["numCoursePMU"].unique()

        cur_course = tableau_partant[tableau_partant["numCoursePMU"] == numcourses[i]]
        # print(cur_course)
        cheval = cur_course[cur_course["num"] == str(choice[i])].iloc[0]
        # print(cheval)
        # print(np.argsort(proba[i]))

        expe_pos = np.max(proba[i]) * cheval["dernierRapportDirect_rapport"]

        deuxquatres = [sorted_proba[i,-1] +1, sorted_proba[i,-2] +1]

        print(cheval["heureCourse"],numcourses[i],cheval["nom"], choice[i],"|",round(expe_pos,2), expe_pos > 1 and np.max(proba[i]) > 0.1, " | 2sur4:", deuxquatres)
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
    if len(args) > 1:
        if args[1] == "next":
            tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > (datetime.datetime.now() - datetime.timedelta(minutes=15))])
        elif args[1] == "one":
            tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > (datetime.datetime.now() - datetime.timedelta(minutes=15))].iloc[:2])
    else:
        tableau_partant = module.get_df_partants(courses)
    pred = module.Predicion(tableau_partant)
    choice,proba = pred.predict()

    sorted_proba = np.argsort(proba)

    nom = tableau_partant["nom"].to_numpy()
    num = tableau_partant["num"].to_numpy()

    for i in range(len(choice)):
        try:
            numcourses = tableau_partant["numCoursePMU"].unique()

            cur_course = tableau_partant[tableau_partant["numCoursePMU"] == numcourses[i]]
            # print(cur_course)
            cheval = cur_course[cur_course["num"] == str(choice[i])].iloc[0]
            # print(cheval)
            # print(np.argsort(proba[i]))

            expe_pos = np.max(proba[i]) * cheval["dernierRapportDirect_rapport"]

            place = [sorted_proba[i,-1] +1, sorted_proba[i,-2] +1, sorted_proba[i,-3] +1]

            c = sorted_proba[i,-1]

            should_bet = proba[i, c] > 0.3 and expe_pos > 1.3 and expe_pos < 4

            print(cheval["heureCourse"],numcourses[i],"=>",cheval["nom"], c+1,"|",round(proba[i, c], 3), should_bet, place)
        except:
            continue
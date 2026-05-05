import pandas as pd
from sqlalchemy import create_engine
from sklearn.neighbors import NearestNeighbors, BallTree
from sklearn.preprocessing import StandardScaler
import numpy as np

#Use existing db for recommendation system
def create_array():
    dbPath = "users_trails_schema.db" #the db where users can add trails into
    engine = create_engine('sqlite:///%s' % dbPath)

    filtered = (pd.read_sql("SELECT name, length_miles, difficulty_category, latitude,"\
    "longitude FROM trails", engine))
    filtered['difficulty_category'] = filtered['difficulty_category'].apply(convert_difficulty)

    #print(filtered.to_numpy()[:,3:6]) 
    return filtered.to_numpy()

#Replace column difficulty_category str with corresponding values 
def convert_difficulty(difficulty_str):
    if difficulty_str == "easy":
        return 1
    elif difficulty_str == "moderate":
        return 2
    elif difficulty_str == "moderately strenuous":
        return 3
    elif difficulty_str == "strenuous":
        return 4
    else: 
        return 5

#Use K Nearest Neighbors for model
#Users can choose to be recommended by location, distance, and difficulty
#Or difficulty/distance only
#If users choose recommendations by distance, there will be 2 stages
#since location overwhelms miles and difficulty category

#function for filtering out trails within n distance
#Note: 
#numpy_arr cols:[(0)name, (1)distance, (2)difficulty, (3)lat, (4)lon]
#query cols:[(0)distance, (1)difficulty, (2)lat, (3)lon]
def filter_location(numpy_arr, query):
    trails_radians = np.radians(numpy_arr[:,3:5].astype(float))
    query_radian = np.radians(np.array([query[2:4]], dtype=float).reshape(1,-1))
    #haversine = shortest distance between 2 points
    #on the surface of a sphere (using radians)
    tree = BallTree(trails_radians, metric='haversine')

    #we want to find trails 50 miles away or less
    miles = 50
    miles_radian = miles / 3958.8
    indices = tree.query_radius(query_radian, r=miles_radian)[0]
    return indices

def recommender_model(query_arr):
    trails_arr = create_array()
    scaler = StandardScaler()
    X = 0;
    #if longitude or latitude is not null, filtering by location
    if (query_arr[2] != None and query_arr[3] != None):
        rows_selected = trails_arr[filter_location(trails_arr, query_arr)]
        X = rows_selected[:,1:3] #use group with location filter 
    else:  
        X = trails_arr[:,1:3] 

    #assign weights since distance overwhelms difficulty as well
    weights = np.array([1.0, 2.5])
    X_scaled = scaler.fit_transform(X) 
    X_weighted = X_scaled * weights

    #performs KNN returning top 7 trails
    #using euclidean or distance between 2 points
    neighbors = NearestNeighbors(n_neighbors=7, metric="euclidean").fit(X_weighted)

    query_scaled = scaler.transform(np.array([query_arr[0:2]])) 
    query_weighted = query_scaled * weights
    n = neighbors.kneighbors(query_weighted) #returns array with neighbor info
    
    return(n[1]) #returns a numpy.ndarray with row index of matched trails

def main():
    query = [3, 2, 37.3382, -121.8863]
    trails = create_array()
    rec = recommender_model(query)
    for i in rec:
        print(trails[i])

if __name__== "__main__":
    main()



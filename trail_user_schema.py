from sqlalchemy import create_engine, Table, Column, Double, Integer, String, PickleType
from sqlalchemy.orm import sessionmaker, declarative_base
import pandas as pd
import ast

db_path = "users_trails_schema.db"
csv = "cleaned_trails/cleaned_ca_trails.csv"
engine = create_engine('sqlite:///%s' % db_path)
Base = declarative_base()

class Trail(Base):
    __tablename__ = "trails"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    difficulty_rating = Column(Integer)
    route_type = Column(String)
    visitor_usage = Column(Integer)
    avg_rating = Column(Double)
    area_name = Column(String)
    city_name = Column(String)
    features = Column(PickleType)
    activities = Column(PickleType)
    num_reviews = Column(Integer)
    latitude = Column(Double)
    longitude = Column(Double)
    length_miles = Column(Double)
    elevation_gain_ft = Column(Double)
    steepness_ftmi = Column(Double)
    difficulty_category = Column(String)
    area_category = Column(String)
    url = Column(String)

class User(Base):
    __tablename__="user"
    name = Column(String, primary_key=True)
    trail_name = Column(String)
    distance = Column(Double)
    elevation = Column(Double)
    difficulty_cat = Column(String)
    diff_rating = Column(Integer)
    rating = Column(Integer)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

try:
    df = pd.read_csv(csv, index_col=False)

    #['dog', 'hike'] got converted into "['dog', 'hike']" so ast converts it back
    df['features'] = df['features'].apply(ast.literal_eval) 
    df['activities'] = df['activities'].apply(ast.literal_eval)

    #turn put row values of csv into respective Table columns
    for _, row in df.iterrows():
        trail = Trail( id= row["ID"],name=row["name"], 
            difficulty_rating=row["difficulty_rating"], 
            route_type=row["route_type"], 
            visitor_usage=row["visitor_usage"], 
            avg_rating=row["avg_rating"], 
            area_name=row["area_name"], 
            city_name=row["city_name"], 
            features=row["features"], 
            activities=row["activities"], 
            num_reviews=row["num_reviews"], 
            latitude=row["latitude"], 
            longitude=row["longitude"], 
            length_miles=row["length_miles"], 
            elevation_gain_ft=row["elevation_gain_ft"], 
            steepness_ftmi=row["steepness_ftmi"], 
            difficulty_category=row["difficulty_category"], 
            area_category=row["area_category"], url=row["url"]) 
        session.add(trail)

    #test that the database works..
    result = session.query(Trail).filter(Trail.name == "Eaton Canyon Trail")
    for trail in result:
        print(trail.name, trail.avg_rating, trail.features, trail.activities)

    session.commit()

except FileNotFoundError as ex:
    print("Check file: " + str(ex))
except KeyError as ex:
    print("Check rows and column names: " + str(ex))
except Exception as ex:
    print("Error: " + str(ex))

finally:
    session.close()

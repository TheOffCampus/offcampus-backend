from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.neighbors import NearestNeighbors
from sklearn.impute import SimpleImputer
import pandas as pd
from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine, text
import os
from dotenv import dotenv_values
from joblib import dump

config = {
    **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

supabase = create_client(config['SUPABASE_URL'], config['SUPABASE_KEY'])
engine = create_engine(config['SQLALCHEMY_DATABASE_URL'])

def get_recs_query_v2(prefs, user_id):
    """
    Generate and execute a raw SQL query to find property recommendations based on user preferences.

    Args:
        prefs (dict): User preferences including filters for campus name, maximum rent, and minimum square footage.

    Returns:
        list of dicts: List of properties with details.
    """
    query = text(f'''
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object,
            CASE WHEN ua.rental_key IS NOT NULL
                THEN 1
                ELSE 0
            END AS isSaved
        FROM
            properties p,
            jsonb_array_elements(p.data->'schools'->'colleges') AS c(college)
        CROSS JOIN LATERAL
            jsonb_array_elements(p.data->'rentals') AS rental_object
        LEFT JOIN
            user_apartment ua ON CAST(rental_object->>'key' AS VARCHAR) = ua.rental_key AND ua.user_id = '{user_id}'
        WHERE
            c.college @> '{{"name": "{prefs.get("campus", "Texas A&M University")}"}}'
            AND (rental_object->>'rent')::int <= {prefs.get("max_rent", 10000)}
            AND (rental_object->>'squareFeet')::int >= {prefs.get("min_sqft", 0)}
        LIMIT 100
        OFFSET (1 - 1) * 50;
    ''')
    
    with engine.connect() as connection:
        result = connection.execute(query).fetchall()

    data = []
    for row in result:
        row_data = {
            "property_id": row[0],
            "property_data": row[1],
            "rental_object": row[2],
            "isSaved": bool(row[3]),
        }
        data.append(row_data)

    return data


def get_prefs_query(id):
    """
	Retrieve user preferences from the Supabase 'User' table by user ID.

	Args:
    	id (int): User ID.

	Returns:
    	dict: User preferences stored in the database.
	"""
    result = supabase.table("User").select("preferences").eq("id", id).execute()

    preferences = result.data[0]['preferences']

    return preferences



def knn_recommender(data, prefs, save_model=True):

    property_data = pd.DataFrame(data)
    # print(property_data.info())

    def get_property_data():
        return property_data
    
    property_data['rating'].fillna(property_data['rating'].mean(), inplace=True)
    property_data['details'] = property_data['details'].apply(lambda x: ', '.join(x))

    categorical_features = ['details']
    numerical_features = ['rent', 'squareFeet', 'walkScore', 'rating', 'latitude', 'longitude']

    numerical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='mean')),  
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),  
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numerical_transformer, numerical_features),
            ('cat', categorical_transformer, categorical_features)
        ]
    )

    X = preprocessor.fit_transform(property_data)

    knn = NearestNeighbors(n_neighbors=20, algorithm='ball_tree')
    knn.fit(X)

    if save_model:
        # Save the preprocessor and KNN model
        dump(preprocessor, 'preprocessor.joblib')
        dump(knn, 'knn_model.joblib')

    # pref_rent = prefs.get("rent")
    # pref_sqft = prefs.get("squareFeet")
    # pref_details = prefs.get("details")

    # user_query = pd.DataFrame({ 
    #     'details': pref_details,
    #     'rent': pref_rent,  
    #     'walkScore': [40],
    #     'squareFeet': pref_sqft,
    #     'rating': [4.2],
    #     'latitude': [30.5], 
    #     'longitude': [-96.3],
    # })

    # user_query_transformed = preprocessor.transform(user_query)

    # distances, indices = knn.kneighbors(user_query_transformed, n_neighbors=20)
    # user_preferences = {
    # 'rent': pref_rent
    # }

    # print(pref_rent)

    # filtered_indices = []
    # for i in indices[0]:
    #     if property_data.iloc[i]['rent'] <= user_preferences['rent']:
    #         filtered_indices.append(i)

    # filtered_data = [property_data.iloc[i].to_dict() for i in filtered_indices]
    # return filtered_data


prefs = get_prefs_query('user_2d3jvU6lHeJc1cSDkB7GVx7QpqB')
recs = get_recs_query_v2(prefs, 'user_2d3jvU6lHeJc1cSDkB7GVx7QpqB')
simplified_recs = []
for rec in recs:
    price = rec['property_data']['models'][0].get('rentLabel', 'N/A')
    price_cleaned = price.replace('/ Person', '').strip()
    simplified_rec = {
        'propertyId': rec['property_id'],
        'key': rec['rental_object'].get('key', 'N/A'),  # Set default as 'N/A' if key is missing
        'name': rec['property_data'].get('propertyName', 'N/A'),
        'modelName': rec['rental_object'].get('modelName', 'N/A'),
        'rent': rec['rental_object'].get('rent', 0),  # Default rent as 0 if missing
        'modelImage': rec['rental_object'].get('image', 'N/A'),
        'address': rec['property_data']['location'].get('fullAddress', 'N/A'),
        'latitude': rec['property_data']['coordinates'].get('latitude', 0),  # Default to 0 if missing
        'longitude': rec['property_data']['coordinates'].get('longitude', 0),
        'walkScore': rec['property_data']['scores'].get('walkScore', 0),
        'price': price_cleaned,
        'photos': rec['property_data'].get('photos', []),
        'details': rec['rental_object'].get('details', {}),
        'squareFeet': rec['rental_object'].get('squareFeet', 0),
        'availableDate': rec['rental_object'].get('availableDate', 'N/A'),
        'isNew': rec['rental_object'].get('isNew', False),
        'features': rec['rental_object'].get('interiorAmenities', []),
        'rating': rec['property_data'].get('rating', 0),
        'hasKnownAvailabilities': rec['rental_object'].get('hasKnownAvailabilities', False),
        'isSaved': rec['isSaved'],
    }
    simplified_recs.append(simplified_rec)
knn_recommender(simplified_recs, prefs)
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.neighbors import NearestNeighbors
from sklearn.impute import SimpleImputer
import pandas as pd

def knn_recommender(data, prefs):

    property_data = pd.DataFrame(data)
    
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
    pref_rent = prefs.get("rent")
    pref_sqft = prefs.get("squareFeet")
    pref_details = prefs.get("details")

    user_query = pd.DataFrame({ 
        'details': pref_details,
        'rent': pref_rent,  
        'walkScore': [40],
        'squareFeet': pref_sqft,
        'rating': [4.2],
        'latitude': [30.5], 
        'longitude': [-96.3],
    })

    user_query_transformed = preprocessor.transform(user_query)

    distances, indices = knn.kneighbors(user_query_transformed, n_neighbors=20)
    user_preferences = {
    'rent': pref_rent
    }

    filtered_indices = []
    for i in indices[0]:
        if property_data.iloc[i]['rent'] <= user_preferences['rent']:
            filtered_indices.append(i)

    filtered_data = [property_data.iloc[i].to_dict() for i in filtered_indices]
    return filtered_data



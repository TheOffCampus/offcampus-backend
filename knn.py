from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.neighbors import NearestNeighbors
from sklearn.impute import SimpleImputer
from joblib import dump

import pandas as pd
import json

df = pd.read_json('dataset_apartments-scraper_2024-02-17_03-39-49-528.json')

with open('dataset_apartments-scraper_2024-02-17_03-39-49-528.json') as f:
    property_data = json.load(f)

property_details = []
for property in property_data:  
    monthly_dog_fee = None
    dog_fees = property['petFees']
    for fee in dog_fees:
        if fee["title"] == "Dogs Allowed":
            for fee_detail in fee["fees"]:
                if fee_detail["key"] == "Monthly pet rent":
                    monthly_dog_fee = fee_detail["value"]
    monthly_cat_fee = None
    cat_fees = property['petFees']
    for fee in cat_fees:
        if fee["title"] == "Cats Allowed":
            for fee_detail in fee["fees"]:
                if fee_detail["key"] == "Monthly pet rent":
                    monthly_cat_fee = fee_detail["value"]
    details = {
        'propertyId': property['id'],  
        'walkScore': property['scores'].get('walkScore'),
        'rating': property['rating'],  
        'city': property['location'].get('city'),
        'state': property['location'].get('state'),
        'latitude': property['coordinates'].get('latitude'),
        'longitude': property['coordinates'].get('longitude'),
        'monthly_dog_fee': monthly_dog_fee,
        'monthly_cat_fee': monthly_cat_fee
    }
    property_details.append(details)

df_property_details = pd.DataFrame(property_details)

all_rentals_with_propertyId = []
for property in property_data:  
    propertyId = property['id']      
    for rental in property['rentals']:  
        rental['propertyId'] = propertyId  
        all_rentals_with_propertyId.append(rental)

df_normalized = pd.json_normalize(all_rentals_with_propertyId)
df_subcategories = pd.json_normalize(all_rentals_with_propertyId, record_path=['interiorAmenities', 'subCategories'])
highlights_amenities = df_subcategories[df_subcategories['name'] == 'Highlights']['amenities']

df_filtered = df_normalized[['propertyId', 'key', 'modelName', 'beds', 'baths', 'maxRent']]

df_combined = pd.merge(df_filtered, df_property_details, on='propertyId', how='left')

categorical_features = ['city', 'state']
numerical_features = ['beds', 'baths', 'maxRent', 'walkScore', 'rating', 'latitude', 'longitude']

df_combined['rating'].fillna(df_combined['rating'].mean(), inplace=True)

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

X = preprocessor.fit_transform(df_combined)

knn = NearestNeighbors(n_neighbors=5, algorithm='ball_tree')
knn.fit(X)

user_query = pd.DataFrame({
    'city': ['College Station'],  
    'state': ['Texas'], 
    'beds': [3],
    'baths': [3.0],
    'maxRent': [1200],  
    'walkScore': [50],
    'rating': [4.0],
    'latitude': [30.5], 
    'longitude': [-96.3],
})

user_query_transformed = preprocessor.transform(user_query)

user_preferences = {
    'maxRent': 1200,
}

distances, indices = knn.kneighbors(user_query_transformed, n_neighbors=20)

filtered_indices = []
for i in indices[0]:
    if df_combined.iloc[i]['maxRent'] <= user_preferences['maxRent']:
        filtered_indices.append(i)
        if len(filtered_indices) == 5:  
            break

for i in filtered_indices:
    print(df_combined.iloc[i])

def get_df_combined():
    return df_combined

dump(preprocessor, 'preprocessor.joblib')
dump(knn, 'knn_model.joblib')
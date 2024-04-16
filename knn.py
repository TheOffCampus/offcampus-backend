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
    monthlyPetFee = None
    dog_fees = property['petFees']
    for fee in dog_fees:
        if fee["title"] == "Dogs Allowed":
            for fee_detail in fee["fees"]:
                if fee_detail["key"] == "Monthly pet rent":
                    monthlyPetFee = fee_detail["value"]
    oneTimeFee = None
    dog_fees = property['petFees']
    for fee in dog_fees:
        if fee["title"] == "Dogs Allowed":
            for fee_detail in fee["fees"]:
                if fee_detail["key"] == "One time Fee":
                    oneTimeFee = fee_detail["value"]
    details = {
        'propertyId': property['id'],  
        'walkScore': property['scores'].get('walkScore'),
        'rating': property['rating'],  
        'city': property['location'].get('city'),
        'state': property['location'].get('state'),
        'address': property['location'].get('fullAddress'),
        'latitude': property['coordinates'].get('latitude'),
        'longitude': property['coordinates'].get('longitude'),
        'photos': property['photos'],
        'monthlyPetFee': monthlyPetFee,
        'oneTimePetFee': oneTimeFee
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

# export interface ApartmentUnit {
#   address: string;
#   photos: string[];
#   modelImage?: string | null;
#   rating: number;
#   features?: Amenity[] | null;
#   leaseOption?: string | null;
# }
# print(df_normalized.info())

# export interface ApartmentUnit {
#   key: string;
#   image: string;
#   name: string;
#   address: string;
#   photos: string[];
#   modelName: string;
#   modelImage?: string | null;
#   rent: string;
#   propertyId: string;
#   details: string[];
#   rating: number;
#   squareFeet: string;
#   features?: Amenity[] | null;
#   isNew?: boolean;
#   hasKnownAvailabilities?: boolean;
#   availableDate?: Date | string | null;
#   leaseOption?: string | null;
# }

df_filtered = df_normalized[['key', 'image', 'modelName', 'rent', 'propertyId', 'details', 'squareFeet', 'isNew', 'hasKnownAvailabilities', 'availableDate']]

df_combined = pd.merge(df_filtered, df_property_details, on='propertyId', how='left')
# print(df_combined.info())

df_combined['rating'].fillna(df_combined['rating'].mean(), inplace=True)
df_combined['details'] = df_combined['details'].apply(lambda x: ', '.join(x))

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

X = preprocessor.fit_transform(df_combined)

knn = NearestNeighbors(n_neighbors=5, algorithm='ball_tree')
knn.fit(X)

user_query = pd.DataFrame({
    'city': ['College Station'],  
    'state': ['Texas'], 
    'details': ['1 Beds, 1 Baths'],
    'rent': [1050],  
    'walkScore': [40],
    'squareFeet': [500],
    'rating': [4.5],
    'latitude': [30.5], 
    'longitude': [-96.3],
})

user_query_transformed = preprocessor.transform(user_query)

user_preferences = {
    'rent': 1100,
}

distances, indices = knn.kneighbors(user_query_transformed, n_neighbors=20)
unique_property = {}

filtered_indices = []
for i in indices[0]:
    if df_combined.iloc[i]['rent'] <= user_preferences['rent']:
        filtered_indices.append(i)
        if len(filtered_indices) == 5:  
            break

# for i in filtered_indices:
#     print(df_combined.iloc[i])

def get_df_combined():
    return df_combined

dump(preprocessor, 'preprocessor.joblib')
dump(knn, 'knn_model.joblib')

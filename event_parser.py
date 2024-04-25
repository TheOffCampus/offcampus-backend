import boto3
import json
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import pandas as pd
from joblib import load
from knn import get_simplified_recs

profile_name = 'AdministratorAccess-432520187639'
session = boto3.Session(profile_name=profile_name)
s3 = boto3.client('s3')
bucket_name = 'offcampus-raw-event-store'
object_key = '2024/04/24/18/OffCampus-Analytics-1-2024-04-24-18-36-30-5c4a036b-a0c2-42d0-97b4-e07130587ee4'

def load_data_from_s3(bucket, key, profile_name):
    session = boto3.Session(profile_name=profile_name)
    s3 = session.client('s3')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return content
    except ClientError as e:
        print(f"An error occurred: {e}")
        return None
    except (NoCredentialsError, PartialCredentialsError) as e:
        print(f"Credentials error: {e}")
        return None

data = load_data_from_s3(bucket_name, object_key, profile_name)

def parse_concatenated_json(json_string):
    decoder = json.JSONDecoder()
    pos = 0
    len_json = len(json_string)
    parsed_data = []

    while pos < len_json:
        try:
            obj, current_pos = decoder.raw_decode(json_string[pos:])
            pos += current_pos
        except json.JSONDecodeError:
            pos += 1
        else:
            parsed_data.append(obj)
    
    return parsed_data

parsed_events = parse_concatenated_json(data)

# activites = {'APARTMENT_DETAILS_VIEW_START': 2, 'APARTMENT_DETAILS_VIEW_END': 1, 'SAVE_APARTMENT': 5}

user_profiles = {}
for event in parsed_events:
    user_id = event.get('userId', 'unknown')
    property_id = event.get('apartmentProperty', {}).get('propertyId', 'N/A')
    apt_details = event.get('apartmentProperty', {}).get('details', []) 
    square_feet = event.get('apartmentProperty', {}).get('squareFeet', 'N/A')
    rent = event.get('apartmentProperty', {}).get('rent', 'N/A')
    rating = event.get('apartmentProperty', {}).get('rating', 'N/A')
    time_spent = int(event.get('metrics', {}).get('totalTime', 0))
    action = event['type']
    
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            'interactions': [],
            'property_time_spent': {},
            'viewed_properties' : set(),
            'saved_properties': set()
        }
    
    if property_id not in user_profiles[user_id]['property_time_spent']:
        user_profiles[user_id]['property_time_spent'][property_id] = 0
    
    user_profiles[user_id]['property_time_spent'][property_id] += time_spent
    user_profiles[user_id]['interactions'].append({
        'action': action,
        'property_id': property_id,
        'details': apt_details,
        'square_feet': square_feet,
        'rent': rent,
        'rating': rating,
        'time_spent': time_spent
    })

    user_profiles[user_id]['viewed_properties'].add(property_id)

    if action == 'SAVE_APARTMENT':
        user_profiles[user_id]['saved_properties'].add(property_id)

def create_interaction_features(user_id, user_profiles, property_data):
    features_list = []
    user_profile = user_profiles.get(user_id, {})

    for property_id, time_spent in user_profile['property_time_spent'].items():
        print(f"Checking property_id: {property_id} in property_data")
        if property_id in property_data.index:
            property_info = property_data.loc[property_id]
            print("Found property_id, adding features.")
            features = {
                'rent': property_info['rent'],
                'squareFeet': property_info['squareFeet'],
                'rating': property_info['rating'],
                'latitude': property_info['latitude'],
                'longitude': property_info['longitude'],
                'walkScore': property_info['walkScore'],
                'time_weighted_interaction': time_spent  
            }
            features_list.append(features)
        else:
            print(f"Property ID {property_id} not found in property_data.")

    if not features_list:
        print("No features were added. Check property IDs and their presence in property_data.")
    
    return pd.DataFrame(features_list)


property_data = get_simplified_recs()
property_data.set_index('propertyId', inplace=True)
interaction_features = create_interaction_features(user_id, user_profiles, property_data)
print(interaction_features)

for user_id, profile in user_profiles.items():
    profile['viewed_properties'] = list(profile['viewed_properties'])
    profile['saved_properties'] = list(profile['saved_properties'])

preprocessor = load('preprocessor.joblib')
knn_model = load('knn_model.joblib')

def interaction_knn_recommender(user_id, user_profiles, property_data, knn_model, preprocessor):
    user_profile = user_profiles.get(user_id, {})
    if not user_profile or not user_profile['property_time_spent']:
        return []

    interaction_features = create_interaction_features(user_id, user_profiles, property_data)

    interaction_features_transformed = preprocessor.transform(interaction_features)

    distances, indices = knn_model.kneighbors(interaction_features_transformed, n_neighbors=20)
    recommended_properties = property_data.iloc[indices.flatten()].to_dict('records')
    return recommended_properties

property_data = get_simplified_recs()
res = interaction_knn_recommender(user_id, user_profiles, property_data, knn_model, preprocessor)
print(res)

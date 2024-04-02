from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine, text
from flask_cors import CORS
from auth.user import get_user_id
import traceback
import os
from dotenv import dotenv_values

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})

config = {
    **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

supabase = create_client(config['SUPABASE_URL'], config['SUPABASE_KEY'])
engine = create_engine(config['SQLALCHEMY_DATABASE_URL'])

def get_recs_query(prefs, user_id):
    """
	Generate and execute a raw SQL query to find property recommendations based on user preferences.

	Args:
    	prefs (dict): User preferences including weights for miles, square footage, and rent,
                  	as well as filters for campus name, maximum rent, and minimum square footage.

	Returns:
    	list of dicts: List of recommended properties with details and calculated scores.
	"""
    query = text(f'''
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object,
            (
                ({prefs.get("miles_weight", 0.5)} * -1 * 1000 * (c.college->>'miles')::float) +
                ({prefs.get("sqft_weight", 0.5)} * 1 * 800 * (rental_object->>'squareFeet')::int) +
                ({prefs.get("rent_weight", 0.5)} * -1 * (rental_object->>'rent')::int)
            ) AS weighted_score,
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
        ORDER BY weighted_score DESC
        LIMIT 10
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
            "score": row[3],
            "isSaved": bool(row[4]),
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

# Execute the raw SQL query
@app.route('/get_recommendations', methods=['GET'])
def get_recs_api():
    """
	API endpoint to get property recommendations for a user based on their stored preferences.

	Expects an 'id' header with the user's ID.
	Returns a JSON response with simplified property recommendation details or an error message.
	"""
    authorization = request.headers.get('Authorization', None)

    if authorization is None:
        return jsonify({ 'error': { 'status': 401, 'code': 'OC.AUTHENTICATION.UNAUTHORIZED', 'message': 'Bearer token not supplied in save apartments request.' } }), 401

    jwt_token = authorization.split()[1]

    user_id = ''
    try:
        user_id = get_user_id(jwt_token)
    except:
        traceback.print_exc()
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.AUTHENTICATION.TOKEN_ERROR', 'message': 'Token failed to be verified' }, 'results': [] }), 500

    try:
        prefs = get_prefs_query(user_id)
        recs = get_recs_query(prefs, user_id)
    

        simplified_recs = []
        for rec in recs:
            price = rec['property_data']['models'][0].get('rentLabel', 'N/A')
            price_cleaned = price.replace('/ Person', '').strip()
            simplified_rec = {
                'propertyId': rec['property_id'],
                'key': rec['rental_object'].get('key'),
                'name': rec['property_data'].get('propertyName', 'N/A'),
                'modelName': rec['rental_object'].get('modelName'),
                'rent': rec['rental_object'].get('rent'),
                'modelImage': rec['rental_object'].get('image'),
                'address': rec['property_data']['location'].get('fullAddress', 'N/A'),
                'price': price_cleaned,
                'score': rec['score'],
                'photos': rec['property_data'].get('photos', []),
                'details': rec['rental_object'].get('details', {}),
                'squareFeet': rec['rental_object'].get('squareFeet'),
                'availableDate': rec['rental_object'].get('availableDate'),
                'isNew': rec['rental_object'].get('isNew'),
                'features': rec['rental_object'].get('interiorAmenities'),
                'rating': rec['property_data'].get('rating'),
                'hasKnownAvailabilities': rec['rental_object'].get('hasKnownAvailabilities'),
                'isSaved': rec['isSaved'],
            }
            simplified_recs.append(simplified_rec)

        return jsonify(simplified_recs), 200
    
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.post('/apartments/save')
def save_apartment():
    authorization = request.headers.get('Authorization', None)

    if authorization is None:
        return jsonify({ 'error': { 'status': 401, 'code': 'OC.AUTHENTICATION.UNAUTHORIZED', 'message': 'Bearer token not supplied in save apartments request.' } }), 401

    jwt_token = authorization.split()[1]

    user_id = ''
    try:
        user_id = get_user_id(jwt_token)
    except:
        traceback.print_exc()
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.AUTHENTICATION.TOKEN_ERROR', 'message': 'Token failed to be verified' }, 'results': [] }), 500

    body = request.get_json()
    property_id = body.get('property_id', None)
    rental_key = body.get('rental_key', None)
    if property_id is None:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.PARAMETER_NOT_GIVEN', 'message': 'A property id was not supplied. Failed to save apartment.' }, 'results': [] }), 500
    if rental_key is None:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.PARAMETER_NOT_GIVEN', 'message': 'A rental unit id was not supplied. Failed to save apartment.' }, 'results': [] }), 500

    saved_apartment = { 'user_id': user_id, 'property_id': property_id, 'rental_key': rental_key }

    try:
        data, count = supabase.table('user_apartment').insert(saved_apartment).execute()
    except:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.APARTMENT.SAVE_FAILURE', 'message': 'Failed to update database with saved apartment' }, 'results': [] }), 500

    if data[1] and len(data[1]) > 0:
        return jsonify({ 'results': [{ 'code': 'OC.MESSAGE.SUCCESS', 'message': 'Successfully saved apartment' }], 'data': data[1] }), 200

    return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.DATABASE_FAILURE', 'message': 'Failed to update database for an unknown reason' }, 'results': [] }), 500


@app.post('/apartments/remove')
def remove_saved_apartment():
    authorization = request.headers.get('Authorization', None)

    if authorization is None:
        return jsonify({ 'error': { 'status': 401, 'code': 'OC.AUTHENTICATION.UNAUTHORIZED', 'message': 'Bearer token not supplied in remove apartments request.' } }), 401

    jwt_token = authorization.split()[1]

    user_id = ''
    try:
        user_id = get_user_id(jwt_token)
    except:
        traceback.print_exc()
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.AUTHENTICATION.TOKEN_ERROR', 'message': 'Token failed to be verified' }, 'results': [] }), 500

    body = request.get_json()
    property_id = body.get('property_id', None)
    rental_key = body.get('rental_key', None)
    if property_id is None:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.PARAMETER_NOT_GIVEN', 'message': 'A property id was not supplied. Failed to remove saved apartment from user account.' }, 'results': [] }), 500
    if rental_key is None:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.PARAMETER_NOT_GIVEN', 'message': 'A rental unit id was not supplied. Failed to remove saved apartment from user account.' }, 'results': [] }), 500

    removed_apartment = { 'user_id': user_id, 'property_id': property_id, 'rental_key': rental_key }

    try:
        data, count = supabase.table('user_apartment').delete().match(removed_apartment).execute()
    except:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.APARTMENT.REMOVE_FAILURE', 'message': 'Failed to remove saved apartment from user account.' }, 'results': [] }), 500

    if data[1] and len(data[1]) > 0:
        return jsonify({ 'results': [{ 'code': 'OC.MESSAGE.SUCCESS', 'message': 'Successfully removed apartment from user.' }], 'data': data[1] })

    return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.DATABASE_FAILURE', 'message': 'Failed to update database for an unknown reason' }, 'results': [] }), 500

def get_saved_apartments(user_id):
    """
    Retrieve all saved apartments for a user from the Supabase 'user_apartment' table.

    Args:
        user_id (int): User ID.

    Returns:
        list of dicts: List of saved apartments with details.
    """
    query = text(f'''
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object
        FROM
            user_apartment ua
        JOIN
            properties p ON ua.property_id = p.id
        CROSS JOIN LATERAL
            jsonb_array_elements(p.data->'rentals') AS rental_object
        WHERE
            ua.user_id = '{user_id}'
            AND CAST(rental_object->>'key' AS VARCHAR) = ua.rental_key
    ''')

    with engine.connect() as connection:
        result = connection.execute(query).fetchall()

    data = []
    for row in result:
        row_data = {
            "property_id": row[0],
            "property_data": row[1],
            "rental_object": row[2],
            "isSaved": True,
        }
        data.append(row_data)

    return data

@app.route('/get_saved_apartments', methods=['GET'])
def get_saved_apartments_api():
    """
    API endpoint to get all saved apartments for a user.

    Expects an 'Authorization' header with the user's JWT token.
    Returns a JSON response with simplified saved apartment details or an error message.
    """
    authorization = request.headers.get('Authorization', None)

    if authorization is None:
        return jsonify({ 'error': { 'status': 401, 'code': 'OC.AUTHENTICATION.UNAUTHORIZED', 'message': 'Bearer token not supplied in get saved apartments request.' } }), 401

    jwt_token = authorization.split()[1]

    user_id = ''
    try:
        user_id = get_user_id(jwt_token)
    except:
        traceback.print_exc()
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.AUTHENTICATION.TOKEN_ERROR', 'message': 'Token failed to be verified' }, 'results': [] }), 500

    try:
        saved_apartments = get_saved_apartments(user_id)

        simplified_apartments = []
        print(saved_apartments)
        for apartment in saved_apartments:
            price = apartment['property_data']['models'][0].get('rentLabel', 'N/A')
            price_cleaned = price.replace('/ Person', '').strip()
            simplified_apartment = {
                'propertyId': apartment['property_id'],
                'key': apartment['rental_object'].get('key'),
                'name': apartment['property_data'].get('propertyName', 'N/A'),
                'modelName': apartment['rental_object'].get('modelName'),
                'rent': apartment['rental_object'].get('rent'),
                'modelImage': apartment['rental_object'].get('image'),
                'address': apartment['property_data']['location'].get('fullAddress', 'N/A'),
                'price': price_cleaned,
                'photos': apartment['property_data'].get('photos', []),
                'details': apartment['rental_object'].get('details', {}),
                'squareFeet': apartment['rental_object'].get('squareFeet'),
                'availableDate': apartment['rental_object'].get('availableDate'),
                'isNew': apartment['rental_object'].get('isNew'),
                'features': apartment['rental_object'].get('interiorAmenities'),
                'rating': apartment['property_data'].get('rating'),
                'hasKnownAvailabilities': apartment['rental_object'].get('hasKnownAvailabilities'),
                'isSaved': apartment['isSaved']
            }
            simplified_apartments.append(simplified_apartment)

     
        return jsonify(simplified_apartments), 200

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.post('/apartments/details')
def get_apartment_details():
    authorization = request.headers.get('Authorization', None)

    if authorization is None:
        return jsonify({ 'error': { 'status': 401, 'code': 'OC.AUTHENTICATION.UNAUTHORIZED', 'message': 'Bearer token not supplied in save apartments request.' } }), 401

    jwt_token = authorization.split()[1]

    user_id = ''
    try:
        user_id = get_user_id(jwt_token)
    except:
        traceback.print_exc()
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.AUTHENTICATION.TOKEN_ERROR', 'message': 'Token failed to be verified' }, 'results': [] }), 500

    body = request.get_json()
    rental_key = body.get('rental_key', None)
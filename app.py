from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine, text
from flask_cors import CORS
from auth.user import get_user_id
import traceback

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.ihnradjuxnddmmioyeqp:oMbKlcQqT9APDtKG@aws-0-us-west-1.pooler.supabase.com/postgres"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

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
        inc = 0
        for rec in recs:

            price = rec['property_data']['models'][0].get('rentLabel', 'N/A')
            price_cleaned = price.replace('/ Person', '').strip()

            leaseOption = ''
            leaseOptionFromFee = ''
            modelUnitAvailable = None

            try:
                leaseOption = rec['property_data']['models'][inc].get('leaseOptions')
            except:
                leaseOption = 'N/A'

            try:
                leaseOptionFromFee = rec['property_data']['fees'][inc].get('policies')
            except:
                leaseOptionFromFee = 'N/A'

            try:
                modelUnitAvailable = rec['property_data']['models'][inc]
            except:
                modelUnitAvailable = 'N/A'
    
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
                'isSaved': rec['isSaved']
                # 'leaseOption': leaseOption
            }
            simplified_recs.append(simplified_rec)

            print('APT Name:', simplified_rec['name'], 'lease', leaseOption)
            print('APT available:', simplified_rec['hasKnownAvailabilities'])
            print('APT lease Fee', leaseOptionFromFee)
            print('APT model available:', modelUnitAvailable)
            print('')
            
            inc += 1

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
    if property_id is None or rental_key is None:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.PARAMETER_NOT_GIVEN', 'message': 'A unit ID was not supplied. Failed to save apartment' }, 'results': [] }), 500

    saved_apartment = { 'user_id': user_id, 'property_id': property_id, 'rental_key': rental_key }

    try:
        data, count = supabase.table('user_apartment').insert(saved_apartment).execute()
    except:
        return jsonify({ 'error': { 'status': 500, 'code': 'OC.BUSINESS.INSERTION_FAILURE', 'message': 'Failed to update database with saved apartment' }, 'results': [] }), 500

    if data[1] and len(data[1]) > 0:
        return jsonify({ 'results': [{ 'code': 'OC.MESSAGE.SUCCESS', 'message': 'Successfully saved apartment' }], 'data': data[1] }), 200

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